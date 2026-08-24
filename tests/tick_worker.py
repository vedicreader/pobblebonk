"One process ticking a shared vault. `test_schedule.py` spawns two at once."
import json, sys

from pobblebonk.pob import Pob

path, at = sys.argv[1], float(sys.argv[2])
out = Pob(path).tick(at=at, run=False)
print(json.dumps(dict(fired=[j['id'] for j in out.fired], blocked=list(out.blocked))))
