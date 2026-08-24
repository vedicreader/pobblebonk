"The prompt a fire sends, and what the handler does with what came back."
import pytest

from pobblebonk.inbox import Inbox
from pobblebonk.lists import Lists
from pobblebonk.pob import Pob
from pobblebonk.queue import Queue
from pobblebonk.run import FakeRunner, attach, fire_handler, prompt_for
from pobblebonk.schedule import FIRE, Schedules


def test_a_prompt_with_no_list_is_the_instruction_and_nothing_else():
    assert prompt_for(dict(name='cart', prompt='Fill my cart.', needs=None)) == 'Fill my cart.'


def test_a_prompt_carries_the_list_it_is_meant_to_work_from():
    got = prompt_for(dict(name='cart', prompt='Fill my cart.', needs='shopping'),
                     items=[dict(text='oat milk'), dict(text='yoghurt')], fire_at=1)
    assert 'shopping list holds 2 item(s)' in got
    assert '- oat milk' in got and '- yoghurt' in got


def test_a_prompt_names_the_fire_it_is_for_and_says_when_it_is_late():
    on_time = prompt_for(dict(name='cart', prompt='Fill.', needs=None), fire_at=1, is_late=False)
    behind = prompt_for(dict(name='cart', prompt='Fill.', needs=None), fire_at=1, is_late=True)
    assert 'run of "cart"' in on_time and 'running late' not in on_time
    assert 'running late' in behind


def test_the_fake_runner_records_what_it_was_asked_and_answers_in_order():
    r = FakeRunner(['first', 'second'])
    assert r('a').text == 'first'
    assert r('b', session='s1').text == 'second'
    assert r('c').text == 'ok'
    assert [a.prompt for a in r.asked] == ['a', 'b', 'c']
    assert r.asked[1].session == 's1'


def test_the_fake_runner_hands_back_the_session_it_was_given_and_invents_one_otherwise():
    r = FakeRunner(session='made-up')
    assert r('a').session == 'made-up'
    assert r('a', session='given').session == 'given'


def test_a_whole_fire_leaves_a_note_uses_the_list_and_keeps_the_session(pob):
    pob.attach(FakeRunner(['added 6 items, no oat milk'], session='cart-1'))
    pob.lists.add('shopping', 'oat milk')
    pob.scheds.add('cart', 'Fill my cart.', every='1h', needs='shopping', start=0)
    out = pob.tick(at=10)
    assert out.ran[0]['status'] == 'ok'
    assert out.ran[0]['result'] == dict(text='added 6 items, no oat milk', items=1,
                                        session='cart-1', refused=[])
    assert pob.drain('leela')[0]['body'] == 'added 6 items, no oat milk'
    assert pob.lists.count('shopping') == 0
    assert pob.scheds.get('cart')['session'] == 'cart-1'


def test_the_next_fire_continues_the_session_the_last_one_kept(pob):
    r = FakeRunner(session='cart-1')
    pob.attach(r)
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    pob.tick(at=10)
    pob.tick(at=10_000)
    assert r.asked[0].session is None
    assert r.asked[1].session == 'cart-1'


def test_a_fire_that_raises_keeps_the_list_and_reports_nothing_as_an_answer(pob):
    pob.attach(FakeRunner([RuntimeError('the shop was down')]))
    pob.lists.add('shopping', 'milk')
    pob.scheds.add('cart', 'Fill my cart.', every='1h', needs='shopping', start=0)
    out = pob.tick(at=10)
    assert out.ran[0]['status'] == 'error'
    assert 'the shop was down' in out.ran[0]['error']
    assert pob.lists.count('shopping') == 1
    assert pob.inbox.count('fire') == 0


def test_a_list_emptied_between_the_tick_and_the_run_is_skipped_and_not_failed(pob):
    pob.attach(FakeRunner())
    i = pob.lists.add('shopping', 'milk')
    pob.scheds.add('cart', 'Fill my cart.', every='1h', needs='shopping', start=0)
    pob.tick(at=10, run=False)
    pob.lists.used([i['id']])
    got = pob.queue.drain('w1', at=10)
    assert got[0]['status'] == 'skipped'
    assert got[0]['result']['why'] == 'the shopping list is empty'
    assert pob.inbox.count('fire') == 0


def test_a_fire_whose_schedule_was_dropped_is_skipped_rather_than_failing(pob):
    pob.attach(FakeRunner())
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    pob.tick(at=10, run=False)
    pob.scheds.drop('cart')
    got = pob.queue.drain('w1', at=10)
    assert got[0]['status'] == 'skipped'
    assert got[0]['result']['why'] == 'the schedule was dropped'


def test_a_handler_can_be_built_without_lists_at_all(db):
    sch, q, ib = Schedules(db), Queue(db), Inbox(db)
    q.register(FIRE, fire_handler(FakeRunner(['done']), sch, ib))
    sch.add('roundup', 'roundup my commits', every='1h', start=0)
    sch.tick(q, at=10)
    assert q.drain('w1', at=10)[0]['status'] == 'ok'
    assert ib.notes()[0]['body'] == 'done'


def test_a_schedule_with_no_runner_attached_dead_letters_and_says_so(db):
    pob = Pob(db=db, max_attempts=1, base=0)
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    pob.tick(at=10)
    assert len(pob.queue.dead()) == 1
    assert pob.inbox.notes(kind='dead')[0]['title'] == 'cart gave up after 1 tries'
