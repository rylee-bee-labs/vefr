"""E4 (endless dungeon): Sections - the pack shape, the depth curve, the
pattern, the landings, and the sweep over Sections. FROZEN: written before
`src/vefr/sections.py` and before the `section` block on the schema table.

PLAN.md section 2 is the spec this file is written from, and the four
rules of the determinism section are the ones with teeth here:

- `locate(depth, pack)` is pure and derived only from the pack's Section
  list, and the story is cycle 0;
- `floor_key` is `run_seed/section.id/cycle/k`;
- a floor is identified by `(gen version, section content hash, floor_key)`,
  so editing a pack's Section data invalidates that Section's floors;
- no float but `floor(rng() * n)` with `0 <= n < 2^31`, and no draw out of
  a dictionary - every list below is a list, sorted, with ties broken by
  index.

Where each part of the slice is pinned:

| what | where in this file |
|---|---|
| the Section pack shape and its sentences | `tests/golden/validator/cases.json` (block `section`), `tests/test_validator_golden.py` |
| the block's refusals, in this file's own words | "the block" |
| the depth curve | "the depth curve" |
| the floor pattern, the special floor's kind | "the pattern" |
| landings, the recorded ones, the flag each sets | "landings" |
| floor identity: the key, the content hash | "floor identity" |
| weighted families, resolved from the Blueprint by id | "the families" |
| `vefr check` sweeps every Section x 200 seeds | "the sweep" |
| a second fixture pack, different Section data, no code change | "two packs" |
| the bake: nine floors, doors, the landing up-stairs | "the bake" |

The two fixture packs are `tests/fixtures/sections/cellar` and
`tests/fixtures/sections/attic`. They are committed Section DATA - a
Blueprint, an affix list and one `sections/<id>.json` each - and they are
deliberately unlike one another: nine floors against eleven, 64x48
against 48x32, three families against two with the weights the other way
round, three special kinds against one, one loot tier against two. Every
test that reads one of them reads the other through the same code, which
is the whole of acceptance 3: a Section is data, not a hardcoded cellar.

The names in both packs are placeholders and stay that way. Section
names, warden assignments, vault notes and points of interest are gated
on Rylee (PLAN.md section 6), so nothing here is canon and nothing here
is meant to become canon.

Run with:

    bash tests/run.sh tests/test_sections_e4.py
"""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import pytest

from blueprint_helpers import normalized_pack, vefr

from vefr import blueprint, cli, delve_v3, locks, maplab, sections, shapes

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sections"
PACKS = ("cellar", "attic")
SEEDS = 200


# ------------------------------------------------------------------ helpers


def fixture_pack(name: str) -> dict:
    """One committed fixture pack's Section, read off disk.

    Read rather than imported, because the acceptance is that the FILES
    validate: a Section that only exists as a Python dict would prove
    nothing about the file a pack author actually writes.
    """
    return json.loads((FIXTURES / name / "sections" / f"{name}.json").read_text(
        encoding="utf-8"))


def resolver(name: str):
    """The `resolve` callable `shapes.check_section` asks families of."""
    source = blueprint.read(FIXTURES / name / "blueprint.json")

    def resolve(family_id: str):
        try:
            return blueprint.resolve_family(source, family_id)
        except blueprint.BlueprintError:
            return None
    return resolve


def a_pack(tmp_path, name: str) -> Path:
    """A real pack carrying one committed fixture pack's Section data.

    Built the shipped way - `make_blueprint_pack` plus a real `vefr
    normalize` - over the FIXTURE's own Blueprint, with its `sections/`
    and `affixes.json` copied in. The Blueprint has to be the fixture's:
    a Section names its families by id and the Blueprint is where a family
    is, so a pack built over a different one would refuse the very Section
    it is being built to carry.
    """
    built = normalized_pack(
        tmp_path,
        blueprint=json.loads((FIXTURES / name / "blueprint.json").read_text(
            encoding="utf-8")))
    for part in ("sections", "affixes.json"):
        source = FIXTURES / name / part
        target = built / part
        if source.is_dir():
            target.mkdir(exist_ok=True)
            for path in sorted(source.glob("*.json")):
                (target / path.name).write_text(path.read_text(encoding="utf-8"),
                                               encoding="utf-8")
        else:
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return built


def a_floor(section: dict, k: int, seed: str = "check-0", cycle: int = 0) -> dict:
    """One v3 FloorPlan, drawn the way the curve says a floor is drawn."""
    key = sections.floor_key(seed, section, cycle, k)
    return delve_v3.generate_floor_v3(
        seed, sections.floor_size(section, key), copy.deepcopy(section),
        sections.floor_kind(section, k, seed, cycle), depth=k)


def walkable(plan: dict) -> set[tuple[int, int]]:
    return {(x, y)
            for y in range(plan["h"])
            for x in range(plan["w"])
            if plan["rows"][y][x] in ".ud"}


def flood(plan: dict, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Every walkable tile 4-connected to `start`."""
    rows, w, h = plan["rows"], plan["w"], plan["h"]
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and rows[ny][nx] in ".ud" \
                    and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def tile_of(plan: dict, anchor: str) -> tuple[int, int]:
    at = plan["anchors"][anchor]
    return (at[0], at[1])


# ------------------------------------------------------------------ the block


def test_the_table_holds_a_section_block():
    assert "section" in shapes.BLOCKS
    assert shapes.BLOCKS["section"] is shapes.SECTION


def test_the_section_shape_of_plan_section_2_has_no_problems():
    """The shape verbatim, as `shapes.check` reads it.

    PLAN.md section 2 writes the Section pack in one line. This is that
    line, so a refusal of any part of it would be a refusal of the spec.
    """
    section = {
        "section": 1, "id": "cellar", "floors": 9,
        "size": {"w": [64, 80], "h": [44, 56]}, "rooms": [12, 18],
        "tiles": {"#": "cellar-wall", ".": "cellar-floor"},
        "fog": {"radius": 4},
        "families": [{"family": "rat", "weight": 5, "depth": [1, 6]}],
        "pattern": ["entry", "n", "n", "special", "landing", "n", "special",
                    "n", "warden"],
        "specials": ["treasure", "infested", "hub"],
        "elites": {"per_floor": [1, 2], "affixes": ["big", "quick", "glowing"]},
        "groups": {"per_floor": [1, 2], "minions": [2, 3]},
        "curve": {"hp": [1.0, 1.4], "atk": [1.0, 1.3]},
        "loot": {"tier": 1},
        "stamps": ["cellar", "any"], "pois": ["the rusted grate"],
        "warden": "ashwing", "vault": "vault-cellar",
    }
    assert shapes.check(shapes.SECTION, section) == []


def only(problems) -> tuple[str, str]:
    """The one problem a value earns, as (pointer, sentence)."""
    assert len(problems) == 1, [p.sentence for p in problems]
    return problems[0].pointer, problems[0].sentence


def base() -> dict:
    """A Section that has no problems, so one edit is what a test changes."""
    return copy.deepcopy(fixture_pack("cellar"))


def test_the_two_required_keys_are_named_one_each():
    """`{}` is two sentences, in table order: `id` and `families`.

    One per missing required key rather than one for the whole table: an
    author who deleted both keys should be told about both. Only TWO keys
    are required, and ADR 0014's own frozen tests are why: a Section may
    leave `elites` out entirely.
    """
    problems = shapes.check(shapes.SECTION, {})
    assert [(p.pointer, p.sentence) for p in problems] == [
        ("/section/id", "section must hold its id"),
        ("/section/families", "section must hold its families"),
    ]


def test_a_section_with_only_the_required_keys_is_legal_without_the_rest():
    """`delve_v3` says only a handful of keys are required, and it is right.

    The comment above `_read_rooms` in `delve_v3.py` is the same claim:
    every accessor defaults and a missing key never raises. A table that
    demanded the whole PLAN shape would refuse a pack that the generator
    already reads without complaint.
    """
    assert shapes.check(shapes.SECTION, {
        "section": 1, "id": "cellar",
        "families": [{"family": "rat", "weight": 5}],
        "elites": {"per_floor": [1, 2], "affixes": ["big"]},
        "groups": {"per_floor": [1, 2], "minions": [2, 3]},
    }) == []


def test_an_unknown_top_level_key_is_refused_with_the_whole_table():
    section = dict(base(), zeta=1)
    (pointer, sentence) = only(shapes.check(shapes.SECTION, section))
    assert pointer == "/section/zeta"
    assert sentence == (
        "section has an unknown key 'zeta'; it may only hold section, id, "
        "floors, size, rooms, tiles, fog, families, pattern, specials, "
        "elites, groups, mobs, curve, loot, stamps, pois, warden, vault and "
        "endless")


def test_the_size_block_bounds_each_half_of_each_pair():
    section = dict(base(), size={"w": [64, 200], "h": [48, 56]})
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/size/w/1", "section.size.w[1] must be between 32 and 128")


def test_the_fog_radius_is_a_whole_number_in_its_range():
    """The low end moves with the ceiling but does not move: still 2, and
    the same pointer. vefr #364 raised `hi` and left this sentence's shape
    alone; `tests/test_fog_radius.py` holds the ceiling itself."""
    section = dict(base(), fog={"radius": 0})
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/fog/radius", "section.fog.radius must be between 2 and 32")


def test_a_tile_table_names_a_tileset_for_every_glyph():
    section = dict(base(), tiles={"#": "cellar-wall", ".": 3})
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/tiles/.", "section.tiles['.'] must name a tileset, such as "
                            '"wall"')


def test_a_family_entry_names_a_family():
    section = dict(base(), families=[{"weight": 5}])
    assert only(shapes.check(shapes.SECTION, section))[0] == (
        "/section/families/0/family")


def test_the_pattern_is_a_list_of_the_five_slots():
    section = dict(base(), pattern="entry")
    assert only(shapes.check(shapes.SECTION, section))[1] == (
        'section.pattern must be a list of "entry", "n", "special", '
        '"landing" and "warden"')


def test_a_pattern_slot_that_is_not_a_slot_is_refused_at_that_entry():
    section = dict(base(), pattern=["entry", "n", "n", "special", "landing",
                                    "n", "special", "n", "boss"])
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/pattern/8", 'section.pattern[8] must be "entry" or "n" or '
                              '"special" or "landing" or "warden"')


def test_the_curve_is_a_pair_of_whole_hundredths():
    section = dict(base(), curve={"hp": [1.0, 1.415], "atk": [1.0, 1.3]})
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/curve/hp/1", "section.curve.hp[1] must be a whole number of "
                               "hundredths, such as 1.25")


def test_the_curve_is_bounded_in_hundredths():
    section = dict(base(), curve={"hp": [1.0, 9.0], "atk": [1.0, 1.3]})
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/curve/hp", "section.curve.hp must be between 1.0 and 3.0")


def test_the_loot_tier_is_a_whole_number_in_its_range():
    section = dict(base(), loot={"tier": 0})
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/loot/tier", "section.loot.tier must be between 1 and 9")


def test_a_pattern_shorter_than_its_section_is_refused():
    # Eight entries, ending in a warden and landing twice, so the length
    # is the ONLY thing wrong with it.
    section = dict(base(), pattern=["entry", "n", "n", "special", "landing",
                                    "n", "special", "warden"])
    assert only(shapes.check_section(section)) == (
        "/pattern", "a section's pattern must have one entry for each of "
                    "its 9 floors, and it has 8")


def test_a_pattern_that_does_not_end_in_a_warden_is_refused():
    section = dict(base(), pattern=["entry", "n", "n", "special", "landing",
                                    "n", "special", "n", "n"])
    assert only(shapes.check_section(section)) == (
        "/pattern", "a section's pattern must end with a warden floor, and "
                    "its last entry is \"n\"")


def test_a_pattern_with_one_landing_is_refused():
    section = dict(base(), pattern=["entry", "n", "n", "n", "n", "n", "n",
                                    "n", "warden"])
    assert only(shapes.check_section(section)) == (
        "/pattern", "every section needs a landing on its first floor and "
                    "another by its fifth, and this pattern names 1")


def test_a_pattern_that_asks_for_a_special_and_names_none_is_refused():
    section = dict(base(), specials=[])
    assert only(shapes.check_section(section)) == (
        "/specials", "a section's pattern asks for a special floor, and "
                     "names no specials")


def test_the_span_checks_are_skipped_by_a_section_that_names_no_pattern():
    """No pattern, nothing to say: the checks are not a required key's shadow.

    `delve_v3` defaults every Section key, and a pack that writes no
    pattern gets the default one. A table that refused it for having no
    pattern would refuse the pack the generator reads without complaint.
    """
    section = {"section": 1, "id": "cellar",
               "families": [{"family": "rat", "weight": 1}],
               "elites": {"per_floor": [0, 0], "affixes": []},
               "groups": {"per_floor": [0, 0], "minions": [2, 3]}}
    assert shapes.check_section(section) == []


# ------------------------------------------------------------- the depth curve


def test_locate_walks_the_story_in_pack_order():
    """Depth 1 is the first floor of the first Section, and cycle 0.

    `locate` is pure and reads nothing but the Section list, so two packs
    with the same Sections locate a depth the same way whatever the files
    around them hold.
    """
    cellar, attic = fixture_pack("cellar"), fixture_pack("attic")
    both = [cellar, attic]
    assert sections.locate(1, both) == (0, cellar, 1)
    assert sections.locate(9, both) == (0, cellar, 9)
    assert sections.locate(10, both) == (0, attic, 1)
    assert sections.locate(20, both) == (0, attic, 11)


def test_locate_takes_a_pack_directory_as_well_as_a_list():
    both = [fixture_pack("cellar"), fixture_pack("attic")]
    assert sections.locate(3, FIXTURES / "cellar") == sections.locate(3, both[:1])
    assert sections.locate(3, str(FIXTURES / "attic")) == sections.locate(3, both[1:2])


def test_locate_orders_sections_by_their_number_and_then_by_id():
    """Arrays sorted by id, ties broken by the record's own order.

    A pack that ships two Sections numbered the same way is a pack whose
    order is the order the files were read in, which is the order their
    ids sort into - never a dictionary's.
    """
    two = [dict(fixture_pack("cellar"), section=2, id="b-section"),
           dict(fixture_pack("attic"), section=1, id="z-section")]
    assert [s["id"] for s in sections.ordered(two)] == ["z-section", "b-section"]


def test_locate_is_refused_a_depth_it_cannot_name():
    """Past the last floor of the story there is no answer yet.

    The endless cycles are slice E10 and this slice does not invent them:
    a depth past the story raises rather than being clamped onto the last
    Section, which would send a player down floors that do not exist.
    """
    both = [fixture_pack("cellar"), fixture_pack("attic")]
    with pytest.raises(ValueError):
        sections.locate(21, both)
    with pytest.raises(ValueError):
        sections.locate(0, both)
    with pytest.raises(ValueError):
        sections.locate("1", both)


def test_locate_never_mutates_the_pack_it_is_handed():
    both = [fixture_pack("cellar"), fixture_pack("attic")]
    before = json.dumps(both, sort_keys=True)
    sections.locate(4, both)
    assert json.dumps(both, sort_keys=True) == before


# ---------------------------------------------------------------- the pattern


def test_the_pattern_defaults_to_the_nine_floors_of_plan_section_4():
    assert sections.pattern({}) == sections.DEFAULT_PATTERN
    assert sections.pattern({}) == (
        "entry", "n", "n", "special", "landing", "n", "special", "n", "warden")


def test_a_section_with_fewer_floors_keeps_its_own_pattern():
    """A Section's pattern is its own; the default is only a default.

    A nine-entry default read onto an eleven-floor Section would be nine
    floors of eleven, so the pattern is padded with `n` rather than
    truncated and never read past its own end.
    """
    assert sections.pattern({"floors": 11})[:9] == sections.DEFAULT_PATTERN
    assert sections.pattern({"floors": 11})[9:] == ("n", "n")
    assert len(sections.pattern({"floors": 11})) == 11


def test_a_slot_is_the_pattern_entry_for_that_floor():
    cellar = fixture_pack("cellar")
    assert [sections.slot(cellar, k) for k in range(1, 10)] == [
        "entry", "n", "n", "special", "landing", "n", "special", "n", "warden"]


def test_a_slot_past_the_end_of_the_pattern_is_an_ordinary_floor():
    cellar = fixture_pack("cellar")
    assert sections.slot(cellar, 10) == "n"


def test_an_ordinary_slot_is_a_normal_floor():
    cellar = fixture_pack("cellar")
    for k in (1, 2, 3, 5, 6, 8, 9):
        assert sections.floor_kind(cellar, k, "check-0") == "normal"


def test_a_special_slot_draws_one_of_the_specials_the_section_names():
    cellar = fixture_pack("cellar")
    drawn = {sections.floor_kind(cellar, k, f"check-{i}") for k in (4, 7)
             for i in range(40)}
    assert drawn <= set(sections.specials(cellar))
    assert drawn, "no special floor was drawn at all"
    assert all(kind in delve_v3.FLOOR_KINDS for kind in drawn)


def test_the_special_floor_of_one_floor_is_the_same_every_time():
    """The draw is on its own stream, keyed off the floor, not off the clock.

    Same run seed, same floor, same special kind - which is what lets the
    JavaScript twin answer without being told anything but the key.
    """
    cellar = fixture_pack("cellar")
    keys = {sections.floor_key("check-3", cellar, 0, 4)}
    assert keys == {"check-3/cellar/0/4"}
    assert sections.floor_kind(cellar, 4, "check-3") == sections.floor_kind(
        cellar, 4, "check-3")


def test_the_two_packs_draw_different_specials_because_they_name_different_ones():
    cellar, attic = fixture_pack("cellar"), fixture_pack("attic")
    assert sections.specials(attic) == ("treasure",)
    assert sections.specials(cellar) == ("treasure", "infested", "hub")
    assert set(sections.floor_kind(attic, 3, f"check-{i}") for i in range(5)) \
        == {"treasure"}
    # The same slot of the pattern in the other pack is not a treasure floor.
    # This is the comparison the test name promises and the first version of it
    # never made: it bound `cellar` and then only ever looked at `attic`.
    assert set(sections.floor_kind(cellar, 3, f"check-{i}") for i in range(5)) \
        != {"treasure"}


# ------------------------------------------------------------------ landings


def test_a_section_has_two_landings_its_first_floor_and_its_fifth():
    assert sections.landings(fixture_pack("cellar")) == (1, 5)
    assert sections.landings(fixture_pack("attic")) == (1, 5)


def test_a_short_section_lands_on_every_floor_of_its_pattern():
    """A five-floor Section has a landing on 1 and on 5; a three has one.

    Stardew's every-five is the rule for a Section long enough to have a
    fifth, and a Section shorter than that lands where its pattern says.
    """
    assert sections.landings({"pattern": ["entry", "n", "warden"]}) == (1,)
    assert sections.landings({"pattern": ["entry", "landing", "warden"]}) == (1, 2)


def test_reaching_a_landing_records_it_under_its_own_flag():
    """The flag is the record, and it is named after the floor it is.

    PLAN.md section 2 keeps landings reached in rule state beside warden
    killed and vault read, and PLAN.md section 4 says a landing records
    it permanently. So the id the player sets has to name the Section and
    the floor and nothing else - one flag, one landing, forever.
    """
    cellar = fixture_pack("cellar")
    assert sections.landing_flag(cellar, 5) == "landing-cellar-5"
    assert sections.landing_flag(cellar, 1) == "landing-cellar-1"
    assert sections.landing_flag(cellar, 5) != sections.landing_flag(cellar, 1)


def test_only_the_landings_the_hero_has_reached_are_offered():
    """The town's stair offers every RECORDED landing, and no others.

    The elevator rule has two halves and this is the second: there is no
    lift down past a floor the hero has not reached. A pack whose flags
    name a landing nobody reached offers nothing for it.
    """
    cellar = fixture_pack("cellar")
    assert sections.recorded_landings(cellar, set()) == ()
    assert sections.recorded_landings(cellar, {"landing-cellar-5"}) == (5,)
    assert sections.recorded_landings(
        cellar, {"landing-cellar-1", "landing-cellar-5"}) == (1, 5)
    # A flag for a floor that is not a landing of this Section is not one.
    assert sections.recorded_landings(cellar, {"landing-cellar-3"}) == ()
    assert sections.recorded_landings(cellar, {"landing-attic-1"}) == ()


def test_a_landing_reached_is_offered_in_pattern_order_not_flag_order():
    """A set of flags has no order; the landings do.

    The forbidden-list rule of PLAN.md section 2 is the reason: a set is
    iterated in no order that two languages would agree on, so the answer
    is the pattern's order every time.
    """
    attic = fixture_pack("attic")
    flags = {"landing-attic-5", "landing-attic-1"}
    assert sections.recorded_landings(attic, flags) == (1, 5)
    assert sections.recorded_landings(attic, set(flags)) == (1, 5)


# ------------------------------------------------------------- floor identity


def test_the_floor_key_is_the_run_seed_the_section_the_cycle_and_the_floor():
    cellar = fixture_pack("cellar")
    assert sections.floor_key("run-1", cellar, 0, 5) == "run-1/cellar/0/5"
    assert sections.floor_key("run-1", cellar, 1, 5) == "run-1/cellar/1/5"
    assert sections.floor_key("run-2", cellar, 0, 5) == "run-2/cellar/0/5"
    assert sections.floor_key("run-1", cellar, 0, 6) == "run-1/cellar/0/6"


def test_two_floors_of_one_section_are_two_floors():
    """The collision this key exists to stop.

    `delve_v3` builds its own stream name out of the seed, the section id
    and the floor KIND, so two floors of one Section that share a kind
    share a floor unless the caller passes the key in as the seed. Every
    caller in this slice does, which is why floors 2 and 3 of the cellar
    are two different maps.
    """
    cellar = fixture_pack("cellar")
    second = a_floor(cellar, 2, "check-9")
    third = a_floor(cellar, 3, "check-9")
    assert second["rows"] != third["rows"]


def test_the_floor_key_is_the_same_key_twice():
    cellar = fixture_pack("cellar")
    assert sections.floor_key("check-9", cellar, 0, 4) \
        == sections.floor_key("check-9", cellar, 0, 4)
    assert a_floor(cellar, 4, "check-9") == a_floor(cellar, 4, "check-9")


def test_the_content_hash_is_a_function_of_the_section_data_alone():
    cellar = fixture_pack("cellar")
    assert sections.content_hash(cellar) == sections.content_hash(
        copy.deepcopy(cellar))
    assert sections.content_hash(cellar) == sections.content_hash(
        fixture_pack("cellar"))


def test_editing_a_section_invalidates_its_floors():
    """Floor identity is (gen version, section content hash, floor key).

    So a pack that edits its Section data gets a different identity for
    every floor of it, and the save's deltas for those floors are dropped
    rather than replayed onto a map that is not the one they were recorded
    on. The hash is over the whole record, so it takes one key to change.
    """
    cellar = fixture_pack("cellar")
    edited = dict(cellar, rooms=[13, 18])
    assert sections.content_hash(edited) != sections.content_hash(cellar)
    assert sections.identity(3, cellar, "run-1/cellar/0/5") != sections.identity(
        3, edited, "run-1/cellar/0/5")
    assert sections.identity(3, cellar, "run-1/cellar/0/5") != sections.identity(
        2, cellar, "run-1/cellar/0/5")


def test_the_two_fixture_packs_have_different_content_hashes():
    assert sections.content_hash(fixture_pack("cellar")) != sections.content_hash(
        fixture_pack("attic"))


def test_the_floor_size_is_drawn_inside_the_section_s_own_range():
    for name in PACKS:
        section = fixture_pack(name)
        lo_w, hi_w, lo_h, hi_h = sections.size_range(section)
        for k in range(1, sections.floors(section) + 1):
            key = sections.floor_key("check-1", section, 0, k)
            w, h = sections.floor_size(section, key)
            assert (lo_w, hi_w) == (section["size"]["w"][0], section["size"]["w"][1])
            assert lo_w <= w <= hi_w and lo_h <= h <= hi_h


def test_the_size_is_the_same_size_every_time_and_a_different_one_per_floor():
    cellar = fixture_pack("cellar")
    keys = [sections.floor_key("check-4", cellar, 0, k) for k in range(1, 10)]
    sizes = [sections.floor_size(cellar, key) for key in keys]
    assert sizes == [sections.floor_size(cellar, key) for key in keys]
    assert len(set(sizes)) > 1, "nine floors all drew the same size"


# ----------------------------------------------------------------- the families


def test_a_section_names_its_families_by_id_and_gets_them_from_the_blueprint():
    """The families come from Blueprint, by id; the Section carries weights.

    ADR 0014 closes the enemy record, so a Section may not carry `hp` and
    `atk` of its own - it names a family and the Blueprint is where a
    family is. The weight and the depth range are the Section's.
    """
    cellar = fixture_pack("cellar")
    resolved = sections.families(cellar, resolver("cellar"))
    assert [entry["family"] for entry in resolved] == ["rat", "moth", "beetle"]
    assert resolved[0]["hp"] == 2 and resolved[0]["atk"] == 1
    assert resolved[0]["weight"] == 5
    assert resolved[0]["depth"] == [1, 6]


def test_a_family_the_blueprint_does_not_have_comes_back_nothing():
    """A missing family is the validator's sentence, not a crash here.

    `shapes.check_section` refuses it with `/families/0/family`, so the
    generator is never handed one that resolves to nothing.
    """
    section = dict(fixture_pack("cellar"), families=[{"family": "ghost",
                                                      "weight": 1}])
    resolved = sections.families(section, resolver("cellar"))
    assert resolved[0]["family"] == "ghost"
    assert "hp" not in resolved[0]


def test_a_pack_with_no_blueprint_resolves_no_families_and_says_nothing():
    section = dict(fixture_pack("cellar"), families=[{"family": "ghost",
                                                      "weight": 1}])
    assert sections.families(section, None) == section["families"]
    assert shapes.check_section(section, resolve=None) == []


def test_a_weighted_draw_uses_the_weights_the_section_wrote():
    """Two Sections, the same ids, the weights the other way round.

    The draw is `_draw_family`'s and it reads the weight list as it is
    given, so a Section that writes its weights differently gets a
    different mix out of the same three families.
    """
    heavy = {"families": [{"family": "rat", "weight": 9},
                          {"family": "moth", "weight": 1}]}
    lean = {"families": [{"family": "rat", "weight": 1},
                         {"family": "moth", "weight": 9}]}
    drawn_heavy = _mix(heavy)
    drawn_lean = _mix(lean)
    assert drawn_heavy[0] > drawn_lean[0]


def _mix(section: dict, draws: int = 60) -> tuple[int, int]:
    """How many of `draws` floors came out rat, over a fixed seed list."""
    rats = 0
    for i in range(draws):
        plan = delve_v3.generate_floor_v3(
            f"mix-{i}", (64, 48), copy.deepcopy(section), "normal")
        families = {spawn["family"] for spawn in plan["spawns"]}
        if "rat" in families:
            rats += 1
    return (rats, draws - rats)


# --------------------------------------------------------------------- sweeps


def test_every_section_of_every_fixture_pack_sweeps_two_hundred_seeds():
    """Acceptance 2: `vefr check` sweeps every Section x 200 seeds.

    The sweep is the PLAN.md section 7 property proof run over Sections
    rather than over one floor kind: every floor of every Section, at the
    Section's own size, drawn from its own floor key, has to hold.
    """
    for name in PACKS:
        with tempfile.TemporaryDirectory() as tmp:
            built = a_pack(Path(tmp), name)
            assert locks.section_findings(built, seeds=SEEDS) == [], name


def test_the_floors_of_a_section_hold_over_two_hundred_seeds():
    """The properties themselves, spelled out, over the whole Section.

    One component; the up-stair reaches the down-stair and every anchor,
    spawn, chest, point of interest and secret with it; the warden stands
    off the up-to-down path; and a Section that names a vault gets a vault
    anchor on every floor it draws.
    """
    for name in PACKS:
        section = fixture_pack(name)
        for seed_number in range(SEEDS):
            seed = f"check-{seed_number}"
            for k in range(1, sections.floors(section) + 1):
                plan = a_floor(section, k, seed)
                where = f"{name} floor {k} seed {seed}"
                assert plan["gen"] == 3, f"{where}: fell back to v2"
                up = flood(plan, tile_of(plan, "up"))
                down = tile_of(plan, "down")
                assert len(up) == len(walkable(plan)), f"{where}: two components"
                for anchor in ("up", "down", "warden", "landmark"):
                    assert tile_of(plan, anchor) in up, f"{where}: {anchor}"
                for poi in plan["pois"]:
                    assert (poi["at"][0], poi["at"][1]) in up, f"{where}: poi"
                for tile in plan["secrets"]:
                    assert (tile[0], tile[1]) in up, f"{where}: secret"
                for spawn in plan["spawns"]:
                    assert (spawn["at"][0], spawn["at"][1]) in up, f"{where}: mob"
                for chest in plan["chests"]:
                    assert (chest["at"][0], chest["at"][1]) in up, f"{where}: chest"
                assert down in up, f"{where}: the down-stair is cut off"
                if section.get("vault"):
                    assert plan["anchors"]["vault"] is not None, f"{where}: no vault"


def test_the_pacing_table_of_a_nine_floor_section_holds():
    """PLAN.md section 4, in one 9-floor Section, over 200 seeds.

    Two special floors; a landing on floor 5; one elite a floor and never
    more than two; the vault and the warden on floor 9; and every floor's
    monsters drawn from the families the Section names.
    """
    cellar = fixture_pack("cellar")
    slots = [sections.slot(cellar, k) for k in range(1, 10)]
    assert slots.count("special") == 2
    assert slots[4] == "landing" and sections.is_landing(cellar, 5)
    assert slots[8] == "warden"

    known = {entry["family"] for entry in cellar["families"]}
    for seed_number in range(SEEDS):
        seed = f"check-{seed_number}"
        for k in range(1, 10):
            plan = a_floor(cellar, k, seed)
            where = f"floor {k} seed {seed}"
            kinds = {sections.floor_kind(cellar, k, seed)}
            if "special" in kinds:
                assert sections.floor_kind(cellar, k, seed) in delve_v3.FLOOR_KINDS
            spawns = plan["spawns"]
            assert all(spawn["family"] in known for spawn in spawns), where
            elites = [s for s in spawns if "elite" in s]
            leaders = [s for s in elites if s.get("leader")]
            assert len(elites) - len(leaders) <= delve_v3.LONE_ELITES_MAX, where
            assert len(elites) >= 1, f"{where}: no elite at all"
            groups = {s["group"] for s in spawns if "group" in s}
            assert len(groups) <= delve_v3.GROUPS_MAX, where
            if k == 9:
                assert plan["anchors"]["vault"] is not None, where


def test_a_sections_floor_reaches_the_next_floors_stair():
    """There is no lift down past a floor the hero has not reached.

    The elevator rule, as a property: floor k's down-stair is reachable
    on floor k, so the hero can always go one floor deeper and never two.
    """
    cellar = fixture_pack("cellar")
    for seed_number in range(25):
        seed = f"check-{seed_number}"
        for k in range(1, 9):
            plan = a_floor(cellar, k, seed)
            up = flood(plan, tile_of(plan, "up"))
            assert tile_of(plan, "down") in up, f"{seed} floor {k}"


def test_a_section_key_is_reachable_before_its_own_door_and_unsellable(tmp_path):
    """The other half of acceptance 2, and it is the rule `locks` already has.

    A Section's key is the item its entry door requires: the bake wires the
    town's stair into the Section's first floor, and the author gates it
    with `requires`. So the same two findings the pack's other locks get
    apply to it - the key must be obtainable before its own door, and it
    must carry no `value`, or a trader could buy the way past the Section.
    """
    built = a_pack(tmp_path, "cellar")
    world = json.loads((built / "world.json").read_text(encoding="utf-8"))
    world["items"]["cellar-key"] = {"name": "a rust-dark key"}
    world["items"]["vault-key"] = {"name": "a vault key", "value": 40}
    (built / "world.json").write_text(json.dumps(world), encoding="utf-8")
    act_path = built / "acts" / "act-1" / "world.json"
    act = json.loads(act_path.read_text(encoding="utf-8"))
    act["regions"] = list(act.get("regions") or []) + ["cellar-1"]
    act["transitions"] = list(act.get("transitions") or []) + [
        {"from": "town", "at": [2, 2], "to": "cellar-1", "to_at": [1, 1],
         "requires": {"item": "cellar-key"}}]
    act_path.write_text(json.dumps(act), encoding="utf-8")
    # A key nothing drops and nothing gives is unreachable, and the
    # reachability rule says so - which is the OTHER half of what this
    # test is about, so it is worth a line of its own here: the key is
    # handed out in town, and the door is the only thing between it and
    # the Section.
    world["rules"] = [{"id": "hand-out", "when": {"enters": {"place": "town"}},
                       "then": [{"give": "cellar-key"}]}]
    (built / "world.json").write_text(json.dumps(world), encoding="utf-8")
    assert locks.findings(built) == []

    world["items"]["cellar-key"]["value"] = 25
    (built / "world.json").write_text(json.dumps(world), encoding="utf-8")
    assert locks.findings(built) == [
        "the key item 'cellar-key' has a value, so it can be sold to a "
        "trader - a sold key would break the pack"]


def test_a_section_with_no_entry_door_says_nothing_about_keys(tmp_path):
    """Both E4 files are optional, and a Section with no door is not a lock."""
    built = a_pack(tmp_path, "cellar")
    assert locks.findings(built) == []


def test_a_section_pack_with_a_broken_pattern_is_a_finding_and_not_a_crash(
        tmp_path, monkeypatch):
    """The sweep reads what is on disk, so a broken Section must not stop it.

    A Section the validator has already refused is still a Section on
    disk. `pattern` here is a bare string where a list of slots belongs,
    and `size` names a width rather than a `[lo, hi]` pair, so both fall
    back to the engine's own defaults: the Section keeps its nine floors
    and draws its default pattern and size. The sweep has to read that
    defaulted Section and report on it rather than raising.

    The empty findings alone would not say so - a sweep that swept
    nothing returns an empty list too. So the draws are counted: the
    sweep must have drawn every floor of the defaulted Section on every
    seed, and the empty list then means those floors all held rather
    than that nothing was checked.
    """
    built = a_pack(tmp_path, "cellar")
    path = built / "sections" / "cellar.json"
    section = json.loads(path.read_text(encoding="utf-8"))
    section["pattern"] = "entry"
    section["size"] = {"w": 3}
    path.write_text(json.dumps(section), encoding="utf-8")

    # Both keys are the malformed ones, and both default rather than raise:
    # a bare string is not a list of slots, and `3` is not a `[lo, hi]` pair.
    assert section["pattern"] == "entry"
    assert sections.pattern(section) == sections.DEFAULT_PATTERN
    assert sections.size_range(section) == (
        sections.DEFAULT_SIZE[0][0], sections.DEFAULT_SIZE[0][0],
        sections.DEFAULT_SIZE[1][0], sections.DEFAULT_SIZE[1][0])

    drawn: list[tuple[str, int]] = []
    real = delve_v3.generate_floor_v3

    def counted(seed, size_range, pack, floor_kind, stamp_pack=None, depth=1,
                trace=None, **kwargs):
        drawn.append((seed, depth))
        return real(seed, size_range, pack, floor_kind, stamp_pack, depth,
                    trace, **kwargs)

    monkeypatch.setattr(delve_v3, "generate_floor_v3", counted)

    seeds = 2
    assert locks.section_findings(built, seeds=seeds) == []
    floors = sections.floors(json.loads(path.read_text(encoding="utf-8")))
    assert drawn == [(f"{locks.SECTION_SEED_PREFIX}{n}", k)
                     for n in range(seeds) for k in range(1, floors + 1)]


# -------------------------------------------------------------------- two packs


def test_both_fixture_packs_validate_green():
    """Acceptance 3, at the door: two packs, two Sections, no code change."""
    for name in PACKS:
        assert maplab.section_errors(FIXTURES / name) == [], name


def test_both_fixture_packs_pass_the_front_door(tmp_path):
    for name in PACKS:
        built = a_pack(tmp_path, name)
        rc, out = vefr("check", "--pack", built)
        assert rc == 0, f"{name}: {out}"


def test_the_two_packs_are_genuinely_different_data():
    """The proof is worthless if the two Sections are the same Section."""
    cellar, attic = fixture_pack("cellar"), fixture_pack("attic")
    assert sections.floors(cellar) != sections.floors(attic)
    assert sections.size_range(cellar) != sections.size_range(attic)
    assert cellar["families"] != attic["families"]
    assert cellar["loot"]["tier"] != attic["loot"]["tier"]
    assert sections.pattern(cellar) != sections.pattern(attic)
    assert cellar["id"] != attic["id"]


def test_a_pack_with_no_sections_directory_says_nothing():
    assert maplab.section_errors(FIXTURES) == []


# ------------------------------------------------------------------------ bake


def test_the_bake_writes_one_region_per_floor_and_wires_the_doors(tmp_path):
    """`vefr delve --section` lays a whole Section, floor by floor.

    The regions are named `<section id>-<k>` in the Section's own order,
    so the town stair, the floors and the depth curve all name the same
    floor the same way.
    """
    built = a_pack(tmp_path, "cellar")
    rc, out = vefr("delve", "--pack", built, "--seed", "run-1",
                   "--from-region", "town", "--from-at", "2,2",
                   "--section", "cellar")
    assert rc == 0, out
    act = json.loads((built / "acts" / "act-1" / "world.json").read_text(
        encoding="utf-8"))
    for k in range(1, 10):
        assert f"cellar-{k}" in act["regions"]
    assert "cellar-10" not in act["regions"]
    # Nine floors, eight down-stairs between them and one from the town:
    # the last floor of a Section is the bottom, and it must not be left
    # holding a stair to nowhere.
    down_from = [t["from"] for t in act["transitions"]
                 if t["from"].startswith("cellar-")
                 and _depth_of(t["to"]) > _depth_of(t["from"])]
    assert down_from == [f"cellar-{k}" for k in range(1, 9)]
    assert "d" not in (built / "acts" / "act-1" / "cellar-9" / "map.md").read_text(
        encoding="utf-8")


def test_a_landing_floor_climbs_straight_to_town(tmp_path):
    """PLAN.md section 4: a landing's up-stair goes straight to town.

    The elevator rule, as wiring. Floors 1 and 5 are the Section's two
    landings, and neither of them climbs back to the floor above it: both
    go to the region the descent started from.
    """
    built = a_pack(tmp_path, "cellar")
    rc, out = vefr("delve", "--pack", built, "--seed", "run-1",
                   "--from-region", "town", "--from-at", "2,2",
                   "--section", "cellar")
    assert rc == 0, out
    act = json.loads((built / "acts" / "act-1" / "world.json").read_text(
        encoding="utf-8"))
    # An up-stair is a door that goes DOWN the Section - to the floor below,
    # or to the town, which is floor 0. A down-stair goes the other way,
    # and asking which is which by tile would be asking two floors to have
    # different tiles on purpose.
    up = {t["from"]: t["to"] for t in act["transitions"]
          if t["from"].startswith("cellar-")
          and _depth_of(t["to"]) < _depth_of(t["from"])}
    assert up["cellar-1"] == "town"
    assert up["cellar-5"] == "town"
    assert up["cellar-2"] == "cellar-1"
    assert up["cellar-9"] == "cellar-8"
    # And the two landings are the only floors that skip a floor on the way
    # up: there is no lift down past a floor the hero has not reached.
    assert up["cellar-4"] == "cellar-3"


def _depth_of(region: str) -> int:
    """A region's floor number in its Section, and 0 for the town."""
    tail = region.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def test_the_baked_contract_says_which_section_and_floor_it_is(tmp_path):
    """The record the player's descent menu reads.

    `section`, `k`, `floor_kind` and `landing` are additive keys on a
    generated region's contract: the shape an authored region already has
    is untouched, and the descent has something to name.
    """
    built = a_pack(tmp_path, "cellar")
    rc, out = vefr("delve", "--pack", built, "--seed", "run-1",
                   "--from-region", "town", "--from-at", "2,2",
                   "--section", "cellar")
    assert rc == 0, out
    for k in range(1, 10):
        contract = json.loads((built / "acts" / "act-1" / f"cellar-{k}"
                               / "contract.json").read_text(encoding="utf-8"))
        assert contract["section"] == "cellar"
        assert contract["k"] == k
        assert contract["floor_kind"] in delve_v3.FLOOR_KINDS
        assert contract["landing"] is (k in (1, 5))


def test_the_bake_refuses_a_section_the_pack_does_not_have(tmp_path):
    built = a_pack(tmp_path, "cellar")
    rc, out = vefr("delve", "--pack", built, "--seed", "run-1",
                   "--from-region", "town", "--from-at", "2,2",
                   "--section", "attic")
    assert rc != 0
    assert "attic" in out


def test_taking_the_down_stair_leaves_every_other_d_alone():
    """The bottom-floor stair removal is a coordinate, not a character.

    `d` is a tile in the map alphabet, not a reserved word: the take-back
    has to clear the one tile the generator put the down anchor on and
    nothing else. A blanket `replace('d', '.')` over the row would also
    take out any other `d` on the map, so this pins the tile and leaves a
    second `d` sitting right next to it.
    """
    rows = ['#####', '#d.d#', '#.u.#', '#####']
    # (3, 1) is the second `d`; the first one at (1, 1) is left standing.
    assert cli._take_the_down_stair(rows, (3, 1)) == ['#####', '#d..#',
                                                      '#.u.#', '#####']
    # A copy, so the caller's own rows are not edited underneath them.
    assert rows == ['#####', '#d.d#', '#.u.#', '#####']


def test_the_bottom_floor_loses_its_stair_tile_and_the_rest_of_the_map(tmp_path):
    """The end of the bake, as geometry: exactly one tile differs.

    Every floor but the last keeps its down-stair, and the last one has
    the tile the generator placed its down anchor on changed to floor,
    with every other tile byte-identical to what the generator drew.

    Today's generator only ever draws one `d` per floor, so this passes
    for the old blanket `replace` as well - the unit test above is what
    catches that. What this pins is the written shape of the rule: the
    bottom floor is the drawn floor minus its anchor tile and nothing
    else, and every floor above it is the drawn floor untouched.
    """
    built = a_pack(tmp_path, "cellar")
    section = fixture_pack("cellar")
    rc, out = vefr("delve", "--pack", built, "--seed", "run-1",
                   "--from-region", "town", "--from-at", "2,2",
                   "--section", "cellar")
    assert rc == 0, out
    last = sections.floors(section)
    for k in range(1, last):
        drawn = a_floor(section, k, "run-1")
        written = (built / "acts" / "act-1" / f"cellar-{k}"
                   / "map.md").read_text(encoding="utf-8").splitlines()
        assert written == drawn["rows"], f"floor {k} was rewritten"

    plan = a_floor(section, last, "run-1")
    written = (built / "acts" / "act-1" / f"cellar-{last}"
               / "map.md").read_text(encoding="utf-8").splitlines()
    down = tuple(plan["anchors"]["down"])
    assert plan["rows"][down[1]][down[0]] == delve_v3.DOWN
    assert written[down[1]][down[0]] == delve_v3.FLOOR
    differing = [(x, y)
                 for y in range(plan["h"]) for x in range(plan["w"])
                 if written[y][x] != plan["rows"][y][x]]
    assert differing == [down], differing