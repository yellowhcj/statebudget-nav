"""Worker entry: launched from a verified source snapshot, no module patching."""
import json
import sys
from .evaluation import run_episode

if __name__=='__main__':
    job=json.load(sys.stdin)
    name=job.pop('env')
    json.dump(run_episode(name,**job),sys.stdout,allow_nan=False)
