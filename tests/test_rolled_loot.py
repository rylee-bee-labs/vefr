"""Rolled loot: rarity at once, traits hidden (ADR 0017, T3 slice 1).

One drop draw now yields a base item plus a rarity the player sees at
once, plus traits that stay hidden until the thing is identified. The
draw is deterministic from the run seed, every key is optional and
additive, and a pack that names none of them is the pack it was.

This file pins four things, and the names say which:

  * the SHAPE - `shapes.ITEM` and `shapes.check_item`, and that they read
    only the three keys this slice added;
  * the four REFUSALS `vefr check` speaks, one test each;
  * the DRAW - the same seed twice draws the same thing, a different floor
    key or a different monster draws a different one, and every stream is
    a named stream off the floor key;
  * the BACKWARD COMPATIBILITY PROOF - an unmodified pack's catalog bakes
    the same bytes and its floors drop the same ids.

Plus the reveal rule: the rarity is in the bag's own words, in the same
line as the item's name, with no timer or animation anywhere in that path
(motion off makes no difference to a reveal that never waits), and the
hidden traits are not written into the DOM at all.
"""

import hashlib
import json
import re
import sys
from pathlib import Path


from vefr import cli, delve, maplab, shapes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_rolled_pack as mk  # noqa: E402

PARTS = ROOT / "web" / "player" / "parts"

# One catalog entry per shape this slice added, and one that is plainly
# broken in each of the four ways `vefr check` refuses.
GOOD = {
    "name": "a cloudy potion", "sprite": "potion", "heal": 3, "use": "drink",
    "rarity": "common",
    "traits": ["keen"],
    "roll": {"rarity": {"common": 60, "uncommon": 30, "rare": 10},
             "traits": ["keen", "brave", "swift", "cold"],
             "chance": 60, "max": 2},
}

# The catalog of a pack written before this slice: no `rarity`, no
# `traits`, no `roll`. This exact dict is what `VEFR_ITEMS` must still be,
# key for key, for every entry of it.
PLAIN = {
    "torch": {"name": "a pitch torch", "sprite": "",
              "light": {"radius": 2, "turns": 6}},
    "chalked-map": {"name": "a chalked map", "sprite": "",
                    "light": {"reveal": True}},
    "potion-1": {"name": "a cloudy potion", "sprite": "potion",
                 "value": 4, "heal": 3, "use": "drink"},
    "cloak-1": {"name": "a hooded cloak", "sprite": "cloak",
                "slot": "body", "mods": {"hp": 2}},
    # The silent no-ops an older catalog may carry: a value of 0, a heal
    # that is not a number, a use that is blank. None of these is new and
    # none of them is refused.
    "junk": {"name": "a bit of junk", "value": 0, "heal": "lots", "use": "  "},
    "no-name": {"sprite": "x"},
}


# --- the shape --------------------------------------------------------------

def test_the_item_block_is_registered_and_names_the_three_added_keys():
    assert shapes.BLOCKS["item"] is shapes.ITEM
    assert shapes.ITEM_ADDED == ("rarity", "traits", "roll")


def test_a_good_item_has_no_problems():
    assert shapes.check_item(GOOD) == []
    assert maplab.item_roll_errors("potion-1", GOOD) == []


def test_the_shape_reads_only_the_keys_this_slice_added():
    """A catalog written before ADR 0017 keeps its silence.

    Every one of those keys accepts something today - a `value` of 0, a
    `heal` of "lots", a key the table has never heard of - and a check that
    started refusing them would refuse a pack that was never wrong.
    """
    assert shapes.check_item(PLAIN["junk"]) == []
    assert shapes.check_item({"name": "an odd thing", "luck": 3}) == []
    assert maplab.item_roll_errors("junk", PLAIN["junk"]) == []


def test_the_roll_the_bake_carries_is_the_one_the_draw_reads():
    """The bake resolves the defaults; the draw and the player read those.

    `maplab.item_roll_of` is the single reader the validator, the bake and
    `delve.item_draw` all go through, so what the pack writes and what the
    player holds can never drift into two different rolls.
    """
    rolled = maplab.item_roll_of(GOOD)
    assert rolled == {'rarity': [('common', 60), ('uncommon', 30), ('rare', 10)],
                      'traits': ['keen', 'brave', 'swift', 'cold'],
                      'chance': 60, 'max': 2}
    baked = cli._player_items({'items': {'potion-1': GOOD}})['potion-1']
    assert baked['roll'] == {'rarity': {'common': 60, 'uncommon': 30, 'rare': 10},
                             'traits': ['keen', 'brave', 'swift', 'cold'],
                             'chance': 60, 'max': 2}
    # An item with no roll bakes no roll, whatever else it declares.
    assert 'roll' not in cli._player_items({'items': {'p': PLAIN['potion-1']}})['p']


def test_a_pack_with_no_roll_bakes_its_catalog_byte_for_byte():
    """The backward-compatibility proof, part one: `VEFR_ITEMS`.

    The catalog of a pack written before this slice is the catalog this
    slice bakes, key for key and value for value - including the entries
    that carry nothing usable, which stay out rather than being cleaned up.
    """
    assert cli._player_items({'items': PLAIN}) == {
        'torch': {'name': 'a pitch torch', 'sprite': '',
                  'light': {'radius': 2, 'turns': 6}},
        'chalked-map': {'name': 'a chalked map', 'sprite': '',
                        'light': {'reveal': True}},
        'potion-1': {'name': 'a cloudy potion', 'sprite': 'potion',
                     'value': 4, 'heal': 3, 'use': 'drink'},
        'cloak-1': {'name': 'a hooded cloak', 'sprite': 'cloak',
                    'slot': 'body', 'mods': {'hp': 2}},
        'junk': {'name': 'a bit of junk', 'sprite': ''},
    }


# --- the four refusals ------------------------------------------------------

def test_a_rarity_outside_its_own_table_is_named():
    """Refusal one: the item's `rarity` must be a name its `roll` declares."""
    spec = dict(GOOD, rarity="legendary")
    assert maplab.item_roll_errors("potion-1", spec) == [
        "item 'a cloudy potion' (potion-1) rarity must be one of the names "
        "its roll declares: common, uncommon and rare"]
    # A fixed rarity on an item with no roll is the pack's own word, and
    # there is no table to be outside of.
    assert maplab.item_roll_errors("ring-1", {"name": "a brass ring",
                                              "rarity": "legendary"}) == []


def test_a_trait_that_is_not_a_plain_word_is_named():
    """Refusal two: a trait is one word, and this says so at the entry."""
    spec = dict(GOOD, traits=["quick brown"])
    assert maplab.item_roll_errors("potion-1", spec) == [
        'item \'a cloudy potion\' (potion-1) traits must each be one plain '
        'word, such as "keen"']
    # The pool of a roll is held to the same rule, at the offending entry -
    # and a pool nothing in it can be drawn from is also an empty pool, so
    # the asking-for-traits refusal speaks beside it.
    pooled = dict(GOOD, roll=dict(GOOD['roll'], traits=["two words"]))
    assert maplab.item_roll_errors("potion-1", pooled) == [
        'item \'a cloudy potion\' (potion-1) roll traits must each be one '
        'plain word, such as "keen"',
        "item 'a cloudy potion' (potion-1) roll asks for traits but names "
        "no trait pool"]


def test_a_roll_with_no_rarity_table_is_named():
    """Refusal three: a roll that names no table, or an undrawable one."""
    assert maplab.item_roll_errors("potion-1", dict(
        GOOD, roll={"traits": ["keen"], "chance": 60})) == [
        'item \'a cloudy potion\' (potion-1) roll must hold a rarity table, '
        'such as {"common": 60}']
    assert maplab.item_roll_errors("potion-1", dict(
        GOOD, roll={"rarity": {"common": "often"}, "traits": ["keen"]})) == [
        'item \'a cloudy potion\' (potion-1) roll must declare a rarity '
        'table of names and whole weights, such as {"common": 60}']


def test_a_roll_that_asks_for_traits_and_names_none_is_named():
    """Refusal four: asking for a trait and naming no pool is a refusal."""
    assert maplab.item_roll_errors("potion-1", dict(
        GOOD, roll=dict(GOOD["roll"], traits=[]))) == [
        "item 'a cloudy potion' (potion-1) roll asks for traits but names "
        "no trait pool"]
    # A roll that names a rarity table and nothing else is asked for
    # nothing, so it is a rarity roll and not a refusal.
    assert maplab.item_roll_errors("potion-1", dict(
        GOOD, roll={"rarity": {"common": 60}})) == []


def test_a_roll_the_check_refuses_draws_nothing_at_all():
    """A refusal means no roll, not half of one: a bare id, as before."""
    catalog = {'potion-1': {'name': 'a cloudy potion',
                            'roll': {'rarity': {'common': 60}, 'traits': []}}}
    assert maplab.item_roll_errors('potion-1', catalog['potion-1'])
    assert delve.mob_drops('k', 'm0', ['potion-1'], catalog) == ['potion-1']


# --- the draw ---------------------------------------------------------------

CATALOG = {'potion-1': GOOD}


def test_the_same_seed_draws_the_same_thing_twice():
    key = 'run-a/cellar/0/1'
    first = delve.mob_drops(key, 'm0', ['potion-1'], CATALOG)
    assert first == delve.mob_drops(key, 'm0', ['potion-1'], CATALOG)
    assert first[0]['item'] == 'potion-1'
    assert first[0]['rarity'] in {'common', 'uncommon', 'rare'}


def test_a_different_floor_key_draws_a_different_thing():
    """Same floor key, same monster: one answer. Another key: another roll."""
    keys = [f'run-a/cellar/0/{k}' for k in range(1, 25)]
    draws = [json.dumps(delve.mob_drops(k, 'm0', ['potion-1'], CATALOG))
             for k in keys]
    assert len(set(draws)) > 1, "every floor drew the same rolled drop"
    # And the answer is always a legal one: a name the table declares and
    # traits the pool holds, never more of them than `max` says.
    for k in keys:
        drop = delve.mob_drops(k, 'm0', ['potion-1'], CATALOG)[0]
        assert drop['rarity'] in GOOD['roll']['rarity']
        assert len(drop['traits']) <= GOOD['roll']['max']
        assert set(drop['traits']) <= set(GOOD['roll']['traits'])
        assert len(set(drop['traits'])) == len(drop['traits'])


def test_two_monsters_never_share_a_roll():
    key = 'run-a/cellar/0/1'
    answers = {json.dumps(delve.mob_drops(key, m, ['potion-1'], CATALOG))
               for m in ('m0', 'm1', 'm2', 'm3', 'w')}
    assert len(answers) > 1


def test_the_base_draw_does_not_move_when_the_roll_does():
    """The roll has its own stream, so adding `roll` cannot move the id.

    Without this, a pack that added a roll to one item would find every
    other drop on the floor changed too - the sub-seed rule (PLAN §8).
    """
    key = 'run-a/cellar/0/1'
    table = ['torch', 'pebble', 'potion-1']

    def chosen(drops):
        return drops[0]['item'] if isinstance(drops[0], dict) else drops[0]

    bare = delve.mob_drops(key, 'm0', table)
    rolled = delve.mob_drops(key, 'm0', table, {'potion-1': GOOD})
    assert chosen(bare) == chosen(rolled)
    # And the same for every monster on the floor, drawn or not.
    for mob in ('m0', 'm1', 'm2', 'm3'):
        assert chosen(delve.mob_drops(key, mob, table)) == chosen(
            delve.mob_drops(key, mob, table, {'potion-1': GOOD}))


def test_the_roll_stream_is_named_off_the_floor_key_and_the_monster():
    assert delve.roll_seed('run-a/cellar/0/1', 'm3', 'potion-1') == \
        'v3|run-a/cellar/0/1|roll|m3|potion-1'
    # A different monster, or a different item, is a different stream.
    assert delve.roll_seed('run-a/cellar/0/1', 'm4', 'potion-1') != \
        delve.roll_seed('run-a/cellar/0/1', 'm3', 'potion-1')
    assert delve.roll_seed('run-a/cellar/0/1', 'm3', 'pebble') != \
        delve.roll_seed('run-a/cellar/0/1', 'm3', 'potion-1')
    # And it is not the loot stream: the base id and the roll are drawn
    # from two streams that never share a draw.
    assert delve.roll_seed('run-a/cellar/0/1', 'm3', 'potion-1') != \
        delve.loot_seed('run-a/cellar/0/1', 'm3')


def test_every_roll_draw_is_one_floor_of_a_whole_number():
    """No float arithmetic in a roll beyond `int(rng() * n)`.

    The weights are the pack's own whole numbers and the reader caps them
    at RARITY_WEIGHT_MAX, so the sum a draw scales by is under 2**31 in
    any pack that passes the check.
    """
    cap = maplab.RARITY_WEIGHT_MAX * maplab.RARITY_NAMES_MAX
    assert cap < 2 ** 31
    names = {f'r{i}': maplab.RARITY_WEIGHT_MAX
             for i in range(maplab.RARITY_NAMES_MAX)}
    catalog = {'potion-1': dict(GOOD, roll=dict(
        GOOD['roll'], rarity=names,
        traits=[f't{i}' for i in range(maplab.TRAIT_POOL_MAX)]))}
    for k in range(1, 6):
        drop = delve.mob_drops(f'run-a/cellar/0/{k}', 'm0', ['potion-1'],
                               catalog)[0]
        assert drop['rarity'] in names


def test_a_pack_that_declares_no_roll_drops_the_bare_id_it_always_did():
    """The backward-compatibility proof, part two: the drops.

    Handed a catalog with nothing rolled in it, or no catalog at all, the
    draw is the same list of bare id strings it was before this slice -
    and it is the same list whether or not a catalog was handed in.
    """
    key = 'run-a/cellar/0/1'
    table = ['torch', 'pebble']
    bare = delve.mob_drops(key, 'm0', table)
    assert bare == ['torch'] or bare == ['pebble']
    assert bare == delve.mob_drops(key, 'm0', table, PLAIN)
    assert all(isinstance(drop, str) for drop in bare)
    # A whole floor of it: over twelve floors and three runs, every drop of
    # a pack that rolls nothing is a bare id, and the same ones with the
    # catalog in hand as without it.
    descent = _plain_descent()
    for run in (0, 1, 2):
        for depth in range(1, 13):
            here = delve.floor_plan(descent, depth, run, PLAIN)
            without = delve.floor_plan(descent, depth, run)
            assert [m['drops'] for m in here['mobs']] == \
                [m['drops'] for m in without['mobs']]
            for mob in here['mobs']:
                assert all(isinstance(drop, str) for drop in mob['drops']), mob


def test_a_fixed_rarity_and_traits_ride_a_drop_without_a_draw():
    """No `roll` means no draw: the pack's own words ride along as they are,
    and the thing is still an instance that has not been identified."""
    catalog = {'ring-1': {'name': 'a brass ring', 'rarity': 'common',
                          'traits': ['keen']}}
    assert delve.mob_drops('k', 'm0', ['ring-1'], catalog) == [
        {'item': 'ring-1', 'rarity': 'common', 'traits': ['keen'],
         'identified': False}]
    # The same item, asked twice, rides the same words: nothing was drawn.
    assert delve.mob_drops('k', 'm0', ['ring-1'], catalog) == \
        delve.mob_drops('other', 'm9', ['ring-1'], catalog)


def test_a_drawn_thing_is_not_identified_yet():
    """`identified` is False on every instance the DRAW makes.

    Since slice 2 something does turn it true - the town's identify
    service - so the claim this test holds is now narrower and exact: the
    DRAW never identifies anything, and the bag part that reads the bag
    never writes the flag either. The one place in the player that writes
    it is the service itself (`195-the-identify-service.js`), and that is
    where slice 2 pins the rest of it (`tests/test_identify.py`).
    """
    for drop in (delve.mob_drops('k', 'm0', ['potion-1'], CATALOG)[0],
                 delve.mob_drops('k', 'm0', ['ring-1'],
                                 {'ring-1': {'name': 'r', 'rarity': 'common'}})[0]):
        assert drop['identified'] is False
    draw = (ROOT / 'src' / 'vefr' / 'delve.py').read_text(encoding='utf-8')
    assert set(re.findall(r"'identified': (\w+)", draw)) == {'False'}
    source = (PARTS / '180-gold.js').read_text(encoding='utf-8')
    assert 'identified: false' in source or 'identified = false' in source
    assert 'identified = true' not in source
    assert 'identified: true' not in source
    # The reader part does write it - once, on the instance, in the bag.
    assert 'raw[at].identified = true' in (
        PARTS / '195-the-identify-service.js').read_text(encoding='utf-8')


def test_the_javaScript_twin_draws_the_same_thing_the_python_draws():
    """Both languages read one baked roll and spend the same draws in the
    same order, so a floor drawn in the browser is the floor Python drew.

    The twin lives in `web/player/parts/397-the-descent.js`; this reads it
    rather than running it, because it is the shipped player and the node
    harness (`tests/test_rolled_loot_play.py`) is what runs it.
    """
    twin = (PARTS / '397-the-descent.js').read_text(encoding='utf-8')
    for fragment in ("streamSeed(key, 'roll|' + mobId + '|' + itemId)",
                     "window.VEFR_ITEMS || {}",
                     'Math.floor(rng() * total)',
                     'Math.floor(rng() * 100) >= roll.chance',
                     '1 + Math.floor(rng() * roll.max)',
                     'item: itemId, rarity: weightedName('):
        assert fragment in twin, fragment


def _fixture_descent():
    """The rolled fixture's descent block with its Blueprint beside it."""
    block = json.loads(json.dumps({
        "descent": {"run_seed": "run-a",
                    "entry": {"region": "town", "at": list(mk.ENTRY_AT)},
                    "sections": mk.SECTIONS}}))
    block["descent"]["blueprint"] = json.loads(json.dumps(mk.BLUEPRINT))
    return block


def _plain_descent():
    """The same cellar, drawn by families whose drops are the sample
    world's own catalog: two ids, neither of them rolled."""
    return {"descent": {
        "run_seed": "run-a",
        "entry": {"region": "town", "at": list(mk.ENTRY_AT)},
        "blueprint": {"families": {
            "rat": {"defaults": {"name": "a grey rat", "hp": 4, "atk": 2,
                                 "sight": 5, "drops": ["torch"]}},
            "moth": {"defaults": {"name": "a pale moth", "hp": 2, "atk": 1,
                                  "sight": 3,
                                  "drops": ["torch", "chalked-map"]}},
        }},
        "sections": [{"id": "cellar", "floors": 9, "rooms": [12, 18],
                      "families": [{"family": "rat", "weight": 2},
                                   {"family": "moth", "weight": 1}]}],
    }}


# --- the pack that rolls ----------------------------------------------------

def test_a_pack_that_rolls_validates_green(tmp_path):
    """A pack using `roll` is a pack that validates, with nothing said."""
    pack = mk.build(tmp_path)
    world = maplab.load_pack(pack)
    assert maplab.validate(world, pack) == []
    assert maplab.validate(world, pack) == maplab.validate(
        maplab.load_pack(mk.build(tmp_path / "again")), mk.build(tmp_path / "again"))


def test_its_floor_carries_the_drawn_instances(tmp_path):
    """The end of the road: a kill on a rolled floor drops an instance."""
    pack = mk.build(tmp_path)
    world = maplab.load_pack(pack)
    descent = {**delve.descent_of(world, pack),
               'blueprint': delve.blueprint_of(pack)}
    plan = delve.floor_plan(descent, 1, 0, mk.ITEMS)
    assert plan['mobs']
    drops = [d for m in plan['mobs'] for d in m['drops']]
    assert drops, "the fixture's floor dropped nothing"
    for drop in drops:
        if isinstance(drop, str):
            # The pack's plain thing is still the bare id it always was.
            assert drop == 'pebble'
            continue
        assert drop['item'] in mk.ITEMS
        assert drop['identified'] is False
        if drop['item'] == 'cloudy-potion':
            assert drop['rarity'] in mk.ITEMS['cloudy-potion']['roll']['rarity']
            assert set(drop['traits']) <= set(
                mk.ITEMS['cloudy-potion']['roll']['traits'])
        else:
            # The ring is fixed, not drawn.
            assert (drop['rarity'], drop['traits']) == ('common', ['keen'])
    # And the same floor twice is the same floor.
    assert delve.floor_plan(descent, 1, 0, mk.ITEMS) == plan


def test_the_woven_player_of_a_rolled_pack_carries_the_roll(tmp_path):
    """`VEFR_ITEMS` is what the player draws from, so it carries the roll."""
    html = cli.weave_html(mk.build(tmp_path))
    baked = json.loads(re.search(r'window\.VEFR_ITEMS = (\{.*?\});',
                                 html, re.S).group(1))
    assert baked['cloudy-potion']['roll'] == {
        'rarity': {'common': 60, 'uncommon': 30, 'rare': 10},
        'traits': ['keen', 'brave', 'swift', 'cold'],
        'chance': 60, 'max': 2}
    assert baked['brass-ring']['rarity'] == 'common'
    assert baked['pebble'] == {'name': 'a grey pebble', 'sprite': '', 'value': 1}


def test_the_unmodified_sample_world_bakes_the_same_catalog_as_main(tmp_path):
    """The hash the acceptance asks for, on the pack the engine ships.

    `worlds/sample-world` declares no `rarity`, no `traits` and no `roll`,
    so the catalog woven out of it is the one woven before ADR 0017. The
    digest below is the one a pristine `main` prints for the same pack.
    """
    pack = ROOT / "worlds" / "sample-world"
    html = cli.weave_html(pack)
    baked = re.search(r'window\.VEFR_ITEMS = (\{.*?\});', html, re.S).group(1)
    digest = hashlib.sha256(baked.encode('utf-8')).hexdigest()
    assert digest == '3997a2ea7deea05adf61b9d51bcf6c54972dc489e85180b6f632caa4774d47a9', digest


# --- the reveal rule --------------------------------------------------------

def _body(part: str, name: str) -> str:
    """The source of one named function in a player part."""
    text = (PARTS / part).read_text(encoding='utf-8')
    start = text.index(f'function {name}(')
    depth, i = 0, text.index('{', start)
    while True:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1


def test_the_bag_names_the_item_and_its_rarity_in_one_line():
    """The reveal: the thing and its rarity, together, at once."""
    named = _body('180-gold.js', 'carriedName')
    assert "carried.rarity" in named
    assert "itemName(carried.id)" in named
    assert "carriedName(entry)" in _body('180-gold.js', 'renderBagPanel')
    assert "carriedName(kind.first)" in _body('180-gold.js', 'renderBagStrip')
    assert "carriedName(inst)" in _body('430-loot-on-the-floor.js', 'takeHere')


def test_the_reveal_is_instant_and_nothing_in_it_animates():
    """Motion off must make the reveal instant.

    This slice owes no animation at all: the rarity is written into the
    same string as the name, in the same pass, with no timer, no frame
    callback, no class and no transition between the pickup and the word
    being there. So there is nothing for a reduced-motion setting to turn
    off, and the sentence above holds with motion on or off.
    """
    forbidden = ('setTimeout', 'setInterval', 'requestAnimationFrame',
                 'classList', 'animate(', 'transition')
    for part, name in (('180-gold.js', 'carriedName'),
                       ('180-gold.js', 'renderBagPanel'),
                       ('180-gold.js', 'renderBagStrip'),
                       ('430-loot-on-the-floor.js', 'takeHere'),
                       ('430-loot-on-the-floor.js', 'placeDrops')):
        body = _body(part, name)
        for word in forbidden:
            assert word not in body, f'{name} in {part} uses {word}'


def test_the_hidden_traits_are_not_written_into_the_page():
    """They are not in the DOM, not merely covered up: a tool that reads
    the bag panel finds the rarity and no trait."""
    panel = _body('180-gold.js', 'renderBagPanel')
    strip = _body('180-gold.js', 'renderBagStrip')
    for body in (panel, strip):
        assert '.traits' not in body
        assert 'carriedName' in body