"The queue: claiming, leases, retries, the dead letter, and what a run keeps."
import json, os, subprocess, sys
from pathlib import Path

import pytest

from pobblebonk.core import vault
from pobblebonk.queue import Queue, Retry, backoff

HERE = Path(__file__).parent


@pytest.fixture
def q(db): return Queue(db, base=0)


def test_a_handler_answer_is_kept_in_run_history_so_a_later_fire_can_read_it(q):
    q.register('greet', lambda p: {'said': f"hello {p['who']}", 'n': 3})
    q.enqueue('greet', dict(who='milk'))
    ran = q.drain('w1')
    assert ran[0]['status'] == 'ok'
    assert ran[0]['result'] == {'said': 'hello milk', 'n': 3}
    assert q.history()[0]['result'] == {'said': 'hello milk', 'n': 3}


def test_an_answer_that_is_not_a_dict_is_kept_as_it_was(q):
    q.register('n', lambda p: [1, 2, 3])
    q.enqueue('n', {})
    assert q.drain('w1')[0]['result'] == [1, 2, 3]
    assert q.history()[0]['result'] == [1, 2, 3]


def test_a_handler_that_returns_nothing_records_a_null_result_and_not_an_empty_dict(q):
    q.register('n', lambda p: None)
    q.enqueue('n', {})
    q.drain('w1')
    assert q.history()[0]['result'] is None


def test_an_idempotency_key_keeps_one_job_while_it_is_still_pending(q):
    a = q.enqueue('k', {}, key='wed')
    b = q.enqueue('k', {}, key='wed')
    assert a['id'] == b['id']
    assert q.pending('k') == 1


def test_the_same_key_is_free_again_once_the_job_finished(q):
    q.register('k', lambda p: 'ok')
    first = q.enqueue('k', {}, key='wed')
    q.drain('w1')
    again = q.enqueue('k', {}, key='wed')
    assert again['id'] != first['id']


def test_a_delayed_job_is_not_claimed_before_its_time(q):
    q.enqueue('later', {}, run_at=1000)
    assert q.claim('w1', at=999) == []
    assert len(q.claim('w1', at=1000)) == 1


def test_priority_decides_which_of_two_due_jobs_goes_first(q):
    q.enqueue('a', dict(n=1), priority=5, at=10)
    q.enqueue('b', dict(n=2), priority=1, at=10)
    assert q.claim('w1', n=2, at=20).attrgot('kind') == ['b', 'a']


def test_a_missing_handler_fails_the_job_rather_than_losing_it(q):
    j = q.enqueue('nobody', {})
    ran = q.drain('w1')
    assert ran[0]['status'] == 'error'
    assert 'no handler' in ran[0]['error']
    assert q.get(j['id'])['state'] == 'ready'


def test_a_raising_handler_retries_then_dead_letters_when_the_attempts_are_spent(db):
    q = Queue(db, max_attempts=2, base=0)
    q.register('bad', lambda p: 1/0)
    j = q.enqueue('bad', {}, at=100)
    assert q.drain('w1', at=100)[0]['status'] == 'error'
    assert q.get(j['id'])['state'] == 'ready'
    assert q.drain('w1', at=100) == []      # backoff never answers zero, so not in the same second
    assert q.drain('w1', at=200)[0]['status'] == 'error'
    assert q.get(j['id'])['state'] == 'dead'
    assert q.dead().attrgot('id') == [j['id']]


def test_a_dead_job_is_not_claimed_again_by_a_later_drain(db):
    q = Queue(db, max_attempts=1, base=0)
    q.register('bad', lambda p: 1/0)
    q.enqueue('bad', {})
    q.drain('w1')
    assert q.drain('w1') == []


def test_retry_puts_a_dead_job_back_with_its_attempts_reset(db):
    q = Queue(db, max_attempts=1, base=0)
    q.register('bad', lambda p: 1/0)
    j = q.enqueue('bad', {})
    q.drain('w1')
    back = q.retry(j['id'], at=100)
    assert back['state'] == 'ready' and back['attempt'] == 0 and back['error'] is None


def test_a_retry_exception_uses_the_delay_it_names(q):
    def wall(p): raise Retry('a bot wall', after=500)
    q.register('wall', wall)
    j = q.enqueue('wall', {}, at=10)
    assert q.drain('w1', at=10)[0]['status'] == 'retry'
    assert q.get(j['id'])['run_at'] == 510


def test_an_expired_lease_comes_back_to_the_queue(db):
    q = Queue(db, lease=0, base=0)
    q.enqueue('slow', {})
    assert len(q.claim('gone-away')) == 1
    assert len(q.reclaim()) == 1
    assert q.stats()['ready'] == 1


def test_a_worker_that_lost_its_lease_cannot_ack_the_job_somebody_else_now_holds(db):
    q = Queue(db, lease=0, base=0)
    q.enqueue('slow', {})
    mine = q.claim('slow-worker')[0]
    q.reclaim()
    q.claim('fast-worker')
    assert q.ack(mine)['state'] == 'lost'


def test_a_handler_whose_lease_was_taken_mid_run_is_recorded_as_lost(db):
    q = Queue(db, lease=0, base=0)
    def slow(p):
        q.reclaim()
        q.claim('somebody-else')
        return 'too late'
    q.register('slow', slow)
    q.enqueue('slow', {})
    assert q.drain('mine')[0]['status'] == 'lost'


def test_stats_and_pending_agree_with_what_is_in_the_table(q):
    q.register('ok', lambda p: 1)
    q.enqueue('ok', {})
    q.enqueue('ok', {}, run_at=10**10)
    q.drain('w1', limit=1)
    s = q.stats()
    assert s['done'] == 1 and s['ready'] == 1
    assert q.pending() == 1 and q.pending('ok') == 1


def test_purge_removes_finished_work_and_leaves_the_dead_letter_alone(db):
    q = Queue(db, max_attempts=1, base=0, keep=0)
    q.register('ok', lambda p: 1)
    q.register('bad', lambda p: 1/0)
    q.enqueue('ok', {})
    q.enqueue('bad', {})
    q.drain('w1')
    got = q.purge(before=10**10)
    assert got['jobs'] == 1 and got['runs'] == 2
    assert len(q.dead()) == 1


def test_backoff_doubles_and_then_stops_at_the_cap():
    assert backoff(1, base=10, jitter=0) == 10
    assert backoff(4, base=10, jitter=0) == 80
    assert backoff(50, base=10, cap=100, jitter=0) == 100


def test_backoff_jitter_spreads_jobs_that_failed_together():
    plain = backoff(3, base=10, jitter=0)
    got = {backoff(3, base=10) for _ in range(200)}
    assert len(got) > 100
    assert min(got) >= plain*0.75 and max(got) <= plain*1.25


def test_eight_processes_on_one_file_claim_every_job_exactly_once(filedb):
    q = Queue(vault(filedb))
    ids = {q.enqueue('work', dict(n=i))['id'] for i in range(400)}
    env = {**os.environ, 'PYTHONPATH': str(HERE.parent)}
    procs = [subprocess.Popen([sys.executable, str(HERE/'claim_worker.py'), filedb, f'w{i}', '7'],
                              stdout=subprocess.PIPE, text=True, env=env) for i in range(8)]
    got = []
    for p in procs:
        out, _ = p.communicate(timeout=120)
        assert p.returncode == 0, out
        got += json.loads(out.strip().splitlines()[-1])
    assert len(got) == len(set(got)) == 400
    assert set(got) == ids


def test_a_handler_asking_for_an_immediate_retry_still_waits_out_the_floor(db):
    q = Queue(db, max_attempts=5)
    q.register('wall', lambda p: (_ for _ in ()).throw(Retry('now please', after=0)))
    q.enqueue('wall', {}, at=10)
    # without a floor one drain re-claims the job it just failed and spends all five attempts
    assert len(q.drain('w1', at=10)) == 1
    assert q.stats()['ready'] == 1
    assert q.get(q.jobs()[0]['id'])['attempt'] == 1
