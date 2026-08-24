"Durations, wall clocks and the catch-up policy."
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from pobblebonk.clock import (CATCHUP, LATE_AFTER, MAX_FIRES, due_fires, late, next_fire, secs,
                              valid_cron, valid_tz)

KOL, NY = ZoneInfo('Asia/Kolkata'), ZoneInfo('America/New_York')


def at(y, m, d, h, mi=0, tz=KOL): return datetime(y, m, d, h, mi, tzinfo=tz).timestamp()


def test_a_duration_is_read_from_a_number_or_from_the_way_a_person_writes_it():
    assert secs(90) == 90 and secs('90') == 90
    assert secs('30m') == 1800
    assert secs('6h') == 21600
    assert secs('1w') == 604800
    assert secs('1h30m') == 5400
    assert secs('2 days') == 172800
    assert secs('2D') == 172800


def test_a_duration_that_cannot_be_read_is_refused_rather_than_guessed():
    for bad in ('soon', '', 'every friday', None):
        with pytest.raises((ValueError, TypeError)): secs(bad)


def test_what_cannot_be_read_is_caught_when_it_is_registered():
    assert valid_cron('0 17 * * 1-5') and not valid_cron('every friday')
    assert valid_tz('Asia/Kolkata') and not valid_tz('Mars/Olympus')


def test_five_pm_on_a_weekday_is_five_pm_in_the_zone_it_was_written_in():
    got = datetime.fromtimestamp(next_fire('0 17 * * 1-5', 'Asia/Kolkata', at(2026, 8, 25, 9)), KOL)
    assert (got.hour, got.minute, got.day) == (17, 0, 25)


def test_a_weekday_schedule_looked_at_on_a_friday_evening_lands_on_the_monday():
    fri = at(2026, 8, 28, 19)
    got = datetime.fromtimestamp(next_fire('0 17 * * 1-5', 'Asia/Kolkata', fri), KOL)
    assert (got.weekday(), got.day, got.hour) == (0, 31, 17)


def test_the_wall_clock_hour_holds_across_a_daylight_saving_change():
    for t in (at(2026, 3, 6, 12, tz=NY), at(2026, 3, 10, 12, tz=NY)):
        got = datetime.fromtimestamp(next_fire('0 17 * * *', 'America/New_York', t), NY)
        assert (got.hour, got.minute) == (17, 0)


def test_nothing_due_costs_no_arithmetic_and_moves_nothing():
    assert due_fires(dict(next_run=200., every=10), at=100) == ([], 200.)


def test_the_three_catch_up_policies_differ_only_in_what_they_run():
    s = dict(next_run=100., every=10)
    assert due_fires(s, 135, 'once') == ([130.], 140.)
    assert due_fires(s, 135, 'all') == ([100., 110., 120., 130.], 140.)
    assert due_fires(s, 135, 'skip') == ([], 140.)
    assert len({due_fires(s, 135, c)[1] for c in CATCHUP}) == 1


def test_a_single_fire_exactly_on_time_runs_once_under_every_policy():
    s = dict(next_run=100., every=10)
    for c in ('once', 'all'): assert due_fires(s, 100, c) == ([100.], 110.)


def test_nine_days_of_a_shut_laptop_is_nine_missed_fires_on_a_wall_clock():
    s = dict(next_run=at(2026, 8, 15, 17), cron='0 17 * * *', tz='Asia/Kolkata')
    got, nxt = due_fires(s, at(2026, 8, 24, 9), 'all')
    assert len(got) == 9
    assert due_fires(s, at(2026, 8, 24, 9), 'once')[0] == got[-1:]
    assert datetime.fromtimestamp(nxt, KOL).day == 24


def test_a_by_the_minute_schedule_left_for_a_year_is_jumped_and_not_walked():
    got, nxt = due_fires(dict(next_run=0., cron='* * * * *'), at=365*86400, catchup='all')
    assert len(got) == MAX_FIRES
    assert nxt > 365*86400


def test_an_interval_schedule_left_for_a_year_is_also_capped():
    got, nxt = due_fires(dict(next_run=0., every=60), at=365*86400, catchup='all')
    assert len(got) == MAX_FIRES
    assert nxt > 365*86400


def test_an_interval_is_read_the_same_way_a_person_wrote_it():
    assert due_fires(dict(next_run=0., every='30m'), at=1800, catchup='once') == ([1800.], 3600.)


def test_a_fire_is_late_only_once_the_machine_was_plainly_off():
    assert not late(100, 100)
    assert not late(100, 100 + LATE_AFTER)
    assert late(100, 100 + LATE_AFTER + 1)
