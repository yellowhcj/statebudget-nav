# From a clean checkout to an auditable result

Use Python 3.10 or newer; the exercised environment is Windows/Python 3.12.7. This does not establish support for every dependency version or platform. GitHub and the Python package index must be reachable; configure any needed proxy for your machine.

## 1. Obtain and install

```text
git clone --branch v0.1.0-dev5 --depth 1 https://github.com/yellowhcj/statebudget-nav.git
cd statebudget-nav
python -m venv .venv
```

On PowerShell activate with `.venv\Scripts\Activate.ps1`; on Linux/macOS use `source .venv/bin/activate`. If execution policy prevents activation, invoke `.venv\Scripts\python.exe` in place of `python` below. No policy change is needed.

```text
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[test]" --no-build-isolation
python -m pytest tests -q
```

The suite has 17 checks. If pytest cannot write to its default temporary directory, add `--basetemp .pytest_tmp_run1`, selecting a new disposable path: pytest may clear an existing basetemp directory. Build prerequisites are deliberate; an earlier independent agent needed setuptools/wheel before installation succeeded.

## 2. Run, inspect and replay

```text
python -m statebudget_nav run --env MiniGrid-FourRooms-v0 --policy compressed --budget 64 --trace runs/trace.jsonl --output runs/result.json
python -m statebudget_nav audit runs/trace.jsonl --fresh-process --stride 10
```

Use new output paths. In the exercised configuration expect success, 81 actions, maximum payload 64 bytes and nine sampled replay comparisons. Timings can differ. `result.json` holds outcomes and fingerprints; `trace.jsonl` holds local frames, input bytes, specifications and expected action/state hashes. Omit `--stride 10` to check every recorded decision. Replay does not bound total RAM or prove arbitrary code has no hidden state.

## 3. Connect your own sensor and controller

```text
python -m statebudget_nav.examples.custom_grid runs/custom-grid
python -m statebudget_nav audit runs/custom-grid/trace.jsonl --fresh-process
```

This uses a new radius-one grid sensor loop without MiniGrid's environment loop and an importable local-walk plugin. The recorded example reaches its goal in 89 actions with four retained bytes. The first command checks nine sampled decisions; the second checks all 89. Inspect:

- `statebudget_nav/examples/custom_grid.py`: sensor mapping, evaluator-private world, actions and checkpoint logging.
- `statebudget_nav/examples/local_walk.py`: the controller retaining a four-byte PRNG word.
- `runs/custom-grid/result.json`: world, plugin and trace hashes, outcomes and replay scope.

Replace the sensor mapping and actuator loop for your own localized grid. Keep goals and doors limited to currently observed cells. Select your installed callable as `python:your_module:step`; archive its source/dependencies and make it importable to fresh interpreters. Frozen queues reject external plugins: their automatic archive currently covers bundled implementations. See EXTENDING.md. This author-provided demonstration is not an external user study or a new navigation algorithm.

## 4. Reproduce a comparison or fault

```text
python -m statebudget_nav.examples.representation_study runs/representations
python -m statebudget_nav verify runs/representations
python -m statebudget_nav summary runs/representations
python -m statebudget_nav.examples.audit_faults runs/faults
```

The comparison runs 96 episodes on inspected development seeds: expect 24/32 successes for sparse LRU, 0/32 for separate history plus LRU and 32/32 for compact/compressed geometry at 112 bytes. This is reproducibility evidence, not held-out validation. The fault report shows full replay detecting three controlled hidden-global faults that first-checkpoint sampling misses.

Queue summaries distinguish episodes, seeded configurations and physical layouts. Agent repeats are not extra independent maps. Check source verification and queue completeness before interpreting outcomes.
