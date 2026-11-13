"""Research interpretation checks, including gaps and invalid pairing."""
import base64
import hashlib
import json
from copy import deepcopy
import pytest
from statebudget_nav.study_analysis import budget_curve, compare_traces
from statebudget_nav.study import validate_plan, worker, run_study


def row(budget, success, status='ok'):
    return dict(budget=budget,success=success,status=status,max_state_bytes=budget)


def test_reversal_is_not_smoothed_or_extrapolated():
    r=budget_curve([row(32,True),row(33,False),row(34,True)],[32,33,34])
    assert r['first_successful_tested_budget']==32
    assert r['successful_suffix_of_tested_points']==34
    assert r['success_to_failure']==[dict(from_budget=32,to_budget=33,consecutive_integer_budgets=True)]


@pytest.mark.parametrize('unknown',['missing','execution_error','audit_error','infeasible'])
def test_unavailable_highest_point_prevents_successful_suffix(unknown):
    r=budget_curve([row(32,True),row(33,None,unknown)],[32,33])
    assert r['successful_suffix_of_tested_points'] is None
    assert not r['success_to_failure']
    assert r['points'][1]['success'] is None


def test_gap_is_not_adjacent_integer_or_untested_success():
    r=budget_curve([row(32,True),row(34,False),row(64,True)],[32,34,64])
    assert not r['all_integer_points_present']
    assert not r['success_to_failure'][0]['consecutive_integer_budgets']
    assert r['successful_suffix_of_tested_points']==64
    missing=budget_curve([row(32,True)],[32,33])
    assert missing['points'][1]['status']=='missing'
    assert missing['successful_suffix_of_tested_points'] is None


def events(actions, frames, states, budget=32):
    result=[]
    for i,action in enumerate(actions):
        result.append(dict(schema='statebudget.checkpoint.v1',spec=dict(width=5,height=5,budget=budget,policy='compressed'),
            frame={'position':frames[i]},state_b64=base64.b64encode(states[i]).decode(),
            expected=dict(action=action,state_sha256=hashlib.sha256(states[i+1]).hexdigest())))
    return result


def save(path, value):
    path.write_text(''.join(json.dumps(e)+'\n' for e in value),encoding='utf-8')
    return path


def result(budget=32):
    return dict(env='example',layout_hash='same',view=7,limit=20,selector='nearest',budget=budget,policy='compressed',steps=3)


def test_distinguishes_returned_state_action_and_observation_prefix(tmp_path):
    a=events([0,0,2],[1,1,2],[b'',b'a',b'b',b'c'])
    b=events([0,1,2],[1,1,3],[b'',b'x',b'y',b'z'],33)
    r=compare_traces(save(tmp_path/'a',a),save(tmp_path/'b',b),result(),result(33))
    assert r['first_differing_call']==dict(input_state=2,output_state=1,action=2,frame=3)
    assert r['witnesses'][1]['matched_observation_and_action_history_before_call']
    assert r['witnesses'][1]['matched_current_frame']
    assert not r['witnesses'][2]['matched_observation_and_action_history_before_call']


@pytest.mark.parametrize('change,match',[
    ({'layout_hash':'other'},'physical tasks'),({'view':5},'sensor/stopping'),({'steps':4},'trace length')])
def test_invalid_pairing_rejected(tmp_path,change,match):
    a=events([0,0,2],[1,1,2],[b'',b'a',b'b',b'c'])
    p=save(tmp_path/'trace',a);right={**result(),**change}
    with pytest.raises(ValueError,match=match):compare_traces(p,p,result(),right)


def test_broken_trace_chain_rejected(tmp_path):
    a=events([0,0,2],[1,1,2],[b'',b'a',b'b',b'c']);b=deepcopy(a)
    b[1]['state_b64']=base64.b64encode(b'unrelated').decode()
    with pytest.raises(ValueError,match='broken state chain'):
        compare_traces(save(tmp_path/'a',a),save(tmp_path/'b',b),result(),result())


def test_unknown_plan_keys_rejected_instead_of_silently_ignored():
    plan=dict(schema='statebudget.study_plan.v1',tasks=[dict(id='t',adapter='minigrid',env='MiniGrid-Empty-8x8-v0',seed=7)],
              controllers=[dict(id='custom',policy='python:module:step')],budgets=[64,96])
    assert validate_plan(plan)==plan
    plan['tasks'][0]['limti']=120
    with pytest.raises(ValueError,match='unknown or missing'):validate_plan(plan)


def test_payload_violation_rejected_by_analyzer():
    r=row(32,True);r['max_state_bytes']=33
    with pytest.raises(ValueError,match='exceeds declared budget'):budget_curve([r],[32])


def condition(tmp_path,budget=0):
    directory=tmp_path/'runs'/'r00000';directory.mkdir(parents=True)
    value=dict(run_id='r00000',task_id='empty',controller_id='counter',budget=budget,audit_stride=60,
        task=dict(id='empty',adapter='minigrid',env='MiniGrid-Empty-8x8-v0',seed=7,limit=3),
        controller=dict(id='counter',policy='python:statebudget_nav.examples.counter:step'))
    path=directory/'condition.json';path.write_text(json.dumps(value),encoding='utf-8')
    return path


def test_plugin_budget_violation_is_execution_error_not_navigation_failure(tmp_path):
    r=worker(condition(tmp_path,0))
    assert r['status']=='execution_error' and r['phase']=='evaluation'
    assert 'success' not in r
    assert (tmp_path/'runs/r00000/record.json').exists()


def test_failed_replay_is_audit_error_and_retains_measured_outcome(tmp_path,monkeypatch):
    import statebudget_nav
    monkeypatch.setattr(statebudget_nav,'replay_checkpoint',lambda *args,**kwargs:
        dict(action=6,state_b64=''))
    r=worker(condition(tmp_path,1))
    assert r['status']=='audit_error' and r['phase']=='audit'
    assert r['success'] is False and r['actions']==3
    curve=budget_curve([r],[1])
    assert curve['points'][0]['success'] is None
    assert curve['successful_suffix_of_tested_points'] is None


def test_two_tasks_get_their_own_charged_goal_through_one_plan(tmp_path):
    import navmemory_example
    (tmp_path/'tiny.map').write_text('type octile\nheight 5\nwidth 7\nmap\n@@@@@@@\n@.....@\n@.....@\n@.....@\n@@@@@@@\n',encoding='ascii')
    (tmp_path/'tiny.scen').write_text('version 1\n0 tiny.map 7 5 1 1 3 1 2\n0 tiny.map 7 5 1 1 1 3 2\n',encoding='ascii')
    for i,goal in [(2,10),(3,22)]:
        (tmp_path/f'goal{i}.bin').write_bytes(navmemory_example.initial(goal))
    plan=dict(schema='statebudget.study_plan.v1',tasks=[dict(id=f't{i}',adapter='movingai',map='tiny.map',scenarios='tiny.scen',line=i,view=3) for i in [2,3]],
        controllers=[dict(id='sparse',policy='python:navmemory_example:step',initial_state={f't{i}':f'goal{i}.bin' for i in [2,3]}),dict(id='raster',policy='lru')],
        budgets=[64],audit_stride=60)
    path=tmp_path/'plan.json';path.write_text(json.dumps(plan),encoding='utf-8')
    report=run_study(path,tmp_path/'study')
    assert report['status_counts']=={'ok':4}
    assert report['distinct_physical_tasks_with_identified_records']==2
    assert all(g['curve']['points'][0]['success'] for g in report['groups'])
    for i,goal in [(0,10),(2,22)]:
        r=json.loads((tmp_path/f'study/runs/r{i:05}/result.json').read_text())
        assert r['initial_state_hex']==navmemory_example.initial(goal).hex()
