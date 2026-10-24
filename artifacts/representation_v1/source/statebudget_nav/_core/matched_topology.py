"""Paired cycle interventions preserving area, anchors AND oracle path length.

No hidden graph statistics are passed to controllers. This is a development
generator, not evidence that all features other than cycle rank are identical.
"""
from collections import deque
from .environments import ControlledNavigation,DXY
from minigrid.core.world_object import Wall


def distances(free,start):
    result={start:0}
    q=deque([start])
    while q:
        x,y=q.popleft()
        for dx,dy in DXY:
            p=x+dx,y+dy
            if p in free and p not in result:
                result[p]=result[(x,y)]+1
                q.append(p)
    return result


class MatchedLoopNavigation(ControlledNavigation):
    def __init__(self,cycles=0,size=31,**kwargs):
        self.requested_cycles=cycles
        super().__init__(size=size,family='maze',**kwargs)

    def _gen_grid(self,width,height):
        super()._gen_grid(width,height)
        start,goal=tuple(self.agent_pos),tuple(self.goal_pos)
        free={(x,y) for x in range(width) for y in range(height)
              if self.grid.get(x,y) is None or self.grid.get(x,y).type=='goal'}
        original_area=len(free)
        original_distance=distances(free,start)[goal]
        for _ in range(self.requested_cycles):
            ds,dt=distances(free,start),distances(free,goal)
            current_leaves=sorted(p for p in free if p not in (start,goal)
                                  and sum((p[0]+dx,p[1]+dy) in free for dx,dy in DXY)==1)
            candidates=[]
            for x in range(1,width-1):
                for y in range(1,height-1):
                    if (x,y) in free:continue
                    ns=[(x+dx,y+dy) for dx,dy in DXY if (x+dx,y+dy) in free]
                    if len(ns)!=2:continue
                    a,b=ns
                    if a[0]!=b[0] and a[1]!=b[1]:continue
                    if min(ds[a]+2+dt[b],ds[b]+2+dt[a])<original_distance:continue
                    # Opening has two incident edges; one non-anchor leaf
                    # deletion restores area while adding exactly one cycle.
                    leaves=[p for p in current_leaves if p not in (a,b)]
                    if leaves:candidates.append(((x,y),leaves))
            if not candidates:raise ValueError(f'cannot preserve path for {self.requested_cycles} cycles')
            opening,leaves=candidates[int(self.np_random.integers(len(candidates)))]
            deletion=leaves[int(self.np_random.integers(len(leaves)))]
            free.add(opening);free.remove(deletion)
            self.grid.set(*opening,None);self.grid.set(*deletion,Wall())
        edges=sum((x+dx,y+dy) in free for x,y in free for dx,dy in ((1,0),(0,1)))
        assert len(free)==original_area
        assert edges-len(free)+1==self.requested_cycles
        ds=distances(free,start)
        assert len(ds)==len(free) and ds[goal]==original_distance
