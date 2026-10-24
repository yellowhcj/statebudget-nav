"""Pure controller: the returned byte string is its entire persistent state.

Transient observations, decoded maps and shortest-path workspace are not bounded.
Do not call this a bound on process RAM. Geometry: 0 unknown, 1 free, 2 blocked,
3 hazardous. In compressed hybrids, code 4 means seen but geometry forgotten.
"""
from collections import OrderedDict, deque
from dataclasses import dataclass, field
import struct
import zlib

NONE = 65535
HEADER = struct.Struct('<HHI')  # exploration target, discovered goal, PRNG
DXY = ((1, 0), (0, 1), (-1, 0), (0, -1))
POLICIES = ('lru', 'fifo', 'obstacle', 'history_lru', 'history_fifo',
            'compressed', 'compressed_history', 'compressed_joint', 'wall_follow', 'random_walk',
            'noisy_wall_4','noisy_wall_16')


@dataclass(frozen=True)
class Config:
    width: int
    height: int
    budget: int
    policy: str
    selector: str = 'nearest'
    rng_seed: int = 1
    neighbors: tuple = field(init=False, repr=False)

    def __post_init__(self):
        if self.policy not in POLICIES or not 0 < self.n < NONE:
            raise ValueError('unsupported policy or map size')
        if self.selector not in ('nearest','frontier','gain'):
            raise ValueError('unsupported exploration selector')
        if not 0<=self.rng_seed<=0xffffffff:
            raise ValueError('PRNG initialization must fit the charged state word')
        minimum = HEADER.size if self.reactive else HEADER.size + (self.history_bytes + 2 if self.sparse else
                                 (self.history_bytes if self.policy == 'compressed_history' else 0) + 18)
        if self.budget < minimum:
            raise ValueError(f'budget {self.budget} < minimum {minimum} for {self.policy}')
        neighbors = []
        for i in range(self.n):
            x, y = i % self.width, i // self.width
            neighbors.append(tuple((y + dy) * self.width + x + dx
                             if 0 <= x + dx < self.width and 0 <= y + dy < self.height
                             else -1 for dx, dy in DXY))
        object.__setattr__(self, 'neighbors', tuple(neighbors))

    @property
    def n(self):
        return self.width * self.height

    @property
    def reactive(self):
        return self.policy in ('wall_follow', 'random_walk','noisy_wall_4','noisy_wall_16')

    @property
    def sparse(self):
        return self.policy not in ('compressed', 'compressed_history', 'compressed_joint')

    @property
    def history(self):
        return self.policy.startswith('history_') or self.policy in ('compressed_history', 'compressed_joint')

    @property
    def history_bytes(self):
        return (self.n + 7) // 8 if self.history else 0

    @property
    def record_bits(self):
        return (self.n - 1).bit_length() + 2

    @property
    def capacity(self):
        return min(self.n, ((self.budget - HEADER.size - self.history_bytes - 2) * 8)
                   // self.record_bits)


@dataclass(frozen=True)
class Frame:
    position: int
    direction: int
    cells: tuple  # (global index, geometry kind), current observation only
    goals: tuple = ()
    doors: tuple = ()  # (global index, sensor state: 0 open, 1 closed, 2 locked)


def pack(values, bits):
    acc = sum(int(value) << (i * bits) for i, value in enumerate(values))
    return acc.to_bytes((len(values) * bits + 7) // 8, 'little')


def unpack(blob, count, bits):
    acc = int.from_bytes(blob, 'little')
    mask = (1 << bits) - 1
    return [(acc >> (i * bits)) & mask for i in range(count)]


def encode_dense(values, bits):
    raw = pack(values, bits)
    candidates = [b'\x00' + raw, b'\x01' + zlib.compress(raw, 6),
                  b'\x02' + zlib.compress(bytes(values), 6)]
    return min(candidates, key=lambda b: (len(b), b[0]))


def decode_dense(blob, count, bits):
    if blob[0] == 2:
        values = list(zlib.decompress(blob[1:]))
        if len(values) != count:
            raise ValueError('invalid dense length')
        return values
    if blob[0] not in (0, 1):
        raise ValueError('invalid codec')
    raw = blob[1:] if blob[0] == 0 else zlib.decompress(blob[1:])
    if len(raw) != (count * bits + 7) // 8:
        raise ValueError('invalid packed length')
    return unpack(raw, count, bits)


def decode(state, cfg):
    if not state:
        return NONE, NONE, cfg.rng_seed, OrderedDict(), [False] * cfg.n
    if len(state) > cfg.budget:
        raise ValueError('oversized input state')
    target, goal, rng = HEADER.unpack_from(state)
    if cfg.reactive:
        if len(state) != HEADER.size:
            raise ValueError('invalid reactive header length')
        return target, goal, rng, OrderedDict(), [False] * cfg.n
    payload = state[HEADER.size:]
    if cfg.sparse:
        hist = unpack(payload[:cfg.history_bytes], cfg.n, 1) if cfg.history else [False] * cfg.n
        count = struct.unpack_from('<H', payload, cfg.history_bytes)[0]
        records = unpack(payload[cfg.history_bytes + 2:], count, cfg.record_bits)
        memory = OrderedDict((r >> 2, r & 3) for r in records)
    else:
        if payload[0] == 3:
            hist = unpack(payload[1:1+cfg.history_bytes], cfg.n, 1)
            values = decode_dense(payload[1+cfg.history_bytes:], cfg.n, 2)
        elif cfg.history and payload[0] in (4,5,6):
            raw = bytes([payload[0]-4]) + payload[1:]
            values = [4 if v == 3 else v for v in decode_dense(raw, cfg.n, 2)]
            hist = [v != 0 for v in values]
        else:
            values = decode_dense(payload, cfg.n, 3 if cfg.history else 2)
            hist = [v != 0 for v in values] if cfg.history else [False] * cfg.n
        memory = OrderedDict((i, v) for i, v in enumerate(values) if 0 < v < 4)
    return target, goal, rng, memory, hist


def encode(target, goal, rng, memory, history, position, cfg):
    header = HEADER.pack(target, goal, rng)
    memory = OrderedDict(memory)
    if cfg.sparse:
        while len(memory) > cfg.capacity:
            if cfg.policy == 'obstacle':
                discard = next((i for i, kind in memory.items() if kind == 1), next(iter(memory)))
                del memory[discard]
            else:
                memory.popitem(last=False)
        hist = pack(history, 1) if cfg.history else b''
        payload = hist + struct.pack('<H', len(memory))
        payload += pack([(i << 2) | v for i, v in memory.items()], cfg.record_bits)
    else:
        values = [4 if flag else 0 for flag in history] if cfg.history else [0] * cfg.n
        for i, kind in memory.items():
            values[i] = kind
        bits = 3 if cfg.history else 2
        def encode_values():
            combined = encode_dense(values, bits)
            if not cfg.history:
                return combined
            split = b'\x03' + pack(history, 1) + encode_dense([v if v < 4 else 0 for v in values], 2)
            candidates = [combined, split]
            # If no remembered hazardous cells exist, there are only four
            # relevant labels. Use the spare 2-bit code for forgotten geometry.
            # The codec tag distinguishes it from genuine geometry kind 3.
            if 3 not in values:
                remapped = encode_dense([3 if v == 4 else v for v in values], 2)
                candidates.append(bytes([remapped[0]+4]) + remapped[1:])
            return min(candidates, key=len)
        payload = encode_values()
        if len(header) + len(payload) > cfg.budget:
            px, py = position % cfg.width, position // cfg.width
            farthest = sorted(memory, key=lambda i: (abs(i % cfg.width - px)
                              + abs(i // cfg.width - py), i), reverse=True)
            # Greedy batch deletion is a heuristic, not optimal compression.
            # Every returned state is nevertheless checked against actual bytes.
            remaining = len(farthest)
            while len(header) + len(payload) > cfg.budget and remaining:
                batch = max(1, remaining // 12)
                for i in farthest[len(farthest)-remaining:len(farthest)-remaining+batch]:
                    values[i] = 4 if cfg.history and history[i] else 0
                remaining -= batch
                payload = encode_values()
            if len(header) + len(payload) > cfg.budget:
                if cfg.policy != 'compressed_joint':
                    raise ValueError('exact history cannot fit budget with this codec')
                # Joint representation may forget remote history too. Its seen
                # flags are conservative (no false positives), not an exact set.
                lost = sorted((i for i, v in enumerate(values) if v == 4),
                              key=lambda i: (abs(i % cfg.width-px)+abs(i//cfg.width-py), i), reverse=True)
                for i in lost:
                    values[i] = 0
                    history[i] = False
                    payload = encode_values()
                    if len(header) + len(payload) <= cfg.budget:
                        break
    state = header + payload
    assert len(state) <= cfg.budget
    return state


def adjacent(i, cfg):
    return ((d, j) for d, j in enumerate(cfg.neighbors[i]) if j >= 0)


def paths(frame, geometry, cfg):
    """Unit-cost move/turn BFS; unknown is optimistic, obstacles impassable.

    Unlocked doors are traversable geometrically. Their toggle cost is handled
    at execution and counted in episode actions, not optimized by this routing
    metric. This is not an oracle for minimum actions including door operations.
    """
    start = frame.position * 4 + frame.direction
    costs, first = [-1] * (cfg.n * 4), [-1] * (cfg.n * 4)
    costs[start] = 0
    queue = deque([start])
    expanded = 0
    while queue:
        node = queue.popleft()
        cost = costs[node]
        expanded += 1
        pos, direction = divmod(node, 4)
        moves = [(pos * 4 + (direction - 1) % 4, 0),
                 (pos * 4 + (direction + 1) % 4, 1)]
        neighbor = cfg.neighbors[pos][direction]
        if neighbor >= 0 and geometry.get(neighbor, 0) < 2:
            moves.append((neighbor * 4 + direction, 2))
        for nxt, action in moves:
            if costs[nxt] < 0:
                costs[nxt] = cost + 1
                first[nxt] = action if node == start else first[node]
                queue.append(nxt)
    by_cell = {}
    for node, cost in enumerate(costs):
        if cost < 0:
            continue
        pos = node // 4
        if pos not in by_cell or cost < by_cell[pos][0]:
            by_cell[pos] = (cost, max(0, first[node]))
    return by_cell, expanded


def step(frame, state, cfg):
    if cfg.reactive:
        return reactive_step(frame, state, cfg)
    target, goal, rng, memory, history = decode(state, cfg)
    # The only pseudo-random state is in the charged header. Episode seed is absent.
    rng = (1664525 * rng + 1013904223) & 0xffffffff
    for i, kind in frame.cells:
        memory[i] = kind
        if cfg.policy in ('lru', 'history_lru'):
            memory.move_to_end(i)
        if cfg.history:
            history[i] = True
    if frame.goals:
        goal = min(frame.goals)
    # Plan with all current observations; cache truncation happens after deciding.
    geometry = dict(memory)
    reachable, expanded = paths(frame, geometry, cfg)
    if goal != NONE:
        target = goal
    elif target == frame.position or geometry.get(target, 0) >= 2 or target not in reachable:
        target = NONE
    selected = False
    fallback = False
    if target == NONE:
        frontiers = [i for i in reachable if geometry.get(i,0)==1
                     and i!=frame.position
                     and any(geometry.get(j,0)==0 and (not cfg.history or not history[j])
                             for _,j in adjacent(i,cfg))] if cfg.selector!='nearest' else []
        candidates = [i for i in reachable if i != frame.position
                      and geometry.get(i, 0) == 0 and (not cfg.history or not history[i])]
        if cfg.selector!='nearest' and frontiers:
            candidates=frontiers
        if not candidates:
            # Lost geometry can disconnect the known frontier; old cells remain
            # traversable, and if all true novelty is gone, recovery is permitted.
            candidates = [i for i in reachable if i != frame.position and geometry.get(i, 0) == 0]
            fallback = True
        if not candidates:
            candidates = [i for i in reachable if i != frame.position]
            fallback = True
        if candidates:
            def priority(i):
                score=reachable[i][0]
                if cfg.selector=='gain':
                    gain=sum(geometry.get(j,0)==0 and (not cfg.history or not history[j])
                             for _,j in adjacent(i,cfg))
                    score/=1+gain
                return score, ((i + 1) * 2654435761 ^ rng) & 0xffffffff, i
            target = min(candidates, key=priority)
            selected = True
    action = reachable.get(target, (0, rng % 2))[1]
    if action == 2:
        front = dict(adjacent(frame.position, cfg)).get(frame.direction)
        if dict(frame.doors).get(front) == 1:
            action = 5  # toggle, solely from the current observed door state
    new_state = encode(target, goal, rng, memory, history, frame.position, cfg)
    return action, new_state, dict(target=target, selected=int(selected), fallback=int(fallback),
                                   expanded=expanded, observed=len(frame.cells))


def reactive_step(frame, state, cfg):
    """Cheap classical controls: committed wall following and persistent random walk.

    A directly adjacent visible goal is prioritized. No global map is hidden in
    the baseline. A neighbor target commits a
    turn and following move, avoiding a spinning 'turn right every frame' bug.
    """
    target, goal, rng, _, _ = decode(state, cfg)
    rng = (1664525 * rng + 1013904223) & 0xffffffff
    visible = dict(frame.cells)
    if frame.goals:
        goal = min(frame.goals)
    neighbor_directions = {i:d for d,i in adjacent(frame.position, cfg)}
    if goal in neighbor_directions and visible.get(goal) == 1:
        target = goal
    action = None
    selected = False
    if action is None:
        if target == frame.position or target not in neighbor_directions or visible.get(target, 0) >= 2:
            target = NONE
        if target == NONE:
            directions = [(frame.direction + turn) % 4 for turn in (1,0,3,2)]
            candidates = [cfg.neighbors[frame.position][d] for d in directions
                          if cfg.neighbors[frame.position][d] >= 0
                          and visible.get(cfg.neighbors[frame.position][d],0) == 1]
            if candidates:
                # LCG low bits have short periods; never use rng % degree here.
                index=0
                if cfg.policy=='random_walk':index=(rng>>16)%len(candidates)
                elif cfg.policy.startswith('noisy_wall_'):
                    period=int(cfg.policy.rsplit('_',1)[1])
                    if (rng>>24)%period==0:index=(rng>>16)%len(candidates)
                target = candidates[index]
                selected = True
        if target != NONE:
            direction = neighbor_directions[target]
            delta = (direction - frame.direction) % 4
            action = 2 if delta == 0 else 0 if delta == 3 else 1
        else:
            action = 1
    if action == 2:
        front = cfg.neighbors[frame.position][frame.direction]
        if dict(frame.doors).get(front) == 1:
            action = 5
    state = HEADER.pack(target, goal, rng)
    assert len(state) <= cfg.budget
    return action, state, dict(target=target, selected=int(selected), fallback=0,
                               expanded=0, observed=len(frame.cells))
