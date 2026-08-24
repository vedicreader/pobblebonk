"The four tables together, and the tick that drives them."
from pobblebonk.core import vault
from pobblebonk.lists import Lists
from pobblebonk.pob import Pob
from pobblebonk.run import FakeRunner
from pobblebonk.schedule import FIRE


def test_everything_lands_in_one_vault_so_another_library_can_open_it_too(filedb):
    pob = Pob(filedb)
    pob.lists.add('shopping', 'milk')
    tables = {r['name'] for r in pob.db.q("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'jobs', 'job_runs', 'pob_items', 'pob_notes', 'pob_reads', 'pob_schedules'} <= tables
    assert Lists(vault(filedb)).count('shopping') == 1


def test_a_vault_something_else_opened_is_used_rather_than_a_second_one(db):
    pob = Pob(db=db)
    assert pob.db is db
    assert pob.queue.db is db and pob.inbox.db is db


def test_a_document_write_and_the_job_it_causes_commit_together(pob):
    pob.db.t.docs.create(id=str, text=str, pk='id', if_not_exists=True)
    try:
        with pob.queue.txn():
            pob.db.t.docs.insert(dict(id='d1', text='a paper'))
            pob.queue.enqueue('index', dict(doc='d1'))
            raise RuntimeError('the parse failed')
    except RuntimeError: pass
    assert pob.db.q('SELECT * FROM docs') == []
    assert pob.queue.pending('index') == 0


def test_the_tick_reclaims_fires_and_runs_in_that_order(db):
    pob = Pob(db=db, lease=1, base=0).attach(FakeRunner())
    pob.queue.enqueue('other', {}, at=0)
    pob.queue.claim('gone-away', at=0)          # its lease runs out at 1, well before the tick at 10
    pob.queue.register('other', lambda p: 'ok')
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    out = pob.tick(at=10)
    assert len(out.reclaimed) == 1
    assert len(out.fired) == 1
    assert {r['kind'] for r in out.ran} == {FIRE}
    # a reclaimed job waits at least a second, so it goes on the next tick rather than this one
    assert pob.queue.get(out.reclaimed[0]['id'])['state'] == 'ready'
    assert {r['kind'] for r in pob.tick(at=100).ran} == {'other'}


def test_a_dry_tick_queues_the_work_and_runs_none_of_it(pob):
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    out = pob.tick(at=10, run=False)
    assert len(out.fired) == 1 and out.ran == []
    assert pob.queue.pending(FIRE) == 1


def test_status_reports_the_whole_vault_in_one_object(pob):
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    pob.scheds.add('news', 'The news.', every='1h', start=0)
    pob.scheds.pause('news')
    pob.lists.add('shopping', 'milk')
    pob.inbox.note('fire', 'a', 'b')
    s = pob.status()
    assert s.schedules == 2 and s.paused == 1
    assert s.topics == dict(shopping=1)
    assert s.notes == 1


def test_a_dead_fire_is_named_by_its_schedule_and_not_by_the_queue_kind(db):
    pob = Pob(db=db, max_attempts=1, base=0).attach(FakeRunner([RuntimeError('down')]))
    pob.scheds.add('the wednesday cart', 'Fill my cart.', every='1h', start=0)
    pob.tick(at=10)
    assert pob.inbox.notes(kind='dead')[0]['title'] == 'the wednesday cart gave up after 1 tries'


def test_a_dead_job_that_was_never_a_fire_is_named_by_its_kind(pob):
    pob.queue.max_attempts = 1
    pob.queue.base = 0
    pob.queue.register('index', lambda p: 1/0)
    pob.queue.enqueue('index', {}, at=0)
    pob.tick(at=10)
    assert pob.inbox.notes(kind='dead')[0]['title'] == 'index gave up after 1 tries'


def test_the_repr_says_what_is_in_there_without_a_query_from_the_caller(pob):
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    assert 'Pob(1 schedules' in repr(pob)
