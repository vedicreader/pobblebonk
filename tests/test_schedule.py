"Standing instructions, the tick, and what happens when two of them race."
import json, os, subprocess, sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pobblebonk.core import vault
from pobblebonk.inbox import Inbox
from pobblebonk.lists import Lists
from pobblebonk.queue import Queue
from pobblebonk.schedule import FIRE, Schedules

HERE = Path(__file__).parent
KOL = ZoneInfo('Asia/Kolkata')


def at(d, h, m=0): return datetime(2026, 8, d, h, m, tzinfo=KOL).timestamp()


@pytest.fixture
def bits(db): return Schedules(db), Queue(db), Inbox(db), Lists(db)


def test_a_schedule_that_cannot_be_read_is_refused_when_it_is_written(bits):
    sch, *_ = bits
    for kw, why in ((dict(cron='every friday'), 'not a cron'),
                    (dict(cron='0 17 * * *', tz='Mars/Olympus'), 'not a time zone'),
                    (dict(), 'exactly one'),
                    (dict(every='1h', cron='0 17 * * *'), 'exactly one'),
                    (dict(every='1h', catchup='maybe'), 'catchup must be'),
                    (dict(every='1h', policy='ask'), 'policy must be')):
        with pytest.raises(ValueError, match=why): sch.add('bad', 'do a thing', **kw)


def test_a_schedule_with_no_instruction_is_refused_because_it_is_all_a_fire_gets(bits):
    sch, *_ = bits
    with pytest.raises(ValueError, match='needs a prompt'): sch.add('empty', '   ', every='1h')


def test_two_schedules_cannot_share_a_name(bits):
    sch, *_ = bits
    sch.add('cart', 'fill it', every='1h')
    with pytest.raises(Exception): sch.add('cart', 'fill it again', every='1h')


def test_a_new_schedule_is_not_due_until_its_first_fire(bits):
    sch, q, *_ = bits
    sch.add('roundup', 'roundup my commits', cron='0 17 * * *', tz='Asia/Kolkata', at=at(24, 9))
    assert sch.due(at(24, 9)) == []
    assert len(sch.due(at(24, 17, 1))) == 1


def test_an_interval_schedule_first_fires_one_interval_from_now(bits):
    sch, *_ = bits
    s = sch.add('poll', 'check the feed', every='30m', at=1000)
    assert s['next_run'] == 1000 + 1800


def test_a_tick_queues_one_fire_and_moves_the_clock_on(bits):
    sch, q, ib, ls = bits
    sch.add('roundup', 'roundup my commits', cron='0 17 * * *', tz='Asia/Kolkata', at=at(24, 9))
    out = sch.tick(q, at=at(24, 17, 1))
    assert len(out.fired) == 1
    assert q.pending(FIRE) == 1
    assert datetime.fromtimestamp(sch.get('roundup')['next_run'], KOL).day == 25


def test_a_fire_carries_only_which_schedule_which_fire_and_whether_it_is_late(bits):
    sch, q, *_ = bits
    s = sch.add('roundup', 'r', cron='0 17 * * *', tz='Asia/Kolkata', start=at(15, 17))
    sch.tick(q, at=at(24, 9))
    p = q.jobs(kind=FIRE)[0]['payload']
    assert sorted(p) == ['fire_at', 'late', 'schedule']
    assert p['schedule'] == s['id'] and p['late'] is True


def test_a_second_tick_in_the_same_minute_queues_nothing_more(bits):
    sch, q, *_ = bits
    sch.add('roundup', 'r', cron='0 17 * * *', tz='Asia/Kolkata', at=at(24, 9))
    sch.tick(q, at=at(24, 17, 1))
    assert sch.tick(q, at=at(24, 17, 2)).fired == []
    assert q.pending(FIRE) == 1


def test_catching_up_runs_the_latest_missed_fire_by_default_and_all_of_them_on_request(bits):
    sch, q, *_ = bits
    sch.add('daily', 'r', cron='0 17 * * *', tz='Asia/Kolkata', start=at(15, 17))
    sch.add('every one', 'r', cron='0 18 * * *', tz='Asia/Kolkata', catchup='all', start=at(15, 18))
    out = sch.tick(q, at=at(24, 9))
    assert len(out.fired) == 1 + 9


def test_a_paused_schedule_does_not_fire_and_resuming_it_starts_from_the_next_one(bits):
    sch, q, *_ = bits
    sch.add('roundup', 'r', cron='0 17 * * *', tz='Asia/Kolkata', at=at(24, 9))
    sch.pause('roundup')
    assert sch.tick(q, at=at(24, 17, 1)).fired == []
    sch.resume('roundup', at=at(24, 18))
    assert sch.get('roundup')['paused'] == 0
    assert datetime.fromtimestamp(sch.get('roundup')['next_run'], KOL).day == 25


def test_a_dropped_schedule_stops_firing_and_leaves_the_notes_it_already_left(bits):
    sch, q, ib, _ = bits
    s = sch.add('roundup', 'r', every='1h', start=0)
    ib.note('fire', 'roundup', 'an answer', ref=s['id'])
    assert sch.drop('roundup') is True
    assert sch.tick(q, at=10).fired == []
    assert ib.count('fire') == 1


def test_a_schedule_needing_an_empty_list_says_so_once_and_queues_nothing(bits):
    sch, q, ib, ls = bits
    sch.add('news', 'the news from my interests', cron='0 7 * * *', tz='Asia/Kolkata',
            needs='interests', at=at(24, 18))
    have = ls.count
    out = sch.tick(q, at=at(25, 7, 1), inbox=ib, have=have)
    assert out.blocked == ['news']
    assert q.pending(FIRE) == 0
    assert ib.notes(kind='blocked')[0]['title'] == 'news needs your interests list'
    assert sch.tick(q, at=at(26, 7, 1), inbox=ib, have=have).blocked == []
    assert ib.count('blocked') == 1


def test_filling_the_list_starts_the_schedule_again_without_anybody_resuming_it(bits):
    sch, q, ib, ls = bits
    sch.add('news', 'the news', cron='0 7 * * *', tz='Asia/Kolkata', needs='interests', at=at(24, 18))
    sch.tick(q, at=at(25, 7, 1), inbox=ib, have=ls.count)
    ls.add('interests', 'sanskrit grammar')
    out = sch.tick(q, at=at(26, 7, 1), inbox=ib, have=ls.count)
    assert out.freed == ['news'] and len(out.fired) == 1
    assert sch.get('news')['blocked'] is None


def test_a_schedule_with_needs_still_fires_when_nobody_gave_the_tick_a_way_to_check(bits):
    sch, q, ib, _ = bits
    sch.add('news', 'the news', every='1h', needs='interests', start=0)
    assert len(sch.tick(q, at=10, inbox=ib).fired) == 1


def test_the_session_a_schedule_runs_in_is_remembered(bits):
    sch, *_ = bits
    sch.add('roundup', 'r', every='1h')
    assert sch.remember('roundup', 'sess-7')['session'] == 'sess-7'
    assert sch.get('roundup')['session'] == 'sess-7'


def test_resuming_forgets_that_a_schedule_was_ever_blocked(bits):
    sch, q, ib, ls = bits
    sch.add('news', 'the news', every='1h', needs='interests', start=0)
    sch.tick(q, at=10, inbox=ib, have=ls.count)
    assert sch.get('news')['blocked'] == 'interests'
    assert sch.resume('news', at=10)['blocked'] is None


def test_a_schedule_is_found_by_id_as_well_as_by_name(bits):
    sch, *_ = bits
    s = sch.add('roundup', 'r', every='1h')
    assert sch.get(s['id'])['name'] == 'roundup'
    assert sch.get('nothing at all') is None


def test_two_processes_ticking_one_vault_queue_the_fire_exactly_once(filedb):
    db = vault(filedb)
    sch, q = Schedules(db), Queue(db)
    sch.add('roundup', 'roundup my commits', cron='0 17 * * *', tz='Asia/Kolkata', start=at(24, 17))
    when = at(24, 17, 1)
    env = {**os.environ, 'PYTHONPATH': str(HERE.parent)}
    procs = [subprocess.Popen([sys.executable, str(HERE/'tick_worker.py'), filedb, str(when)],
                              stdout=subprocess.PIPE, text=True, env=env) for _ in range(4)]
    fired = []
    for p in procs:
        out, _ = p.communicate(timeout=120)
        assert p.returncode == 0, out
        fired += json.loads(out.strip().splitlines()[-1])['fired']
    assert q.pending(FIRE) == 1
    assert len(set(fired)) == 1                 # every tick that saw it saw the same one job
    assert len(q.jobs(kind=FIRE)) == 1
