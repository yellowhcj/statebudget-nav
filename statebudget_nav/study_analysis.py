"""Portable analysis of declared studies; no controller execution or causal inference."""
import base64
import gzip
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def movingai_physical_identity(world_sha256, width, height, start, goal, heading=0):
    """Identify geometry/endpoints/initial pose independently of sensing context."""
    content = dict(world=world_sha256, width=width, height=height,
                   start=start, goal=goal, heading=heading)
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def task_identity(result):
    if 'physical_task_sha256' in result:
        task = result.get('task', {})
        if 'world_sha256' in result and all(k in task for k in ('width', 'height', 'start', 'goal')):
            canonical = movingai_physical_identity(result['world_sha256'], task['width'], task['height'],
                                                  task['start'], task['goal'], result.get('initial_heading', 0))
            # Earlier versions included view in the stored digest. Derive the
            # geometry identity without editing those historical result files.
            if result.get('physical_task_identity_schema') == 'statebudget.movingai_physical_task.v2':
                if result['physical_task_sha256'] != canonical:
                    raise ValueError('physical task digest differs from declared geometry')
            return 'movingai:' + canonical
        # Incomplete legacy metadata cannot be reconstructed; retain its key
        # rather than inventing an equivalence between unsupported records.
        return 'movingai:' + result['physical_task_sha256']
    if 'layout_hash' in result:
        return 'minigrid:' + result['env'] + ':' + result['layout_hash']
    raise ValueError('result needs a supported physical task identity')


def context(result):
    keys = ('env', 'view', 'limit', 'selector') if 'env' in result else ('view', 'limit')
    return {key: result[key] for key in keys}


def budget_curve(rows, budgets):
    """Describe planned points, never interpolate errors or missing points as failures."""
    budgets = sorted(budgets)
    if not budgets or len(set(budgets)) != len(budgets):
        raise ValueError('nonempty unique budgets required')
    indexed = {r['budget']: r for r in rows}
    if len(indexed) != len(rows) or set(indexed) - set(budgets):
        raise ValueError('duplicate or unplanned budget records')
    points = []
    allowed = {'ok','missing','infeasible','execution_error','audit_error'}
    for b in budgets:
        row = indexed.get(b, {'budget': b, 'status': 'missing'})
        point = dict(row)
        if row['status'] not in allowed:
            raise ValueError('unknown condition status')
        if row['status'] == 'ok':
            if type(row.get('success')) is not bool:
                raise ValueError('completed record requires a boolean success')
            if row['max_state_bytes'] > b:
                raise ValueError('record exceeds declared budget')
        else:
            point['success'] = None
        points.append(point)
    transitions = []
    for a, b in zip(points, points[1:]):
        if a['status'] == b['status'] == 'ok' and a['success'] and not b['success']:
            transitions.append({'from_budget': a['budget'], 'to_budget': b['budget'],
                                'consecutive_integer_budgets': b['budget'] == a['budget'] + 1})
    # A suffix must reach the highest PLANNED point without errors or missing data.
    suffix = None
    for p in reversed(points):
        if p['status'] != 'ok' or not p['success']:
            break
        suffix = p['budget']
    successes = [p['budget'] for p in points if p['status'] == 'ok' and p['success']]
    return {'tested_budget_points': budgets, 'all_integer_points_present': all(b == a+1 for a,b in zip(budgets,budgets[1:])),
            'points': points, 'first_successful_tested_budget': min(successes) if successes else None,
            'successful_suffix_of_tested_points': suffix, 'success_to_failure': transitions,
            'scope': 'A suffix concerns listed tested points only; gaps are not interpolated and no guarantee extends beyond them.'}


def trace_events(path):
    path = Path(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            if event.get('schema') != 'statebudget.checkpoint.v1':
                raise ValueError('unsupported checkpoint schema')
            base64.b64decode(event['state_b64'], validate=True)
            if 'expected' not in event:
                raise ValueError('trace needs recorded expected action and output digest')
            yield event


def compare_traces(left, right, left_result, right_result):
    """Locate recorded differences; call numbers are one-based, comparisons structural."""
    if task_identity(left_result) != task_identity(right_result):
        raise ValueError('different physical tasks cannot be paired')
    if context(left_result) != context(right_result):
        raise ValueError('different sensor/stopping contexts cannot be paired')
    trace_hashes = {'left': sha(left), 'right': sha(right)}
    trace_result_binding = {}
    for side, result in (('left', left_result), ('right', right_result)):
        if 'trace_sha256' in result:
            if trace_hashes[side] != result['trace_sha256']:
                raise ValueError(side + ' trace/result file SHA256 mismatch')
            trace_result_binding[side] = 'verified_file_sha256'
        else:
            trace_result_binding[side] = 'unavailable_in_result'
    a, b = list(trace_events(left)), list(trace_events(right))
    for events, result in ((a, left_result), (b, right_result)):
        dimensions = set()
        for i, event in enumerate(events):
            spec = event['spec']
            dimensions.add((spec['width'],spec['height']))
            if spec['budget'] != result['budget']:
                raise ValueError('trace/result budget mismatch')
            if spec['policy'] != result.get('controller_identity',result['policy']):
                raise ValueError('trace/result controller mismatch')
            raw = base64.b64decode(event['state_b64'],validate=True)
            if len(raw) > spec['budget']:
                raise ValueError('trace input exceeds budget')
            if i and hashlib.sha256(raw).hexdigest() != events[i-1]['expected']['state_sha256']:
                raise ValueError('broken state chain between recorded calls')
        if len(dimensions)>1:
            raise ValueError('dimensions changed within a trace')
    first = {k: None for k in ('input_state', 'output_state', 'action', 'frame')}
    common_history = True
    witnesses = []
    for index, (x, y) in enumerate(zip(a, b), 1):
        if (x['spec']['width'], x['spec']['height']) != (y['spec']['width'], y['spec']['height']):
            raise ValueError('trace dimensions differ')
        same_frame = x['frame'] == y['frame']
        differences = {
            'input_state': base64.b64decode(x['state_b64']) != base64.b64decode(y['state_b64']),
            'output_state': x['expected']['state_sha256'] != y['expected']['state_sha256'],
            'action': x['expected']['action'] != y['expected']['action'],
            'frame': not same_frame}
        newly = []
        for key, different in differences.items():
            if different and first[key] is None:
                first[key] = index
                newly.append(key)
        if newly:
            witnesses.append({'call_one_based': index, 'new_differences': newly,
                'matched_observation_and_action_history_before_call': common_history,
                'matched_current_frame': same_frame,
                'left': x, 'right': y})
        common_history = common_history and same_frame and not differences['action']
    # Verify provenance relations available in these records; identity is evaluator metadata,
    # not reconstructible from a single local observation.
    for events, result in ((a, left_result), (b, right_result)):
        expected_count = result.get('actions', result.get('steps'))
        if expected_count is not None and len(events) != expected_count:
            raise ValueError('trace length differs from completed result')
    return {'schema': 'statebudget.trace_comparison.v1', 'task_identity': task_identity(left_result),
            'context': context(left_result), 'call_numbering': 'one-based controller calls',
            'left_sha256': trace_hashes['left'], 'right_sha256': trace_hashes['right'],
            'trace_result_binding': trace_result_binding,
            'left_calls': len(a), 'right_calls': len(b), 'compared_calls': min(len(a), len(b)),
            'unpaired_tail_calls': abs(len(a)-len(b)),
            'first_differing_call': first, 'witnesses': witnesses,
            'scope': 'Structural recorded-state/action differences, not semantic information loss or proof of the cause of task failure. Replay is reported separately.'}


def verify_files(directory):
    root = Path(directory).resolve()
    receipt = read_json(root / 'STUDY_RECEIPT.json')
    for name, digest in receipt['files_sha256'].items():
        p = (root / name).resolve()
        if not p.is_relative_to(root) or sha(p) != digest:
            raise ValueError('missing or changed study artifact: ' + name)
    return {'verified_files': len(receipt['files_sha256']), 'all_matched': True,
            'scope': 'Integrity relative to supplied receipt, not an authenticity signature or full dependency archive.'}


def summarize_study(directory):
    root = Path(directory)
    plan = read_json(root / 'plan.json')
    slots = read_json(root / 'conditions.json')
    records = []
    identity_aliases = {}
    for slot in slots:
        path = root / 'runs' / slot['run_id'] / 'record.json'
        record = read_json(path) if path.exists() else dict(slot, status='missing')
        if any(record[k] != slot[k] for k in ('run_id','task_id','controller_id','budget')):
            raise ValueError('record does not match planned condition')
        if record.get('result') and record.get('task_identity', '').startswith('movingai:'):
            measured = read_json(path.parent / record['result'])
            canonical = task_identity(measured)
            original = 'movingai:' + measured['physical_task_sha256']
            if record['task_identity'] not in (original, canonical):
                raise ValueError('record/result physical task identity mismatch')
            for alias in (original, record['task_identity']):
                if identity_aliases.setdefault(alias, canonical) != canonical:
                    raise ValueError('inconsistent legacy physical task identity')
        records.append(record)
    # Preflight failures may have no result file. Normalize them only when a
    # complete result proved the same recorded key's geometry elsewhere in
    # this study; otherwise keep the original identity without guessing.
    records = [{**r, 'recorded_task_identity': r['task_identity'],
                'task_identity': identity_aliases[r['task_identity']]}
               if r.get('task_identity') in identity_aliases
               and identity_aliases[r['task_identity']] != r['task_identity'] else r
               for r in records]
    groups = []
    for task in plan['tasks']:
        for controller in plan['controllers']:
            rows = [r for r in records if r['task_id'] == task['id'] and r['controller_id'] == controller['id']]
            identities = {r['task_identity'] for r in rows if r.get('task_identity')}
            contexts = {json.dumps(r['context'], sort_keys=True) for r in rows if r.get('context')}
            if len(identities) > 1 or len(contexts) > 1:
                raise ValueError('task or context changed across paired conditions')
            groups.append({'task_id': task['id'], 'controller_id': controller['id'],
                           'task_identity': next(iter(identities), None),
                           'curve': budget_curve(rows, plan['budgets'])})
    for task in plan['tasks']:
        identified=[r for r in records if r['task_id']==task['id'] and r.get('task_identity')]
        if len({r['task_identity'] for r in identified})>1 or len({json.dumps(r['context'],sort_keys=True) for r in identified})>1:
            raise ValueError('task or context changed across controllers')
    identities = {r['task_identity'] for r in records if r.get('task_identity')}
    task_contexts = {(r['task_identity'], json.dumps(r['context'], sort_keys=True))
                     for r in records if r.get('task_identity') and r.get('context')}
    return {'schema': 'statebudget.study_report.v1', 'planned_executions': len(slots),
            'status_counts': {s: sum(r['status'] == s for r in records) for s in sorted({r['status'] for r in records})},
            'distinct_physical_tasks_with_identified_records': len(identities),
            'distinct_task_contexts_with_identified_records': len(task_contexts),
            'groups': groups, 'scope': 'Conditional per-task/controller budget curves. Task aliases/repeats are not independent physical samples; no global codec ranking.'}
