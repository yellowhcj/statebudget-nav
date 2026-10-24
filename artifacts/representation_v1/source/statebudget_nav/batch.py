"""Frozen-source, single-writer batch evaluation with verified resume.

Each job runs in an independent interpreter importing the archived package.
Integrity checks detect ordinary drift/corruption, not malicious manifest edits.
"""
from datetime import datetime,timezone
from importlib import metadata
from pathlib import Path
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from . import __version__,ControllerSpec

FIELDS={'env','seed','policy','budget','limit','view','selector','agent_seed'}
DEFAULTS=dict(seed=10000,policy='compressed',budget=64,limit=600,view=7,
              selector='nearest',agent_seed=1)


def digest(data):return hashlib.sha256(data).hexdigest()


def atomic_json(path,value):
    path=Path(path)
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                     suffix='.tmp',delete=False) as stream:
        temporary=Path(stream.name)
        json.dump(value,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def canonical_bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def environment():
    versions={}
    for name in ['numpy','gymnasium','minigrid','pygame','cloudpickle','farama-notifications']:
        try:versions[name]=metadata.version(name)
        except metadata.PackageNotFoundError:versions[name]=None
    return dict(python=platform.python_version(),implementation=platform.python_implementation(),
                platform=platform.platform(),dependencies=versions)


def normalize_jobs(jobs):
    normalized=[];seen=set()
    if not isinstance(jobs,list) or not jobs:raise ValueError('nonempty JSON job list required')
    for raw in jobs:
        if not isinstance(raw,dict) or set(raw)-FIELDS or 'env' not in raw:
            raise ValueError('invalid job keys or missing environment')
        job={**DEFAULTS,**raw}
        if not isinstance(job['env'],str) or not job['env']:raise ValueError('invalid environment')
        if not isinstance(job['policy'],str) or job['policy'].startswith('python:'):
            raise ValueError('frozen batches currently support bundled controllers only')
        if any(type(job[k]) is not int for k in ['seed','budget','limit','view','agent_seed']):
            raise ValueError('job numerical fields must be integers')
        if job['limit']<1 or job['view']<3 or job['view']%2!=1:
            raise ValueError('positive limit and odd view >=3 required')
        if job['selector'] not in ['nearest','frontier','gain']:raise ValueError('invalid selector')
        ControllerSpec(5,5,job['budget'],job['policy'],job['selector'],job['agent_seed'])
        key=digest(canonical_bytes(job))
        if key in seen:raise ValueError('duplicate job configuration')
        seen.add(key);normalized.append(dict(job_id=key,configuration=job))
    return normalized


def source_files(root):
    return {str(p.relative_to(root)).replace('\\','/'):digest(p.read_bytes())
            for p in sorted(root.rglob('*')) if p.is_file() and p.suffix in ('.py','.json')
            and '__pycache__' not in p.parts}


def create_batch(path,jobs):
    jobs=normalize_jobs(jobs);path=Path(path).resolve()
    path.mkdir(parents=True,exist_ok=False)
    source=path/'source'/'statebudget_nav';source.mkdir(parents=True)
    package=Path(__file__).resolve().parent
    for name in source_files(package):
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((package/name).read_bytes())
    (path/'jobs').mkdir();(path/'failures').mkdir()
    manifest=dict(schema='statebudget.batch.v1',version=__version__,
                  created_utc=datetime.now(timezone.utc).isoformat(),environment=environment(),
                  source_sha256=source_files(source),jobs=jobs)
    atomic_json(path/'manifest.json',manifest)
    return manifest


def verify_batch(path,check_environment=True):
    path=Path(path).resolve();manifest=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema')!='statebudget.batch.v1':raise ValueError('unknown batch schema')
    if source_files(path/'source'/'statebudget_nav')!=manifest['source_sha256']:
        raise ValueError('archived source integrity mismatch')
    normalized=normalize_jobs([j['configuration'] for j in manifest['jobs']])
    if normalized!=manifest['jobs']:raise ValueError('job configuration digest mismatch')
    if check_environment and environment()!=manifest['environment']:
        raise ValueError('runtime environment changed; refusing silent resume')
    expected={j['job_id']:j for j in manifest['jobs']};complete=0
    for file in (path/'jobs').glob('*.json'):
        record=json.loads(file.read_text(encoding='utf-8'));key=file.stem
        if key not in expected or record.get('configuration')!=expected[key]['configuration']:
            raise ValueError('unrecognized completed job or configuration mismatch')
        result=record['result']
        if record.get('result_sha256')!=digest(canonical_bytes(result)):
            raise ValueError('completed result integrity mismatch')
        if any(result.get(k)!=v for k,v in record['configuration'].items()):
            raise ValueError('result/configuration mismatch')
        if not 0<=result['max_state_bytes']<=result['budget']:
            raise ValueError('invalid recorded payload size')
        if not 1<=result['steps']<=result['limit'] or result['success'] not in (0,1):
            raise ValueError('invalid recorded episode outcome')
        complete+=1
    return manifest,dict(jobs=len(expected),complete=complete,pending=len(expected)-complete,
                         source_verified=True,environment_verified=check_environment)


def run_batch(path,max_jobs=None):
    """Run pending jobs sequentially; successful records are never recomputed.

    Failed attempts are retained separately. Calling again retries failed jobs.
    A lock prevents accidental concurrent writers; a crash may leave the lock,
    which must be inspected before explicit removal by the user.
    """
    if max_jobs is not None and (type(max_jobs) is not int or max_jobs<0):
        raise ValueError('max_jobs must be a nonnegative integer')
    path=Path(path).resolve();lock=path/'writer.lock'
    with lock.open('x',encoding='ascii') as stream:stream.write(str(os.getpid()))
    try:
        manifest,_=verify_batch(path);attempted=0;failures=0
        child_env=dict(os.environ);child_env.pop('PYTHONPATH',None)
        for job in manifest['jobs']:
            key=job['job_id'];destination=path/'jobs'/(key+'.json')
            if destination.exists():continue
            if max_jobs is not None and attempted>=max_jobs:break
            attempted+=1
            try:
                completed=subprocess.run([sys.executable,'-B','-m','statebudget_nav.batch_worker'],
                    input=json.dumps(job['configuration']),text=True,capture_output=True,
                    cwd=path/'source',env=child_env,check=True)
                result=json.loads(completed.stdout)
                atomic_json(destination,dict(configuration=job['configuration'],result=result,
                    result_sha256=digest(canonical_bytes(result))))
            except Exception as error:
                failures+=1
                stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
                detail=dict(configuration=job['configuration'],error=str(error),
                            stderr=getattr(error,'stderr',None))
                atomic_json(path/'failures'/(key+'_'+stamp+'.json'),detail)
        _,report=verify_batch(path)
        report.update(attempted=attempted,failed_attempts_this_call=failures)
        atomic_json(path/'progress.json',report)
        return report
    finally:lock.unlink()
