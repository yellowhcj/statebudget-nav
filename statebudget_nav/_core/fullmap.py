"""32-bit map-memory example plugins. Only returned bytes persist between calls.

The codec and policies reproduce the full-map pilot; they are conventional
examples, not new compression algorithms. Decoded maps/search workspace are
temporary and outside the serialized persistent-state budget.
"""
import ctypes
import hashlib
import heapq
import os
from pathlib import Path
import struct
import zlib
import numpy as np
from . import fullmap_face

HEADER=struct.Struct('<BIIII')
TAG=77
DXY=((1,0),(0,1),(-1,0),(0,-1))


def pack(position,goal,tick,ids,known):
    raw=known.tobytes() if hasattr(known,'tobytes') else bytes(known)
    z=zlib.compressobj(9,zlib.DEFLATED,-15)
    return HEADER.pack(TAG,position,goal,tick,len(ids))+struct.pack('<'+'I'*len(ids),*ids)+z.compress(raw)+z.flush()


def unpack(raw,spec):
    """Decode a bounded payload and reject inconsistent metadata or symbols."""
    try:
        tag,pos,goal,tick,count=HEADER.unpack_from(raw)
        columns=(spec.width+30)//31;tiles=columns*((spec.height+30)//31)
        if tag!=TAG or max(pos,goal)>=spec.width*spec.height or count>tiles:
            raise ValueError('invalid full-map header')
        offset=HEADER.size+4*count
        ids=list(struct.unpack_from('<'+'I'*count,raw,HEADER.size))
        if len(ids)!=len(set(ids)) or any(t>=tiles for t in ids):raise ValueError('invalid tile directory')
        decoder=zlib.decompressobj(-15)
        data=decoder.decompress(raw[offset:],spec.width*spec.height+1)
        if len(data)!=spec.width*spec.height or not decoder.eof or decoder.unused_data:
            raise ValueError('invalid full-map symbol stream')
        known=np.frombuffer(data,dtype=np.uint8).copy().reshape(spec.height,spec.width)
        if known.max()>2:raise ValueError('invalid full-map symbol')
        # Every nonzero symbol must belong to a charged directory entry.
        active=set(ids)
        for y in range(0,spec.height,31):
            for x in range(0,spec.width,31):
                t=y//31*columns+x//31
                if t not in active and known[y:y+31,x:x+31].any():raise ValueError('uncharged tile')
        return pos,goal,tick,ids,known
    except (struct.error,zlib.error) as exc:
        raise ValueError('invalid full-map payload') from exc


def initial(spec,start,goal):
    if any(type(v) is not int or not 0<=v<spec.width*spec.height for v in (start,goal)):
        raise ValueError('invalid endpoint')
    name=spec.policy.rsplit(':',1)[-1]
    if name=='face_route':raw=fullmap_face.initial(goal,start)
    elif name in ('lru','walls','lru_native','walls_native'):
        raw=pack(start,goal,0,[],np.zeros((spec.height,spec.width),dtype=np.uint8))
    else:raise ValueError('unsupported full-map controller')
    if len(raw)>spec.budget:raise ValueError('budget below initial representation size')
    return raw


def next_python(known,w,h,start,goal):
    """Optimistic A*: known cost1, unknown cost2; deterministic(f,g,index) ties."""
    def H(p):return abs(p%w-goal%w)+abs(p//w-goal//w)
    if start==goal:return start
    values=known.reshape(-1);dist={start:0};parent={};queue=[(H(start),0,start)]
    while queue:
        _,g,p=heapq.heappop(queue)
        if dist[p]!=g:continue
        if p==goal:break
        x,y=p%w,p//w
        for dx,dy in DXY:
            xx,yy=x+dx,y+dy
            if not (0<=xx<w and 0<=yy<h):continue
            q=yy*w+xx
            if values[q]==2:continue
            ng=g+(1 if values[q]==1 else 2)
            if ng<dist.get(q,float('inf')):dist[q]=ng;parent[q]=p;heapq.heappush(queue,(ng+H(q),ng,q))
    if goal not in parent:return start
    q=goal
    while parent[q]!=start:q=parent[q]
    return q


def native_library():
    # Only an immutable compiled implementation is loaded; no episode state.
    path=os.environ.get('STATEBUDGET_NAV_NATIVE_LIBRARY')
    if not path:raise ValueError('set STATEBUDGET_NAV_NATIVE_LIBRARY to a compiled fullmap_search library')
    lib=ctypes.CDLL(str(Path(path).resolve()))
    lib.next4.argtypes=[ctypes.c_void_p]+[ctypes.c_int]*4+[ctypes.POINTER(ctypes.c_int)]
    lib.next4.restype=ctypes.c_int
    return lib


def next_native(known,w,h,start,goal):
    if w*h>=2**31:raise ValueError('native backend requires fewer than2**31 cells')
    expanded=ctypes.c_int()
    return native_library().next4(known.ctypes.data,w,h,start,goal,ctypes.byref(expanded))


def tile_cells(known,tile,columns):
    ox,oy=tile%columns*31,tile//columns*31;h,w=known.shape
    area=known[oy:min(h,oy+31),ox:min(w,ox+31)]
    return [(oy+int(y))*w+ox+int(x) for y,x in zip(*np.nonzero(area))]


def advance(frame,state,spec,policy,native=False):
    _,goal,tick,ids,known=unpack(state,spec)
    if tick==0xffffffff:raise ValueError('full-map tick overflow')
    columns=(spec.width+30)//31;touched=[]
    for p,v in frame.cells:
        if v not in (1,2):raise ValueError('full-map example supports free/wall observations only')
        known.flat[p]=v;t=p//spec.width//31*columns+p%spec.width//31
        if t not in touched:touched.append(t)
    for t in touched:
        if t in ids:ids.remove(t)
        ids.append(t)
    nxt=(next_native if native else next_python)(known,spec.width,spec.height,frame.position,goal)
    ops=free=walls=empty=0
    while True:
        out=pack(frame.position,goal,tick+1,ids,known)
        if len(out)<=spec.budget:break
        if not ids:raise ValueError('budget below empty representation size')
        tile=ids[0];removed=tile_cells(known,tile,columns)
        if policy=='walls':
            for candidate in ids:
                ff=[p for p in tile_cells(known,candidate,columns) if known.flat[p]==1]
                if ff:tile=candidate;removed=ff;break
        free+=sum(known.flat[p]==1 for p in removed);walls+=sum(known.flat[p]==2 for p in removed)
        for p in removed:known.flat[p]=0
        if not tile_cells(known,tile,columns):ids.remove(tile);empty+=1
        ops+=1
    if nxt==frame.position:action=0
    else:
        d=DXY.index((nxt%spec.width-frame.position%spec.width,nxt//spec.width-frame.position//spec.width));delta=(d-frame.direction)%4
        action=2 if delta==0 else 0 if delta==3 else 1
    return action,out,dict(prune_operations=ops,deleted_free=int(free),deleted_walls=int(walls),empty_tiles=empty)


def lru(frame,state,spec):return advance(frame,state,spec,'lru')
def walls(frame,state,spec):return advance(frame,state,spec,'walls')
def lru_native(frame,state,spec):return advance(frame,state,spec,'lru',True)
def walls_native(frame,state,spec):return advance(frame,state,spec,'walls',True)
def face_route(frame,state,spec):return fullmap_face.step(frame,state,spec)
