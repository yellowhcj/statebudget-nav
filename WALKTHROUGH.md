# From a clean checkout to an auditable result

Use Python 3.10 or newer. These general commands apply to the current source
checkout; record its version and `git rev-parse HEAD`. This version is dev12;
use its release tag when a fixed dev12 installation is required. Historical dev7 records below
are retained as examples, not newly measured results from dev12.

The dev7 release was exercised on Windows/Python 3.12.7, with its recorded CI on
Ubuntu/Windows and Python 3.10/3.12. That historical evidence is not a dev12 platform
validation. GitHub and the Python package index must be reachable; configure any
needed proxy for your machine. Check Git, Python and pip before starting. Choose
an installed Python or Conda environment >=3.10 rather than replacing system Python.

For an exact historical reproduction, check out the original release tag/commit
before installation. Historical tags and source packages are not moved by later
documentation corrections. The commands below clone the current default branch;
they do not automatically select a historical tag; explicitly check out the requested version before installation.

## 1. Obtain and install

```text
git clone https://github.com/yellowhcj/statebudget-nav.git
cd statebudget-nav
git rev-parse HEAD
python -m venv .venv
```

On PowerShell activate with `.venv\Scripts\Activate.ps1`; on Linux/macOS use `source .venv/bin/activate`. If execution policy prevents activation, invoke `.venv\Scripts\python.exe` in place of `python` below. No policy change is needed.

```text
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[test]" --no-build-isolation
python -m pip install -e external_examples/navmemory_example --no-build-isolation --no-deps
python -m pytest tests -q
```

Install the separate example to exercise the complete integration suite; exact test counts belong to each version’s validation receipt. If pytest cannot write to its default temporary directory, add `--basetemp .pytest_tmp_run1`, selecting a new disposable path: pytest may clear an existing basetemp directory. Build prerequisites are deliberate; an earlier independent agent needed setuptools/wheel before installation succeeded.

## 2. Run, inspect and replay

```text
python -m statebudget_nav run --env MiniGrid-FourRooms-v0 --policy compressed --budget 64 --trace runs/trace.jsonl --output runs/result.json
python -m statebudget_nav audit runs/trace.jsonl --fresh-process --stride 10
```

Use new output paths. The historical dev7 example recorded success, 81 actions, maximum payload 64 bytes and nine sampled replay comparisons; verify the current output rather than treating these as a new dev12 measurement. Timings can differ. `result.json` holds outcomes and fingerprints; `trace.jsonl` holds local frames, input bytes, specifications and expected action/state hashes. Omit `--stride 10` to check every recorded decision. Replay does not bound total RAM or prove arbitrary code has no hidden state.

For this 19-by-19 map, `compressed` has a 26-byte structural minimum. Smaller
budgets are invalid configurations, not failed navigation episodes. Current source checks this before creating a trace, so correcting the budget can reuse
the uncreated path. Existing output files are never overwritten. Errors after
execution starts can still leave a useful partial trace; inspect it and select a
new output path rather than deleting evidence automatically.

Budget can affect retention and route choice: with the fixed default settings,
seed 10003 succeeds at 32 bytes, fails at 33, and succeeds at 34. A budget sweep
should therefore record failures as well as the first success; more bytes do not
guarantee success. A successful suffix describes only the tested budget range.

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
