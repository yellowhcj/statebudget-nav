# StateBudget-Nav

A Python toolkit for comparing symbolic navigation controllers under a serialized persistent-state payload budget. This repository candidate is a local development snapshot; its public URL and software license have not yet been set.

## Quick start

Requires Python 3.10 or later. From a fresh clone, install the project and its declared dependencies, then run the small integration suite and a real navigation episode:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]" --no-build-isolation
python -m pytest tests -q
python -m statebudget_nav run --env MiniGrid-FourRooms-v0 --policy compressed --budget 64 --trace runs/trace.jsonl --output runs/result.json
python -m statebudget_nav audit runs/trace.jsonl --fresh-process --stride 10
```

The `runs` directory must not already exist. On macOS or Linux, activate the environment with `source .venv/bin/activate`. The audit checks recorded decisions in a fresh interpreter; it does not prove that all possible hidden state is absent.

For a faster install check without setting up a virtual environment, run `python -m pip install -e ".[test]" --no-build-isolation` in an environment where the declared dependencies and a build backend are already available. Network access is needed if pip must download missing dependencies; the `--no-build-isolation` option avoids a separate build-tool download when those tools are already installed.

The controller sees only current visible cells, accurate position/orientation, and immutable public configuration. Its entire declared cross-step state is a `bytes` value. Goals, PRNG state, scan modes, cache order, counters and representation metadata must fit the same budget. Transient planning workspace, Python object overhead, immutable configuration and interpreter memory are outside this budget. **It is not a process-RAM limit or hostile-code sandbox.**

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

The clean-wheel report records the actual dependency versions and build hash. Only that environment has been exercised; declared minimum versions are dependency constraints, not a cross-platform test matrix.

POPGym already compares memory models with equal recurrent-state dimensions; Memory Gym already supplies memory-focused decision tasks. This toolkit is scoped to byte-accounted symbolic navigation and audit artifacts. It does not claim to be the first memory benchmark, to reproduce those libraries, or to beat their learned policies.
