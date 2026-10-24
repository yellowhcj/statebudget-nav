# Adding a controller

Implement an importable Python function with this signature:

```python
def step(frame, state, specification):
    counter = state[0] if state else 0
    action = counter % 2
    return action, bytes([(counter + 1) % 256]), {"counter": counter}
```

This counter is an interface example, not a useful navigation policy. A working example is included as `statebudget_nav.examples.counter:step`.

```text
python -m statebudget_nav run --env Controlled-maze-9 --policy python:statebudget_nav.examples.counter:step --budget 1 --limit 20 --trace runs/plugin.jsonl
python -m statebudget_nav audit runs/plugin.jsonl --fresh-process
```

Install your own plugin module in the same Python environment so that a fresh interpreter can import it. The toolkit does not accept uploaded code, fetch modules or install dependencies automatically. Frozen batch queues currently reject external plugins because the queue does not archive their complete implementation and dependencies.

`Frame` contains a flattened position, direction, currently visible `(cell, kind)` pairs, currently visible goals and door observations. Directions follow MiniGrid (east, south, west, north). Cell kinds are 1 for traversable, 2 for blocking and 3 for a static hazard. MiniGrid actions 0–6 are permitted by the boundary; the current bundled controllers use turns, forward movement and door toggle. Goals and door states must refer to currently visible cells. No full environment, map seed, hidden goal coordinate, elapsed step count or evolving random object is supplied.

`ControllerSpec` contains width, height, budget, controller name, selector and an independent initialization seed. The same random initialization must be used across a comparison plan rather than being selected from information about a hidden world. Public immutable configuration and code are outside the payload budget. Any learned or environment-specific immutable data would need a separately declared experimental contract; it cannot be silently added while retaining the current comparison interpretation.

The new state must be exactly `bytes` and fit the budget. Encode every decision-relevant value carried to a later call, including random generator state, scan progress, cache order, destination, counts and partial plans. Do not carry mutable module globals, object attributes, environment references, files, clocks or uncharged random generators across calls. Diagnostics are evaluator output and are never returned as controller input.

The boundary validates observations, actions, types and lengths. Checkpoints record the input observation, input bytes and specification. A restart audit compares the output action and complete returned-byte digest. These are complementary checks: a hidden dependency that is not exercised by the checked observations can pass replay. The included fault demonstration shows this limitation directly. Code review remains necessary, and even complete replay of one recorded episode does not prove behavior on all possible episodes.

The budget counts serialized payload between decisions. Transient decoding, planning workspace, object headers and interpreter memory are outside it. Profiling total process memory is a separate measurement. The intended comparison concerns information explicitly retained across decisions, under accurate localization and known grid dimensions.
