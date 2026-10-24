"""Intentionally faulty trusted plugins for an auditable diagnostic example.

These functions are counterexamples, not recommended navigation policies.
Run this module with a NEW output directory to reproduce the detection table.
"""
from pathlib import Path
import hashlib
import json
import sys
from .. import Frame,ControllerSpec,checked_step,checkpoint
from ..audit import audit_trace

_calls=0


def hidden_action(frame,state,spec):
    global _calls
    _calls+=1
    return _calls%2,b'',{}


def hidden_payload(frame,state,spec):
    global _calls
    _calls+=1
    return 0,bytes([_calls%256]),{}


def late_hidden_action(frame,state,spec):
    global _calls
    _calls+=1
    return int(_calls>=8),b'',{}


def oversized(frame,state,spec):return 0,b'x'*(spec.budget+1),{}
def invalid_action(frame,state,spec):return 7,b'',{}


def demonstrate(path):
    global _calls
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    frame=Frame(12,0,((12,1),(13,1)))
    rows=[]
    for name,expect in [('hidden_action',False),('hidden_payload',False),
                        ('late_hidden_action',False),('compliant_counter',True)]:
        _calls=0
        policy=('python:statebudget_nav.examples.counter:step' if name=='compliant_counter'
                else 'python:'+__package__+'.audit_faults:'+name)
        spec=ControllerSpec(5,5,8,policy);state=b'';events=[]
        for _ in range(12):
            event=checkpoint(frame,state,spec)
            action,state,_=checked_step(frame,state,spec)
            event['expected']=dict(action=action,state_sha256=hashlib.sha256(state).hexdigest())
            events.append(event)
        trace=path/(name+'.jsonl')
        trace.write_text(''.join(json.dumps(e)+'\n' for e in events),encoding='utf-8')
        row=dict(fixture=name,steps=12,expected_full_replay_pass=expect)
        for stride,label in [(1,'all'),(16,'first_only')]:
            try:row[label]=dict(passed=True,**audit_trace(trace,True,stride))
            except ValueError as error:row[label]=dict(passed=False,error=str(error))
        if row['all']['passed']!=expect:raise AssertionError('fault demonstration did not reproduce')
        rows.append(row)
    for name in ['oversized','invalid_action']:
        spec=ControllerSpec(5,5,8,'python:'+__package__+'.audit_faults:'+name)
        try:checked_step(frame,b'',spec)
        except ValueError as error:rows.append(dict(fixture=name,rejected_at_step_boundary=True,error=str(error)))
        else:raise AssertionError('invalid plugin was accepted')
    report=dict(rows=rows,scope='controlled fault injection, not a malicious-code security test',
                sampled_replay_limitation='first-only replay passes all three hidden-state fixtures',
                expected_behaviors_reproduced=True)
    (path/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    from .audit_faults import demonstrate as run
    print(json.dumps(run(sys.argv[1]),indent=2))
