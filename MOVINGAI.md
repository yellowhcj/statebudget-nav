# Full maps and official MovingAI scenarios

The MovingAI adapter introduced in dev7 connects map-memory studies to the public
`Frame`, `ControllerSpec`, `checked_step`, checkpoint and replay interfaces.
Trusted importable plugins can use 32-bit cell indices; bundled MiniGrid policies
retain their 16-bit limit. The latest public release is dev10; this source tree is
a local dev11 successor candidate, not yet published.

Completed navigation results are saved before replay auditing. A replay mismatch
or replay process error preserves that result with `replay_audit.status="error"`
and raises `ReplayAuditError`; the study layer records `audit_error` and excludes
it from audited success curves. Genuine execution errors still preserve only the
available partial artifacts. Zero-decision tasks report no replay evidence.

In this candidate, `movingai-fetch` downloads and validates both archives in a
temporary sibling directory before publishing the final input directory. A network
or validation error leaves that final path available for retry. Existing output
directories are rejected and preserved. Use one writer for a destination; a hard
process termination can leave a temporary sibling directory for manual inspection.

These examples compare serialized persistent bytes, not total robot RAM.
Map symbols, destination, previous position, tick and tile replacement order
are charged. Temporary decoded arrays and A* workspace are outside this budget.
The conventional retention rules are examples, not new compression algorithms.

## Install, obtain inputs and select an original task

Install from this candidate source directory or its wheel:

```powershell
python -m pip install . --no-build-isolation
python -m statebudget_nav movingai-fetch --map-url https://www.movingai.com/benchmarks/street/Berlin_1_256.map.zip --scenario-url https://www.movingai.com/benchmarks/street/Berlin_1_256.map-scen.zip --output inputs/berlin
```

The output directory must be new. Exact URL, response and extracted-file hashes
and data attribution are saved. If the server is temporarily unavailable, retry
the same uncreated destination or use map/scenario files you already downloaded. Maps are
not bundled into or relicensed by the MIT software package.

Keep the original dimensions, start, goal and direction. A task can be selected
by original file line number, including the header as line1, or by a distance
quantile sorted by(published distance, original line). Quantile0.25/0.75 selects
the same rows as the registered pilot; it is not random sampling or the full
official suite. Verify an official task before the adapted comparison:

```powershell
python -m statebudget_nav movingai-verify --map inputs/berlin/Berlin_1_256.map --scenarios inputs/berlin/Berlin_1_256.map.scen --line 231
```

This runs independent Python Dijkstra using eight-neighbor edges, diagonal cost
sqrt(2) and no corner cutting, and checks the published distance within1e-5.
The adapted run separately computes its four-neighbor distance. Its result has
`official_distance_verified=false` because the separate verification output is
not silently inferred from a prior command; retain both records when reporting.

## Compare memory choices with the Python backend

```powershell
python -m statebudget_nav movingai --map inputs/berlin/Berlin_1_256.map --scenarios inputs/berlin/Berlin_1_256.map.scen --line 231 --policy lru --budget 1024 --output runs/berlin-lru
python -m statebudget_nav movingai --map inputs/berlin/Berlin_1_256.map --scenarios inputs/berlin/Berlin_1_256.map.scen --line 231 --policy walls --budget 1024 --output runs/berlin-walls
python -m statebudget_nav movingai-summary runs/berlin-lru runs/berlin-walls
python -m statebudget_nav audit runs/berlin-walls/trace.jsonl.gz --fresh-process --stride 10
```

Python is portable and requires no compiler. Larger grids can take longer;
the optional native backend accelerates the same deterministic A* search.
`face_route` is a conventional34-byte face-routing reference with a different
planning strategy, so it is not an isolated compression comparison.

Each run writes the original scenario row, physical-task fingerprint, source
snapshots, budget and actual peak bytes, full gzip checkpoints, complete result
and first/middle/last replay inputs. Those three checkpoints are replayed in new
interpreters before the result is finalized. The `audit` command can replay
additional/all decisions. This is deterministic replay, not a separate proof of
the world, sensor, movement and retention semantics; those were independently
audited in the pilot evidence. Partial directories from an interrupted run must
not be mistaken for complete results. The adapter snapshots its own relevant
source files; the matching wheel and dependencies are also needed for replay.

## Reuse with a separate controller package

The CLI also accepts `--policy python:importable.module:function` together with
`--initial-state path/to/state.bin`. The file is exactly the incoming bytes for
the first decision; its length counts toward the same cap. A plugin must not
expect the built-in map format. Its initializer must use only declared public
metadata (for example, dimensions, start and known destination), and retain all
decision-relevant values in those bytes. It must not encode the unobserved map
or task oracle into initialization or immutable constants.

The separate `navmemory-example` distribution is included under
`external_examples/navmemory_example`. Install it into the same environment with
`python -m pip install ./external_examples/navmemory_example --no-deps --no-build-isolation`
(or install the two release wheels), then run:

```powershell
python -m navmemory_example --map inputs/berlin/Berlin_1_256.map --scenarios inputs/berlin/Berlin_1_256.map.scen --line 231 --output initial.bin
python -m statebudget_nav movingai --map inputs/berlin/Berlin_1_256.map --scenarios inputs/berlin/Berlin_1_256.map.scen --line 231 --policy python:navmemory_example:step --initial-state initial.bin --budget 1024 --output runs/external
python -m statebudget_nav audit runs/external/trace.jsonl.gz --fresh-process --stride 17
```

The example uses ordered five-byte `(uint32 cell, uint8 kind)` records, a charged
five-byte destination header, FIFO removal and transient optimistic A*. It uses
only the public frame/specification API. Its source is a separate distribution;
it is an author-created reuse example, not a new algorithm or independent user
study. On the selected Berlin task it completes in 114 movements / 124 actions,
with a 1020-byte peak under a 1024-byte cap. This is an engineering check on one
chosen task, not comparative performance evidence.

The adapter saves `initial_state.bin`, its hash, the plugin identity and an entry
module snapshot before execution. It validates actual incoming/outgoing payloads
and uses the same sensor, movement, stopping conditions and replay path as the
built-ins. Non-numeric diagnostics are omitted from
numeric totals; checkpoints retain inputs and expected action/state digests. Initial-state overrides for built-in policies are rejected.

Plugins are trusted Python modules, not sandboxed. The entry-module snapshot
is not the complete dependency closure: archive the exact plugin wheel,
StateBudget-Nav wheel and dependencies as well. Replay requires those modules
to remain importable in the selected Python environment. A failed/interrupted
run may leave partial traces, but it never gains a completed `result.json`.

## Optional C++ backend

Install a C++17 compiler, then build outside the package directory:

```powershell
python -m statebudget_nav build-native native/fullmap_search.dll
$env:STATEBUDGET_NAV_NATIVE_LIBRARY=(Resolve-Path native/fullmap_search.dll).Path
python -m statebudget_nav movingai --map inputs/berlin/Berlin_1_256.map --scenarios inputs/berlin/Berlin_1_256.map.scen --quantile 0.25 --policy walls_native --budget 1024 --output runs/berlin-native
```

On Linux/macOS use an appropriate shared-library suffix and set the same
environment variable using your shell's syntax. Linux/macOS builds are provided
by the portable source but have not been exercised on those systems in this
release candidate. On Windows, the tested build uses MinGW-w64g++11.2 with
static runtime linking. Record the resulting library hash; the environment
variable points only to immutable backend code and supplies no episode memory.
Fresh replay needs the same library and environment variable. Python/native
policies share the codec, tie order, costs and pruning behavior. Build or backend
selection errors are reported explicitly; there is no silent backend fallback.
Generated binaries retain the compiler/runtime license conditions. The source
package contains C++ source, not vendored third-party runtime DLLs.

## Task and evidence conventions

The official MovingAI model provides known maps and eight-direction movement.
Our run is an **adapted four-direction, partial-observation comparison**, with
exact pose, known charged destination, initial east heading and7x7 square
observations through walls. It is not an official score, a SLAM experiment or
a physical robot deployment. Swamp/water are rejected because their traversal
semantics are outside these examples. Moving allowance is max(600,6D4) and the
action allowance is three times that value. No early cycle termination is used.

The original pilot evaluated13 complete maps and26 official endpoint pairs:
LRU1KiB22/26; obstacle-priority1KiB23/26; obstacle-priority4KiB24/26; ample
reference24/26. Its130 executions,574608 decisions and390 fresh replays belong
to frozen experimental sources. Package port parity is separately checked on
saved checkpoints; do not relabel it as a new130-run scientific evaluation.
For all26 tasks use the map identities and original rows in the supplied pilot
`INPUTS.json`. This walkthrough demonstrates one task end to end.

Cite N. R. Sturtevant(2012), Benchmarks for Grid-Based Pathfinding, IEEE TCIAIG
4(2),144-148. Source: https://www.movingai.com/benchmarks/grids.html .
Data terms and attribution remain separate from the software MIT license.
