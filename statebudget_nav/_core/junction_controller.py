"""Classical sparse port-marking baselines, not claimed as novel algorithms.

All decision state uses a serialized header and bounded ordered vertex records.
Each record stores a coordinate, four observed-open port bits and four two-bit
departure counts. Sensors are scanned by charged turn-count state if ports have
not yet been observed. Unknown blocked ports are not inferred from the true map.
"""
from collections import OrderedDict
from dataclasses import dataclass
import struct
from .controller import DXY,Frame,NONE,pack,unpack

HEADER=struct.Struct('<HHIBB') # move target, goal, PRNG, heading at entry, turns
POLICIES=('ports_all','ports_junction','ports_lru','ports_lfv','ports_random')


@dataclass(frozen=True)
class PortConfig:
    width:int
    height:int
    budget:int
    policy:str
    selector:str='nearest'
    rng_seed:int=1

    def __post_init__(self):
        if self.policy not in POLICIES or self.budget<HEADER.size+2 or self.n>=NONE or self.capacity<1:
            raise ValueError('unsupported port configuration')

    @property
    def n(self):return self.width*self.height
    @property
    def record_bits(self):return (self.n-1).bit_length()+16
    @property
    def capacity(self):return max(0,(self.budget-HEADER.size-2)*8//self.record_bits)


def decode_ports(state,cfg):
    if not state:return NONE,NONE,cfg.rng_seed,0,0,OrderedDict()
    if len(state)>cfg.budget:raise ValueError('oversized ports state')
    target,goal,rng,entry,turns=HEADER.unpack_from(state)
    count=struct.unpack_from('<H',state,HEADER.size)[0]
    raw=unpack(state[HEADER.size+2:],count,cfg.record_bits)
    records=OrderedDict((r>>16,r&65535) for r in raw)
    return target,goal,rng,entry,turns,records


def encode_ports(target,goal,rng,entry,turns,records,cfg):
    records=OrderedDict(records)
    while len(records)>cfg.capacity:
        if cfg.policy=='ports_lfv':
            # Keep frequently visited vertices, deterministic oldest on ties.
            victim=min(records,key=lambda p:sum((records[p]>>(8+2*d))&3 for d in range(4)))
            del records[victim]
        else:records.popitem(last=False)
    body=struct.pack('<H',len(records))+pack([(i<<16)|v for i,v in records.items()],cfg.record_bits)
    state=HEADER.pack(target,goal,rng,entry,turns)+body
    assert len(state)<=cfg.budget
    return state


def neighbors(pos,cfg):
    x,y=pos%cfg.width,pos//cfg.width
    return tuple((y+dy)*cfg.width+x+dx if 0<=x+dx<cfg.width and 0<=y+dy<cfg.height
                 else -1 for dx,dy in DXY)


def step_ports(frame,state,cfg):
    target,goal,rng,entry,turns,records=decode_ports(state,cfg)
    rng=(1664525*rng+1013904223)&0xffffffff
    if frame.goals:goal=min(frame.goals)
    pos=frame.position
    neigh=neighbors(pos,cfg)
    visible=dict(frame.cells)
    old=records.get(pos,0)
    open_mask=old&15
    known_mask=(old>>4)&15
    for d,i in enumerate(neigh):
        if i<0 or i in visible:
            known_mask|=1<<d
            if i>=0 and visible[i]==1:open_mask|=1<<d
            else:open_mask&=~(1<<d)
    selected=False
    scan=False
    if target==pos:
        target=NONE
        entry=frame.direction
        turns=0
        # A successful commanded move proves the immediately preceding cell
        # was traversable; the arrival direction is charged in the header.
        back=(frame.direction+2)%4
        known_mask|=1<<back
        open_mask|=1<<back
    if target!=NONE and target not in neigh:
        target=NONE
        turns=0
    if target!=NONE and visible.get(target,0)>=2:
        target=NONE
        turns=0
    # Recover the orientation at an unrecorded first visit; never read a trace.
    if not state:entry=frame.direction
    if target==NONE and known_mask!=15:
        action=1
        turns=min(4,turns+1)
        scan=True
    else:
        candidates=[d for d in range(4) if open_mask&(1<<d)]
        if goal in neigh and visible.get(goal)==1:
            target=goal
        if target==NONE and candidates:
            if cfg.policy=='ports_random':
                chosen=candidates[(rng>>16)%len(candidates)]
            else:
                # Choose least-used departure, break ties by right-hand order
                # relative to arrival. This is a classical port heuristic.
                priority=[(entry+t)%4 for t in (1,0,3,2)]
                chosen=min(candidates,key=lambda d:((old>>(8+2*d))&3,priority.index(d)))
            target=neigh[chosen]
            selected=True
        if target==NONE:action=1
        else:
            direction=neigh.index(target)
            delta=(direction-frame.direction)%4
            action=2 if delta==0 else 0 if delta==3 else 1
            if action==2:
                count=(old>>(8+2*direction))&3
                old=(old&~(3<<(8+2*direction)))|(min(3,count+1)<<(8+2*direction))
    # Serialize scan knowledge as well as counts. When junction-only, scanning
    # partial records are kept until classification; corridors then discarded.
    record=(old&0xff00)|(known_mask<<4)|open_mask
    if cfg.policy!='ports_junction' or known_mask!=15 or open_mask.bit_count()>=3:
        records[pos]=record
        if cfg.policy in ('ports_lru','ports_junction'):records.move_to_end(pos)
    else:records.pop(pos,None)
    if action==2 and dict(frame.doors).get(neigh[frame.direction])==1:action=5
    state=encode_ports(target,goal,rng,entry,turns,records,cfg)
    return action,state,dict(target=target,selected=int(selected),fallback=0,expanded=0,
                              observed=len(frame.cells),scan=int(scan))
