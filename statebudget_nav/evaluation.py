"""Explicit dispatcher evaluator; world geometry is never passed to a policy."""
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import time
from . import ControllerSpec,checked_step,checkpoint
from ._core.benchmark import sensor_frame,world_stats
from ._core.environments import make
from ._core.matched_topology import MatchedLoopNavigation


def run_episode(env_name,seed=10000,policy='compressed',budget=64,limit=600,
                view=7,selector='nearest',agent_seed=1,trace_path=None):
    if type(limit) is not int or limit<1 or type(view) is not int or view<3 or view%2!=1:
        raise ValueError('positive integer limit and odd view >=3 required')
    if env_name.startswith('Matched-'):
        _,size,cycles=env_name.split('-')
        env=MatchedLoopNavigation(size=int(size),cycles=int(cycles),agent_view_size=view)
    else:env=make(env_name,view)
    stream=None
    try:
        e=env.unwrapped;e.max_steps=limit;obs,_=env.reset(seed=seed)
        spec=ControllerSpec(e.width,e.height,budget,policy,selector,agent_seed)
        stats=world_stats(env);state=b'';trace=hashlib.sha256();max_bytes=0;cpu_ns=0
        success=False;merges=0;loops=0
        if trace_path:
            trace_path=Path(trace_path);trace_path.parent.mkdir(parents=True,exist_ok=True)
            stream=trace_path.open('x',encoding='utf-8')
        for t in range(limit):
            frame=sensor_frame(obs,e.agent_pos,e.agent_dir,e.width,e.height)
            begun=time.process_time_ns();action,new_state,diagnostic=checked_step(frame,state,spec)
            cpu_ns+=time.process_time_ns()-begun
            if stream:
                event=checkpoint(frame,state,spec)
                event['expected']=dict(action=action,state_sha256=hashlib.sha256(new_state).hexdigest())
                stream.write(json.dumps(event,separators=(',',':'))+'\n')
            state=new_state;max_bytes=max(max_bytes,len(state))
            trace.update(frame.position.to_bytes(2,'little')+bytes([frame.direction,action])+state)
            loops+=diagnostic.get('loop_detected',0);merges+=diagnostic.get('face_merged',0)
            obs,reward,terminated,truncated,_=env.step(action)
            if terminated or truncated:
                success=bool(terminated and reward>0);break
        return dict(env=env_name,seed=seed,agent_seed=agent_seed,policy=policy,budget=budget,
                    limit=limit,view=view,selector=selector,success=int(success),steps=t+1,
                    max_state_bytes=max_bytes,cpu_ms=cpu_ns/1e6,
                    trajectory_hash=trace.hexdigest(),loops_detected=loops,face_merges=merges,**stats)
    finally:
        if stream:stream.close()
        env.close()
