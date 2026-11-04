import argparse
import base64
import hashlib
import json
from pathlib import Path
from . import replay_checkpoint
from .audit import audit_trace


def main():
    parser=argparse.ArgumentParser(prog='statebudget-nav')
    sub=parser.add_subparsers(dest='command',required=True)
    run=sub.add_parser('run',help='Run one paired, sensor-only episode')
    run.add_argument('--env',default='MiniGrid-FourRooms-v0')
    run.add_argument('--policy',default='compressed');run.add_argument('--budget',type=int,default=64)
    run.add_argument('--seed',type=int,default=10000);run.add_argument('--agent-seed',type=int,default=1)
    run.add_argument('--limit',type=int,default=600);run.add_argument('--view',type=int,default=7)
    run.add_argument('--selector',choices=['nearest','frontier','gain'],default='nearest')
    run.add_argument('--trace');run.add_argument('--output')
    audit=sub.add_parser('audit',help='Replay recorded sensor/state checkpoints')
    audit.add_argument('trace');audit.add_argument('--fresh-process',action='store_true')
    audit.add_argument('--stride',type=int,default=1)
    batch=sub.add_parser('batch',help='Create or resume a frozen-source job queue')
    batch.add_argument('directory');batch.add_argument('--jobs',help='New queue JSON list; omit to resume')
    batch.add_argument('--max-jobs',type=int)
    verify=sub.add_parser('verify',help='Check archived source, result digests and current runtime')
    verify.add_argument('directory')
    summary=sub.add_parser('summary',help='Average random repeats and duplicate physical layouts')
    summary.add_argument('directory');summary.add_argument('--allow-partial',action='store_true')
    full=sub.add_parser('movingai',help='Run an adapted4-way task with official map/scenario endpoints')
    full.add_argument('--map',required=True);full.add_argument('--scenarios',required=True);full.add_argument('--output',required=True)
    selection=full.add_mutually_exclusive_group(required=True)
    selection.add_argument('--line',type=int);selection.add_argument('--quantile',type=float)
    full.add_argument('--policy',default='walls',help='Built-in name or python:importable.module:function')
    full.add_argument('--initial-state',help='Binary initial payload, required for external controllers; all bytes count')
    full.add_argument('--budget',type=int,default=1024);full.add_argument('--view',type=int,default=7)
    full.add_argument('--movement-multiplier',type=float,default=6)
    native=sub.add_parser('build-native',help='Compile the optional full-map search backend')
    native.add_argument('output');native.add_argument('--compiler')
    compare=sub.add_parser('movingai-summary',help='Summarize complete adapted runs and preserve task identities')
    compare.add_argument('directories',nargs='+')
    fetch=sub.add_parser('movingai-fetch',help='Download one map and its official scenarios with provenance')
    fetch.add_argument('--map-url',required=True);fetch.add_argument('--scenario-url',required=True);fetch.add_argument('--output',required=True)
    verify_scen=sub.add_parser('movingai-verify',help='Reproduce one original8-way scenario distance')
    verify_scen.add_argument('--map',required=True);verify_scen.add_argument('--scenarios',required=True);verify_scen.add_argument('--line',required=True,type=int)
    args=parser.parse_args()
    if args.command=='run':
        from .evaluation import run_episode
        if args.limit<1 or args.view<3 or args.view%2!=1:parser.error('positive limit and odd view >=3 required')
        result=run_episode(args.env,args.seed,args.policy,args.budget,args.limit,args.view,
                           args.selector,args.agent_seed,args.trace)
        if args.output:
            path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
            with path.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    elif args.command=='audit':
        if args.stride<1:parser.error('stride must be positive')
        result=audit_trace(args.trace,args.fresh_process,args.stride)
    elif args.command=='batch':
        from .batch import create_batch,run_batch
        if args.jobs:create_batch(args.directory,json.loads(Path(args.jobs).read_text(encoding='utf-8')))
        result=run_batch(args.directory,args.max_jobs)
    elif args.command=='verify':
        from .batch import verify_batch
        result=verify_batch(args.directory)[1]
    elif args.command=='summary':
        from .analysis import summarize_batch
        result=summarize_batch(args.directory,args.allow_partial)
    elif args.command=='movingai':
        from .movingai import run as run_movingai
        initial=Path(args.initial_state).read_bytes() if args.initial_state else None
        result=run_movingai(args.map,args.scenarios,args.output,args.policy,args.budget,args.line,args.quantile,args.view,args.movement_multiplier,initial)
    elif args.command=='build-native':
        from .movingai import build_native
        result=build_native(args.output,args.compiler)
    elif args.command=='movingai-fetch':
        from .movingai import fetch
        result=fetch(args.map_url,args.scenario_url,args.output)
    elif args.command=='movingai-verify':
        from .movingai import load_map,load_scenarios,select,verify_distance8
        grid=load_map(args.map);scene=select(load_scenarios(args.scenarios,grid),line=args.line)
        value=verify_distance8(grid,scene)
        result=dict(original_line=scene.line,published_distance=scene.official_distance,reproduced_distance=value,all_passed=True,convention='official8-way diagonal sqrt2 without corner cutting')
    else:
        from .movingai import report
        result=report(args.directories)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
