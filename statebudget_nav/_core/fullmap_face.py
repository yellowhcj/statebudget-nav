"""Conventional full-face routing on the sensed planar free-grid graph."""
import struct

FORMAT = struct.Struct('<BB8I')
TAG = 41
NONE = 4294967295
# Cartesian counterclockwise directions; evaluator headings are E,S,W,N.
DELTAS = ((1, 0), (0, -1), (-1, 0), (0, 1))


def pack(mode, goal, origin, first, best, pending):
    return FORMAT.pack(TAG, mode, goal, origin, *first, *best, *pending)


def initial(goal, origin):
    return pack(0, goal, origin, (NONE, NONE), (NONE, NONE), (NONE, NONE))


def unpack(raw):
    if len(raw) != FORMAT.size:
        raise ValueError('Invalid face state size')
    tag, mode, goal, origin, fu, fv, bu, bv, eu, ev = FORMAT.unpack(raw)
    if tag != TAG or mode not in range(5):
        raise ValueError('Invalid face state header')
    return mode, goal, origin, (fu, fv), (bu, bv), (eu, ev)


def neighbour(q, direction, width, height):
    dx, dy = DELTAS[direction]
    x, y = q % width + dx, q // width + dy
    return y * width + x if 0 <= x < width and 0 <= y < height else None


def direction(u, v, width):
    ux, uy, vx, vy = u % width, u // width, v % width, v // width
    try:
        return DELTAS.index((vx - ux, vy - uy))
    except ValueError as exc:
        raise ValueError('Non-adjacent routing edge') from exc


def crossing(edge, origin, goal, width):
    """Proper segment intersection parameter as positive integer fraction, or None."""
    if edge[0] == NONE:
        return None
    k = 4 * width
    scale = k * k
    sx, sy = origin % width * scale + k, -(origin // width) * scale + 1
    dx = (goal % width - origin % width) * scale
    dy = (origin // width - goal // width) * scale
    u, v = edge
    ax, ay = u % width * scale, -(u // width) * scale
    bx, by = v % width * scale, -(v // width) * scale
    ex, ey = bx - ax, by - ay
    den = dx * ey - dy * ex
    if den == 0:
        return None
    numerator = (ax - sx) * ey - (ay - sy) * ex
    along = (ax - sx) * dy - (ay - sy) * dx
    if den < 0:
        den, numerator, along = -den, -numerator, -along
    return (numerator, den) if 0 < numerator < den and 0 < along < den else None


def greater(a, b):
    return a is not None and (b is None or a[0] * b[1] > b[0] * a[1])


def step(frame, raw, spec):
    if spec.width * spec.height > NONE or spec.budget < FORMAT.size:
        raise ValueError('Unsupported face routing domain/budget')
    mode, goal, origin, first, best, pending = unpack(raw)
    if max(goal, origin) >= spec.width * spec.height:
        raise ValueError('Invalid endpoint')
    q = frame.position
    cells = dict(frame.cells)
    free = {d: r for d in range(4)
            if (r := neighbour(q, d, spec.width, spec.height)) is not None and cells.get(r) == 1}
    stats = dict(face_completed=0, face_switched=0, routing_exhausted=0)
    if q == goal:
        return 0, raw, stats
    if mode == 4:
        stats['routing_exhausted'] = 1
        return 0, raw, stats
    if first[0] == NONE:
        if q != origin:
            raise ValueError('Initial frame/source mismatch')
        if not free:
            return 0, pack(4, goal, origin, first, best, pending), dict(stats, routing_exhausted=1)
        d = next(d for d in (0, 3, 2, 1) if d in free)
        first = pending = (q, free[d])
    elif q == pending[1]:
        # Process the completed edge once, after all turns and the actual forward move.
        if mode % 2 == 0:
            candidate = crossing(pending, origin, goal, spec.width)
            threshold = crossing(first, origin, goal, spec.width) if mode == 2 else None
            if greater(candidate, threshold) and greater(candidate, crossing(best, origin, goal, spec.width)):
                best = pending
        incoming = direction(pending[0], pending[1], spec.width)
        reverse = (incoming + 2) % 4
        outgoing = next((d for turn in range(1, 5) if (d := (reverse - turn) % 4) in free), None)
        if outgoing is None:
            raise ValueError('Previously traversed edge disappeared')
        following = (q, free[outgoing])
        if mode % 2 == 0 and following == first:
            stats['face_completed'] = 1
            if best[0] == NONE:
                mode = 4
            else:
                mode += 1
        if mode in (1, 3) and pending == best:
            pending = first = (pending[1], pending[0])
            best = (NONE, NONE)
            mode = 2
            stats['face_switched'] = 1
        elif mode != 4:
            pending = following
    elif q != pending[0]:
        raise ValueError('Frame is not at pending edge')
    outgoing_raw = pack(mode, goal, origin, first, best, pending)
    if mode == 4:
        stats['routing_exhausted'] = 1
        return 0, outgoing_raw, stats
    d = direction(*pending, spec.width)
    if pending[0] != q or free.get(d) != pending[1]:
        raise ValueError('Pending edge is not currently observed free')
    heading = (-d) % 4
    delta = (heading - frame.direction) % 4
    # Same E,S,W,N movement/turn convention as the fixed evaluator.
    action = 2 if delta == 0 else (1 if delta == 1 else 0)
    return action, outgoing_raw, stats
