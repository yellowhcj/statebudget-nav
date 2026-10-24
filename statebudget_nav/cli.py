import argparse
import base64
import hashlib
import json
from pathlib import Path
from . import replay_checkpoint
from .evaluation import run_episode
from .audit import audit_trace
from .batch import create_batch,run_batch,verify_batch
from .analysis import summarize_batch


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
    args=parser.parse_args()
    if args.command=='run':
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
        if args.jobs:create_batch(args.directory,json.loads(Path(args.jobs).read_text(encoding='utf-8')))
        result=run_batch(args.directory,args.max_jobs)
    elif args.command=='verify':result=verify_batch(args.directory)[1]
    else:result=summarize_batch(args.directory,args.allow_partial)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
