"""External map-controller initialization, budget and fresh replay behavior."""
import base64,gzip,hashlib,json
from pathlib import Path
import pytest
from statebudget_nav.movingai import run
from statebudget_nav.audit import audit_trace

def fixture(tmp_path):
    mp=tmp_path/'tiny.map';mp.write_text('type octile\nheight 3\nwidth 6\nmap\n@@@@@@\n@....@\n@@@@@@\n')
    sc=tmp_path/'tiny.scen';sc.write_text('version 1\n0 tiny.map 6 3 1 1 4 1 3\n')
    return mp,sc

def test_separate_controller_init_source_identity_and_all_decision_replay(tmp_path):
    plugin=pytest.importorskip("navmemory_example")
    mp,sc=fixture(tmp_path);state=plugin.initial(10)
    result=run(mp,sc,tmp_path/'external',policy='python:navmemory_example:step',budget=25,line=2,initial_state=state)
    assert result['success'] and result['moves']==3 and result['max_state_bytes']<=25
    assert result['external_plugin'] and result['controller_identity']=='python:navmemory_example:step'
    assert result['initial_state_sha256']==hashlib.sha256(state).hexdigest()
    assert result['plugin_module_sha256']==hashlib.sha256(Path(plugin.__file__).read_bytes()).hexdigest()
    assert (tmp_path/'external/source/external_plugin.py').read_bytes()==Path(plugin.__file__).read_bytes()
    assert (tmp_path/'external/initial_state.bin').read_bytes()==state
    assert 'representation' not in result['statistics']
    assert audit_trace(tmp_path/'external/trace.jsonl.gz',True)['all_passed']
    with gzip.open(tmp_path/'external/trace.jsonl.gz','rt') as stream:first=json.loads(next(stream))
    assert base64.b64decode(first['state_b64'])==state

def test_init_errors_do_not_create_completed_or_partial_run(tmp_path):
    pytest.importorskip("navmemory_example")
    mp,sc=fixture(tmp_path)
    for tag,kwargs,match in (
        ('missing',dict(policy='python:navmemory_example:step'),'explicit initial'),
        ('overflow',dict(policy='python:navmemory_example:step',initial_state=b'x'*26),'initial state exceeds'),
        ('builtin',dict(policy='walls',initial_state=b''),'override'),
        ('unknown',dict(policy='unsupported'),'unsupported'),
        ('notcallable',dict(policy='python:navmemory_example:TAG',initial_state=b''),'not callable')):
        with pytest.raises(ValueError,match=match):run(mp,sc,tmp_path/tag,budget=25,line=2,**kwargs)
        assert not (tmp_path/tag).exists()

def test_external_bad_output_is_rejected_and_partial_never_completed(tmp_path):
    mp,sc=fixture(tmp_path)
    # counter emits one byte: zero-budget input is legal but output must fail.
    with pytest.raises(ValueError,match='exceeded'):run(mp,sc,tmp_path/'bad',policy='python:statebudget_nav.examples.counter:step',budget=0,line=2,initial_state=b'')
    assert not (tmp_path/'bad/result.json').exists()
