"""Explicit controller dispatch and checkpoint audits for trusted research code.

The contract counts serialized persistent payload, not process RAM. Restart
checks detect ordinary hidden state; this is not a hostile-code sandbox.
"""
from dataclasses import dataclass,asdict
from pathlib import Path
import base64
import importlib
import json
import subprocess
import sys
from . import controller,junction_controller,loop_controller,rotor_controller,face_controller


@dataclass(frozen=True)
class ControllerSpec:
    width:int
    height:int
    budget:int
    policy:str
    selector:str='nearest'
    agent_seed:int=1

    def __post_init__(self):
        if any(type(v) is not int for v in [self.width,self.height,self.budget,self.agent_seed]):
            raise ValueError('dimensions, budget and PRNG initialization must be integers')
        if self.width<1 or self.height<1 or self.budget<0 or self.width*self.height>=controller.NONE:
            raise ValueError('invalid public dimensions or budget')
        if not 0<=self.agent_seed<=0xffffffff:raise ValueError('invalid PRNG initialization')


def implementation(spec):
    if spec.policy.startswith('python:'):
        parts=spec.policy.split(':')
        if len(parts)!=3 or not parts[1] or not parts[2]:
            raise ValueError('plugin policy must be python:importable.module:function')
        advance=getattr(importlib.import_module(parts[1]),parts[2])
        if not callable(advance):raise ValueError('plugin controller is not callable')
        # Trusted importable plugins have the same sensor/state/spec interface.
        # No environment reference or extra mutable configuration is injected.
        return advance,spec
    for module,config,advance in [
        (controller,controller.Config,controller.step),
        (junction_controller,junction_controller.PortConfig,junction_controller.step_ports),
        (loop_controller,loop_controller.LoopConfig,loop_controller.step_loop),
        (rotor_controller,rotor_controller.RotorConfig,rotor_controller.step_rotor),
        (face_controller,face_controller.FaceConfig,face_controller.step_face)]:
        if spec.policy in module.POLICIES:
            cfg=config(spec.width,spec.height,spec.budget,spec.policy,
                       selector=spec.selector,rng_seed=spec.agent_seed)
            return advance,cfg
    raise ValueError('unknown controller policy')


def validate_frame(frame,spec):
    n=spec.width*spec.height
    if type(frame.position) is not int or not 0<=frame.position<n or frame.direction not in range(4):
        raise ValueError('invalid position or orientation')
    cells=dict(frame.cells)
    if len(cells)!=len(frame.cells) or any(type(p) is not int or not 0<=p<n or k not in (1,2,3) for p,k in frame.cells):
        raise ValueError('invalid or duplicated sensor cells')
    if any(p not in cells or cells[p]!=1 for p in frame.goals):
        raise ValueError('goal must be currently observed and traversable')
    if any(p not in cells or status not in (0,1,2) for p,status in frame.doors):
        raise ValueError('door state must be currently observed')


def checked_step(frame,state,spec):
    if type(state) is not bytes or len(state)>spec.budget:
        raise ValueError('input must be bytes within the persistent payload budget')
    validate_frame(frame,spec)
    advance,cfg=implementation(spec)
    action,new_state,diagnostics=advance(frame,state,cfg)
    if type(action) is not int or action not in range(7):raise ValueError('invalid MiniGrid action')
    if type(new_state) is not bytes or len(new_state)>spec.budget:
        raise ValueError('controller exceeded serialized persistent payload budget')
    return action,new_state,diagnostics


def checkpoint(frame,state,spec):
    return dict(schema='statebudget.checkpoint.v1',spec=asdict(spec),frame=asdict(frame),
                state_b64=base64.b64encode(state).decode('ascii'))


def restore(payload):
    if payload['schema']!='statebudget.checkpoint.v1':raise ValueError('unknown checkpoint schema')
    spec=ControllerSpec(**payload['spec']);f=payload['frame']
    frame=controller.Frame(int(f['position']),int(f['direction']),tuple(map(tuple,f['cells'])),
                           tuple(f['goals']),tuple(map(tuple,f['doors'])))
    state=base64.b64decode(payload['state_b64'],validate=True)
    return frame,state,spec


def replay_checkpoint(payload,fresh_process=False):
    if fresh_process:
        result=subprocess.run([sys.executable,'-B','-m',__package__+'.checkpoint_worker'],
            input=json.dumps(payload),text=True,capture_output=True,check=True,
            cwd=Path(__file__).resolve().parents[len(__package__.split('.'))],timeout=60)
        return json.loads(result.stdout)
    frame,state,spec=restore(payload)
    action,new_state,diagnostics=checked_step(frame,state,spec)
    return dict(action=action,state_b64=base64.b64encode(new_state).decode('ascii'),diagnostics=diagnostics)
