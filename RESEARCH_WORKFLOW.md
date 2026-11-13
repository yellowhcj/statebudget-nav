# Study a memory choice, then deliver inspectable evidence

This workflow is for accurately localized, static-grid symbolic navigation.
Its resource is the declared serialized state retained between decisions, not
total process RAM. Choose the scientific question before choosing a compressor.

## Who writes what?

| Researcher supplies | Reused toolkit work |
| --- | --- |
| Memory representation, update and retention rules | Incoming/outgoing bytes, action and observation validation |
| A trusted `step(frame, state, spec)` and explicit initial bytes | Local-input checkpoints and fresh-interpreter action/output comparisons |
| Task/observation assumptions, comparison conditions and reporting choices | Existing MiniGrid/MovingAI sensing and execution, result/task identities |
| Review of task-specific constants and all persistent information | Trace/audit files and declared source snapshots |

For an existing adapter, replacing the memory does not require replacing the
evaluator. A new task type still needs a sensor/action adapter and its identity
convention. Plugins have normal Python permissions. Reproducible recorded calls
do not establish absence of all uncharged information; review the code as well.

## Install the tool and a separate example controller

Use Python 3.10+ and an environment with pip/build tools. From this source root:

```text
python -m pip install . --no-build-isolation
python -m pip install ./external_examples/navmemory_example --no-deps --no-build-isolation
```

Or install the matching two wheels. Record their hashes and dependency versions.
For configurable plans and paired diagnosis in dev13, start with
[STUDIES.md](STUDIES.md). This page preserves the earlier two convenience examples.
Their historical dev7/dev8 records retain their original matching versions;
the convenience commands remain available in dev13.
Use a new output directory for each study; existing evidence is never overwritten.

## Question 1: what changes when another memory representation is connected?

Use the original Berlin task already documented in MOVINGAI.md. Obtain inputs
with the download command there, or use unchanged previously downloaded files.
The files must be named `Berlin_1_256.map` and `Berlin_1_256.map.scen`.

```text
python tools/research_workflow.py fullmap --map inputs/Berlin_1_256.map --scenarios inputs/Berlin_1_256.map.scen --line 231 --budget 1024 --output runs/memory-comparison
```

This command is a convenience composition of the public CLI. It:

1. Copies and hashes the supplied map/scenario and verifies the original
   eight-neighbor distance independently of the adapted navigation run.
2. Runs the built-in raster LRU and the separately installed sparse-map FIFO
   controller at the same budget, task, local sensor and stopping conditions.
3. Saves both initial states, source records, results and traces, summarizes
   identities, and replays sampled decisions in fresh interpreters.
4. Records versions and command logs in `WORKFLOW_RECEIPT.json`. A failure leaves
   `FAILED.json` and its diagnostic logs, never a completed receipt.

Read `comparison.json` for task count, each complete configuration's success,
actions and peak payload. This selected example demonstrates replacement; it is
not a new benchmark or a pure compression ranking. The two representations also
use different retention granularity. A general performance study needs a declared
task set and conditions beyond this example.

To integrate your own representation, install its module and replace the policy
and initial-state commands shown in MOVINGAI.md:

```text
python -m statebudget_nav movingai --map inputs/Berlin_1_256.map --scenarios inputs/Berlin_1_256.map.scen --line 231 --policy python:your_module:step --initial-state your_initial.bin --budget 1024 --output runs/your-controller
python -m statebudget_nav audit runs/your-controller/trace.jsonl.gz --fresh-process --stride 17
```

The adapter is unchanged. Your initializer may use the declared known target,
but that target must persist in the charged bytes; it cannot hide the unobserved
map in free code/configuration. Serialize order, counters and randomness too.

## Question 2: does a successful budget stay successful at a larger cap?

Budget changes can change retained content, actions and later observations.
Choose a range before inspecting outcomes. A compact regression exercise uses
two previously investigated FourRooms layouts and three adjacent budgets:

```text
python tools/research_workflow.py budget --seeds 10003 10010 --budgets 32 33 34 --output runs/budget-sensitivity
```

The runner saves all six episode results and traces, pairs conditions by layout,
reports adjacent success-to-failure transitions, and samples restart checks.
These are selected historical examples, not a new estimate of how common
non-monotonicity is. Run your own declared seeds/range with the same options.
Keep failures and report the tested interval; a first successful point or a
successful suffix does not imply behavior outside that range.

The external participant's original study used public dev7, 20 layouts and
26--64 bytes. This convenience runner and the author's dev8 checks do not change
the attribution or create another independent user study.

## What should another researcher receive?

Deliver the exact tool/plugin wheels, dependency versions, controller code,
inputs and initial payload, results, full traces and audit coverage. The runner
can copy and hash supplied wheels with repeated `--wheel path/to/file.whl`
options; it verifies their packaged Python/core files against the installation.
This does not bundle the Python interpreter or all transitive dependencies.

MovingAI runs snapshot selected adapter/controller files and an external entry
module. Replay imports installed modules; snapshots alone do not switch imports
to the saved source. Install the matching wheels before replay. Generic frozen
batch queues support bundled controllers only; this workflow does not silently
extend them to arbitrary plugins.

For pure coding efficiency, encode the same logical information with each codec
and verify restoration. Closed-loop success answers a different question about
the complete representation/retention/planning configuration. Report runtime,
temporary workspace and shared static tables separately from the payload.
