"""Sensor-only diagnostic candidate using verified permutation splices.

All persistent detector, scan, mode, reservoir and permutation bytes are charged.
Classical cycle-splicing identity is not claimed as a new mathematical result.
"""
from collections import OrderedDict
from dataclasses import dataclass
import struct
from .controller import NONE,DXY,pack,unpack

FIELDS=('target','goal','rng','scan','knowledge','entry','phase','anchor','power','length',
        'period','remaining','sample_a','sample_b','sample_table','seen_b','samples','n')
HEADER=struct.Struct('<HHIHBBBHHHHHHHBBHH')
POLICIES=('face_merge','face_fifo','face_fast','face_junction')


@dataclass(frozen=True)
class FaceConfig:
    width:int
    height:int
    budget:int
    policy:str
    selector:str='nearest'
    rng_seed:int=1
    reactive=True
    history=False
    @property
    def n(self):return self.width*self.height
    @property
    def record_bits(self):return (self.n-1).bit_length()+8
    @property
    def capacity(self):return (self.budget-HEADER.size)*8//self.record_bits
    def __post_init__(self):
        if self.policy not in POLICIES or self.capacity<1 or self.n*4>=NONE:raise ValueError('invalid face config')


def decode_face(state,cfg):
    if not state:
        s=dict.fromkeys(FIELDS,0)
        for k in ['target','goal','scan','anchor','sample_a','sample_b']:s[k]=NONE
        s['rng']=cfg.rng_seed;s['power']=1
        return s,OrderedDict()
    if len(state)>cfg.budget:raise ValueError('oversized face state')
    s=dict(zip(FIELDS,HEADER.unpack_from(state)))
    records=OrderedDict((v>>8,v&255) for v in unpack(state[HEADER.size:],s['n'],cfg.record_bits))
    return s,records


def encode_face(s,records,cfg):
    s['n']=len(records)
    state=HEADER.pack(*(s[k] for k in FIELDS))+pack([(p<<8)|v for p,v in records.items()],cfg.record_bits)
    assert len(state)<=cfg.budget
    return state


def reset_detector(s):
    s.update(phase=0,anchor=NONE,power=1,length=0,period=0,remaining=0,
             sample_a=NONE,sample_b=NONE,samples=0,seen_b=0)


def local_table(opened):
    table=0
    if not opened:return table
    for entry in range(4):
        direction=next((entry+t)%4 for t in (1,0,3,2) if opened&(1<<((entry+t)%4)))
        table|=direction<<(2*entry)
    return table


def decision(s,records,pos,opened,cfg):
    """Called once per vertex arrival, after observing every local port."""
    entry=s['entry'];pose=pos*4+entry
    table=records.get(pos,local_table(opened))
    merged=False
    fast=cfg.policy in ('face_fast','face_junction')
    def sample_alternative():
        if cfg.policy=='face_junction' and opened.bit_count()<3:return
        for other in [e for e in range(4) if e!=entry and opened&(1<<((e+2)%4))]:
            s['samples']=min(65535,s['samples']+1)
            s['rng']=(1664525*s['rng']+1013904223)&0xffffffff
            if (s['rng']>>16)%s['samples']==0:
                s.update(sample_a=pose,sample_b=pos*4+other,sample_table=table)
    if s['phase']==0:
        detected=False
        if s['anchor']==NONE:s.update(anchor=pose,power=1,length=0,samples=0,sample_a=NONE)
        else:
            s['length']+=1
            if pose==s['anchor']:
                detected=True
                if fast:
                    if s['sample_a']==NONE:reset_detector(s)
                    else:s.update(phase=2,period=s['length'],remaining=s['length'],seen_b=0)
                else:s.update(phase=1,period=s['length'],remaining=s['length'],samples=0,sample_a=NONE)
            elif s['length']>=s['power']:
                s.update(anchor=pose,power=min(32768,s['power']*2),length=0,samples=0,sample_a=NONE)
        if fast and not detected:sample_alternative()
    elif s['phase']==1:
        sample_alternative()
        s['remaining']-=1
        if s['remaining']==0:
            if s['sample_a']==NONE:reset_detector(s)
            else:s.update(phase=2,remaining=s['period'],seen_b=0)
    else:
        s['seen_b']|=int(pose==s['sample_b'])
        s['remaining']-=1
        if s['remaining']==0:
            if not s['seen_b']:
                p,a=divmod(s['sample_a'],4);_,b=divmod(s['sample_b'],4)
                if p in records or len(records)<cfg.capacity or cfg.policy=='face_fifo':
                    v=s['sample_table'];da=(v>>(a*2))&3;db=(v>>(b*2))&3
                    v=(v&~((3<<(a*2))|(3<<(b*2))))|(db<<(a*2))|(da<<(b*2))
                    if p not in records and len(records)>=cfg.capacity:records.popitem(last=False)
                    records[p]=v;merged=True
                    if p==pos:table=v
            reset_detector(s)
    return (table>>(2*entry))&3,merged


def step_face(frame,state,cfg):
    s,records=decode_face(state,cfg)
    pos=frame.position;x,y=pos%cfg.width,pos//cfg.width
    ns=tuple((y+dy)*cfg.width+x+dx if 0<=x+dx<cfg.width and 0<=y+dy<cfg.height else -1 for dx,dy in DXY)
    visible=dict(frame.cells)
    if frame.goals:s['goal']=min(frame.goals)
    if s['scan']!=pos:
        arrived=s['target']==pos
        s.update(scan=pos,knowledge=0,entry=frame.direction,target=NONE)
        if arrived:
            back=(frame.direction+2)%4;s['knowledge']=(1<<back)|(1<<(back+4))
    opened,known=s['knowledge']&15,s['knowledge']>>4
    for d,p in enumerate(ns):
        if p<0 or p in visible:
            known|=1<<d
            if p>=0 and visible[p]==1:opened|=1<<d
            else:opened&=~(1<<d)
    s['knowledge']=(known<<4)|opened
    if s['target'] not in ns or visible.get(s['target'],0)>=2:s['target']=NONE
    merged=False;selected=False
    if s['target']==NONE and known!=15:action=1
    else:
        if s['target']==NONE and opened:
            direction,merged=decision(s,records,pos,opened,cfg)
            s['target']=ns[direction];selected=True
        if s['goal'] in ns and visible.get(s['goal'])==1:s['target']=s['goal']
        if s['target']==NONE:action=1
        else:
            delta=(ns.index(s['target'])-frame.direction)%4
            action=2 if delta==0 else 0 if delta==3 else 1
    if action==2 and dict(frame.doors).get(ns[frame.direction])==1:
        action=5;reset_detector(s)
    state=encode_face(s,records,cfg)
    return action,state,dict(target=s['target'],selected=int(selected),fallback=0,expanded=0,
                              observed=len(frame.cells),face_merged=int(merged))
