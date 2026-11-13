# StateBudget-Nav

[![MIT license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Version 0.1.0.dev13](https://img.shields.io/badge/version-0.1.0.dev13-blue.svg)
[![Tests](https://github.com/yellowhcj/statebudget-nav/actions/workflows/tests.yml/badge.svg)](https://github.com/yellowhcj/statebudget-nav/actions/workflows/tests.yml)

Version **0.1.0.dev13** separates MovingAI physical-task identity from sensor context, so changing the view does not create another physical map/endpoint task. Pairing still requires matching sensor/stopping contexts. It retains the completed-outcome audit handling and canonical source bytes introduced in dev12.
Start with [STUDIES.md](STUDIES.md) for configurable plans and paired trace diagnosis.
See [RESEARCH_WORKFLOW.md](RESEARCH_WORKFLOW.md) for a complete comparison,
budget-sensitivity study and the division between user code and toolkit checks.
It validates controller configuration before creating an episode trace and stages
MovingAI downloads before publishing their destination. Existing outputs remain protected.

Version **0.1.0.dev7** added complete MovingAI maps, original scenario endpoints,
and external map-memory controllers through the same byte-accounting and replay
interface. See [MOVINGAI.md](MOVINGAI.md) for download, Python/native runs and
checkpoint replay. These use an adapted four-direction/local-observation model.

For the complete installation-to-output workflow and a custom sensor/controller extension, start with [WALKTHROUGH.md](WALKTHROUGH.md). This is research software for auditing declared serialized persistent state. The accompanying manuscript is a draft; publication and research-adoption status are recorded separately from installation checks.

A Python toolkit for comparing symbolic navigation controllers under a serialized persistent-state payload budget. The public repository is [github.com/yellowhcj/statebudget-nav](https://github.com/yellowhcj/statebudget-nav) and the package is released under the [MIT License](LICENSE).

## Quick start

Prerequisites: Git (for a clone), Python 3.10 or later with `venv` and pip, and
network access to GitHub and the Python package index or a suitable public mirror.
Check `git --version`, `python --version` and `python -m pip --version` first.
If the system Python is older, select a newer interpreter before creating the
environment, for example `python3.12 -m venv .venv` on Linux. An existing Conda
environment with Python >=3.10 is another option; upgrading system Python is unnecessary.
From a fresh clone, install the project and its declared dependencies, then run the small integration suite and a real navigation episode:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[test]" --no-build-isolation
python -m pip install -e external_examples/navmemory_example --no-build-isolation --no-deps
python -m pytest tests -q
python -m statebudget_nav run --env MiniGrid-FourRooms-v0 --policy compressed --budget 64 --trace runs/trace.jsonl --output runs/result.json
python -m statebudget_nav audit runs/trace.jsonl --fresh-process --stride 10
```

Trace and result file paths must be new; their parent `runs` directory may already
exist. On macOS or Linux, activate the environment with `source .venv/bin/activate`.
The audit checks recorded decisions in a fresh interpreter; it does not prove that
all possible hidden state is absent.

For a faster install check without setting up a virtual environment, run `python -m pip install -e ".[test]" --no-build-isolation` in an environment where the declared dependencies and a build backend are already available. Network access is needed if pip must download missing dependencies; the `--no-build-isolation` option avoids a separate build-tool download when those tools are already installed.

The controller sees only current visible cells, accurate position/orientation, and immutable public configuration. Its entire declared cross-step state is a `bytes` value. Goals, PRNG state, scan modes, cache order, counters and representation metadata must fit the same budget. Transient planning workspace, Python object overhead, immutable configuration and interpreter memory are outside this budget. **It is not a process-RAM limit or hostile-code sandbox.**

Bundled controllers also have a structural minimum budget. For example, on the
19-by-19 FourRooms map, `compressed` requires at least 26 bytes; `lru` requires
10, and `wall_follow` requires 8. History-based policies can have a larger,
dimension-dependent floor. `run` checks the bundled configuration before opening
the trace. A valid budget permits execution; it does not guarantee navigation success.
Plugin-specific validation can still fail when the plugin is called.

**Budget is part of the controller configuration.** Increasing it can change
retention choices and the resulting trajectory, so success and action count need
not improve monotonically. Compare a declared budget range. A first successful
budget, or a successful suffix within that range, is an observed outcome rather
than a guarantee outside the tested range. Keep the task, controller, action limit
and other settings fixed when comparing budgets.

The tool compares sparse/compact/compressed geometry, geometry/history representations, wall following, random walks, port heuristics, cyclic rotors and experimental cycle interventions. The latter are research candidates, not validated new algorithms. MiniGrid supplies its real occluded sensor. Matched controlled maps additionally keep reachable area, start/goal, heading and shortest-path distance equal while changing graph cycle rank; other shape features may still vary.

With dependencies already installed, from this directory:

```text
python -m statebudget_nav run --env MiniGrid-FourRooms-v0 --policy compressed --budget 64 --trace runs/trace.jsonl --output runs/result.json
python -m statebudget_nav audit runs/trace.jsonl --fresh-process --stride 10
```

Trace and result paths must be new. Audit records contain local observations, charged states and public specifications, never the environment object or environment seed as policy input. The evaluator separately records the seed and world fingerprints for pairing. Fresh-interpreter replay checks output actions and complete returned states; passing sampled checks cannot prove absence of all possible hidden state. Code review remains required.

The `_core/provenance.json` manifest links each frozen implementation to its audited research source and SHA256. Do not silently edit the copied core; create a new snapshot and version for changes. The current package is extracted from a larger development study with immutable per-run source snapshots, paired-data audits and held-out seed restrictions; this CLI itself is a general evaluation tool and does not make arbitrary user-supplied seeds part of that preregistered study.

For a reproducible development example comparing three representations on the same 32 MultiRoom instances:

```text
python -m statebudget_nav.examples.representation_study runs/representation
python -m statebudget_nav verify runs/representation
python -m statebudget_nav summary runs/representation
```

This runs 96 episodes with reused development seeds. Every job imports an archived copy of this package in a separate interpreter. The source and result digests are checked before resuming. The example is a reproduction exercise, not a new held-out evaluation.

For your own queue, save a JSON list such as:

```json
[
  {"env":"MiniGrid-DistShift1-v0", "seed":10000, "policy":"wall_follow", "budget":8, "limit":600},
  {"env":"MiniGrid-DistShift1-v0", "seed":10001, "policy":"wall_follow", "budget":8, "limit":600}
]
```

```text
python -m statebudget_nav batch runs/custom --jobs jobs.json --max-jobs 1
python -m statebudget_nav batch runs/custom
python -m statebudget_nav summary runs/custom
```

The second command resumes pending work and preserves completed records. Runtime-version or archived-source drift prevents silent continuation. Failed attempts are retained separately and retried on the next invocation. There is one writer per queue; do not launch two runners on the same directory. A crash may leave a `writer.lock`, which should be inspected before explicitly removing it. Queue workers currently support bundled controllers; external plugins require separate provenance handling and are rejected for frozen batches.

Summaries average independent agent random repeats inside each seeded instance, then give duplicate physical layouts one weight per condition. Environment name, observation width, action limit, selector and payload size remain distinct. The layout identity ignores colors only for the supported static goal-navigation tasks where those colors are irrelevant. Summaries are descriptive and report partial queues explicitly; they do not create statistical significance claims.

To see exactly what checkpoint replay can detect:

```text
python -m statebudget_nav.examples.audit_faults runs/faults
```

The example intentionally injects hidden global counters that alter actions or returned bytes. Replaying all checkpoints detects these violations; checking only the first checkpoint misses them. It also demonstrates immediate rejection of excess payload and invalid actions, and successful replay of an explicitly serialized counter.

New trusted controllers can use `python:importable.module:function` in single-episode runs and checkpoint audits. The callable receives `(frame, state_bytes, specification)` and returns `(action, new_state_bytes, diagnostics)`. See [EXTENDING.md](EXTENDING.md). This loads local Python code with normal process permissions and is intended for reviewed research implementations.

See [REUSE_TEST.md](REUSE_TEST.md) for a protocol to test installation and use from a clean checkout. A successful AI-agent run is an agent-based usability check; it is not evidence of human adoption or independent scientific validation.

Local validation:

```text
python -m pytest tests -q
python -m pip wheel . --no-index --no-deps --no-build-isolation --wheel-dir dist
```

The separate [sparse-map example](external_examples/navmemory_example) is an
optional distribution; install it as above to exercise the complete integration suite.
Test counts and exact environments are recorded in the validation receipt for each version.
The new study integration test also requires this plugin. The CI workflow installs both packages
on Ubuntu and Windows with Python 3.10 and 3.12. The live badge reports its actual
status; configuring a matrix does not by itself establish successful runs.
Local validation reports retain exact dependency versions and build hashes.

## Citation and release notes

Citation metadata is in [CITATION.cff](CITATION.cff), and version changes are recorded in [CHANGELOG.md](CHANGELOG.md). The MIT license permits reuse with the copyright and license notice preserved. The copyright holder is Chongjun Huang.

Navigation-memory evaluation and diagnostics are established in POPGym, Memory Gym,
Memory Maze, MultiON, Habitat and POPGym Arcade. RLlib, Sacred and ReproZip already
provide state restoration or experiment records. This toolkit implements a specific
declared-byte and decision-audit workflow for trusted symbolic controllers. See
[RELATED_WORK.md](RELATED_WORK.md) for the overlap and the reusable integration.

## Software archive

Software version **0.1.0.dev13** has a [versioned release page](https://github.com/yellowhcj/statebudget-nav/releases/tag/v0.1.0-dev13)
with tagged source, matching tool/example wheels and SHA256 hashes. The release
preserves completed MovingAI outcomes separately from replay-audit status.
No Zenodo DOI has been assigned; add a real version DOI only after an archive
record is published. See [ARCHIVING.md](ARCHIVING.md).
Historical examples retain their original source snapshots and matching software
in separate scientific archives; dev13 does not regenerate those historical results.
