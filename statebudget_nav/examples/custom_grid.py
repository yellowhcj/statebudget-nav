"""Complete sensor-adapter example without MiniGrid's environment loop.

Usage: python -m statebudget_nav.examples.custom_grid runs/custom-grid
All outputs are created in a new directory. The evaluator owns the world;
the importable plugin receives only local observations and declared bytes.
"""
import hashlib
import json
from pathlib import Path
import sys

from statebudget_nav import ControllerSpec, Frame, checked_step, checkpoint
from statebudget_nav.audit import audit_trace


WORLD = (
    '#########',
    '#.......#',
    '#.#####.#',
    '#...#...#',
    '###.#.#.#',
    '#.....#G#',
    '#########',
)
DIRECTIONS = ((1, 0), (0, 1), (-1, 0), (0, -1))


def local_frame(world, position, direction):
    """Adapt a position and a radius-one cross sensor to the public frame."""
    width, height = len(world[0]), len(world)
    x, y = position % width, position // width
    cells, goals = [], []
    for dx, dy in ((0, 0), *DIRECTIONS):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            cell, symbol = ny * width + nx, world[ny][nx]
            cells.append((cell, 2 if symbol == '#' else 1))
            if symbol == 'G':
                goals.append(cell)
    return Frame(position, direction, tuple(cells), tuple(goals))


def run(directory, limit=1000, audit_stride=10):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    spec = ControllerSpec(9, 7, 4,
        'python:statebudget_nav.examples.local_walk:step', agent_seed=1)
    position, direction, state = 10, 0, b''
    max_bytes, success = 0, False
    trace = directory / 'trace.jsonl'
    with trace.open('x', encoding='utf-8') as stream:
        for index in range(limit):
            frame = local_frame(WORLD, position, direction)
            event = checkpoint(frame, state, spec)
            action, state, _ = checked_step(frame, state, spec)
            event['expected'] = dict(action=action,
                state_sha256=hashlib.sha256(state).hexdigest())
            stream.write(json.dumps(event, separators=(',', ':')) + '\n')
            max_bytes = max(max_bytes, len(state))
            if action in (0, 1):
                direction = (direction + (-1 if action == 0 else 1)) % 4
            elif action == 2:
                dx, dy = DIRECTIONS[direction]
                nx, ny = position % spec.width + dx, position // spec.width + dy
                if 0 <= nx < spec.width and 0 <= ny < spec.height and WORLD[ny][nx] != '#':
                    position = ny * spec.width + nx
            if WORLD[position // spec.width][position % spec.width] == 'G':
                success = True
                break
    result = dict(example='author-provided custom grid and plugin',
        environment='radius-one cross sensor, known pose, static grid',
        steps=index + 1, success=success, budget=spec.budget,
        max_state_bytes=max_bytes,
        world_sha256=hashlib.sha256('\n'.join(WORLD).encode()).hexdigest(),
        plugin_sha256=hashlib.sha256(Path(__file__).with_name('local_walk.py').read_bytes()).hexdigest(),
        trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
        audit=audit_trace(trace, fresh_process=True, stride=audit_stride))
    (directory / 'result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), indent=2))
