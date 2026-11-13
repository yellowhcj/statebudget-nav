"""Geometry counts stay distinct from sensor contexts, including legacy results."""
from copy import deepcopy
import hashlib
import json
import pytest
from statebudget_nav.movingai import run, report
from statebudget_nav.study import worker
from statebudget_nav.study_analysis import movingai_physical_identity, task_identity, compare_traces, summarize_study


def inputs(tmp_path):
    grid = tmp_path / 'tiny.map'
    grid.write_text('type octile\nheight 3\nwidth 6\nmap\n@@@@@@\n@....@\n@@@@@@\n', encoding='ascii')
    scenario = tmp_path / 'tiny.scen'
    scenario.write_text('version 1\n0 tiny.map 6 3 1 1 4 1 3\n0 tiny.map 6 3 4 1 1 1 3\n', encoding='ascii')
    return grid, scenario


def test_one_geometry_different_views_count_once_but_cannot_be_paired(tmp_path):
    grid, scenario = inputs(tmp_path)
    a = run(grid, scenario, tmp_path / 'view3', 'lru', 256, line=2, view=3)
    b = run(grid, scenario, tmp_path / 'view5', 'lru', 256, line=2, view=5)
    assert a['physical_task_sha256'] == b['physical_task_sha256']
    assert a['sensor_task_sha256'] != b['sensor_task_sha256']
    summary = report([tmp_path / 'view3', tmp_path / 'view5'])
    assert summary['distinct_physical_tasks'] == 1
    assert summary['distinct_task_contexts'] == 2
    with pytest.raises(ValueError, match='sensor/stopping'):
        compare_traces(tmp_path / 'view3/trace.jsonl.gz', tmp_path / 'view5/trace.jsonl.gz', a, b)
    same_view = report([tmp_path / 'view3', tmp_path / 'view3'])
    assert same_view['distinct_physical_tasks'] == same_view['distinct_task_contexts'] == 1


def test_legacy_metadata_derives_identity_without_rewriting_original(tmp_path):
    grid, scenario = inputs(tmp_path)
    current = run(grid, scenario, tmp_path / 'current', 'lru', 256, line=2, view=3)
    legacy = deepcopy(current)
    legacy['package_version'] = '0.1.0.dev12'
    legacy['physical_task_sha256'] = legacy.pop('sensor_task_sha256')
    legacy.pop('physical_task_identity_schema')
    legacy.pop('initial_heading')
    original = json.dumps(legacy, sort_keys=True)
    old_dir = tmp_path / 'legacy'
    old_dir.mkdir()
    path = old_dir / 'result.json'
    path.write_text(original, encoding='utf-8')
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    assert task_identity(legacy) == task_identity(current)
    assert report([old_dir, tmp_path / 'current'])['distinct_physical_tasks'] == 1
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_layout_endpoints_and_initial_pose_remain_distinct():
    baseline = movingai_physical_identity('a' * 64, 6, 3, 7, 10)
    assert baseline != movingai_physical_identity('b' * 64, 6, 3, 7, 10)
    assert baseline != movingai_physical_identity('a' * 64, 6, 3, 10, 7)
    assert baseline != movingai_physical_identity('a' * 64, 6, 3, 7, 9)
    assert baseline != movingai_physical_identity('a' * 64, 6, 3, 7, 10, 1)
    assert baseline != movingai_physical_identity('a' * 64, 3, 6, 7, 10)


def test_incomplete_legacy_metadata_falls_back_without_inventing_geometry():
    legacy = dict(physical_task_sha256='legacy_key', view=3)
    assert task_identity(legacy) == 'movingai:legacy_key'


def test_new_schema_rejects_inconsistent_geometry_digest():
    record = dict(physical_task_sha256='wrong', physical_task_identity_schema='statebudget.movingai_physical_task.v2',
                  world_sha256='a' * 64, task=dict(width=6, height=3, start=7, goal=10))
    with pytest.raises(ValueError, match='declared geometry'):
        task_identity(record)


def test_study_preflight_and_summary_separate_geometry_from_context(tmp_path):
    inputs(tmp_path)
    tasks = [dict(id='view' + str(view), adapter='movingai', map='tiny.map', scenarios='tiny.scen',
                  line=2, view=view) for view in (3, 5)]
    controller = dict(id='raster', policy='lru')
    slots = []
    for index, task in enumerate(tasks):
        slot = dict(run_id='r' + str(index).zfill(5), task_id=task['id'], controller_id='raster', budget=256,
                    task=task, controller=controller, audit_stride=60)
        folder = tmp_path / 'runs' / slot['run_id']
        folder.mkdir(parents=True)
        path = folder / 'condition.json'
        path.write_text(json.dumps(slot), encoding='utf-8')
        record = worker(path)
        assert record['status'] == 'ok'
        slots.append(slot)
    (tmp_path / 'conditions.json').write_text(json.dumps(slots), encoding='utf-8')
    (tmp_path / 'plan.json').write_text(json.dumps(dict(tasks=tasks, controllers=[controller], budgets=[256])), encoding='utf-8')
    summary = summarize_study(tmp_path)
    assert summary['distinct_physical_tasks_with_identified_records'] == 1
    assert summary['distinct_task_contexts_with_identified_records'] == 2
    assert summary['status_counts'] == {'ok': 2}
    # Analyze complete older study records without rewriting their stored keys.
    before = {}
    for slot in slots:
        folder = tmp_path / 'runs' / slot['run_id']
        result_path = folder / 'result.json'
        measured = json.loads(result_path.read_text())
        measured['physical_task_sha256'] = measured.pop('sensor_task_sha256')
        measured.pop('physical_task_identity_schema')
        measured.pop('initial_heading')
        result_path.write_text(json.dumps(measured), encoding='utf-8')
        record_path = folder / 'record.json'
        record = json.loads(record_path.read_text())
        record['task_identity'] = 'movingai:' + measured['physical_task_sha256']
        record_path.write_text(json.dumps(record), encoding='utf-8')
        for path in (result_path, record_path):
            before[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    legacy_summary = summarize_study(tmp_path)
    assert legacy_summary['distinct_physical_tasks_with_identified_records'] == 1
    assert legacy_summary['distinct_task_contexts_with_identified_records'] == 2
    assert all('recorded_task_identity' in group['curve']['points'][0] for group in legacy_summary['groups'])
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in before.items())
