"""Declared budget studies composed from existing evaluator and replay interfaces."""
import argparse
import hashlib
import importlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from .study_analysis import (sha, read_json, task_identity, context, trace_events,
                             compare_traces, summarize_study, verify_files)
from ._runtime_identity import assert_runtime_matches


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def keys(value, allowed, required):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('unknown or missing plan keys: ' + repr(value))


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('integer >= ' + str(minimum) + ' required')


def validate_plan(plan):
    keys(plan, ('schema','tasks','controllers','budgets','audit_stride'), ('schema','tasks','controllers','budgets'))
    if plan['schema'] != 'statebudget.study_plan.v1':
        raise ValueError('unsupported study plan schema')
    for name in ('tasks', 'controllers', 'budgets'):
        if not isinstance(plan[name], list) or not plan[name]:
            raise ValueError('nonempty list required: ' + name)
    for b in plan['budgets']:
        integer(b)
    if len(set(plan['budgets'])) != len(plan['budgets']):
        raise ValueError('duplicate budgets')
    integer(plan.get('audit_stride', 60), 1)
    for name in ('tasks', 'controllers'):
        ids = []
        for entry in plan[name]:
            if not isinstance(entry.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]+', entry['id']):
                raise ValueError('portable alphanumeric id required')
            ids.append(entry['id'])
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate ' + name + ' ids')
    for c in plan['controllers']:
        keys(c, ('id','policy','initial_state'), ('id','policy'))
        if not isinstance(c['policy'], str) or not c['policy']:
            raise ValueError('controller policy required')
        if 'initial_state' in c:
            initial=c['initial_state']
            if not (isinstance(initial,str) and initial) and not (
                isinstance(initial,dict) and set(initial)=={t['id'] for t in plan['tasks']}
                and all(isinstance(v,str) and v for v in initial.values())):
                raise ValueError('initial_state needs a path or a path per task id')
    for t in plan['tasks']:
        if t.get('adapter') == 'minigrid':
            keys(t, ('id','adapter','env','seed','view','limit','selector','agent_seed'), ('id','adapter','env','seed'))
            integer(t['seed']); integer(t.get('limit',600),1); integer(t.get('agent_seed',1))
            if not isinstance(t['env'], str) or not t['env']:
                raise ValueError('environment required')
            if t.get('selector','nearest') not in ('nearest','frontier','gain'):
                raise ValueError('unsupported selector')
            if any('initial_state' in c for c in plan['controllers']):
                raise ValueError('MiniGrid starts with empty bytes; initial_state is MovingAI-only')
        elif t.get('adapter') == 'movingai':
            keys(t, ('id','adapter','map','scenarios','line','view','movement_multiplier'), ('id','adapter','map','scenarios','line'))
            integer(t['line'], 2)
            m = t.get('movement_multiplier',6)
            if type(m) not in (int,float) or not math.isfinite(m) or m <= 0:
                raise ValueError('positive movement_multiplier required')
            for c in plan['controllers']:
                if c['policy'].startswith('python:') != ('initial_state' in c):
                    raise ValueError('MovingAI external controllers require initial_state; builtins do not')
        else:
            raise ValueError('supported adapters: minigrid, movingai')
        integer(t.get('view',7),3)
        if t.get('view',7) % 2 != 1:
            raise ValueError('odd view required')
    return plan


def runtime_identity(plan):
    from . import __version__
    package = Path(__file__).parent
    modules = {p.relative_to(package).as_posix(): sha(p) for p in sorted(package.rglob('*'))
               if p.is_file() and p.suffix in ('.py','.cpp','.json') and '__pycache__' not in p.parts}
    plugins = {}
    for controller in plan['controllers']:
        if controller['policy'].startswith('python:'):
            parts = controller['policy'].split(':')
            if len(parts) != 3:
                raise ValueError('expected python:module:function')
            m = importlib.import_module(parts[1])
            if not callable(getattr(m, parts[2])):
                raise ValueError('plugin entry must be callable')
            plugins[parts[1]] = {'origin': m.__file__, 'sha256': sha(m.__file__)}
    return {'package_version': __version__, 'package_files_sha256': modules,
            'plugin_entry_modules': plugins, 'python': sys.version,
            'dependencies': {n: importlib.metadata.version(n) for n in ('numpy','gymnasium','minigrid')},
            'scope': 'Installed package and plugin ENTRY module identities; not transitive dependency closure or a code-isolation proof.'}


class Infeasible(ValueError):
    pass


def worker(condition_path):
    """One isolated process per condition; preserve partial traces on execution errors."""
    condition_path = Path(condition_path).resolve()
    cfg = read_json(condition_path)
    root = condition_path.parents[2]
    directory = condition_path.parent
    t, c, budget = cfg['task'], cfg['controller'], cfg['budget']
    record = {k: cfg[k] for k in ('run_id','task_id','controller_id','budget')}
    phase = 'preflight'
    embedded_audit_error = None
    try:
        if t['adapter'] == 'minigrid':
            from . import ControllerSpec
            from ._core.public_api import implementation
            from ._core.environments import make
            from ._core.matched_topology import MatchedLoopNavigation
            from ._core.benchmark import world_stats
            if t['env'].startswith('Matched-'):
                _, size, cycles = t['env'].split('-')
                env = MatchedLoopNavigation(size=int(size),cycles=int(cycles),agent_view_size=t.get('view',7))
            else:
                env = make(t['env'], t.get('view',7))
            try:
                env.reset(seed=t['seed']); e = env.unwrapped
                info = dict(env=t['env'],view=t.get('view',7),limit=t.get('limit',600),
                            selector=t.get('selector','nearest'),**world_stats(env))
                record.update(task_identity=task_identity(info),context=context(info))
                try:
                    implementation(ControllerSpec(e.width,e.height,budget,c['policy'],t.get('selector','nearest'),t.get('agent_seed',1)))
                except ValueError as error:
                    # Bundled validation proves this lower bound; arbitrary plugin messages do not.
                    if re.fullmatch(r'budget \d+ < minimum \d+ for \w+',str(error)) and not c['policy'].startswith('python:'):
                        raise Infeasible(str(error)) from error
                    raise
            finally:
                env.close()
            from .evaluation import run_episode
            phase = 'evaluation'
            result = run_episode(t['env'],t['seed'],c['policy'],budget,t.get('limit',600),t.get('view',7),
                                 t.get('selector','nearest'),t.get('agent_seed',1),directory/'trace.jsonl')
            trace = directory/'trace.jsonl'
        else:
            from .movingai import load_map,load_scenarios,select,distance4,run,ReplayAuditError
            from ._core import fullmap
            from . import ControllerSpec
            map_path, scen_path = root/t['map'], root/t['scenarios']
            grid = load_map(map_path); scene = select(load_scenarios(scen_path,grid),line=t['line'])
            d4 = distance4(grid,scene.start,scene.goal)
            if d4 is None:
                raise ValueError('endpoints unsupported by 4-way adaptation')
            # Match evaluator identity exactly, including the sensor convention.
            physical = hashlib.sha256(json.dumps(dict(world=hashlib.sha256(grid.cells).hexdigest(),width=grid.width,
                height=grid.height,start=scene.start,goal=scene.goal,heading=0,view=t.get('view',7)),sort_keys=True).encode()).hexdigest()
            record.update(task_identity='movingai:'+physical,
                          context=dict(view=t.get('view',7),limit=max(600,math.ceil(t.get('movement_multiplier',6)*d4))))
            initial_path=c.get('initial_state')
            if isinstance(initial_path,dict):initial_path=initial_path[t['id']]
            initial = (root/initial_path).read_bytes() if initial_path is not None else None
            if initial is not None and len(initial) > budget:
                raise Infeasible('initial payload exceeds budget')
            if initial is None:
                spec = ControllerSpec(grid.width,grid.height,budget,'python:statebudget_nav._core.fullmap:'+c['policy'])
                try:
                    fullmap.initial(spec,scene.start,scene.goal)
                except ValueError as error:
                    if str(error) == 'budget below initial representation size':
                        raise Infeasible(str(error)) from error
                    raise
            phase = 'evaluation'
            try:
                result = run(map_path,scen_path,directory/'episode',c['policy'],budget,line=t['line'],
                             view=t.get('view',7),multiplier=t.get('movement_multiplier',6),initial_state=initial)
            except ReplayAuditError as error:
                result = error.result
                embedded_audit_error = error
            trace = directory/'episode/trace.jsonl.gz'
        dump(directory/'result.json',result)
        if task_identity(result) != record['task_identity'] or context(result) != record['context']:
            raise ValueError('task identity/context changed between preflight and evaluation')
        record.update(success=bool(result['success']),actions=result.get('actions',result.get('steps')),
                      moves=result.get('moves'),max_state_bytes=result['max_state_bytes'],
                      stop_reason=result.get('stop_reason','success' if result['success'] else 'episode_ended_without_success'),
                      result='result.json',trace=trace.relative_to(directory).as_posix())
        phase = 'audit'
        if embedded_audit_error is not None:
            record['audit'] = result['replay_audit']
            raise embedded_audit_error
        from . import replay_checkpoint
        events = list(trace_events(trace)); stride = cfg['audit_stride']
        if len(events)!=record['actions']:
            raise ValueError('trace call count differs from result actions')
        indices = sorted(set(range(0,len(events),stride)) | ({len(events)-1} if events else set()))
        checked = []
        for i in indices:
            out = replay_checkpoint(events[i],fresh_process=True)
            digest = hashlib.sha256(__import__('base64').b64decode(out['state_b64'],validate=True)).hexdigest()
            if out['action'] != events[i]['expected']['action'] or digest != events[i]['expected']['state_sha256']:
                raise ValueError('checkpoint replay mismatch at zero-based index '+str(i))
            checked.append(i+1)
        record['audit'] = {'all_passed':True if events else None,'fresh_interpreter':True,'total_calls':len(events),
                           'checked_calls_one_based':checked,'stride':stride,
                           'scope':'Recorded calls only; no hostile code isolation or hidden-constant proof.'}
        record['status'] = 'ok'
    except Infeasible as error:
        record.update(status='infeasible',phase=phase,error=str(error))
    except Exception as error:
        record.update(status='audit_error' if phase == 'audit' else 'execution_error',phase=phase,
                      error=type(error).__name__+': '+str(error))
    dump(directory/'record.json',record)
    return record


def run_study(plan_path, directory, timeout=1800):
    plan_path = Path(plan_path).resolve()
    plan = validate_plan(read_json(plan_path))
    before = runtime_identity(plan)
    # Resolve all declared assets before reserving an output directory.
    assets=[]
    for t in plan['tasks']:
        if t['adapter']=='movingai':assets.extend([t['map'],t['scenarios']])
    for c in plan['controllers']:
        if 'initial_state' in c:
            assets.extend(c['initial_state'].values() if isinstance(c['initial_state'],dict) else [c['initial_state']])
    for path in assets:
        if not (plan_path.parent/path).is_file():raise ValueError('missing declared asset: '+path)
    root = Path(directory).resolve(); root.mkdir(parents=True,exist_ok=False)
    dump(root/'source_plan.json',plan)
    source_dir=root/'source';source_dir.mkdir()
    package=Path(__file__).parent
    for relative in before['package_files_sha256']:
        target=source_dir/'statebudget_nav'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(package/relative,target)
    for module,identity in before['plugin_entry_modules'].items():
        target=source_dir/'plugin_entries'/(module.replace('.','_')+Path(identity['origin']).suffix)
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(identity['origin'],target)
    # Copy declared data assets; same map basename is retained for scenario matching.
    def asset(value):
        source = (plan_path.parent/value).resolve()
        relative = Path('inputs')/sha(source)/source.name
        destination = root/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source,destination)
        return relative.as_posix()
    for t in plan['tasks']:
        if t['adapter'] == 'movingai':
            t['map'],t['scenarios'] = asset(t['map']),asset(t['scenarios'])
    for c in plan['controllers']:
        if 'initial_state' in c:
            if isinstance(c['initial_state'],dict):
                c['initial_state']={k:asset(v) for k,v in c['initial_state'].items()}
            else:c['initial_state'] = asset(c['initial_state'])
    dump(root/'plan.json',plan); dump(root/'runtime.json',before)
    slots = []
    for t in plan['tasks']:
        for c in plan['controllers']:
            for b in sorted(plan['budgets']):
                run_id = 'r'+str(len(slots)).zfill(5)
                slots.append(dict(run_id=run_id,task_id=t['id'],controller_id=c['id'],budget=b,
                                  task=t,controller=c,audit_stride=plan.get('audit_stride',60)))
    dump(root/'conditions.json',slots)
    child_env = {k:v for k,v in os.environ.items() if k != 'PYTHONPATH'}
    child_env['PYTHONDONTWRITEBYTECODE']='1'
    for slot in slots:
        run_dir = root/'runs'/slot['run_id']; run_dir.mkdir(parents=True)
        cfg = run_dir/'condition.json'; dump(cfg,slot)
        try:
            done = subprocess.run([sys.executable,'-I','-B','-m','statebudget_nav','study','_worker',str(cfg)],
                cwd=root,env=child_env,text=True,encoding='utf-8',errors='replace',capture_output=True,timeout=timeout)
            (run_dir/'stdout.txt').write_text(done.stdout,encoding='utf-8')
            (run_dir/'stderr.txt').write_text(done.stderr,encoding='utf-8')
            if done.returncode or not (run_dir/'record.json').exists():
                raise RuntimeError('condition worker exited with code '+str(done.returncode))
        except Exception as error:
            dump(run_dir/'record.json',dict(slot,status='execution_error',phase='worker',error=type(error).__name__+': '+str(error)))
    after = runtime_identity(plan)
    if before != after:
        dump(root/'SOURCE_CHANGED.json',{'before':before,'after':after})
        raise ValueError('installed source/runtime identity changed during study')
    report = summarize_study(root); dump(root/'report.json',report)
    files = {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*'))
             if p.is_file() and p.name != 'STUDY_RECEIPT.json'}
    dump(root/'STUDY_RECEIPT.json',{'schema':'statebudget.study_receipt.v1',
        'execution_finished':True,'scientific_outcomes_in_report':True,
        'files_sha256':files,'source_unchanged':True,
        'scope':'Errors are preserved per condition. This receipt is not a promise that every run or audit passed.'})
    return report


def verify_study(directory, replay=False):
    root=Path(directory)
    result=verify_files(root)
    recorded=read_json(root/'runtime.json')
    current=runtime_identity(read_json(root/'plan.json'))
    assert_runtime_matches(recorded, current)
    result['installed_runtime_matches']=True
    result['replayed_calls']=0
    if replay:
        from . import replay_checkpoint
        import base64
        for path in sorted((root/'runs').glob('*/record.json')):
            record=read_json(path)
            if record['status']!='ok':
                continue
            events=list(trace_events(path.parent/record['trace']))
            for number in record['audit']['checked_calls_one_based']:
                event=events[number-1]
                actual=replay_checkpoint(event,fresh_process=True)
                digest=hashlib.sha256(base64.b64decode(actual['state_b64'],validate=True)).hexdigest()
                if actual['action']!=event['expected']['action'] or digest!=event['expected']['state_sha256']:
                    raise ValueError('relocated replay mismatch')
                result['replayed_calls']+=1
    result['replay_requested']=replay
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(prog='statebudget-nav study')
    sub=parser.add_subparsers(dest='action',required=True)
    run=sub.add_parser('run');run.add_argument('plan');run.add_argument('--output',required=True)
    run.add_argument('--timeout',type=int,default=1800)
    report=sub.add_parser('report');report.add_argument('directory')
    verify=sub.add_parser('verify');verify.add_argument('directory');verify.add_argument('--replay',action='store_true')
    compare=sub.add_parser('compare')
    for name in ('left','right','left-result','right-result'):
        compare.add_argument('--'+name,required=True)
    compare.add_argument('--output')
    internal=sub.add_parser('_worker',help=argparse.SUPPRESS);internal.add_argument('condition')
    args=parser.parse_args(argv)
    if args.action=='run':
        integer(args.timeout,1); result=run_study(args.plan,args.output,args.timeout)
    elif args.action=='report':result=summarize_study(args.directory)
    elif args.action=='verify':result=verify_study(args.directory,args.replay)
    elif args.action=='compare':
        result=compare_traces(args.left,args.right,read_json(args.left_result),read_json(args.right_result))
        if args.output:
            with Path(args.output).open('x',encoding='utf-8') as stream:
                json.dump(result,stream,ensure_ascii=False,indent=2)
    else:result=worker(args.condition)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
