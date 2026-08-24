"One worker draining claims from a shared vault. `test_queue.py` spawns several."
import json, sys

from pobblebonk.core import vault
from pobblebonk.queue import Queue

path, worker, batch = sys.argv[1], sys.argv[2], int(sys.argv[3])
q = Queue(vault(path))
got = []
while True:
    claimed = q.claim(worker, n=batch)
    if not claimed: break
    got += [j['id'] for j in claimed]
print(json.dumps(got))
