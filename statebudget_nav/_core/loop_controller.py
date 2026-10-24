"""Development candidate: Brent detection and sparse wall-rule exceptions.

Brent cycle detection and wall following are classical. No novelty claim.
All detector, reservoir and cache state is serialized.
Only static accurately localized observations are assumed.
"""
from collections import OrderedDict
from dataclasses import dataclass,field
import struct
from .controller import Config,HEADER as BASE_HEADER,NONE,pack,unpack,reactive_step

# base header; anchor pose/target; power/length; sampled pose/count; dir; count
HEADER=struct.Struct('<HHIHHHHHHBH')
POLICIES=('loop_exceptions','loop_reset','periodic_escape',
          'loop_burst_16','loop_burst_64','loop_burst_adaptive')


@dataclass(frozen=True)
class LoopConfig:
    width:int
    height:int
    budget:int
    policy:str
    selector:str='nearest'
    rng_seed:int=1
    base:Config=field(init=False,repr=False)
    walk:Config=field(init=False,repr=False)
    history=False
    reactive=True

    def __post_init__(self):
        if self.policy not in POLICIES or self.budget<HEADER.size or self.n*4>=NONE:
            raise ValueError('unsupported cycle-control configuration')
        if self.policy=='loop_exceptions' and self.capacity<1:
            raise ValueError('exception control needs at least one record')
        object.__setattr__(self,'base',Config(self.width,self.height,8,'wall_follow'))
        object.__setattr__(self,'walk',Config(self.width,self.height,8,'random_walk'))

    @property
    def n(self):return self.width*self.height
    @property
    def record_bits(self):return (4*self.n-1).bit_length()+2
    @property
    def capacity(self):return (self.budget-HEADER.size)*8//self.record_bits


def decode_loop(state,cfg):
    if not state:
        return NONE,NONE,cfg.rng_seed,NONE,NONE,1,0,NONE,0,0,OrderedDict()
    if len(state)>cfg.budget:raise ValueError('oversized loop state')
    target,goal,rng,anchor,anchor_target,power,length,sample,count,direction,n=HEADER.unpack_from(state)
    records=OrderedDict((v>>2,v&3) for v in unpack(state[HEADER.size:],n,cfg.record_bits))
    return target,goal,rng,anchor,anchor_target,power,length,sample,count,direction,records


def encode_loop(values,records,cfg):
    records=OrderedDict(records)
    while len(records)>cfg.capacity:records.popitem(last=False)
    state=HEADER.pack(*values,len(records))+pack([(p<<2)|d for p,d in records.items()],cfg.record_bits)
    assert len(state)<=cfg.budget
    return state


def step_loop(frame,state,cfg):
    target,goal,rng,anchor,anchor_target,power,length,sample,count,direction,records=decode_loop(state,cfg)
    visible=dict(frame.cells)
    neighbors=cfg.base.neighbors[frame.position]
    if target==frame.position or target not in neighbors or visible.get(target,0)>=2:target=NONE
    is_choice=target==NONE
    if cfg.policy.startswith('loop_burst_') and count>0:
        action,base,diagnostic=reactive_step(frame,BASE_HEADER.pack(target,goal,rng),cfg.walk)
        target,goal,rng=BASE_HEADER.unpack(base)
        count-=1
        if count==0:
            anchor=NONE;length=0;sample=NONE
        state=encode_loop((target,goal,rng,anchor,anchor_target,power,length,sample,count,direction),records,cfg)
        diagnostic['loop_detected']=0
        return action,state,diagnostic
    pose=frame.position*4+frame.direction
    detected=False
    if cfg.policy=='periodic_escape':
        length=min(65535,length+1)
        detected=length>=64
    else:
        if anchor==NONE:
            anchor,anchor_target=pose,target
            power,length=1,0
            sample,count=NONE,0
        else:
            length+=1
            detected=(pose,target)==(anchor,anchor_target)
            if not detected and length>=power:
                anchor,anchor_target=pose,target
                power=min(32768,power*2);length=0
                sample,count=NONE,0
    directions=[(frame.direction+t)%4 for t in (1,0,3,2)]
    candidates=[d for d in directions if neighbors[d]>=0 and visible.get(neighbors[d])==1]
    next_rng=(1664525*rng+1013904223)&0xffffffff
    if target==NONE and candidates:
        default=records.get(pose,candidates[0])
        if default not in candidates:default=candidates[0]
        alternatives=[d for d in candidates if d!=default]
        if cfg.policy=='loop_exceptions' and pose in records:
            target=neighbors[default]
        if alternatives and cfg.policy=='loop_exceptions':
            count=min(65535,count+1)
            if (next_rng>>16)%count==0:
                sample=pose;direction=alternatives[(((next_rng*2246822519)&0xffffffff)>>16)%len(alternatives)]
        if detected and cfg.policy in ('loop_reset','periodic_escape') and alternatives:
            target=neighbors[alternatives[(next_rng>>16)%len(alternatives)]]
            anchor=NONE;length=0;sample=NONE;count=0
    if detected and cfg.policy=='loop_exceptions' and sample!=NONE:
        records[sample]=direction;records.move_to_end(sample)
        # Already at the sampled decision? Apply immediately.
        if sample==pose and is_choice and direction in candidates:
            target=neighbors[direction]
        # A full cache can evict an earlier exception and change the route.
        # Keep detecting even if the new exception is never encountered.
        anchor=NONE;length=0;sample=NONE;count=0
    if detected and cfg.policy.startswith('loop_burst_'):
        count=min(256,max(16,length*2)) if cfg.policy=='loop_burst_adaptive' else int(cfg.policy.rsplit('_',1)[1])
        target=NONE
        anchor=NONE;length=0;sample=NONE
    # The local reset ablation can interrupt a committed turn.
    if detected and cfg.policy=='loop_reset' and target!=NONE:
        target=NONE
        if len(candidates)>1:
            target=neighbors[candidates[1+(next_rng>>16)%(len(candidates)-1)]]
        anchor=NONE;length=0;sample=NONE;count=0
    mode=cfg.walk if cfg.policy.startswith('loop_burst_') and count>0 else cfg.base
    action,base,diagnostic=reactive_step(frame,BASE_HEADER.pack(target,goal,rng),mode)
    if mode is cfg.walk:count-=1
    target,goal,rng=BASE_HEADER.unpack(base)
    if action==5:
        # Opening a door changes the transition function. The identical pose
        # immediately before and after a toggle is not a static-state cycle.
        anchor=NONE;length=0;sample=NONE;count=0
    state=encode_loop((target,goal,rng,anchor,anchor_target,power,length,sample,count,direction),records,cfg)
    diagnostic['loop_detected']=int(detected)
    return action,state,diagnostic
