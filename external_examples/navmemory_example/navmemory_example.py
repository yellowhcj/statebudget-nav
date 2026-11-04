"""Conventional sparse map, FIFO retention and optimistic A*; public API only.

The goal and every stored cell occupy returned bytes. Temporary dicts/search
are outside the persistent-state cap. No world, oracle, tick or hidden history.
"""
import argparse,heapq,struct
from pathlib import Path
HEADER=struct.Struct('<BI');RECORD=struct.Struct('<IB');TAG=83
DXY=((1,0),(0,1),(-1,0),(0,-1))

def initial(goal):
    if type(goal) is not int or not 0<=goal<0xffffffff:raise ValueError('invalid goal')
    return HEADER.pack(TAG,goal)

def decode(state,width,height):
    if len(state)<HEADER.size or (len(state)-HEADER.size)%RECORD.size:raise ValueError('invalid sparse payload length')
    tag,goal=HEADER.unpack_from(state)
    if tag!=TAG or goal>=width*height:raise ValueError('invalid sparse header')
    known={}
    for p,kind in RECORD.iter_unpack(state[HEADER.size:]):
        if p>=width*height or kind not in (1,2) or p in known:raise ValueError('invalid sparse record')
        known[p]=kind
    return goal,known

def next_cell(known,width,height,start,goal):
    heuristic=lambda p:abs(p%width-goal%width)+abs(p//width-goal//width)
    distance={start:0};parent={};queue=[(heuristic(start),0,start)]
    while queue:
        _,cost,p=heapq.heappop(queue)
        if cost!=distance[p]:continue
        if p==goal:break
        for dx,dy in DXY:
            x,y=p%width+dx,p//width+dy
            if not(0<=x<width and 0<=y<height):continue
            q=y*width+x;kind=known.get(q,0)
            if kind==2:continue
            value=cost+(1 if kind==1 else 2)
            if value<distance.get(q,float('inf')):
                distance[q]=value;parent[q]=p;heapq.heappush(queue,(value+heuristic(q),value,q))
    if goal not in parent:return start
    q=goal
    while parent[q]!=start:q=parent[q]
    return q

def step(frame,state,spec):
    if spec.budget<HEADER.size:raise ValueError('budget below charged goal header')
    goal,known=decode(state,spec.width,spec.height)
    for p,kind in frame.cells:
        if kind not in (1,2):raise ValueError('example supports free/blocked cells only')
        known[p]=kind
    nxt=next_cell(known,spec.width,spec.height,frame.position,goal)
    if nxt==frame.position:action=0
    else:
        desired=DXY.index((nxt%spec.width-frame.position%spec.width,nxt//spec.width-frame.position//spec.width));turn=(desired-frame.direction)%4
        action=2 if turn==0 else 0 if turn==3 else 1
    capacity=(spec.budget-HEADER.size)//RECORD.size;deleted=max(0,len(known)-capacity)
    # Dict insertion order is serialized; updates keep FIFO age.
    for _ in range(deleted):del known[next(iter(known))]
    raw=initial(goal)+b''.join(RECORD.pack(p,kind) for p,kind in known.items())
    return action,raw,dict(retained_cells=len(known),deleted_cells=deleted,representation='ordered sparse uint32/uint8')

def main():
    p=argparse.ArgumentParser(description='Prepare charged initial bytes from public scenario endpoints')
    p.add_argument('--map',required=True);p.add_argument('--scenarios',required=True);p.add_argument('--line',required=True,type=int);p.add_argument('--output',required=True)
    a=p.parse_args()
    # Parse public metadata to choose the declared target. The map content
    # returned by the parser is never used in initial state or controller.
    from statebudget_nav.movingai import load_map,load_scenarios,select
    grid=load_map(a.map);scene=select(load_scenarios(a.scenarios,grid),line=a.line)
    with Path(a.output).open('xb') as stream:stream.write(initial(scene.goal))
    print(f'Wrote {HEADER.size} charged bytes; goal={scene.goal}')
if __name__=='__main__':main()
