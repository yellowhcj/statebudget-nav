"""Reproduce a development audit; these are reused, not held-out map seeds."""
from pathlib import Path
import json
import sys
from ..batch import create_batch,run_batch
from ..analysis import summarize_batch


def demonstrate(path):
    jobs=[dict(env='MiniGrid-MultiRoom-N6-v0',seed=seed,policy=policy,budget=112,limit=600)
          for policy in ['lru','history_lru','compressed'] for seed in range(10000,10032)]
    create_batch(path,jobs)
    progress=run_batch(path)
    if progress['pending']:raise RuntimeError('reproduction has failed or unfinished jobs')
    report=summarize_batch(path)
    (Path(path)/'summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':print(json.dumps(demonstrate(sys.argv[1]),indent=2))
