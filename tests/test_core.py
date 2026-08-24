"The vault, the row parsing, and what `Store` gives a subclass."
import pytest
from fastcore.all import xdumps

from pobblebonk.core import MAX_TEXT, Store, clip, mkid, now, row, rows, vault


class Demo(Store):
    name = 'demo'
    cols = dict(id=str, topic=str, payload=str, at=float)
    idx = ('CREATE INDEX IF NOT EXISTS demo_topic ON demo(topic, at)',)


def test_a_json_column_survives_the_round_trip_as_the_object_it_started_as():
    for o in ({'qty': 2}, [1, 2, 3], 'a string', 4.5, True, None):
        assert row(dict(id='x', payload=xdumps(o)))['payload'] == o


def test_a_column_never_set_and_a_column_set_to_nothing_read_back_the_same():
    assert row(dict(id='x', payload=None))['payload'] is None
    assert row(dict(id='x', payload=''))['payload'] is None
    assert row(dict(id='x', payload=xdumps(None)))['payload'] is None


def test_a_column_that_is_not_json_is_left_exactly_as_it_was():
    got = row(dict(id='x', topic='milk', at=1.5))
    assert got['topic'] == 'milk' and got['at'] == 1.5


def test_rows_parses_every_row_and_row_passes_none_through():
    assert row(None) is None
    assert rows([dict(id='a', payload=xdumps(1)), dict(id='b', payload=xdumps(2))]).attrgot('payload') == [1, 2]


def test_clipped_text_says_how_much_it_dropped_rather_than_dropping_it_quietly():
    assert clip('abcdef', 3) == 'abc\n... [3 more chars]'
    assert clip('abc', 3) == 'abc'
    assert clip(None) == ''
    assert len(clip('x'*(MAX_TEXT+50))) < MAX_TEXT + 40


def test_ids_are_short_and_do_not_collide_over_a_few_thousand():
    got = {mkid() for _ in range(5000)}
    assert len(got) == 5000
    assert all(len(i) == 12 for i in got)


def test_a_store_subclass_creates_its_table_and_its_indexes_on_first_use(db):
    Demo(db)
    made = {r['name'] for r in db.q("SELECT name FROM sqlite_master WHERE type IN ('table','index')")}
    assert 'demo' in made and 'demo_topic' in made


def test_opening_the_same_store_twice_is_harmless(db):
    Demo(db)
    Demo(db)
    assert Demo(db).q('SELECT * FROM demo') == []


def test_a_store_reads_back_parsed_rows_from_q_and_one(db):
    d = Demo(db)
    with d.txn(): d.t.insert(dict(id=mkid(), topic='milk', payload=xdumps({'qty': 2}), at=now()))
    assert d.one('SELECT * FROM demo WHERE topic=?', ['milk'])['payload'] == {'qty': 2}
    assert d.q('SELECT * FROM demo')[0]['payload'] == {'qty': 2}
    assert d.one('SELECT * FROM demo WHERE topic=?', ['nothing']) is None


def test_a_transaction_that_raises_leaves_no_row_behind(db):
    d = Demo(db)
    with pytest.raises(RuntimeError):
        with d.txn():
            d.t.insert(dict(id=mkid(), topic='eggs', payload=None, at=now()))
            raise RuntimeError('the document write failed')
    assert d.q('SELECT * FROM demo WHERE topic=?', ['eggs']) == []


def test_transactions_nest_so_one_store_can_write_inside_another(db):
    d = Demo(db)
    with d.txn():
        with d.txn(): d.t.insert(dict(id=mkid(), topic='a', payload=None, at=1.))
        d.t.insert(dict(id=mkid(), topic='b', payload=None, at=2.))
    assert len(d.q('SELECT * FROM demo')) == 2


def test_the_vault_opens_on_disk_and_keeps_what_was_written(filedb):
    d = Demo(vault(filedb))
    with d.txn(): d.t.insert(dict(id='kept', topic='milk', payload=xdumps([1]), at=1.))
    again = Demo(vault(filedb))
    assert again.one('SELECT * FROM demo WHERE id=?', ['kept'])['payload'] == [1]


def test_the_vault_opens_without_the_search_extensions_so_a_tick_pays_nothing_for_search(db):
    # no usearch functions registered: this is what makes `pob tick` cheap once a minute
    with pytest.raises(Exception): db.q('SELECT usearch_version()')
