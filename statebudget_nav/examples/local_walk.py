"""Reviewed extension example: local motion with a four-byte PRNG state.

An interface demonstration, not a new or competitive navigation algorithm.
No environment, mutable globals, clock or uncharged random object is used.
"""


def step(frame, state, spec):
    if state and len(state) != 4:
        raise ValueError('local_walk expects empty initial state or four bytes')
    rng = int.from_bytes(state, 'little') if state else spec.agent_seed
    rng = (1664525 * rng + 1013904223) & 0xffffffff
    x, y = frame.position % spec.width, frame.position // spec.width
    dx, dy = ((1, 0), (0, 1), (-1, 0), (0, -1))[frame.direction]
    nx, ny = x + dx, y + dy
    front = ny * spec.width + nx
    safe = (0 <= nx < spec.width and 0 <= ny < spec.height
            and dict(frame.cells).get(front) == 1)
    # Use only a currently visible goal; retain no hidden goal coordinate.
    if safe and front in frame.goals:
        action = 2
    elif frame.goals:
        goal = frame.goals[0]
        gx, gy = goal % spec.width, goal // spec.width
        desired = (0 if gx > x else 2) if gx != x else (1 if gy > y else 3)
        action = 2 if desired == frame.direction and safe else (
            1 if (desired - frame.direction) % 4 == 1 else 0)
    else:
        choice = (rng >> 16) % 4
        action = 2 if safe and choice < 2 else choice % 2
    return action, rng.to_bytes(4, 'little'), {'payload_bytes': 4}
