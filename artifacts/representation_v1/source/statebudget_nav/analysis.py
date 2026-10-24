"""Descriptive summaries with one weight per physical layout in each stratum."""
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean
from .batch import verify_batch


def summarize_batch(path,allow_partial=False):
    path=Path(path);manifest,status=verify_batch(path,check_environment=False)
    if status['pending'] and not allow_partial:raise ValueError('incomplete batch; partial analysis must be explicit')
    records=[json.loads(p.read_text(encoding='utf-8'))['result'] for p in sorted((path/'jobs').glob('*.json'))]
    # Each seed instance first averages its independent controller random repeats.
    # Duplicated physical layouts then share one weight within each condition.
    by_instance=defaultdict(list);tasks=set();instances=set();world_by_instance={}
    for r in records:
        condition=(r['env'],r['view'],r['limit'],r['policy'],r['budget'],r['selector'])
        instance=(r['env'],r['view'],r['seed'])
        if instance in world_by_instance and world_by_instance[instance]!=r['world_hash']:
            raise ValueError('same environment instance produced different physical worlds')
        world_by_instance[instance]=r['world_hash']
        by_instance[(*condition,r['layout_hash'],r['seed'])].append(r)
        tasks.add((r['env'],r['view'],r['layout_hash']));instances.add(instance)
    by_layout=defaultdict(list)
    repeat_sets=defaultdict(set)
    for key,values in by_instance.items():
        seeds=[r['agent_seed'] for r in values]
        if len(set(seeds))!=len(seeds):raise ValueError('duplicated agent random repeat')
        repeat_sets[key[:-2]].add(tuple(sorted(seeds)))
        by_layout[key[:-1]].append(dict(success=mean(r['success'] for r in values),
                                      steps=mean(r['steps'] for r in values),
                                      max_bytes=max(r['max_state_bytes'] for r in values)))
    by_condition=defaultdict(list)
    for key,values in by_layout.items():
        by_condition[key[:-1]].append(dict(layout_hash=key[-1],
            success=mean(r['success'] for r in values),steps=mean(r['steps'] for r in values),
            max_bytes=max(r['max_bytes'] for r in values)))
    summaries=[]
    for key,values in sorted(by_condition.items()):
        row=dict(zip(['env','view','limit','policy','budget','selector'],key))
        row.update(unique_physical_tasks=len(values),mean_success=mean(r['success'] for r in values),
                   mean_actions=mean(r['steps'] for r in values),
                   max_state_bytes=max(r['max_bytes'] for r in values),
                   agent_repeat_sets=[list(v) for v in sorted(repeat_sets[key])])
        summaries.append(row)
    layouts_by_stratum=defaultdict(dict)
    for key,values in by_condition.items():
        layouts_by_stratum[key[:3]][key[3:]]={r['layout_hash'] for r in values}
    matched=all(len({tuple(sorted(v)) for v in methods.values()})==1
                for methods in layouts_by_stratum.values())
    return dict(schema='statebudget.summary.v1',episodes=len(records),seeded_instances=len(instances),
                physical_tasks_by_environment_and_view=len(tasks),partial=bool(status['pending']),
                identical_task_sets_within_observation_and_action_limits=matched,
                aggregation='agent repeats within seed; duplicate physical layouts within condition; no p values',
                summaries=summaries)
