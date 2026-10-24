"""Fresh interpreter audit endpoint; no environment or episode seed input."""
import json
import sys
from .public_api import replay_checkpoint

if __name__=='__main__':
    json.dump(replay_checkpoint(json.load(sys.stdin)),sys.stdout)
