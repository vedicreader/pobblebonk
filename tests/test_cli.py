"The command line, driven the way cron and a person drive it."
import os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent


def pob(vault, *args):
    "Run `pob` against `vault` and give back its output."
    env = {**os.environ, 'PYTHONPATH': str(HERE.parent)}
    r = subprocess.run([sys.executable, '-m', 'pobblebonk.cli', *args, '--db', str(vault)],
                       capture_output=True, text=True, env=env, timeout=120)
    return r


def test_status_on_a_vault_that_does_not_exist_yet_makes_one_and_says_it_is_empty(tmp_path):
    r = pob(tmp_path/'new'/'vault.db', 'status')
    assert r.returncode == 0, r.stderr
    assert '0 schedules' in r.stdout
    assert (tmp_path/'new'/'vault.db').exists()


def test_a_schedule_added_by_hand_shows_up_in_the_listing(filedb):
    assert pob(filedb, 'add', '--name', 'cart', '--prompt', 'Fill my cart.',
               '--cron', '0 20 * * 3', '--tz', 'Asia/Kolkata', '--needs', 'shopping',
               '--policy', 'write').returncode == 0
    out = pob(filedb, 'ls').stdout
    assert 'cart' in out and '0 20 * * 3' in out and 'shopping' in out and 'write' in out


def test_a_schedule_that_cannot_be_read_fails_rather_than_being_written(filedb):
    r = pob(filedb, 'add', '--name', 'bad', '--prompt', 'x', '--cron', 'every friday')
    assert r.returncode != 0
    assert 'not a cron' in r.stderr
    assert '0 schedules' in pob(filedb, 'status').stdout


def test_an_item_goes_on_a_list_and_the_list_is_counted(filedb):
    assert pob(filedb, 'item', '--topic', 'shopping', '--text', 'oat milk').returncode == 0
    pob(filedb, 'item', '--topic', 'shopping', '--text', 'yoghurt')
    assert 'shopping: 2 open' in pob(filedb, 'items').stdout
    assert 'oat milk' in pob(filedb, 'items', '--topic', 'shopping').stdout


def test_a_dry_tick_queues_the_fire_and_runs_nothing(filedb):
    pob(filedb, 'add', '--name', 'cart', '--prompt', 'Fill my cart.', '--every', '1s')
    out = pob(filedb, 'tick', '--dry').stdout
    assert '1 fired, 0 ran' in out
    assert '1 ready' in pob(filedb, 'status').stdout


def test_pausing_and_resuming_shows_in_the_listing(filedb):
    pob(filedb, 'add', '--name', 'cart', '--prompt', 'Fill my cart.', '--every', '1h')
    assert pob(filedb, 'pause', '--name', 'cart').stdout.strip().endswith('P')
    assert '1 paused' in pob(filedb, 'status').stdout
    assert not pob(filedb, 'resume', '--name', 'cart').stdout.strip().endswith('P')


def test_dropping_a_schedule_says_so_and_says_when_there_was_none(filedb):
    pob(filedb, 'add', '--name', 'cart', '--prompt', 'Fill my cart.', '--every', '1h')
    assert 'dropped' in pob(filedb, 'drop', '--name', 'cart').stdout
    assert 'no such schedule' in pob(filedb, 'drop', '--name', 'cart').stdout


def test_notes_are_shown_once_per_reader(filedb):
    from pobblebonk.pob import Pob
    Pob(filedb).inbox.note('fire', 'git roundup', '9 commits')
    assert 'git roundup' in pob(filedb, 'notes').stdout
    assert 'git roundup' not in pob(filedb, 'notes').stdout
    assert 'git roundup' in pob(filedb, 'notes', '--reader', 'phone').stdout


def test_an_unknown_command_names_the_ones_that_exist(filedb):
    r = pob(filedb, 'wednesday')
    assert 'unknown command' in r.stderr and 'tick' in r.stderr


def test_a_tick_with_nothing_due_is_quiet_and_cheap(filedb):
    out = pob(filedb, 'tick').stdout
    assert out.strip() == '0 fired, 0 ran, 0 blocked, 0 reclaimed'
