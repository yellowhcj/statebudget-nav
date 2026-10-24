"""Classical cyclic rotor control with charged sparse pointer and scan state.

Finite cache means no general rotor-router coverage theorem is claimed.
Unlike port-count baselines this needs two pointer bits per cached location.
"""
from dataclasses import dataclass
from collections import OrderedDict
import struct
from .controller import NONE,pack,unpack,DXY

HEADER=struct.Struct('<HHIHBBH') # target/goal/rng/current scan cell/open+known/entry/n
POLICIES=('rotor_all','rotor_junction','rotor_fifo')


@dataclass(frozen=True)
class RotorConfig:
    width:int
    height:int
    budget:int
    policy:str
    selector:str='nearest'
    rng_seed:int=1
    reactive=True
    history=False

    def __post_init__(self):
        if self.policy not in POLICIES or self.capacity<1:raise ValueError('invalid rotor config')
    @property
    def n(self):return self.width*self.height
    @property
    def record_bits(self):return (self.n-1).bit_length()+2
    @property
    def capacity(self):return (self.budget-HEADER.size)*8//self.record_bits


def decode_rotor(state,cfg):
    if not state:return NONE,NONE,cfg.rng_seed,NONE,0,0,OrderedDict()
    if len(state)>cfg.budget:raise ValueError('oversized rotor state')
    target,goal,rng,scan,knowledge,entry,n=HEADER.unpack_from(state)
    records=OrderedDict((v>>2,v&3) for v in unpack(state[HEADER.size:],n,cfg.record_bits))
    return target,goal,rng,scan,knowledge,entry,records


def step_rotor(frame,state,cfg):
    target,goal,rng,scan,knowledge,entry,records=decode_rotor(state,cfg)
    rng=(1664525*rng+1013904223)&0xffffffff
    pos=frame.position;x,y=pos%cfg.width,pos//cfg.width
    ns=tuple((y+dy)*cfg.width+x+dx if 0<=x+dx<cfg.width and 0<=y+dy<cfg.height else -1 for dx,dy in DXY)
    visible=dict(frame.cells)
    if frame.goals:goal=min(frame.goals)
    if scan!=pos:
        scan=pos;knowledge=0;entry=frame.direction
        if target==pos:
            back=(frame.direction+2)%4
            knowledge=(1<<back)|(1<<(back+4))
        target=NONE
    opened,known=knowledge&15,knowledge>>4
    for d,p in enumerate(ns):
        if p<0 or p in visible:
            known|=1<<d
            if p>=0 and visible[p]==1:opened|=1<<d
            else:opened&=~(1<<d)
    if target not in ns or visible.get(target,0)>=2:target=NONE
    selected=False
    if target==NONE and known!=15:
        action=1
    else:
        candidates=[d for d in range(4) if opened&(1<<d)]
        if target==NONE and candidates:
            if cfg.policy=='rotor_junction' and len(candidates)<3:
                chosen=next(d for d in [(entry+t)%4 for t in (1,0,3,2)] if d in candidates)
            else:
                pointer=records.get(pos,0)
                chosen=next((pointer+t)%4 for t in range(4) if (pointer+t)%4 in candidates)
                records[pos]=(chosen+1)%4
                if cfg.policy!='rotor_fifo':records.move_to_end(pos)
            target=ns[chosen];selected=True
        if goal in ns and visible.get(goal)==1:target=goal
        if target==NONE:action=1
        else:
            direction=ns.index(target);delta=(direction-frame.direction)%4
            action=2 if delta==0 else 0 if delta==3 else 1
    if action==2 and dict(frame.doors).get(ns[frame.direction])==1:action=5
    while len(records)>cfg.capacity:records.popitem(last=False)
    payload=pack([(p<<2)|d for p,d in records.items()],cfg.record_bits)
    state=HEADER.pack(target,goal,rng,scan,(known<<4)|opened,entry,len(records))+payload
    assert len(state)<=cfg.budget
    return action,state,dict(target=target,selected=int(selected),fallback=0,expanded=0,observed=len(frame.cells))
