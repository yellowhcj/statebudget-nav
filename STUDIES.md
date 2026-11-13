# Budget studies with your own controller

This interface composes the installed evaluators and fresh-process replay.
It accepts built-in or `python:module:function` controllers. No change to the
evaluator or analysis script is required when switching an importable controller.
It measures declared serialized persistent bytes, not total process RAM.

## Declare a plan before running

Save `plan.json`. IDs are portable labels, not controller inputs. Paths are
relative to this JSON file. Output directories must be new.

```json
{
  "schema": "statebudget.study_plan.v1",
  "tasks": [
    {"id": "empty7", "adapter": "minigrid", "env": "MiniGrid-Empty-8x8-v0",
     "seed": 7, "view": 7, "limit": 120}
  ],
  "controllers": [
    {"id": "lru", "policy": "lru"},
    {"id": "compressed", "policy": "compressed"}
  ],
  "budgets": [32, 64, 96],
  "audit_stride": 60
}
```

```text
python -m statebudget_nav study run plan.json --output runs/my-study
python -m statebudget_nav study report runs/my-study
python -m statebudget_nav study verify runs/my-study --replay
```

Each condition runs in its own interpreter with a timeout (default 1800 seconds,
override with `--timeout`). A frozen normalized plan, copied declared inputs,
condition records, stdout/stderr, results, traces, source snapshots and hash
receipt are preserved. This is a sequential convenience study, not a resumable
distributed queue. Keep partial directories after interruptions; report can
identify missing records, but verify requires a completed receipt.

## MovingAI and external memories

Prepare charged initial bytes using your initializer. The separate sparse FIFO
example installed from its own wheel can generate a five-byte target header:

```text
python -m navmemory_example --map inputs/Berlin_1_256.map --scenarios inputs/Berlin_1_256.map.scen --line 231 --output inputs/goal231.bin
```

For a MovingAI study use:

Scenario `line` is the one-based original text-file line, including the
`version 1` header: the first scenario is **line 2**, not line 1.

```json
{
  "schema": "statebudget.study_plan.v1",
  "tasks": [
    {"id": "berlin231", "adapter": "movingai", "map": "inputs/Berlin_1_256.map",
     "scenarios": "inputs/Berlin_1_256.map.scen", "line": 231, "view": 7,
     "movement_multiplier": 6}
  ],
  "controllers": [
    {"id": "raster", "policy": "lru"},
    {"id": "my_memory", "policy": "python:navmemory_example:step",
     "initial_state": "inputs/goal231.bin"}
  ],
  "budgets": [768, 1024, 1280],
  "audit_stride": 60
}
```

To supply a different target per task, `initial_state` accepts an object mapping
**every** task ID to a binary path, for example
`{"berlin231":"inputs/goal231.bin","berlin232":"inputs/goal232.bin"}`.
Never reuse one goal header blindly for different endpoints. Built-in MovingAI
controllers initialize their own charged state and reject overrides.

The local-sensing four-neighbor adaptation uses square through-wall views,
accurate pose, known dimensions and a charged target. The movement limit is
`max(600, ceil(movement_multiplier * D4))`, and action limit is three times that.
These are adapted experiments using official inputs, not official benchmark scores.
MiniGrid uses its environment sensor, optional `selector` (default `nearest`),
optional `agent_seed` (default 1) and starts with empty bytes. MiniGrid does not
accept an initial-state override in this interface.

All controllers for a plan share declared tasks, budgets and limits. Tasks may
have different documented sensors, but only matching contexts are paired. A
plan mixing adapters cannot use a MovingAI initial-state controller on MiniGrid.
Use separate plans for incompatible interfaces. Unknown plan keys are errors.

## Read the report without changing the question

`status` records whether execution and replay succeeded, independently of arrival:

| Status | Meaning |
| --- | --- |
| `ok` | Episode completed and recorded replay checks passed; `success` may be false. |
| `infeasible` | A known preflight structural bound or initial-payload length prevents execution. |
| `execution_error` | Import, controller, resource, invalid movement, timeout or other execution error. |
| `audit_error` | A produced run failed its replay/trace check, including MovingAI internal replay; measured outcome remains in raw records. |
| `missing` | A declared condition has no record, for example after interruption. |

Only `ok` records enter success/failure transitions. A plugin exception about
memory is not automatically classified as a proven structural lower bound.
Report errors separately; silently dropping them can bias a comparison.

The report keeps per-task/controller budget curves, first successful tested
budget, success-to-failure transitions and a successful suffix of **tested points**.
A missing or erroneous highest point prevents such a suffix. Nonconsecutive
budgets are not interpolated. Neither statistic guarantees success beyond the
tested points. Distinct physical task counts deduplicate aliases and seeds;
groups are not independent samples and no overall codec ranking is computed.

MovingAI physical identity covers occupancy, dimensions, endpoints and initial
heading. View and stopping limits remain separate context: two views of the same
map/endpoint task count once physically but cannot be paired for trace diagnosis.
Reports give both physical-task and task/context counts. New results mark the
geometry-only identity as `statebudget.movingai_physical_task.v2`; a separate
`sensor_task_sha256` preserves the earlier sensor-inclusive key. Reading complete
older result metadata derives the geometry key without rewriting the old files.
When geometry metadata is absent, its original legacy key is retained instead.

## Inspect paired recorded decisions

Choose runs with matching physical tasks and sensor/stopping context. Run IDs
and their task/controller/budget assignments are listed in `conditions.json`.
MiniGrid uses `trace.jsonl`; MovingAI uses `episode/trace.jsonl.gz`.

```text
python -m statebudget_nav study compare --left runs/my-study/runs/r00000/trace.jsonl --right runs/my-study/runs/r00001/trace.jsonl --left-result runs/my-study/runs/r00000/result.json --right-result runs/my-study/runs/r00001/result.json --output diagnosis.json
```

Call numbers are one-based. The report separates first input-state bytes,
output-state digest, action and current-frame differences. It checks state-chain
continuity, trace length and result identity; witnesses indicate whether the
entire preceding observation/action history still matches. It does not mistake
different budget values in `spec` for behavioral divergence. A later action
difference after observation histories separated is not an isolated memory effect.
Byte differences do not alone show semantic information loss or explain eventual failure.

## Share and reproduce

Send the entire study directory, matching tool/plugin wheels and dependency
versions. `study report` recalculates the analysis without executing controllers;
`study verify` checks artifact hashes and current installed module identities;
`study verify --replay` reruns the recorded sample indices in fresh interpreters.
The first, every stride-th and final decision are selected; actual call numbers
and total trace calls are recorded for each successful audit. Zero-call tasks
have no successful replay evidence and explicitly report a null replay outcome.

Source snapshots are supporting artifacts; replay imports installed modules.
Source identity keys use POSIX relative paths on every operating system.
Verification accepts legacy Windows separators, while still requiring exact
package version, every source digest, dependency versions and plugin entry hashes.
Use the original matching installation to verify older-version studies; installing
a successor does not make its changed source identical to the recorded version.
The wheel, all plugin dependencies and scientific review remain your responsibility.
The receipt is not a digital authenticity signature or a complete environment
archive. Plugins remain trusted Python code with ordinary permissions. Source
review must check no task-specific map/goal/history is hidden in free constants,
global mutable state, files or services. Immutable learned models and runtime
workspace need separate disclosure. This workflow does not enforce hostile-code
isolation and does not certify total RAM usage.
