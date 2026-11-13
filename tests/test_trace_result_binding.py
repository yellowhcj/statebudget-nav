"""Wrong trace-path selection must not create a same-task diagnosis."""
from copy import deepcopy
import pytest
from statebudget_nav.movingai import run
from statebudget_nav.evaluation import run_episode
from statebudget_nav.study_analysis import compare_traces, sha


def test_real_task_traces_are_bound_to_their_results(tmp_path):
    grid = tmp_path / 'tiny.map'
    grid.write_text('type octile\nheight 5\nwidth 7\nmap\n@@@@@@@\n@.....@\n@.....@\n@.....@\n@@@@@@@\n', encoding='ascii')
    scenarios = tmp_path / 'tiny.scen'
    scenarios.write_text('version 1\n0 tiny.map 7 5 1 1 3 1 2\n0 tiny.map 7 5 1 3 3 3 2\n', encoding='ascii')
    a = run(grid, scenarios, tmp_path / 'a', policy='lru', budget=64, line=2, view=3)
    b = run(grid, scenarios, tmp_path / 'b', policy='lru', budget=64, line=3, view=3)
    left, right = [tmp_path / name / 'trace.jsonl.gz' for name in ('a', 'b')]
    assert a['actions'] == b['actions'] == 2
    assert a['physical_task_sha256'] != b['physical_task_sha256']
    with pytest.raises(ValueError, match='different physical tasks'):
        compare_traces(left, right, a, b)
    valid = compare_traces(left, left, a, a)
    assert valid['trace_result_binding'] == dict(left='verified_file_sha256', right='verified_file_sha256')
    assert all(value is None for value in valid['first_differing_call'].values())
    with pytest.raises(ValueError, match='right trace/result file SHA256 mismatch'):
        compare_traces(left, right, a, a)
    with pytest.raises(ValueError, match='left trace/result file SHA256 mismatch'):
        compare_traces(right, left, a, a)
    legacy = deepcopy(a)
    legacy.pop('trace_sha256')
    compatible = compare_traces(left, left, legacy, a)
    assert compatible['trace_result_binding'] == dict(left='unavailable_in_result', right='verified_file_sha256')
    assert 'trace_sha256' not in legacy


def test_new_minigrid_results_bind_written_traces_only(tmp_path):
    policy = 'python:statebudget_nav.examples.counter:step'
    left, right = tmp_path / 'a.jsonl', tmp_path / 'b.jsonl'
    a = run_episode('MiniGrid-FourRooms-v0', seed=10000, policy=policy, budget=1, limit=3, trace_path=left)
    b = run_episode('MiniGrid-FourRooms-v0', seed=10001, policy=policy, budget=1, limit=3, trace_path=right)
    assert a['steps'] == b['steps'] == 3
    assert a['layout_hash'] != b['layout_hash']
    assert a['trace_sha256'] == sha(left)
    assert b['trace_sha256'] == sha(right)
    valid = compare_traces(left, left, a, a)
    assert valid['trace_result_binding'] == dict(left='verified_file_sha256', right='verified_file_sha256')
    with pytest.raises(ValueError, match='different physical tasks'):
        compare_traces(left, right, a, b)
    with pytest.raises(ValueError, match='right trace/result file SHA256 mismatch'):
        compare_traces(left, right, a, a)
    untraced = run_episode('MiniGrid-FourRooms-v0', seed=10000, policy=policy, budget=1, limit=3)
    assert 'trace_sha256' not in untraced
    assert untraced['trajectory_hash'] == a['trajectory_hash']
