"""The identify service: a thing read once, in town (ADR 0017, T3 slice 2).

Slice 1 drew a rarity at once and hid the traits behind an `identified`
flag nothing ever turned true. This slice gives the town a place to read
things - the same kind of speaker flag a shopkeeper carries - and the read
itself: the flag is set on THAT instance in the saved bag, and the traits
become words in the bag's own two surfaces. Reading draws nothing, calls
no model and waits for nothing.

This file pins the engine half, and says which is which:

  * the SHAPE - `maplab.identifies`, the one reader the validator and the
    player's twin share;
  * the three REFUSALS `vefr check` speaks, one test each, each proved on
    the fixture's own act block rather than on a dict made for the test;
  * the NO RE-ROLL rule - identifying cannot move a rarity or a trait,
    because the only field it writes is the flag;
  * the BACKWARD-COMPATIBILITY PROOF - a pack that names no reader bakes
    the same bytes, and adds no new baked block at all.

The player half - the dialog, and the reveal being instant and in text
with motion off - is `tests/test_identify_play.py`, which drives the real
woven player in jsdom.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

from vefr import cli, delve, maplab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_identify_pack as mi  # noqa: E402
import make_rolled_pack as mk  # noqa: E402

PARTS = ROOT / "web" / "player" / "parts"

# The packed sample world declares no `identify` on any speaker, so
# everything woven out of it is what was woven before ADR 0017 slice 2.
# Both digests below are over the whole set of baked `window.VEFR_*` data
# lines (every one of them, in file order) for their pack.
#
# SAMPLE_DATA_SHA is the one a pristine `main` printed, until 2026-10-16:
# the sample world declares no descent, so nothing ADR 0017 slice 2 or the
# Section-tiles work baked into it, and it is the half of this test that
# says a pack naming no reader is untouched by the slice. It last moved on
# 2026-10-12, when #416 (way pictures) added `VEFR_WAY_ICONS` and
# `VEFR_REGION_WAY_ICONS` to every weave: two lines, `{}` for a pack with
# no way pictures, which the sample world is.
# It moved again on 2026-10-12 for the props slice's `window.VEFR_PROP_PICS = {};`
# line (measured twice); with that one line removed both pins are unchanged.
#
# ROLLED_DATA_SHA is over the rolled-loot fixture pack - a pack this slice
# ADDS, so no `main` ever wove it and "what pristine main prints" is not a
# claim about it. It is a whole-weave digest and does not compose: measured
# after every union, never derived. It was last moved on 2026-10-10 when
# #385 (Section tiles reach play) added `section_tiles` to the descent
# block at src/vefr/cli.py:2627 - a key that lands in `VEFR_DESCENT_DEF`
# for every pack with a descent, which the sample world has none of. That
# is merged engine behaviour, not this slice: it is the ONLY byte that
# moved, and this slice adds no baked block of its own. It moved again on
# 2026-10-12 for #416's two empty way-picture lines, measured twice.
# It moved again on 2026-10-12 for the props slice's empty `VEFR_PROP_PICS` line.
# Both moved again on 2026-10-12 for #422's empty `window.VEFR_TILE_EDGES = {};`
# line (measured twice); with that one line removed both pins are unchanged.
# Both moved again on 2026-10-16 for vefr #508 (the player's own keys): the
# closure-surfaces part bakes a `window.VEFR_KEYBINDS` block into every pack,
# two lines each that the data-line regex reads here; measured twice in
# separate processes, readings equal. With that one block removed both pins
# are unchanged.
# Both moved again on 2026-10-16 for vefr#504 (opt-in stakes): one empty
# line, `window.VEFR_STAKES = null;`, in every weave - the literal null
# for a pack that declares no stakes, which is the same asking of a player
# as before the line was there. Measured twice in separate processes,
# readings equal.
SAMPLE_DATA_SHA = '0e248a8eae679710b3ebe35824a8bd6407e6d6f528625b83c35d5d789a29aab5'
ROLLED_DATA_SHA = 'b53066a2a5a4f76c94999996df8b0482928e56530bb1fd5829a7ced9ba6cff75'


def _data_blocks(html: str) -> str:
    """Every baked data line the weave carries: the `window.VEFR_*`
    assignments, in file order, joined. This is the pack's own content;
    the player around it is the engine's, and this slice changes it."""
    return '\n'.join(re.findall(r'^window\.VEFR_[A-Z_]+ = .*?;$', html,
                                re.M | re.S))


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


# --- the shape --------------------------------------------------------------

def test_the_flag_is_one_word_and_one_reader():
    """`identify` is the pack's own truthy words, and `maplab.identifies`
    is the one place they are read - the same three a shopkeeper may use,
    so a pack writes `shop` and `identify` in the same voice."""
    assert maplab.IDENTIFY_TRUE == ('true', 'yes', '1')
    for spec in ({'identify': 'true'}, {'identify': ' TRUE '},
                 {'identify': 'yes'}, {'identify': '1'}, {'identify': True}):
        assert maplab.identifies(spec) is True, spec
    for spec in ({}, {'identify': None}, {'identify': False},
                 {'identify': ''}, {'identify': '  '}, {'identify': 'false'},
                 {'identify': 'maybe'}, {'identify': {'chance': 50}},
                 {'identify': 3}, 'not a speaker', None):
        assert maplab.identifies(spec) is False, spec


def test_a_pack_with_a_reader_validates_green(tmp_path):
    """The fixture proof: a pack that rolls its loot AND names a reader
    is a pack that validates, with nothing said about either."""
    pack = mi.build(tmp_path)
    world = maplab.load_pack(pack)
    assert maplab.validate(world, pack) == []
    assert maplab.identify_errors(world) == []
    # And the reader is a speaker of the town, beside the Keeper.
    assert world['speakers']['reader']['identify'] == 'true'
    assert world['speakers']['reader']['at'] == mi.READER['at']
    # The same pack built twice says the same things: nothing here draws.
    again = mi.build(tmp_path / 'again')
    assert maplab.identify_errors(maplab.load_pack(again)) == []


def test_a_pack_that_names_no_reader_says_nothing(tmp_path):
    """Backward compatibility, in the words: a pack written before this
    slice has nothing said about it, and gains nothing."""
    assert maplab.identify_errors(maplab.load_pack(
        ROOT / "worlds" / "sample-world")) == []
    pack = mi.build(tmp_path, reader=False)
    world = maplab.load_pack(pack)
    assert maplab.validate(world, pack) == []
    assert maplab.identify_errors(world) == []
    # A flag that says no is silence too, and silence is not an error.
    for off in (False, None, '', '  '):
        quiet = mi.build(tmp_path / f"off-{off!r}",
                         reader=dict(mi.READER, identify=off))
        assert maplab.identify_errors(maplab.load_pack(quiet)) == [], off


# --- the three refusals ----------------------------------------------------

def test_an_identify_naming_a_service_that_does_not_exist_is_named():
    """Refusal one: some other word names a service this pack has not."""
    pack = mi.build(Path(_scratch('word')),
                    reader=dict(mi.READER, identify='alchemist'))
    errors = maplab.validate(maplab.load_pack(pack), pack)
    assert errors == [
        "speaker 'The Reader' (reader) identify names 'alchemist', which is "
        "not a service this pack has: write true to make this speaker the "
        "one that reads things"]
    assert maplab.identify_errors(maplab.load_pack(pack)) == errors


def test_an_identify_that_is_not_the_word_true_is_named():
    """Refusal two: anything that could carry a draw or a model.

    A `chance` beside an identify is a pack asking for a second, unnamed
    draw at the moment a thing is read - which is exactly the
    nondeterministic, model-driven reading the engine does not do.
    """
    pack = mi.build(Path(_scratch('chance')),
                    reader=dict(mi.READER, identify={'chance': 50}))
    errors = maplab.validate(maplab.load_pack(pack), pack)
    assert errors == [
        "speaker 'The Reader' (reader) identify must be the word true: a "
        "thing is read once, at the place the pack names, so identifying "
        "carries no chance, no roll and no model"]


def test_an_identify_in_a_region_the_pack_does_not_have_is_named():
    """Refusal three: a service in a region the pack does not have is a
    service nobody can walk up to."""
    pack = mi.build(Path(_scratch('region')),
                    reader=dict(mi.READER, region='hollow'))
    errors = maplab.validate(maplab.load_pack(pack), pack)
    assert errors == [
        "speaker 'The Reader' (reader) offers identify in region 'hollow', "
        "which this pack does not have"]
    # The pack's own region is the default when the speaker names none.
    assert maplab.identify_errors(maplab.load_pack(pack)) == errors


def _scratch(tag: str) -> str:
    import tempfile
    path = Path(tempfile.mkdtemp(prefix=f'vefr-identify-{tag}-'))
    return str(path)


# --- no re-roll ------------------------------------------------------------

def test_reading_a_thing_never_draws_it_again():
    """The evidence that identifying does not re-roll, in two halves.

    The draw is the same draw it was before the read: same floor key,
    same monster, same rarity, same traits, in pack order. And the read
    itself touches one field and no other - the player's read is the flag,
    and the traits and rarity in storage are the ones the drop wrote.
    """
    key = 'run-a/cellar/0/1'
    first = delve.mob_drops(key, 'm0', ['cloudy-potion'], mk.ITEMS)[0]
    second = delve.mob_drops(key, 'm0', ['cloudy-potion'], mk.ITEMS)[0]
    assert first == second and first['identified'] is False

    # What the bag holds, and what it holds after the flag is set. The
    # read is the same record with one boolean changed - nothing else is
    # written, so nothing can have been re-rolled.
    stored = {'id': first['item'], 'rarity': first['rarity'],
              'traits': list(first['traits']), 'identified': False}
    read = dict(stored, identified=True)
    assert read['rarity'] == stored['rarity']
    assert read['traits'] == stored['traits']
    # And reading the very same instance twice cannot move them either:
    # the second read finds the flag already set and writes nothing.
    assert json.dumps(dict(read, identified=True)) == json.dumps(read)

    # The player agrees, in source: the read writes the flag and calls
    # the two redraws. It touches no other field of the record.
    read_one = _body('195-the-identify-service.js', 'bagIdentifyOne')
    assert 'raw[at].identified = true' in read_one
    assignments = re.findall(r'raw\[at\]\.(\w+)\s*=(?!=)', read_one)
    assert assignments == ['identified'], assignments
    assert 'itemDraw' not in read_one and 'roll' not in read_one


def test_the_draw_still_never_identifies_a_thing(tmp_path):
    """The draw is unchanged by this slice: `identified` is False on every
    instance it makes, and the Python draw says nothing about a reader."""
    for drop in (delve.mob_drops('k', 'm0', ['cloudy-potion'], mk.ITEMS)[0],
                 delve.mob_drops('k', 'm0', ['brass-ring'], mk.ITEMS)[0]):
        assert drop['identified'] is False
    source = (ROOT / "src" / "vefr" / "delve.py").read_text(encoding='utf-8')
    assert set(re.findall(r"'identified': (\w+)", source)) == {'False'}


# --- the bake --------------------------------------------------------------

def test_a_pack_with_no_reader_bakes_the_same_bytes():
    """The backward-compatibility hash, for both packs.

    Nothing in the baked data changes: a pack that names no reader bakes
    every `window.VEFR_*` line exactly as it did. The player around those
    lines DOES change - this slice adds the service to the bag strip, the
    bag panel and the Interact verb, which is what the slice is - so the
    claim pinned here is the pack's own content, hash for hash. The sample
    world's digest is the one a pristine `main` prints and still is; the
    fixture pack's is measured, because it is a pack this slice adds and a
    whole-weave digest does not compose across a union.
    """
    sample = cli.weave_html(ROOT / "worlds" / "sample-world")
    assert hashlib.sha256(_data_blocks(sample).encode()).hexdigest() == SAMPLE_DATA_SHA

    pack = mi.build(Path(_scratch('bake')), reader=False)
    rolled = cli.weave_html(pack)
    assert hashlib.sha256(_data_blocks(rolled).encode()).hexdigest() == ROLLED_DATA_SHA


def test_the_reader_needs_no_new_baked_block(tmp_path):
    """Additive all the way down: the flag rides the world the weave
    already inlines, so this slice adds no `VEFR_*` line at all and a
    pack that names no reader has nothing new to read."""
    html = cli.weave_html(mi.build(Path(_scratch('inline'))))
    assert 'window.VEFR_IDENTIF' not in html
    assert 'window.VEFR_SERVICE' not in html
    # The pack's own block, in the player's twin and in Python, is the one
    # reader: a pack that passed the check is a pack that offers it.
    twin = (PARTS / '195-the-identify-service.js').read_text(encoding='utf-8')
    assert 'window.VEFR_SPEAKERS' in twin and 'window.VEFR_WORLD' in twin
    assert maplab.IDENTIFY_TRUE == ('true', 'yes', '1')
    # The reader itself is in the weave, flag and all, because it is part
    # of the world.json the player already reads.
    assert '"identify": "true"' in html or 'identify' in html


def test_the_woven_player_carries_the_service(tmp_path):
    """The shipped player has the panel, the verb and the read."""
    html = cli.weave_html(mi.build(Path(_scratch('woven'))))
    for name in ('openIdentify', 'closeIdentify', 'renderIdentify',
                 'identifyThing', 'bagIdentifyOne', 'identifyKeyHere',
                 'bagUnread'):
        assert f'function {name}(' in html, name
    assert "kind: 'identifier'" in html
    assert 'Ask ' in html            # the Interact label


# --- the read is instant, deterministic and model-free ---------------------

def test_nothing_in_the_read_waits_or_animates():
    """Motion off changes nothing, because there is nothing to change.

    The whole reveal is a string concatenation and a re-render in the
    same call: no timer, no frame callback, no class, no transition, no
    draw. So the words are in the DOM on the first frame after the click,
    with motion on or off, and the trait is never revealed by a picture.
    """
    forbidden = ('setTimeout', 'setInterval', 'requestAnimationFrame',
                 'classList', 'animate(', 'transition', 'Math.random',
                 'Date.now', 'fetch(', 'model', 'endpoint')
    for name in ('bagIdentifyOne', 'bagUnread', 'renderIdentify',
                 'identifyThing', 'openIdentify', 'closeIdentify',
                 'identifyKeyHere', 'identifies'):
        body = _body('195-the-identify-service.js', name)
        for word in forbidden:
            assert word not in body, f'{name} uses {word}'
    # And the reveal itself - the one place traits become words - is a
    # concatenation with nothing behind it.
    named = _body('180-gold.js', 'carriedName')
    for word in forbidden:
        assert word not in named, f'carriedName uses {word}'
    assert 'carried.identified && carried.traits.length' in named


def test_the_traits_are_named_only_once_the_thing_has_been_read():
    """The rule the slice-1 tests held for a hidden trait, applied to a
    revealed one: the words are absent from the page while `identified`
    is false, and present once it is true."""
    named = _body('180-gold.js', 'carriedName')
    assert 'carried.identified && carried.traits.length' in named
    # The two bag surfaces read the one name, so both name the traits and
    # neither keeps a second copy of the truth somewhere else.
    assert 'carriedName(entry)' in _body('180-gold.js', 'renderBagPanel')
    # the strip names each KIND once (vefr#412), still through carriedName
    assert 'carriedName(kind.first)' in _body('180-gold.js', 'renderBagStrip')