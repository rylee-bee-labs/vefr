"""Capture the validator golden from the code as it stands. Run once on main, before any
migration, then never again without a written reason: `uv run python tests/golden/validator/gen.py`.

S2 added the `rules` and `album` cases (the two `when` validators), BEFORE the migration, with the
reason in tests/test_event_table.py: S0 captured `saves` and `sound` only, so the sentences this
slice moves onto one table were never pinned, and the sentence the plan expected to regenerate
("the six events") had already been corrected on main by c364adb. Nothing was regenerated or
edited after the migration: the added cases are the proof that moving the vocabulary onto
`shapes.EVENTS` changed no sentence and no order.

One sentence changed on purpose a second time, for #365 (`falls` and `wakes`): an unknown event now
lists thirteen, not eleven. That is the same one-time regeneration the table earned when the
vocabulary moved, written down here because this file says a change needs a reason. Four `when`
cases were added beside it - two events, an accepted shape and a refused one each - and nothing
else in the capture moved: the diff is that one line and the eight new cases.

One sentence changed on purpose a third time, for the item-grants slice (`uses-verb`): an
unknown event now lists fourteen, not thirteen. The same one-time regeneration the table
earned the last two times, and the same shape of reason: four `when` cases were added beside
it - a refused verb and a missing key, for both validators - the accepted shape is pinned in
tests/test_event_table.py GOOD, where a pack's own verb exists to be named, and nothing else in
the capture moved. This world is unchanged, so every other case's bytes are untouched."""
import json
from pathlib import Path

from vefr import maplab

SAVES = [None, 0, "x", [], {}, {"rules": "persist"}, {"rules": "reset"}, {"rules": "nope"},
         {"rules": 3}, {"rules": "persist", "legacy": "fresh"}, {"rules": "persist", "legacy": "from-log"},
         {"legacy": "bad"}, {"legacy": None}, {"extra": 1}, {"rules": "x", "legacy": "y", "extra": 1, "more": 2},
         {"zeta": 1, "rules": "persist", "alpha": 2}]
SOUND = [None, 0, "x", [], {}, {"theme": "soft"}, {"theme": "loud"}, {"theme": 1}, {"theme": None},
         {"theme": "soft", "volume": 3}, {"volume": 3}, {"b": 1, "a": 2}, {"theme": "loud", "x": 1}]

# The world every `when` case is written into: one region, two items,
# one phase, one flag, so a case that names a real id says nothing and
# a case that names an absent one says exactly one sentence. No pack
# directory: every id below comes from the world itself.
WHENS = [
    "starts",
    {"starts": {}},
    {},
    {"starts": {}, "enters": {"place": "town"}},
    {"bogus": {}},
    {"starts": []},
    {"enters": {"place": "town"}},
    {"enters": {"place": "nowhere"}},
    {"enters": {"place": 3}},
    {"enters": {}},
    {"enters": {"place": "town", "extra": 1}},
    {"comes-near": {"who": "torch", "distance": 0}},
    {"comes-near": {"who": "torch", "distance": 2}},
    {"comes-near": {"who": "ghost", "distance": 1}},
    {"comes-near": {"who": "torch", "distance": True}},
    {"comes-near": {"who": "torch", "distance": 10}},
    {"comes-near": {"who": "torch", "distance": -1}},
    {"opens": {"what": "torch"}},
    {"opens": {"what": "ghost"}},
    {"picks-up": {"what": "chalked-map"}},
    {"picks-up": {"what": "ghost"}},
    {"uses-with": {"item": "torch", "with": "chalked-map"}},
    {"uses-with": {"item": "ghost", "with": "chalked-map"}},
    {"uses-with": {"item": "torch", "with": "ghost"}},
    {"uses-with": {"item": "torch"}},
    {"defeats": {"what": "rat"}},
    {"buys": {"what": "chalked-map"}},
    {"sells": {"what": "chalked-map"}},
    {"reads": {"what": "almanac"}},
    {"reads": {"what": "ghost"}},
    {"phase-changes": {"to": "dawn"}},
    {"phase-changes": {"to": "dusk"}},
    # #365 added `falls` and `wakes` to shapes.EVENTS, and the sentence the
    # two `when` validators speak for them changed with the table: an unknown
    # event now lists thirteen, and `falls` - the first two-field event whose
    # second field is not a distance - has to name `where` beside `what`. There
    # is no pack directory here, so `enemies` is empty and every enemy id in a
    # `falls` payload is refused by name; the accepted shape is pinned where a
    # pack exists (tests/test_event_table.py GOOD, tests/test_death_events.py).
    {"falls": {"what": "rat", "where": "town"}},
    {"falls": {"what": "rat"}},
    {"wakes": {"where": "town"}},
    {"wakes": {"where": "nowhere"}},
    # The item-grants slice added `uses-verb` to shapes.EVENTS, and with it
    # the sentence the two `when` validators speak for an unknown event
    # changed again: it now lists fourteen. There is no pack directory here,
    # so the only verb this world has is the one `mend-kit` grants - which is
    # the point of the pair: a verb the pack declared is accepted by name,
    # and one it never declared is refused by name.
    {"uses-verb": {"verb": "mend"}},
    {"uses-verb": {"verb": "ghost"}},
    {"uses-verb": {}},
]
BASE = {
    "regions": {"town": {"name": "Town"}},
    # `mend-kit` is the item-grants slice's one item: it grants the verb
    # `mend`, which is what makes `uses-verb`'s accepted case nameable here
    # with no pack directory at all.
    "items": {"torch": {"name": "torch"}, "chalked-map": {"name": "map"},
              "mend-kit": {"name": "a mend kit",
                           "grants": [{"verb": "mend", "label": "Mend"}]}},
    "phases": {"dawn": "dawn"},
    "flags": {"lit": "the torch burns"},
}
RULE = {"id": "r1", "then": [{"set": "lit"}]}
STICKER = {"id": "s1", "name": "A sticker", "kind": "open"}


def whens():
    for when in WHENS:
        yield "rules", json.dumps(when), dict(BASE, rules=[dict(RULE, when=when)])
        yield "album", json.dumps(when), dict(BASE, album=[dict(STICKER, when=when)])


# E4 added the `section` block BEFORE it landed, with its expected
# sentences written out by hand from the table's own defaults and put in
# cases.json; this file is the re-capture path for them, and running it
# after the block landed reproduced cases.json byte for byte. A Section is
# not a world block, so a case carries a `section` and the pack's affix
# list rather than a `world`, and one `resolve` stands in for the
# Blueprint: `rat` is a family, everything else is not one.
SECTION_FILE = "sections/cellar.json"
SECTION = {
    "section": 1, "id": "cellar", "floors": 9,
    "size": {"w": [64, 80], "h": [44, 56]},
    "rooms": [12, 18],
    "tiles": {"#": "cellar-wall", ".": "cellar-floor"},
    "fog": {"radius": 4},
    "families": [{"family": "rat", "weight": 5, "depth": [1, 6]}],
    "pattern": ["entry", "n", "n", "special", "landing", "n", "special", "n",
                "warden"],
    "specials": ["treasure", "infested", "hub"],
    "elites": {"per_floor": [1, 2], "affixes": ["broad", "quick"]},
    "groups": {"per_floor": [1, 2], "minions": [2, 3]},
    "curve": {"hp": [1.0, 1.4], "atk": [1.0, 1.3]},
    "loot": {"tier": 1},
    "stamps": ["cellar", "any"],
    "pois": ["the rusted grate"],
    "warden": "ashwing", "vault": "vault-cellar",
}
SECTION_AFFIXES = [{"id": "broad", "label": "Broad {name}"},
                   {"id": "quick", "label": "Quick {name}"}]
LAST_BOSS = ["entry", "n", "n", "special", "landing", "n", "special", "n",
             "boss"]
EIGHT_FLOORS = ["entry", "n", "n", "special", "landing", "n", "special",
                "warden"]


def resolve(family_id: str):
    """The base record of a family the Blueprint has, or None for one it has not."""
    if family_id != "rat":
        return None
    return {"name": "a rat", "hp": 2, "atk": 1, "xp": 1}


def _section(label, **kw):
    """One `section` case: `SECTION` with `kw` written over it."""
    section = dict(SECTION)
    section.update(kw)
    return {"block": "section", "case": label, "section": section,
            "affixes": SECTION_AFFIXES,
            "errors": maplab.section_block_errors(
                section, SECTION_AFFIXES, resolve, SECTION_FILE)}


def _whole(label, section, affixes=SECTION_AFFIXES):
    """One `section` case written out whole rather than as an edit."""
    return {"block": "section", "case": label, "section": section,
            "affixes": affixes,
            "errors": maplab.section_block_errors(
                section, affixes, resolve, SECTION_FILE)}


def sections():
    yield _section("the shape of plan section 2")
    yield _whole("a section pack that is not an object", [])
    yield _whole("the five required keys and nothing else", {
        "section": 1, "id": "cellar",
        "families": [{"family": "rat", "weight": 5}],
        "elites": {"per_floor": [1, 2], "affixes": ["broad"]},
        "groups": {"per_floor": [1, 2], "minions": [2, 3]}})
    yield _whole("nothing at all is the two missing keys", {})
    for label, kw in (
        ("an unknown key", {"zeta": 1}),
        ("two unknown keys and two wrong values",
         {"zeta": 1, "alpha": 2, "section": 0, "rooms": [2, 18]}),
        ("an id that is not a string", {"id": 3}),
        ("an id with nothing in it", {"id": ""}),
        ("more floors than a section may have", {"floors": 12}),
        ("a size that is not an object", {"size": 3}),
        ("a size with no width", {"size": {"h": [44, 56]}}),
        ("a width half out of range", {"size": {"w": [64, 200], "h": [44, 56]}}),
        ("a height that is a triple", {"size": {"w": [64, 80], "h": [44, 56, 60]}}),
        ("a fog with no radius", {"fog": {}}),
        # 33, not 9: vefr #364 raised the ceiling on a Section's fog radius
        # from 8 to a quarter of the widest floor `SIZE` allows (32), so the
        # case that pins the refusal moves with it. See tests/test_fog_radius.py.
        ("a fog radius out of range", {"fog": {"radius": 33}}),
        ("a tile table that is not a table", {"tiles": []}),
        ("a glyph with no tileset", {"tiles": {"#": "cellar-wall", ".": 3}}),
        ("families that are not a list", {"families": {}}),
        ("a family with no family in it", {"families": [{"weight": 5}]}),
        ("a family weight of zero", {"families": [{"family": "rat", "weight": 0}]}),
        ("a pattern that is not a list", {"pattern": "entry"}),
        ("a pattern slot that is not a slot", {"pattern": LAST_BOSS}),
        ("a special kind the dungeon does not have", {"specials": ["maze"]}),
        ("specials that are not a list", {"specials": 3}),
        ("a curve half that is not a whole hundredth",
         {"curve": {"hp": [1.0, 1.41], "atk": [1.0, 1.3]}}),
        ("a curve out of range", {"curve": {"hp": [1.0, 9.0], "atk": [1.0, 1.3]}}),
        ("a loot tier of zero", {"loot": {"tier": 0}}),
        ("a pattern shorter than its section", {"pattern": EIGHT_FLOORS}),
        ("a pattern with no warden floor", {"pattern": ["n"] * 9}),
        ("a pattern with one landing",
         {"pattern": ["entry", "n", "n", "n", "n", "n", "n", "n", "warden"]}),
        ("a pattern asking for a special it does not name", {"specials": []}),
        ("a stamp id that is not a string", {"stamps": ["cellar", 3]}),
        ("a point of interest that is not a name", {"pois": [3]}),
        ("a warden with nothing in it", {"warden": ""}),
        ("an affix the pack never defines",
         {"elites": {"per_floor": [1, 2], "affixes": ["broad", "vast"]}}),
        ("an elite-led group with no affix to lead it",
         {"elites": {"per_floor": [1, 2], "affixes": []}}),
        ("a family the blueprint does not have",
         {"families": [{"family": "ghost", "weight": 1}]}),
    ):
        yield _section(label, **kw)
    # A whole Section with no `affixes.json` behind it: a pack that names
    # affixes and ships no list is answered by a different function, on
    # the same block.
    yield _whole("affixes named in a pack with no affixes.json",
                 dict(SECTION), affixes=None)
    yield _section("a slot, a family and a pattern wrong at once",
                   pattern=LAST_BOSS,
                   families=[{"family": "ghost", "weight": 1}])


def cases():
    for name, fn, values in (("saves", maplab.saves_errors, SAVES), ("sound", maplab.sound_errors, SOUND)):
        for v in values:
            if v is None:
                yield {"block": name, "case": "absent", "world": {},
                       "errors": fn({})}
            w = {name: v}
            yield {"block": name, "case": json.dumps(v), "world": w,
                   "errors": fn(w)}
    for name, case, w in whens():
        fn = maplab.rules_errors if name == "rules" else maplab.album_errors
        yield {"block": name, "case": case, "world": w, "errors": fn(w)}
    yield from sections()


if __name__ == "__main__":
    out = list(cases())
    Path(__file__).with_name("cases.json").write_text(json.dumps(out, indent=1) + "\n")
    print(len(out), "cases")
