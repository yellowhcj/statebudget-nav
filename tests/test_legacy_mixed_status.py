"""Legacy studies retain failed/preflight conditions during geometry migration."""
import hashlib
import json
from statebudget_nav.study_analysis import summarize_study, movingai_physical_identity


def test_legacy_success_and_infeasible_same_task_do_not_become_different_tasks(tmp_path):
    geometry = dict(world='a' * 64, width=6, height=3, start=7, goal=10, heading=0)
    legacy_key = hashlib.sha256(json.dumps({**geometry, 'view': 3}, sort_keys=True).encode()).hexdigest()
    canonical = movingai_physical_identity('a' * 64, 6, 3, 7, 10)
    context = dict(view=3, limit=600)
    slots = [dict(run_id='r0', task_id='corridor', controller_id='raster', budget=32),
             dict(run_id='r1', task_id='corridor', controller_id='raster', budget=64)]
    plan = dict(tasks=[dict(id='corridor')], controllers=[dict(id='raster')], budgets=[32, 64])
    (tmp_path / 'plan.json').write_text(json.dumps(plan), encoding='utf-8')
    (tmp_path / 'conditions.json').write_text(json.dumps(slots), encoding='utf-8')
    for slot in slots:
        folder = tmp_path / 'runs' / slot['run_id']
        folder.mkdir(parents=True)
        record = {**slot, 'task_identity': 'movingai:' + legacy_key, 'context': context}
        if slot['budget'] == 32:
            record.update(status='infeasible', error='budget below initial representation size')
        else:
            record.update(status='ok', success=True, max_state_bytes=60, result='result.json')
            result = dict(physical_task_sha256=legacy_key, world_sha256='a' * 64,
                          task=dict(width=6, height=3, start=7, goal=10))
            (folder / 'result.json').write_text(json.dumps(result), encoding='utf-8')
        (folder / 'record.json').write_text(json.dumps(record), encoding='utf-8')
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob('*.json')}
    report = summarize_study(tmp_path)
    assert report['distinct_physical_tasks_with_identified_records'] == 1
    assert report['status_counts'] == {'infeasible': 1, 'ok': 1}
    curve = report['groups'][0]['curve']
    assert curve['points'][0]['success'] is None and curve['points'][1]['success'] is True
    assert report['groups'][0]['task_identity'] == 'movingai:' + canonical
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in before.items())
