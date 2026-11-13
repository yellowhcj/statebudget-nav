"""Completed MovingAI measurements survive replay failure without entering curves."""
import base64
import json
from pathlib import Path
import pytest

import statebudget_nav.movingai as movingai
from statebudget_nav.study import worker
from statebudget_nav.study_analysis import budget_curve


def condition(tmp_path, zero_calls=False, policy='lru', initial=None):
    (tmp_path/'tiny.map').write_text(
        'type octile\nheight 3\nwidth 6\nmap\n@@@@@@\n@....@\n@@@@@@\n',encoding='ascii')
    goal=1 if zero_calls else 4
    (tmp_path/'tiny.scen').write_text(
        f'version 1\n0 tiny.map 6 3 1 1 {goal} 1 {0 if zero_calls else 3}\n',encoding='ascii')
    folder=tmp_path/'runs/r00000';folder.mkdir(parents=True)
    controller=dict(id='raster',policy=policy)
    if initial is not None:
        (tmp_path/'initial.bin').write_bytes(initial)
        controller['initial_state']='initial.bin'
    value=dict(run_id='r00000',task_id='corridor',controller_id='raster',budget=256,audit_stride=60,
        task=dict(id='corridor',adapter='movingai',map='tiny.map',scenarios='tiny.scen',line=2,view=3),
        controller=controller)
    path=folder/'condition.json';path.write_text(json.dumps(value),encoding='utf-8')
    return path


@pytest.mark.parametrize('failure',['action','state','process'])
def test_completed_movingai_replay_failure_retains_outcome_and_stays_out_of_curve(tmp_path,monkeypatch,failure):
    original=movingai.replay_checkpoint
    observed=[]
    def failed_replay(event,*args,**kwargs):
        # The completed measurement exists before the first audit attempt.
        measured=json.loads((tmp_path/'runs/r00000/episode/result.json').read_text())
        assert measured['success'] is True and measured['moves']==3
        assert measured['replay_audit']['status']=='pending'
        observed.append(True)
        if failure=='process':raise RuntimeError('injected replay process failure')
        output=original(event,*args,**kwargs)
        if failure=='action':output['action']=6
        else:output['state_b64']=base64.b64encode(b'wrong returned state').decode()
        return output
    monkeypatch.setattr(movingai,'replay_checkpoint',failed_replay)
    record=worker(condition(tmp_path))
    assert observed
    assert record['status']=='audit_error' and record['phase']=='audit'
    assert record['success'] is True and record['actions']==3 and record['moves']==3
    assert record['max_state_bytes']<=256
    folder=tmp_path/'runs/r00000'
    assert (folder/record['trace']).is_file()
    for path in (folder/'result.json',folder/'episode/result.json'):
        measured=json.loads(path.read_text())
        assert measured['success'] is True and measured['moves']==3
        assert measured['fresh_replays']==0
        assert measured['replay_audit']['status']=='error'
        assert measured['replay_audit']['all_passed'] is False
    point=budget_curve([record],[256])
    assert point['points'][0]['success'] is None
    assert point['successful_suffix_of_tested_points'] is None
    displayed=movingai.report([folder/'episode'])['rows'][0]
    assert displayed['replay_audit']['status']=='error'


def test_movingai_execution_failure_remains_distinct(tmp_path,monkeypatch):
    def invalid_step(*args,**kwargs):raise ValueError('injected controller failure')
    monkeypatch.setattr(movingai,'checked_step',invalid_step)
    record=worker(condition(tmp_path))
    assert record['status']=='execution_error' and record['phase']=='evaluation'
    assert 'success' not in record
    folder=tmp_path/'runs/r00000'
    assert (folder/'episode/trace.jsonl.gz').exists()
    assert not (folder/'result.json').exists()
    assert not (folder/'episode/result.json').exists()


def test_zero_call_movingai_has_no_replay_evidence(tmp_path,monkeypatch):
    def forbidden_replay(*args,**kwargs):raise AssertionError('zero-call task cannot replay')
    monkeypatch.setattr(movingai,'replay_checkpoint',forbidden_replay)
    record=worker(condition(tmp_path,zero_calls=True))
    assert record['status']=='ok' and record['success'] is True and record['actions']==0
    assert record['audit']['all_passed'] is None
    measured=json.loads((tmp_path/'runs/r00000/episode/result.json').read_text())
    assert measured['fresh_replays']==0
    assert measured['replay_audit']['status']=='no_calls'
    assert measured['replay_audit']['all_passed'] is None


def test_successful_movingai_keeps_measured_outcome_and_replay_samples(tmp_path):
    record=worker(condition(tmp_path))
    assert record['status']=='ok' and record['success'] is True
    assert record['actions']==record['moves']==3
    measured=json.loads((tmp_path/'runs/r00000/episode/result.json').read_text())
    assert measured['replay_audit']['status']=='passed'
    assert measured['replay_audit']['all_passed'] is True
    assert measured['replay_audit']['checked_calls_one_based']==[1,2,3]
    assert measured['fresh_replays']==3


def test_source_drift_during_replay_is_not_accepted(tmp_path,monkeypatch):
    original_replay=movingai.replay_checkpoint
    original_read=Path.read_bytes
    source=Path(movingai.fullmap.__file__).resolve()
    audited=[]
    def replay(*args,**kwargs):
        output=original_replay(*args,**kwargs)
        audited.append(True)
        return output
    def changed_read(path):
        data=original_read(path)
        return data+b'\n# simulated source drift\n' if audited and path.resolve()==source else data
    monkeypatch.setattr(movingai,'replay_checkpoint',replay)
    monkeypatch.setattr(Path,'read_bytes',changed_read)
    record=worker(condition(tmp_path))
    assert record['status']=='execution_error'
    assert 'source changed during run' in record['error']
    assert 'success' not in record
