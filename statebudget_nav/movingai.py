"""MovingAI full-map inputs and an explicitly adapted partial-observation loop.

Original scenario endpoints/distances are retained. Reported navigation is
four-neighbor/local-observation adaptation, not an official benchmark score.
"""
from collections import deque
from dataclasses import asdict,dataclass
import base64
import gzip
import hashlib
import json
import math
import heapq
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

from . import ControllerSpec,Frame,checked_step,checkpoint,replay_checkpoint,__version__
from ._core import fullmap


def sha(data):return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Grid:
    width:int
    height:int
    cells:bytes
    map_name:str
    source_sha256:str


@dataclass(frozen=True)
class Scenario:
    line:int
    bucket:int
    map_name:str
    width:int
    height:int
    start:int
    goal:int
    official_distance:float
    original_line:str


def load_map(path):
    path=Path(path);raw=path.read_bytes();lines=raw.decode('ascii').splitlines()
    if len(lines)<4 or lines[0]!='type octile' or lines[3]!='map':raise ValueError('expected MovingAI octile map')
    try:
        if lines[1].split()[0]!='height' or lines[2].split()[0]!='width':raise ValueError('invalid dimensions')
        h,w=int(lines[1].split()[1]),int(lines[2].split()[1])
    except (IndexError,ValueError) as exc:raise ValueError('invalid dimensions') from exc
    if w<1 or h<1 or w*h>=0xffffffff:raise ValueError('unsupported dimensions')
    rows=lines[4:]
    if len(rows)!=h or any(len(row)!=w for row in rows):raise ValueError('map rows do not match dimensions')
    text=''.join(rows)
    if not set(text)<=set('.G@OT'):raise ValueError('unsupported terrain; swamp/water require different traversal semantics')
    return Grid(w,h,bytes(1 if c in '.G' else 2 for c in text),path.name,sha(raw))


def load_scenarios(path,grid):
    lines=Path(path).read_text(encoding='ascii').splitlines()
    if not lines or lines[0].split() not in (['version','1'],['version','1.0']):raise ValueError('unsupported scenario version')
    result=[]
    for number,line in enumerate(lines[1:],2):
        fields=line.split()
        if not fields:continue
        if len(fields)!=9:raise ValueError(f'scenario line{number}: expected9 fields')
        bucket,name,w,h,sx,sy,gx,gy,d=fields
        w,h,sx,sy,gx,gy,bucket=map(int,(w,h,sx,sy,gx,gy,bucket));distance=float(d)
        if Path(name.replace('\\','/')).name!=grid.map_name or (w,h)!=(grid.width,grid.height):raise ValueError('scenario map/dimensions mismatch; scaling is not implicit')
        if not(0<=sx<w and 0<=gx<w and 0<=sy<h and 0<=gy<h):raise ValueError('scenario endpoint out of bounds')
        s,g=sy*w+sx,gy*w+gx
        if grid.cells[s]!=1 or grid.cells[g]!=1:raise ValueError('blocked scenario endpoint')
        if not math.isfinite(distance) or distance<0 or bucket<0:raise ValueError('invalid official distance/bucket')
        result.append(Scenario(number,bucket,name,w,h,s,g,distance,line))
    if not result:raise ValueError('empty scenario file')
    return result


def select(rows,line=None,quantile=None):
    if (line is None)==(quantile is None):raise ValueError('choose exactly one original line or distance quantile')
    if line is not None:
        found=[r for r in rows if r.line==line]
        if len(found)!=1:raise ValueError('scenario line not found')
        return found[0]
    if not 0<=quantile<=1:raise ValueError('quantile must be in[0,1]')
    return sorted(rows,key=lambda r:(r.official_distance,r.line))[int(quantile*(len(rows)-1))]


def distance4(grid,start,goal):
    queue=deque([start]);dist={start:0};w,h=grid.width,grid.height
    while queue:
        p=queue.popleft()
        if p==goal:return dist[p]
        x,y=p%w,p//w
        for dx,dy in fullmap.DXY:
            xx,yy=x+dx,y+dy;q=yy*w+xx
            if 0<=xx<w and 0<=yy<h and grid.cells[q]==1 and q not in dist:dist[q]=dist[p]+1;queue.append(q)
    return None


def verify_distance8(grid,scenario):
    """Independent Dijkstra with official diagonal/no-corner-cutting rules."""
    start,goal=scenario.start,scenario.goal;w,h=grid.width,grid.height
    dist={start:0.};queue=[(0.,start)]
    while queue:
        d,p=heapq.heappop(queue)
        if dist[p]!=d:continue
        if p==goal:
            if abs(d-scenario.official_distance)>1e-5:raise ValueError('official distance mismatch')
            return d
        x,y=p%w,p//w
        for yy in range(max(0,y-1),min(h,y+2)):
            for xx in range(max(0,x-1),min(w,x+2)):
                q=yy*w+xx
                if q==p or grid.cells[q]!=1:continue
                diagonal=xx!=x and yy!=y
                if diagonal and (grid.cells[y*w+xx]!=1 or grid.cells[yy*w+x]!=1):continue
                nd=d+(math.sqrt(2) if diagonal else 1)
                if nd<dist.get(q,float('inf')):dist[q]=nd;heapq.heappush(queue,(nd,q))
    raise ValueError('official endpoints not connected under8-way rules')


def fetch(map_url,scenario_url,directory):
    """Retrieve official ZIPs; preserve responses, provenance and attribution."""
    for url in (map_url,scenario_url):
        parsed=urllib.parse.urlparse(url)
        if parsed.scheme not in ('http','https') or parsed.hostname not in ('www.movingai.com','movingai.com') or not parsed.path.startswith('/benchmarks/'):
            raise ValueError('use explicit official MovingAI benchmark URLs')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False);records=[]
    for url,suffix in ((map_url,'.map'),(scenario_url,'.scen')):
        with urllib.request.urlopen(url,timeout=60) as response:
            final_url=response.url
            final=urllib.parse.urlparse(final_url)
            if final.hostname not in ('www.movingai.com','movingai.com'):raise ValueError('unexpected download redirect')
            raw=response.read()
        archive_name='map.zip' if suffix=='.map' else 'scenario.zip'
        (directory/archive_name).write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members=[n for n in z.namelist() if n.endswith(suffix)]
            if len(members)!=1:raise ValueError('expected exactly one map/scenario per archive')
            info=z.getinfo(members[0])
            if info.file_size>64*1024*1024:raise ValueError('archive member too large')
            content=z.read(info);name=Path(members[0].replace('\\','/')).name
            (directory/name).write_bytes(content)
        records.append(dict(url=url,final_url=final_url,archive=archive_name,archive_sha256=sha(raw),member=members[0],file=name,sha256=sha(content)))
    grid=load_map(directory/records[0]['file']);load_scenarios(directory/records[1]['file'],grid)
    receipt=dict(records=records,source='MovingAI Lab, Sturtevant2012 Benchmarks for Grid-Based Pathfinding',
        attribution_url='https://www.movingai.com/benchmarks/grids.html',data_license='Open Data Commons Attribution; original source rights retained, not software MIT')
    (directory/'DOWNLOAD_RECEIPT.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


def observe(grid,position,direction,goal,view=7):
    radius=view//2;w,h=grid.width,grid.height;x,y=position%w,position//w
    cells=tuple((yy*w+xx,grid.cells[yy*w+xx]) for yy in range(max(0,y-radius),min(h,y+radius+1)) for xx in range(max(0,x-radius),min(w,x+radius+1)))
    return Frame(position,direction,cells,(goal,) if any(p==goal for p,v in cells) else ())


def build_native(output,compiler=None):
    """Build an optional immutable search backend, outside the installed package."""
    output=Path(output).resolve()
    if output.exists():raise FileExistsError(output)
    compiler=compiler or shutil.which('g++')
    if not compiler:raise ValueError('g++ required for optional native backend; Python backend needs no compiler')
    output.parent.mkdir(parents=True,exist_ok=True)
    source=Path(fullmap.__file__).with_name('fullmap_search.cpp')
    flags=['-std=c++17','-O3','-shared']
    if os.name=='nt':flags+=['-static-libgcc','-static-libstdc++','-static','-Wl,--no-insert-timestamp']
    else:flags+=['-fPIC']
    command=[str(compiler),*flags,str(source),'-o',str(output)]
    result=subprocess.run(command,capture_output=True,text=True)
    if result.returncode:raise RuntimeError('native build failed: '+result.stderr)
    receipt=dict(command=command,source_sha256=sha(source.read_bytes()),library_sha256=sha(output.read_bytes()),platform=platform.platform())
    output.with_name(output.name+'.build.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


def run(map_path,scenario_path,directory,policy='walls',budget=1024,line=None,quantile=None,view=7,multiplier=6,initial_state=None):
    if type(view) is not int or view<3 or view%2!=1:raise ValueError('view must be odd and>=3')
    if not math.isfinite(multiplier) or multiplier<=0:raise ValueError('positive movement multiplier required')
    grid=load_map(map_path);rows=load_scenarios(scenario_path,grid);s=select(rows,line,quantile)
    d4=distance4(grid,s.start,s.goal)
    if d4 is None:raise ValueError('official endpoints unsupported by this4-way adaptation; do not replace them silently')
    builtin=policy in ('lru','walls','lru_native','walls_native','face_route')
    external=not builtin and isinstance(policy,str) and policy.startswith('python:')
    if not builtin and not external:raise ValueError('unsupported controller')
    spec=ControllerSpec(grid.width,grid.height,budget,policy if external else 'python:statebudget_nav._core.fullmap:'+policy)
    plugin_source=None
    if external:
        if type(initial_state) is not bytes:raise ValueError('external controller requires explicit initial bytes')
        if len(initial_state)>budget:raise ValueError('initial state exceeds budget')
        from ._core.public_api import implementation
        import importlib
        implementation(spec)
        module=importlib.import_module(policy.split(':')[1])
        location=getattr(module,'__file__',None)
        if not location or not Path(location).is_file():raise ValueError('plugin module needs a readable source artifact')
        plugin_source=Path(location)
        state=initial_state
    else:
        if initial_state is not None:raise ValueError('initial state override is only for external controllers')
        state=fullmap.initial(spec,s.start,s.goal)
    backend=None
    if builtin and policy.endswith('_native'):
        fullmap.native_library();backend=Path(os.environ['STATEBUDGET_NAV_NATIVE_LIBRARY']).resolve()
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    modules=(Path(fullmap.__file__),Path(fullmap.__file__).with_name('fullmap_face.py'),Path(__file__),Path(__file__).with_name('_core')/'public_api.py',Path(__file__).with_name('_core')/'controller.py')
    source_dir=directory/'source';source_dir.mkdir()
    sources={}
    for p in modules:
        dest=source_dir/p.name;shutil.copyfile(p,dest);sources[p.name]=sha(p.read_bytes())
    if plugin_source:
        plugin_name='external_plugin'+plugin_source.suffix
        shutil.copyfile(plugin_source,source_dir/plugin_name);sources[plugin_name]=sha(plugin_source.read_bytes())
    (directory/'initial_state.bin').write_bytes(state)
    limit=max(600,math.ceil(multiplier*d4));pos=s.start;heading=moves=actions=0;peak=len(state);initial=state.hex();statistics={}
    path=directory/'trace.jsonl.gz'
    with gzip.open(path,'wt',encoding='utf-8',compresslevel=3,newline='\n') as stream:
        while pos!=s.goal and moves<limit and actions<3*limit:
            frame=observe(grid,pos,heading,s.goal,view);e=checkpoint(frame,state,spec)
            a,state,diag=checked_step(frame,state,spec);actions+=1;peak=max(peak,len(state))
            for k,v in diag.items():
                if type(v) in (int,float) and math.isfinite(v):statistics[k]=statistics.get(k,0)+v
            e['expected']=dict(action=a,state_sha256=sha(state));stream.write(json.dumps(e,separators=(',',':'))+'\n')
            if a in (0,1):heading=(heading+(-1 if a==0 else 1))%4
            elif a==2:
                dx,dy=fullmap.DXY[heading];x,y=pos%grid.width+dx,pos//grid.width+dy
                if not(0<=x<grid.width and 0<=y<grid.height and grid.cells[y*grid.width+x]==1):raise ValueError('controller attempted illegal movement')
                pos=y*grid.width+x;moves+=1
            else:raise ValueError('adapted evaluator permits turn/forward actions only')
    indices={0,actions//2,actions-1};samples=[]
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for k,line_text in enumerate(stream):
            if k in indices:
                event=json.loads(line_text);out=replay_checkpoint(event,True)
                if out['action']!=event['expected']['action'] or sha(base64.b64decode(out['state_b64']))!=event['expected']['state_sha256']:raise ValueError('fresh replay mismatch')
                samples.append(event)
    for p in modules:
        if sources[p.name]!=sha(p.read_bytes()):raise ValueError('source changed during run')
    if plugin_source and sources[plugin_name]!=sha(plugin_source.read_bytes()):raise ValueError('plugin source changed during run')
    task_id=sha(json.dumps(dict(world=sha(grid.cells),width=grid.width,height=grid.height,start=s.start,goal=s.goal,heading=0,view=view),sort_keys=True).encode())
    result=dict(package_version=__version__,convention='MovingAI data; adapted4-way partial-observation navigation, not official scores',
        task=asdict(s),physical_task_sha256=task_id,map_sha256=grid.source_sha256,world_sha256=sha(grid.cells),scenario_sha256=sha(Path(scenario_path).read_bytes()),
        oracle4=d4,official_distance_verified=False,limit=limit,view=view,policy=policy,budget=budget,success=pos==s.goal,moves=moves,actions=actions,
        stop_reason='goal' if pos==s.goal else 'move_limit' if moves>=limit else 'action_limit',max_state_bytes=peak,
        initial_state_hex=initial,initial_state_sha256=sha(bytes.fromhex(initial)),final_state_hex=state.hex(),statistics=statistics,trace_sha256=sha(path.read_bytes()),fresh_replays=len(samples),
        controller_identity=spec.policy,external_plugin=external,plugin_module_sha256=sources.get(plugin_name) if plugin_source else None,
        source_sha256=sources,native_library_sha256=sha(backend.read_bytes()) if backend else None,
        source_scope='Adapter and controller snapshots, not a complete dependency archive. Install the matching package wheel for replay.')
    (directory/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (directory/'replay_samples.json').write_text(json.dumps(samples,indent=2),encoding='utf-8')
    return result


def report(directories):
    rows=[json.loads((Path(p)/'result.json').read_bytes()) for p in directories]
    identities=[r['physical_task_sha256'] for r in rows]
    return dict(executions=len(rows),distinct_physical_tasks=len(set(identities)),not_official_scores=True,
        rows=[{k:r[k] for k in ('physical_task_sha256','policy','budget','success','moves','oracle4','max_state_bytes','fresh_replays')} for r in rows])
