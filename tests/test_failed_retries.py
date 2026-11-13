"""Regressions from the externally executed 2026-11-05 trial."""
import io
import json
import zipfile

import pytest

from statebudget_nav import movingai
from statebudget_nav.evaluation import run_episode


def test_invalid_budget_does_not_reserve_trace_path(tmp_path):
    trace = tmp_path/'nested/trace.jsonl'
    with pytest.raises(ValueError,match='minimum 26'):
        run_episode('MiniGrid-FourRooms-v0',budget=1,trace_path=trace)
    assert not trace.exists()
    result = run_episode('MiniGrid-FourRooms-v0',budget=64,trace_path=trace)
    assert result['success'] == 1 and result['steps'] == 81
    original = trace.read_bytes()
    with pytest.raises(FileExistsError):
        run_episode('MiniGrid-FourRooms-v0',budget=64,trace_path=trace)
    assert trace.read_bytes() == original


def test_preflight_never_calls_plugin_step(tmp_path,monkeypatch):
    from statebudget_nav.examples import local_walk
    original = local_walk.step
    calls = []

    def counted(frame,state,spec):
        calls.append(frame)
        return original(frame,state,spec)

    monkeypatch.setattr(local_walk,'step',counted)
    result = run_episode('MiniGrid-FourRooms-v0',budget=4,limit=3,
        policy='python:statebudget_nav.examples.local_walk:step',trace_path=tmp_path/'trace.jsonl')
    assert len(calls) == result['steps'] == 3


def archive(name,text):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr(name,text)
    return stream.getvalue()


MAP_URL = 'https://www.movingai.com/benchmarks/test/tiny.map.zip'
SCEN_URL = 'https://www.movingai.com/benchmarks/test/tiny.scen.zip'
MAP = archive('tiny.map','type octile\nheight 3\nwidth 6\nmap\n@@@@@@\n@....@\n@@@@@@\n')
SCEN = archive('tiny.scen','version 1\n0 tiny.map 6 3 1 1 4 1 3.000000\n')


def response(url,raw):
    stream = io.BytesIO(raw)
    stream.url = url
    return stream


@pytest.mark.parametrize('failure',['first_download','second_download','invalid_zip','invalid_scenario'])
def test_failed_fetch_can_retry_same_destination(tmp_path,monkeypatch,failure):
    destination = tmp_path/'inputs'

    def failing(url,timeout):
        if failure == 'first_download' or (failure == 'second_download' and url == SCEN_URL):
            raise ConnectionRefusedError('simulated connection failure')
        if url == SCEN_URL and failure == 'invalid_zip':
            return response(url,b'not a zip')
        if url == SCEN_URL and failure == 'invalid_scenario':
            return response(url,archive('tiny.scen','invalid scenario'))
        return response(url,MAP if url == MAP_URL else SCEN)

    monkeypatch.setattr(movingai.urllib.request,'urlopen',failing)
    with pytest.raises((ConnectionRefusedError,zipfile.BadZipFile,ValueError)):
        movingai.fetch(MAP_URL,SCEN_URL,destination)
    assert not destination.exists()
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(movingai.urllib.request,'urlopen',
        lambda url,timeout: response(url,MAP if url == MAP_URL else SCEN))
    receipt = movingai.fetch(MAP_URL,SCEN_URL,destination)
    assert (destination/'tiny.map').is_file() and (destination/'tiny.scen').is_file()
    assert json.loads((destination/'DOWNLOAD_RECEIPT.json').read_text()) == receipt
    assert len(receipt['records']) == 2


def test_fetch_preserves_existing_output_without_network(tmp_path,monkeypatch):
    destination = tmp_path/'inputs'; destination.mkdir()
    marker = destination/'keep.txt'; marker.write_text('user data')

    def unexpected(*args,**kwargs):
        raise AssertionError('should not download when destination exists')

    monkeypatch.setattr(movingai.urllib.request,'urlopen',unexpected)
    with pytest.raises(FileExistsError):
        movingai.fetch(MAP_URL,SCEN_URL,destination)
    assert marker.read_text() == 'user data'


@pytest.mark.parametrize('seed,budget,success,steps,trajectory',[
    (10000,52,0,600,'cd0e79dcf1c11f298ad974d387086dc4e05e6c3e1d7dc482bdc1b5d7065fde98'),
    (10000,53,1,211,'6375a77395e7c399393fbd8a381e521493ad18c4d793e694fbbcf995e74534c4'),
    (10003,33,0,600,'474fdff4f345c9bab5fe8ab12afd8d36cbc47f4ae434c96aab4f31294185e06f'),
])
def test_preflight_preserves_trial_trajectories(seed,budget,success,steps,trajectory):
    actual = run_episode('MiniGrid-FourRooms-v0',seed=seed,budget=budget)
    assert (actual['success'],actual['steps'],actual['trajectory_hash']) == (success,steps,trajectory)
