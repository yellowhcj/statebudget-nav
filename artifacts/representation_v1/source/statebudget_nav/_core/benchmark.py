"""Sensor adapter and evaluator. True-world information stays in this module."""
from collections import deque
import hashlib
import time

import gymnasium as gym
import minigrid  # register benchmarks

from .controller import Config, DXY, Frame, step, decode
from .environments import make


def sensor_frame(obs, position, direction, width, height):
    """Convert visible sensor pixels using supplied accurate localization."""
    image = obs['image']
    k = image.shape[0]
    ax, ay = map(int, position)
    fx, fy = DXY[direction]
    rx, ry = DXY[(direction + 1) % 4]
    cells, doors, goals = {}, [], []
    for row in range(k):
        for col in range(k):
            obj, _, state = map(int, image[row, col])
            if obj == 0:
                continue
            x = ax + fx * (k-1-col) + rx * (row-k//2)
            y = ay + fy * (k-1-col) + ry * (row-k//2)
            if not (0 <= x < width and 0 <= y < height):
                continue
            i = y * width + x
            if obj == 4:
                doors.append((i, state))
            if obj == 8:
                goals.append(i)
            # Static, unlocked doors are passable geometrically. Keys, boxes,
            # balls are not silently treated as empty; these tasks are excluded.
            cells[i] = 2 if obj in (2, 5, 6, 7) or (obj == 4 and state == 2) else 3 if obj == 9 else 1
    cells[ay * width + ax] = 1
    return Frame(ay * width + ax, int(direction), tuple(sorted(cells.items())),
                 tuple(sorted(goals)), tuple(sorted(doors)))


def world_stats(env):
    """Evaluation only; excludes unreachable exterior from reachable area."""
    e = env.unwrapped
    start = tuple(map(int, e.agent_pos))
    q, distance = deque([start]), {start: 0}
    goal_distance = None
    branches = 0
    while q:
        x, y = q.popleft()
        degree = 0
        for dx, dy in DXY:
            p = x + dx, y + dy
            if not (0 <= p[0] < e.width and 0 <= p[1] < e.height):
                continue
            obj = e.grid.get(*p)
            walkable = obj is None or obj.type in ('goal', 'floor') or (obj.type == 'door' and not obj.is_locked)
            if not walkable:
                continue
            degree += 1
            if obj is not None and obj.type == 'goal':
                goal_distance = min(goal_distance if goal_distance is not None else 10**9,
                                    distance[(x, y)] + 1)
            if p not in distance:
                distance[p] = distance[(x, y)] + 1
                q.append(p)
        branches += degree >= 3
    fingerprint = hashlib.sha256(e.grid.encode().tobytes() + bytes(start) + bytes([e.agent_dir])).hexdigest()
    canonical=e.grid.encode().copy();canonical[:,:,1]=0
    layout_hash=hashlib.sha256(canonical.tobytes()+bytes(start)+bytes([e.agent_dir])).hexdigest()
    return dict(world_hash=fingerprint,layout_hash=layout_hash,reachable_area=len(distance),oracle_cells=goal_distance,
                branch_cells=branches)


def run_episode(name, seed, budget, policy, limit=600, view=7, selector='nearest', agent_seed=1):
    env = make(name, view)
    e = env.unwrapped
    e.max_steps = limit
    obs, _ = env.reset(seed=seed)
    cfg = Config(e.width, e.height, budget, policy, selector=selector,rng_seed=agent_seed)
    info = world_stats(env)
    state = b''
    observed = set()  # evaluator only, never supplied to step()
    max_bytes, false_targets, choices, fallbacks, expanded = 0, 0, 0, 0, 0
    cpu_ns = 0
    first_goal = None
    loops_detected=0
    face_merges=0
    success = False
    forgotten_geometry_events, forgotten_history_events = 0, 0
    prev_memory, prev_history = set(), set()
    trajectories = hashlib.sha256()
    for t in range(limit):
        frame = sensor_frame(obs, e.agent_pos, e.agent_dir, e.width, e.height)
        observed.update(i for i, _ in frame.cells)
        if frame.goals and first_goal is None:
            first_goal = t
        begun = time.process_time_ns()
        action, new_state, diagnostic = step(frame, state, cfg)
        loops_detected+=diagnostic.get('loop_detected',0)
        face_merges+=diagnostic.get('face_merged',0)
        cpu_ns += time.process_time_ns() - begun
        choices += diagnostic['selected']
        false_targets += int(diagnostic['selected'] and diagnostic['target'] in observed)
        fallbacks += diagnostic['fallback']
        expanded += diagnostic['expanded']
        state = new_state
        max_bytes = max(max_bytes, len(state))
        _, _, _, stored, flags = decode(state, cfg)
        source_memory = prev_memory | {i for i, _ in frame.cells}
        source_history = prev_history | {i for i, _ in frame.cells}
        retained_history = {i for i, v in enumerate(flags) if v}
        forgotten_geometry_events += len(source_memory - set(stored))
        if cfg.history:
            forgotten_history_events += len(source_history - retained_history)
        prev_memory, prev_history = set(stored), retained_history
        trajectories.update(frame.position.to_bytes(2, 'little') + bytes([frame.direction, action]) + state)
        obs, reward, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            success = bool(terminated and reward > 0)
            break
    _, _, _, memory, hist = decode(state, cfg)
    env.close()
    return dict(env=name, seed=seed, agent_seed=agent_seed,policy=policy, budget=budget, steps=t+1,
                success=int(success), first_goal=first_goal, max_state_bytes=max_bytes,
                choices=choices, false_targets=false_targets if not cfg.reactive else None, fallbacks=fallbacks,
                distinct_observed=len(observed), final_geometry=len(memory) if not cfg.reactive else None,
                final_history=sum(hist) if cfg.history else None,
                forgotten_geometry_events=forgotten_geometry_events if not cfg.reactive else None,
                forgotten_history_events=forgotten_history_events,
                cpu_ms=cpu_ns/1e6, expanded=expanded, loops_detected=loops_detected,
                face_merges=face_merges,
                trajectory_hash=trajectories.hexdigest(), **info)
