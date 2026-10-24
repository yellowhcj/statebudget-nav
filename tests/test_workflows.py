"""Behavioral checks for package workflows, source drift and hidden persistence."""
import hashlib
import json
import pytest
from statebudget_nav import ControllerSpec,Frame,checked_step,checkpoint,replay_checkpoint
from statebudget_nav.audit import audit_trace
from statebudget_nav.batch import create_batch,run_batch,verify_batch
from statebudget_nav.analysis import summarize_batch


def test_frozen_queue_resumes_and_deduplicates_physical_layouts(tmp_path):
    path=tmp_path/'queue'
    jobs=[dict(env='MiniGrid-DistShift1-v0',policy='wall_follow',budget=8,limit=12,
               seed=seed,agent_seed=agent) for seed in [10000,10001] for agent in [1,7919]]
    create_batch(path,jobs)
    first=run_batch(path,max_jobs=1)
    assert first['complete']==1 and first['pending']==3
    assert summarize_batch(path,allow_partial=True)['partial']
    with pytest.raises(ValueError,match='incomplete'):summarize_batch(path)
    completed=list((path/'jobs').glob('*.json'))[0];before=completed.read_bytes()
    second=run_batch(path)
    assert second['complete']==4 and second['attempted']==3
    assert completed.read_bytes()==before
    report=summarize_batch(path)
    assert report['episodes']==4 and report['seeded_instances']==2
    assert report['physical_tasks_by_environment_and_view']==1
    assert report['summaries'][0]['agent_repeat_sets']==[[1,7919]]
    source=path/'source'/'statebudget_nav'/'evaluation.py'
    source.write_text(source.read_text(encoding='utf-8')+'\n# drift\n',encoding='utf-8')
    with pytest.raises(ValueError,match='source integrity'):verify_batch(path)


def test_completed_result_corruption_is_detected(tmp_path):
    path=tmp_path/'queue'
    create_batch(path,[dict(env='Controlled-maze-9',policy='wall_follow',budget=8,limit=4)])
    assert run_batch(path)['complete']==1
    file=next((path/'jobs').glob('*.json'));record=json.loads(file.read_text(encoding='utf-8'))
    record['result']['success']=1-record['result']['success']
    file.write_text(json.dumps(record),encoding='utf-8')
    with pytest.raises(ValueError,match='result integrity'):verify_batch(path)


def test_plugin_global_counter_is_detected_by_restart(tmp_path,monkeypatch):
    plugin=tmp_path/'hidden_counter_fixture.py'
    plugin.write_text('count=0\ndef step(frame,state,spec):\n'
        '    global count\n    count+=1\n    return count%2,b"",{}\n',encoding='utf-8')
    monkeypatch.syspath_prepend(str(tmp_path));monkeypatch.setenv('PYTHONPATH',str(tmp_path))
    frame=Frame(12,0,((12,1),(13,1)))
    spec=ControllerSpec(5,5,8,'python:hidden_counter_fixture:step')
    checked_step(frame,b'',spec)  # First call survives a restart; second does not.
    action,state,_=checked_step(frame,b'',spec)
    event=checkpoint(frame,b'',spec)
    event['expected']=dict(action=action,state_sha256=hashlib.sha256(state).hexdigest())
    path=tmp_path/'hidden.jsonl';path.write_text(json.dumps(event)+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='replay mismatch'):audit_trace(path,fresh_process=True)


def test_declared_plugin_counter_restarts_and_empty_trace_rejected(tmp_path):
    spec=ControllerSpec(5,5,1,'python:statebudget_nav.examples.counter:step')
    frame=Frame(12,0,((12,1),(13,1)));state=b''
    for _ in range(3):
        event=checkpoint(frame,state,spec)
        assert replay_checkpoint(event)==replay_checkpoint(event,True)
        _,state,_=checked_step(frame,state,spec)
    path=tmp_path/'empty.jsonl';path.write_text('',encoding='utf-8')
    with pytest.raises(ValueError,match='empty trace'):audit_trace(path)
    with pytest.raises(ValueError,match='budget'):checked_step(frame,b'',ControllerSpec(5,5,0,spec.policy))


def test_invalid_or_duplicate_jobs_are_rejected_before_queue_creation(tmp_path):
    job=dict(env='Controlled-maze-9',policy='wall_follow',budget=8)
    with pytest.raises(ValueError,match='duplicate'):create_batch(tmp_path/'a',[job,job])
    assert not (tmp_path/'a').exists()
    with pytest.raises(ValueError,match='bundled'):create_batch(tmp_path/'b',[dict(job,policy='python:x:y')])


def test_runtime_version_drift_prevents_silent_resume(tmp_path,monkeypatch):
    import statebudget_nav.batch as batch
    path=tmp_path/'queue'
    batch.create_batch(path,[dict(env='Controlled-maze-9',policy='wall_follow',budget=8,limit=4)])
    original=batch.environment
    def changed(names=None):
        value=original(names);value['dependencies']['numpy']='deliberately-changed'
        return value
    monkeypatch.setattr(batch,'environment',changed)
    with pytest.raises(ValueError,match='runtime environment changed'):batch.run_batch(path)
    assert not (path/'writer.lock').exists()
    assert not list((path/'jobs').glob('*.json'))
