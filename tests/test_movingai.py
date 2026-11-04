"""Public large-grid workflow, original endpoints and state-boundary regressions."""
import base64,gzip,hashlib,json,struct
from dataclasses import replace
import pytest
from statebudget_nav import ControllerSpec,Frame,checked_step,checkpoint,replay_checkpoint
from statebudget_nav._core import fullmap
from statebudget_nav.movingai import load_map,load_scenarios,select,run,report,verify_distance8
from statebudget_nav.audit import audit_trace


def fixture(tmp_path):
    mp=tmp_path/'tiny.map';mp.write_text('type octile\nheight 3\nwidth 6\nmap\n@@@@@@\n@....@\n@@@@@@\n',encoding='ascii')
    sc=tmp_path/'tiny.scen';sc.write_text('version 1\n0 tiny.map 6 3 1 1 4 1 3.000000\n0 tiny.map 6 3 4 1 1 1 3.000000\n',encoding='ascii')
    return mp,sc


def test_adapter_preserves_original_direction_and_replays_gzip(tmp_path):
    mp,sc=fixture(tmp_path);g=load_map(mp);rows=load_scenarios(sc,g)
    assert select(rows,quantile=.75).line==2
    assert (select(rows,line=3).start,select(rows,line=3).goal)==(10,7)
    r=run(mp,sc,tmp_path/'run',budget=256,line=3)
    assert r['success'] and r['moves']==3 and r['oracle4']==3
    assert r['task']['line']==3 and r['task']['original_line']==sc.read_text().splitlines()[2]
    assert r['max_state_bytes']<=r['budget'] and not r['official_distance_verified']
    assert audit_trace(tmp_path/'run/trace.jsonl.gz',True)['all_passed']
    assert report([tmp_path/'run',tmp_path/'run'])['distinct_physical_tasks']==1
    with pytest.raises(FileExistsError):run(mp,sc,tmp_path/'run',budget=256,line=3)


@pytest.mark.parametrize('name',['lru','walls','face_route'])
def test_large_plugin_coordinates_survive_checkpoint_restart(name):
    spec=ControllerSpec(512,512,1024,'python:statebudget_nav._core.fullmap:'+name)
    frame=Frame(70000,0,((70000,1),(70001,1),(70002,1)))
    state=fullmap.initial(spec,70000,70002)
    a,out,_=checked_step(frame,state,spec);e=checkpoint(frame,state,spec)
    actual=replay_checkpoint(e,True)
    assert actual['action']==a and base64.b64decode(actual['state_b64'])==out
    with pytest.raises(ValueError):ControllerSpec(512,512,1024,'compressed')
    with pytest.raises(ValueError):checked_step(frame,state,replace(spec,budget=0))


def test_inconsistent_stream_and_unsupported_terrain_rejected(tmp_path):
    mp,sc=fixture(tmp_path);grid=load_map(mp)
    sc.write_text(sc.read_text().replace('6 3','3 6'))
    with pytest.raises(ValueError,match='dimensions'):load_scenarios(sc,grid)
    mp.write_text(mp.read_text().replace('....','S...'))
    with pytest.raises(ValueError,match='terrain'):load_map(mp)
    spec=ControllerSpec(6,3,256,'python:statebudget_nav._core.fullmap:walls')
    import numpy as np
    known=np.zeros((3,6),dtype=np.uint8);known[1,1]=1
    raw=fullmap.pack(7,10,0,[],known)
    with pytest.raises(ValueError,match='uncharged'):fullmap.unpack(raw,spec)
    raw=fullmap.pack(7,10,0,[0],known)+b'extra'
    with pytest.raises(ValueError,match='stream'):fullmap.unpack(raw,spec)


def test_gzip_audit_rejects_modified_action(tmp_path):
    mp,sc=fixture(tmp_path);folder=tmp_path/'run';run(mp,sc,folder,budget=256,line=2)
    path=folder/'trace.jsonl.gz'
    with gzip.open(path,'rt') as stream:events=[json.loads(s) for s in stream]
    events[0]['expected']['action']=(events[0]['expected']['action']+1)%3
    with gzip.open(path,'wt') as stream:
        for e in events:stream.write(json.dumps(e)+'\n')
    with pytest.raises(ValueError,match='mismatch'):audit_trace(path,True)


def test_invalid_initial_budget_and_disconnected_official_task(tmp_path):
    mp,sc=fixture(tmp_path)
    with pytest.raises(ValueError,match='budget'):run(mp,sc,tmp_path/'bad',budget=1,line=2)
    assert not (tmp_path/'bad').exists()
    mp.write_text(mp.read_text().replace('@....@','@.@..@'))
    with pytest.raises(ValueError,match='unsupported'):run(mp,sc,tmp_path/'disconnected',budget=256,line=2)
    assert not (tmp_path/'disconnected').exists()


def test_official_distance_uses_diagonals_without_corner_cutting(tmp_path):
    mp=tmp_path/'corner.map';mp.write_text('type octile\nheight 3\nwidth 3\nmap\n.@.\n...\n...\n')
    sp=tmp_path/'corner.scen';sp.write_text('version 1\n0 corner.map 3 3 0 0 1 1 2\n')
    grid=load_map(mp);scenario=load_scenarios(sp,grid)[0]
    assert verify_distance8(grid,scenario)==2
    sp.write_text(sp.read_text().replace('1 1 2','1 1 1.414213562'))
    with pytest.raises(ValueError,match='mismatch'):verify_distance8(grid,load_scenarios(sp,grid)[0])
