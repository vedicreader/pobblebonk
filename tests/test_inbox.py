"How an answer reaches a person, and why every reader sees it once."
from pobblebonk.inbox import Inbox


def test_a_note_is_stored_with_its_metadata_and_given_a_rising_sequence(db):
    ib = Inbox(db)
    a = ib.note('fire', 'git roundup', '9 commits', ref='sch1', meta=dict(late=True), at=1)
    b = ib.note('fire', 'cart', 'added 6', at=2)
    assert (a['seq'], b['seq']) == (1, 2)
    assert a['meta'] == {'late': True} and a['ref'] == 'sch1' and a['at'] == 1


def test_a_reader_starts_at_nothing_and_reading_does_not_move_it(db):
    ib = Inbox(db)
    ib.note('fire', 'a')
    assert ib.seen('leela') == 0
    assert len(ib.unread('leela')) == 1
    assert len(ib.unread('leela')) == 1


def test_draining_gives_every_note_once_to_the_reader_that_drained(db):
    ib = Inbox(db)
    ib.note('fire', 'a')
    ib.note('blocked', 'b')
    assert ib.drain('leela').attrgot('title') == ['a', 'b']
    assert ib.drain('leela') == []


def test_one_reader_draining_does_not_consume_the_notes_for_another(db):
    ib = Inbox(db)
    ib.note('fire', 'a')
    ib.note('fire', 'b')
    assert len(ib.drain('leela')) == 2
    assert len(ib.drain('terminal')) == 2
    assert len(ib.drain('pycharm')) == 2


def test_a_note_left_later_reaches_every_reader_that_was_already_caught_up(db):
    ib = Inbox(db)
    ib.note('fire', 'a')
    for r in ('leela', 'terminal'): ib.drain(r)
    ib.note('fire', 'b')
    for r in ('leela', 'terminal'): assert ib.drain(r).attrgot('title') == ['b']


def test_a_cursor_never_moves_backwards_so_a_reader_cannot_be_shown_a_note_twice(db):
    ib = Inbox(db)
    for t in 'abc': ib.note('fire', t)
    ib.drain('leela')
    assert ib.mark_read('leela', 1) == 3
    assert ib.drain('leela') == []


def test_a_cursor_cannot_be_pushed_past_the_newest_note(db):
    ib = Inbox(db)
    ib.note('fire', 'a')
    assert ib.mark_read('leela', 999) == 1
    ib.note('fire', 'b')
    assert ib.drain('leela').attrgot('title') == ['b']


def test_marking_a_reader_on_an_empty_inbox_is_allowed(db):
    assert Inbox(db).mark_read('leela') == 0


def test_a_drain_takes_at_most_the_limit_and_leaves_the_rest(db):
    ib = Inbox(db)
    for i in range(5): ib.note('fire', str(i))
    assert ib.drain('leela', limit=2).attrgot('title') == ['0', '1']
    assert ib.drain('leela', limit=2).attrgot('title') == ['2', '3']
    assert ib.drain('leela').attrgot('title') == ['4']


def test_notes_can_be_listed_by_kind_and_by_what_they_came_from(db):
    ib = Inbox(db)
    ib.note('fire', 'a', ref='sch1')
    ib.note('blocked', 'b', ref='sch2')
    ib.note('fire', 'c', ref='sch1')
    assert ib.notes(kind='fire').attrgot('title') == ['c', 'a']       # newest first
    assert ib.notes(ref='sch2').attrgot('title') == ['b']
    assert ib.count() == 3 and ib.count('fire') == 2


def test_a_long_answer_is_clipped_and_a_long_title_more_so(db):
    ib = Inbox(db)
    n = ib.note('fire', 'x'*900, 'y'*40_000)
    assert len(n['title']) < 350 and len(n['body']) < 20_100


def test_purging_old_notes_leaves_a_reader_that_had_read_past_them_alone(db):
    ib = Inbox(db)
    ib.note('fire', 'old', at=1)
    ib.drain('leela')
    ib.note('fire', 'new', at=1000)
    assert ib.purge(before=500) == 1
    assert ib.drain('leela').attrgot('title') == ['new']
