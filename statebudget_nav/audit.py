"""Checkpoint comparisons; this checks reproducibility, not hostile-code safety."""
import base64
import hashlib
import json
from pathlib import Path
from . import replay_checkpoint


def audit_trace(path,fresh_process=True,stride=1):
    if type(stride) is not int or stride<1:raise ValueError('stride must be positive')
    checked=0
    with Path(path).open(encoding='utf-8') as stream:
        for i,line in enumerate(stream):
            if i%stride:continue
            event=json.loads(line);actual=replay_checkpoint(event,fresh_process)
            digest=hashlib.sha256(base64.b64decode(actual['state_b64'],validate=True)).hexdigest()
            if actual['action']!=event['expected']['action'] or digest!=event['expected']['state_sha256']:
                raise ValueError(f'checkpoint {i} replay mismatch')
            checked+=1
    if checked==0:raise ValueError('empty trace cannot establish successful replay')
    return dict(checkpoints=checked,all_passed=True,fresh_interpreter=fresh_process,
                stride=stride,scope='sampled deterministic replay; not a proof of state isolation')
