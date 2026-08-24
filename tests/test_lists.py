"The lists you add to over a week, and who is allowed to empty them."
from pobblebonk.lists import MAX_ITEM, Lists


def test_items_come_back_oldest_first_with_their_metadata_parsed(db):
    ls = Lists(db)
    ls.add('shopping', 'yoghurt', meta=dict(photo='img_2201.heic'), at=1)
    ls.add('shopping', 'oat milk', at=2)
    assert ls.items('shopping').attrgot('text') == ['yoghurt', 'oat milk']
    assert ls.items('shopping')[0]['meta'] == {'photo': 'img_2201.heic'}


def test_lists_do_not_see_each_other(db):
    ls = Lists(db)
    ls.add('shopping', 'milk')
    ls.add('interests', 'sanskrit grammar')
    assert ls.count('shopping') == 1 and ls.count('interests') == 1
    assert ls.items('shopping').attrgot('text') == ['milk']


def test_the_same_thing_sent_twice_is_one_item(db):
    ls = Lists(db)
    a = ls.add('shopping', 'yoghurt', key='img_2201.heic')
    b = ls.add('shopping', 'yoghurt again', key='img_2201.heic')
    assert a['id'] == b['id']
    assert ls.count('shopping') == 1


def test_the_same_key_is_free_again_once_the_item_was_used(db):
    ls = Lists(db)
    a = ls.add('shopping', 'yoghurt', key='img_2201.heic')
    ls.used([a['id']], by='cart')
    b = ls.add('shopping', 'yoghurt', key='img_2201.heic')
    assert b['id'] != a['id']
    assert ls.count('shopping') == 1


def test_the_same_key_on_two_lists_is_two_items(db):
    ls = Lists(db)
    a = ls.add('shopping', 'x', key='k')
    b = ls.add('interests', 'x', key='k')
    assert a['id'] != b['id']


def test_reading_a_list_does_not_empty_it_so_a_failed_run_loses_nothing(db):
    ls = Lists(db)
    ls.add('shopping', 'milk')
    ls.add('shopping', 'bread')
    got = ls.items('shopping')
    assert ls.count('shopping') == 2
    assert ls.items('shopping').attrgot('id') == got.attrgot('id')


def test_only_the_work_that_finished_marks_items_done(db):
    ls = Lists(db)
    ls.add('shopping', 'milk')
    ls.add('shopping', 'bread')
    got = ls.items('shopping')
    assert ls.used(got.attrgot('id'), by='cart', at=99) == 2
    assert ls.count('shopping') == 0
    assert ls.history('shopping').attrgot('used_by') == ['cart', 'cart']
    assert all(i['used_at'] == 99 for i in ls.history('shopping'))


def test_marking_the_same_items_used_twice_counts_them_once(db):
    ls = Lists(db)
    got = [ls.add('shopping', 'milk')['id']]
    assert ls.used(got) == 1
    assert ls.used(got) == 0


def test_marking_nothing_used_is_allowed_and_does_nothing(db):
    assert Lists(db).used([]) == 0


def test_an_item_added_by_mistake_can_be_removed_outright(db):
    ls = Lists(db)
    i = ls.add('shopping', 'anchovies')
    assert ls.drop(i['id']) is True
    assert ls.drop(i['id']) is False
    assert ls.count('shopping') == 0
    assert ls.history('shopping') == []


def test_topics_names_every_list_with_something_open_on_it(db):
    ls = Lists(db)
    ls.add('shopping', 'milk', at=5)
    ls.add('interests', 'sqlite', at=3)
    used = ls.add('reading', 'a paper')
    ls.used([used['id']])
    got = {t['topic']: t['n'] for t in ls.topics()}
    assert got == dict(interests=1, shopping=1)
    assert ls.topics()[0]['since'] == 3


def test_a_very_long_item_is_clipped_rather_than_stored_whole(db):
    ls = Lists(db)
    i = ls.add('shopping', 'x'*(MAX_ITEM + 500))
    assert len(ls.items('shopping')[0]['text']) < MAX_ITEM + 40
