"`AcpRunner` against a real ACP agent over the real wire protocol."
import os, sys
from pathlib import Path

import pytest

from pobblebonk.pob import Pob
from pobblebonk.run import AcpRunner

pytest.importorskip('acp')

HERE = Path(__file__).parent
STUB = str(HERE/'acp_stub.py')


def runner(policy='read', **env):
    "An `AcpRunner` pointed at the stub agent, with this repo importable inside it."
    return AcpRunner(sys.executable, args=(STUB,), policy=policy,
                     env={**os.environ, 'PYTHONPATH': str(HERE.parent), **env}, timeout=90)


def test_a_fire_reaches_a_real_agent_and_its_answer_comes_back(tmp_path):
    got = runner()('roundup my commits', cwd=str(tmp_path))
    assert 'roundup my commits' in got.text
    assert got.session == 'stub-1'
    assert got.stop == 'end_turn'
    assert got.refused == []


def test_a_prompt_with_no_session_starts_a_new_conversation_every_time(tmp_path):
    r = runner()
    assert r('one', cwd=str(tmp_path)).text.startswith('turn 1 of stub-1')
    assert r('two', cwd=str(tmp_path)).text.startswith('turn 1 of stub-1')


def test_naming_the_session_continues_the_conversation_it_names(tmp_path):
    r = runner()
    first = r('day one', cwd=str(tmp_path))
    again = r('day two', session=first.session, cwd=str(tmp_path))
    assert again.session == first.session
    assert again.text.startswith('turn 1 of stub-1')     # a fresh process, but the same named session


def test_a_session_the_agent_cannot_find_starts_a_new_one_rather_than_losing_the_fire(tmp_path):
    got = runner(STUB_LOAD='fail')('the fire', session='a-session-from-last-month',
                                   cwd=str(tmp_path))
    assert got.session == 'stub-1'
    assert 'the fire' in got.text


def test_a_read_policy_refuses_a_write_and_records_what_it_refused(tmp_path):
    got = runner('read', STUB_TOOL='1')('fix the import', cwd=str(tmp_path))
    assert 'the write was refused' in got.text
    assert got.refused == ['create_file (edit)']


def test_a_write_policy_allows_the_same_write(tmp_path):
    got = runner('write', STUB_TOOL='1')('fix the import', cwd=str(tmp_path))
    assert 'the write was allowed' in got.text
    assert got.refused == []


def test_what_a_fire_refused_is_written_into_the_note_a_person_reads(tmp_path):
    pob = Pob().attach(runner('read', STUB_TOOL='1'), cwd=str(tmp_path))
    pob.scheds.add('cart', 'Fill my cart.', every='1h', start=0)
    out = pob.tick(at=10)
    assert out.ran[0]['status'] == 'ok'
    note = pob.drain('leela')[0]
    assert 'Refused under the `read` policy: create_file (edit)' in note['body']
    assert note['meta']['refused'] == ['create_file (edit)']


def test_a_whole_schedule_runs_against_a_real_agent_and_keeps_its_session(tmp_path):
    pob = Pob().attach(runner(), cwd=str(tmp_path))
    pob.lists.add('shopping', 'oat milk')
    pob.scheds.add('cart', 'Fill my cart from the shopping list.', every='1h',
                   needs='shopping', policy='write', start=0)
    out = pob.tick(at=10)
    assert out.ran[0]['status'] == 'ok'
    assert pob.scheds.get('cart')['session'] == 'stub-1'
    assert pob.lists.count('shopping') == 0
    assert 'oat milk' in pob.drain('leela')[0]['body']


def test_a_fire_that_takes_too_long_is_cut_off_rather_than_holding_the_tick(tmp_path):
    r = AcpRunner(sys.executable, args=['-c', 'import time; time.sleep(30)'], timeout=2,
                  env={**os.environ, 'PYTHONPATH': str(HERE.parent)})
    with pytest.raises(Exception): r('anything', cwd=str(tmp_path))
