"""Compose installed public commands; keep user controllers outside the evaluator."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('fullmap', 'budget'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--map', type=Path)
    parser.add_argument('--scenarios', type=Path)
    parser.add_argument('--line', type=int, default=231)
    parser.add_argument('--budget', type=int, default=1024)
    parser.add_argument('--seeds', nargs='+', type=int, default=[10003, 10010])
    parser.add_argument('--budgets', nargs='+', type=int, default=[32, 33, 34])
    parser.add_argument('--wheel', action='append', default=[], type=Path)
    args = parser.parse_args()
    if args.mode == 'fullmap' and (args.map is None or args.scenarios is None):
        parser.error('fullmap needs --map and --scenarios')
    if len(args.seeds) != len(set(args.seeds)) or len(args.budgets) != len(set(args.budgets)):
        parser.error('duplicate seed/budget conditions are not permitted')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    commands = []
    child_env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    child_env['PYTHONDONTWRITEBYTECODE'] = '1'

    def command(label, arguments, expect_json=True):
        argv = [sys.executable, '-I', '-B', *map(str, arguments)]
        result = subprocess.run(argv, cwd=root, env=child_env, text=True, encoding='utf-8',
                                errors='replace', capture_output=True, timeout=1800)
        (root / (label + '.stdout.txt')).write_text(result.stdout, encoding='utf-8')
        (root / (label + '.stderr.txt')).write_text(result.stderr, encoding='utf-8')
        commands.append({'label': label, 'argv': argv, 'returncode': result.returncode})
        if result.returncode:
            raise RuntimeError(f'{label} failed: {result.stderr[-1500:]}')
        value = json.loads(result.stdout) if expect_json else {'message': result.stdout.strip()}
        dump(root / (label + '.json'), value)
        return value

    try:
        versions = command('versions', ['-c',
            'import importlib.metadata as m,importlib.util,json,sys,statebudget_nav;'
            'print(json.dumps(dict(python=sys.version,package_origin=statebudget_nav.__file__,'
            'plugin_origin=getattr(importlib.util.find_spec("navmemory_example"),"origin",None),'
            'dependencies={n:m.version(n) for n in '
            '["statebudget-nav","numpy","gymnasium","minigrid"]})))'])
        wheels = []
        if args.wheel:
            artifacts = root / 'wheels'
            artifacts.mkdir()
            # Match archive bytes to installed module paths through a child process.
            for wheel in args.wheel:
                wheel = wheel.resolve()
                copied = artifacts / wheel.name
                shutil.copy2(wheel, copied)
                module = 'navmemory_example' if wheel.name.startswith('navmemory_example-') else 'statebudget_nav'
                result = command('wheel_' + module, ['-c',
                    'import importlib,pathlib,json,zipfile,hashlib;'
                    f'm=importlib.import_module({module!r});w=pathlib.Path({str(copied)!r});'
                    'site=pathlib.Path(m.__file__).parent;'
                    + ('site=site.parent;' if module == 'statebudget_nav' else '') +
                    'z=zipfile.ZipFile(w);'
                    'names=[n for n in z.namelist() if n.endswith((".py",".cpp","/provenance.json")) '
                    'and not ".dist-info/" in n];'
                    'assert names;'
                    'assert all((site/n).read_bytes()==z.read(n) for n in names),"wheel/install drift";'
                    'print(json.dumps(dict(files_matched=len(names),all_matched=True)))'])
                wheels.append({'name': wheel.name, 'sha256': sha(copied), **result})
        if args.mode == 'fullmap':
            inputs = root / 'inputs'
            inputs.mkdir()
            for source in (args.map.resolve(), args.scenarios.resolve()):
                shutil.copy2(source, inputs / source.name)
            map_path, scen_path = inputs / args.map.name, inputs / args.scenarios.name
            selection = ['--map', map_path, '--scenarios', scen_path, '--line', args.line]
            command('official_distance', ['-m', 'statebudget_nav', 'movingai-verify', *selection])
            command('initial', ['-m', 'navmemory_example', *selection, '--output', root / 'external_initial.bin'], expect_json=False)
            directories = []
            for label, policy in [('raster', 'lru'), ('sparse', 'python:navmemory_example:step')]:
                directory = root / label
                extra = ['--initial-state', root / 'external_initial.bin'] if label == 'sparse' else []
                command(label, ['-m', 'statebudget_nav', 'movingai', *selection, '--policy', policy,
                                '--budget', args.budget, '--output', directory, *extra])
                command(label + '_audit', ['-m', 'statebudget_nav', 'audit', directory / 'trace.jsonl.gz',
                                          '--fresh-process', '--stride', 17])
                directories.append(directory)
            comparison = command('comparison', ['-m', 'statebudget_nav', 'movingai-summary', *directories])
            assert comparison['distinct_physical_tasks'] == 1
        else:
            records = []
            for seed in args.seeds:
                for budget in sorted(args.budgets):
                    label = f'seed{seed}_b{budget}'
                    trace = root / (label + '.jsonl')
                    value = command(label, ['-m', 'statebudget_nav', 'run', '--env', 'MiniGrid-FourRooms-v0',
                        '--seed', seed, '--policy', 'compressed', '--budget', budget,
                        '--limit', 600, '--trace', trace, '--output', root / (label + '_result.json')])
                    command(label + '_audit', ['-m', 'statebudget_nav', 'audit', trace,
                                              '--fresh-process', '--stride', 60])
                    records.append(value)
            transitions = []
            for seed in args.seeds:
                rows = sorted((r for r in records if r['seed'] == seed), key=lambda r: r['budget'])
                assert len({r['layout_hash'] for r in rows}) == 1
                for previous, current in zip(rows, rows[1:]):
                    if previous['success'] and not current['success']:
                        transitions.append({'seed': seed, 'from_budget': previous['budget'],
                                            'to_budget': current['budget']})
            comparison = {'executions': len(records), 'physical_layouts': len({r['layout_hash'] for r in records}),
                'success_to_failure': transitions,
                'scope': 'Selected historical sensitivity cases, not a new generalization estimate',
                'records': records}
            dump(root / 'comparison.json', comparison)
        files = {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob('*'))
                 if p.is_file() and p.name != 'WORKFLOW_RECEIPT.json'}
        receipt = {'schema': 'statebudget.research_workflow.v1', 'completed': True,
            'created_utc': datetime.now(timezone.utc).isoformat(), 'mode': args.mode,
            'runner_sha256': sha(Path(__file__)), 'versions': versions, 'wheels': wheels,
            'commands': commands, 'files_sha256': files,
            'scope': 'Author-provided CLI composition; audit imports installed modules, not automatically saved source',
            'dependency_scope': 'Versions recorded; wheels supplied optionally; not a complete dependency closure'}
        dump(root / 'WORKFLOW_RECEIPT.json', receipt)
        print(json.dumps({'completed': True, 'mode': args.mode, 'output': str(root),
                          'commands': len(commands), 'wheels_checked': len(wheels)}, indent=2))
    except Exception as error:
        dump(root / 'FAILED.json', {'completed': False, 'error': type(error).__name__ + ': ' + str(error),
                                   'commands': commands})
        raise


if __name__ == '__main__':
    main()
