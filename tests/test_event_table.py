"""S2 (tighten-shapes plan section 4). FROZEN CONTRACT for the one event table.

The event vocabulary was typed three times and had already drifted (vefr #269): in
`maplab._rule_event_errors`, in `maplab._album_when_errors`, and in the JavaScript `EVENTS`
table in the woven player. S2 gives the Python side one table, `shapes.EVENTS`, and both
validators read it. This file pins:

  - the table itself: fourteen events, in order, each with exactly its payload fields, each
    field's kind, ref kind and bounds;
  - that `maplab` holds no second list: `RULE_EVENTS` and `RULE_EVENT_KEYS` are derived, and
    no event name is typed anywhere else in `maplab.py`;
  - that both validators still speak today's sentences, byte for byte, from the table;
  - that the JavaScript twin still matches (S3 generates it; until then this is the guard
    that would catch the next drift).

The S0 golden (tests/test_validator_golden.py) pins the same sentences through the public
`rules_errors` / `album_errors`; this file pins them through the table, so a change that
kept the prose but moved the vocabulary back out of the table fails here.
"""

import inspect
import re
from pathlib import Path

from vefr import maplab, shapes

# The fourteen events, in the order the pack contract and the player speak them.
# `falls` and `wakes` are the hero's own two facts (vefr #365): nothing in the eleven
# before them said the hero died. `uses-verb` came with the item-grants slice: a verb
# an item hands the hero is a thing the player does, so a pack can write what it does.
THIRTEEN = ('starts', 'enters', 'comes-near', 'opens', 'picks-up', 'uses-with',
            'defeats', 'buys', 'sells', 'reads', 'phase-changes', 'falls', 'wakes',
            'uses-verb')

# event -> ((field, kind, ref, lo, hi), ...), in payload order. `ref` is the pack id a field
# names; a field with no ref is a number the table bounds itself.
EXPECTED = {
    'starts': (),
    'enters': (('place', 'ref', 'place', None, None),),
    'comes-near': (('who', 'ref', 'thing', None, None),
                   ('distance', 'int', None, 0, 9)),
    'opens': (('what', 'ref', 'thing', None, None),),
    'picks-up': (('what', 'ref', 'item', None, None),),
    'uses-with': (('item', 'ref', 'item', None, None),
                  ('with', 'ref', 'thing', None, None)),
    'defeats': (('what', 'ref', 'enemy', None, None),),
    'buys': (('what', 'ref', 'item', None, None),),
    'sells': (('what', 'ref', 'item', None, None),),
    'reads': (('what', 'ref', 'book', None, None),),
    'phase-changes': (('to', 'ref', 'phase', None, None),),
    'falls': (('what', 'ref', 'enemy', None, None),
              ('where', 'ref', 'place', None, None)),
    'wakes': (('where', 'ref', 'place', None, None),),
    'uses-verb': (('verb', 'ref', 'verb', None, None),),
}

KNOWN = {
    'items': {'torch', 'chalked-map'},
    'people': {'keeper'},
    'places': {'town'},
    'pois': {'hearth'},
    'books': {'almanac'},
    'enemies': {'rat'},
    'acts': set(),
    'phases': {'dawn'},
    'things': {'torch', 'chalked-map', 'keeper', 'town', 'hearth', 'almanac', 'rat'},
    'flags': {'lit'},
    'claims': {'keeper-watches'},
    'verbs': {'console'},
}

GOOD = {
    'starts': {},
    'enters': {'place': 'town'},
    'comes-near': {'who': 'torch', 'distance': 2},
    'opens': {'what': 'torch'},
    'picks-up': {'what': 'chalked-map'},
    'uses-with': {'item': 'torch', 'with': 'hearth'},
    'defeats': {'what': 'rat'},
    'buys': {'what': 'torch'},
    'sells': {'what': 'torch'},
    'reads': {'what': 'almanac'},
    'phase-changes': {'to': 'dawn'},
    'falls': {'what': 'rat', 'where': 'town'},
    'wakes': {'where': 'town'},
    'uses-verb': {'verb': 'console'},
}


def _fields(event):
    return tuple((k.name, k.kind, k.ref, k.lo, k.hi) for k in shapes.EVENTS[event])


# --- the table -----------------------------------------------------------

def test_the_table_holds_the_fourteen_events_in_order():
    assert tuple(shapes.EVENTS) == THIRTEEN


def test_every_event_carries_exactly_its_payload_fields():
    assert {event: _fields(event) for event in shapes.EVENTS} == EXPECTED


def test_the_table_is_the_only_place_the_vocabulary_is_typed():
    source = inspect.getsource(maplab)
    for event in THIRTEEN:
        assert f"'{event}'" not in source, event
        assert f'"{event}"' not in source, event


def test_maplab_derives_its_two_names_from_the_table():
    assert maplab.RULE_EVENTS == tuple(shapes.EVENTS)
    assert maplab.RULE_EVENT_KEYS == {
        event: tuple(k.name for k in fields)
        for event, fields in shapes.EVENTS.items()}


def test_shapes_is_still_stdlib_only():
    import ast
    import sys
    tree = ast.parse(inspect.getsource(shapes))
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level:
            names = [node.module or '']
        for module in names:
            assert module.split('.')[0] in sys.stdlib_module_names, module


# --- both validators read the table --------------------------------------

def test_every_event_a_pack_can_write_is_accepted_by_both_validators():
    for event, payload in GOOD.items():
        assert maplab._rule_event_errors('r', {event: payload}, KNOWN) == [], event
        assert maplab._album_when_errors('s', {event: payload}, KNOWN) == [], event


def test_distance_is_bounded_by_the_table_and_each_author_hears_their_own_words():
    for distance in (True, -1, 10):
        when = {'comes-near': {'who': 'torch', 'distance': distance}}
        assert maplab._rule_event_errors('r', when, KNOWN) == [
            "rule 'r' when 'comes-near' distance must be an integer 0..9 "
            "(0 is standing on it)"]
        assert maplab._album_when_errors('s', when, KNOWN) == [
            "sticker 's' when 'comes-near' distance must be an integer 0 to 9"]
    # 0 is standing on the thing, and the table is what says so.
    assert maplab._rule_event_errors(
        'r', {'comes-near': {'who': 'torch', 'distance': 0}}, KNOWN) == []


def test_a_field_that_names_nothing_the_pack_declares_names_the_author_and_the_thing():
    assert maplab._rule_event_errors('r', {'picks-up': {'what': 'ghost'}}, KNOWN) == [
        "rule 'r' when 'picks-up' names unknown item 'ghost'"]
    assert maplab._album_when_errors('s', {'picks-up': {'what': 'ghost'}}, KNOWN) == [
        "sticker 's' when 'picks-up' names unknown item 'ghost'"]


def test_a_two_field_event_names_the_field_and_a_one_field_event_does_not():
    # The wording follows the table: an event with one field is named by its event alone,
    # an event with two is named by event and field.
    assert maplab._rule_event_errors('r', {'enters': {'place': 'ghost'}}, KNOWN) == [
        "rule 'r' when 'enters' names unknown place 'ghost'"]
    assert maplab._rule_event_errors('r', {'uses-with': {'item': 'ghost',
                                                         'with': 'hearth'}}, KNOWN) == [
        "rule 'r' when 'uses-with' item names unknown item 'ghost'"]


def test_a_field_of_the_wrong_shape_keeps_its_own_author_s_grammar():
    # 'a item' is today's byte in the album validator, and it stays: this slice moves the
    # vocabulary, not the prose.
    assert maplab._album_when_errors('s', {'picks-up': {'what': 3}}, KNOWN) == [
        "sticker 's' when 'picks-up' must be a item"]
    assert maplab._rule_event_errors('r', {'picks-up': {'what': 3}}, KNOWN) == [
        "rule 'r' when 'picks-up' must be a item id"]


def test_an_unknown_or_missing_field_is_still_reported_in_payload_order():
    assert maplab._rule_event_errors(
        'r', {'uses-with': {'with': 'hearth', 'item': 'torch', 'extra': 1}}, KNOWN) == [
            "rule 'r' when 'uses-with' has unknown key 'extra'"]
    assert maplab._rule_event_errors('r', {'uses-with': {'with': 'hearth'}}, KNOWN) == [
        "rule 'r' when 'uses-with' needs key 'item'"]
    # Unknown fields first, in the pack's own order, then the missing ones in table order.
    assert maplab._album_when_errors(
        's', {'uses-with': {'with': 'hearth', 'extra': 1}}, KNOWN) == [
            "sticker 's' when 'uses-with' has unknown key 'extra'",
            "sticker 's' when 'uses-with' needs key 'item'"]


def test_an_unknown_event_is_refused_and_the_sentence_lists_the_whole_table():
    (rule,) = maplab._rule_event_errors('r', {'bogus': {}}, KNOWN)
    assert rule == ("rule 'r' when names unknown event 'bogus' - the events are "
                    + ', '.join(THIRTEEN))
    assert 'six' not in rule
    assert maplab._album_when_errors('s', {'bogus': {}}, KNOWN) == [
        "sticker 's' when names unknown event 'bogus'"]


def test_a_when_that_names_zero_or_two_events_is_refused_before_the_table():
    assert maplab._rule_event_errors('r', {}, KNOWN) == [
        "rule 'r' when must name exactly one event"]
    assert maplab._rule_event_errors(
        'r', {'starts': {}, 'enters': {'place': 'town'}}, KNOWN) == [
            "rule 'r' when must name exactly one event"]
    assert maplab._rule_event_errors('r', 'starts', KNOWN) == [
        'rule \'r\' when must be an event object']
    assert maplab._rule_event_errors('r', {'starts': []}, KNOWN) == [
        "rule 'r' when 'starts' carries an object payload"]
    assert maplab._album_when_errors('s', {}, KNOWN) == [
        "sticker 's' when must name exactly one event"]
    assert maplab._album_when_errors('s', 'starts', KNOWN) == [
        "sticker 's' when must name one event"]


def test_both_validators_reach_the_same_table_for_the_same_payload():
    # One table, two voices: every event the rule validator accepts is one the sticker
    # validator accepts, and the two disagree about nothing but the words they use.
    for event, payload in GOOD.items():
        assert maplab._rule_event_errors('r', {event: payload}, KNOWN) == (
            maplab._album_when_errors('s', {event: payload}, KNOWN))
    for event in THIRTEEN:
        assert set(maplab.RULE_EVENT_KEYS[event]) == set(
            k.name for k in shapes.EVENTS[event])


# --- the JavaScript twin, until S3 generates it --------------------------

def _js_events():
    """The hand-written `EVENTS` table the woven player runs, from whatever part holds it."""
    root = Path(__file__).resolve().parents[1]
    found = {}
    for part in sorted((root / 'web' / 'player' / 'parts').glob('*.js')):
        for name, keys in re.findall(
                r"'([a-z-]+)':\s*\{\s*keys:\s*\[([^\]]*)\]", part.read_text()):
            if name not in THIRTEEN:
                continue
            found[name] = re.findall(r"'([^']*)'", keys)
    return found


def test_the_player_event_table_still_matches_the_python_one():
    # S3 generates this block from `shapes.EVENTS` (it waits on K3, the camera split). Until
    # then this is the guard against the drift #269 was: both tables must name the same
    # events carrying the same keys, in the same order.
    assert _js_events() == {event: [field[0] for field in EXPECTED[event]]
                            for event in THIRTEEN}