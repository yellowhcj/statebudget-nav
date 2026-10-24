import base64
import hashlib
import json
from dataclasses import replace
import pytest
from statebudget_nav import ControllerSpec,Frame,checked_step,checkpoint,replay_checkpoint
from statebudget_nav.evaluation import run_episode
from statebudget_nav.cli import main


@pytest.mark.parametrize('policy,budget',[
    ('compressed',64),('compressed_joint',64),('wall_follow',8),('random_walk',8),
    ('ports_lfv',32),('rotor_junction',32),('loop_burst_64',32),('face_junction',64)])
def test_public_package_episode_budget_pairing_and_replay(tmp_path,policy,budget):
    path=tmp_path/(policy+'.jsonl')
    result=run_episode('Controlled-braid-9',10000,policy,budget,200,trace_path=path)
    assert result['max_state_bytes']<=budget
    assert result['steps']>=1
    event=json.loads(path.read_text(encoding='utf-8').splitlines()[0])
    output=replay_checkpoint(event,fresh_process=True)
    assert output['action']==event['expected']['action']
    assert hashlib.sha256(base64.b64decode(output['state_b64'])).hexdigest()==event['expected']['state_sha256']
    assert not any(k in event['spec'] for k in ['seed','env','world_hash','map','goal'])


def test_cli_audit_rejects_corrupt_expected_action(tmp_path,monkeypatch):
    spec=ControllerSpec(5,5,32,'compressed')
    frame=Frame(12,0,((12,1),(13,1),(17,2),(11,2),(7,2)))
    action,state,_=checked_step(frame,b'',spec)
    event=checkpoint(frame,b'',spec)
    event['expected']=dict(action=(action+1)%7,state_sha256=hashlib.sha256(state).hexdigest())
    path=tmp_path/'corrupt.jsonl';path.write_text(json.dumps(event)+'\n',encoding='utf-8')
    monkeypatch.setattr('sys.argv',['statebudget-nav','audit',str(path)])
    with pytest.raises(ValueError,match='replay mismatch'):main()


def test_dispatch_and_sensor_contract_fail_closed():
    spec=ControllerSpec(5,5,64,'compressed')
    frame=Frame(12,0,((12,1),(13,1)))
    before=checked_step(frame,b'',spec)
    checked_step(frame,b'',replace(spec,policy='ports_lfv'))
    assert checked_step(frame,b'',spec)==before
    with pytest.raises(ValueError,match='goal'):checked_step(replace(frame,goals=(7,)),b'',spec)
    with pytest.raises(ValueError,match='budget'):checked_step(frame,b'x'*65,spec)
