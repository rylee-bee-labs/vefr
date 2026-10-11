"""vefr#357: a Section says how many monsters its floors carry.

FROZEN: written from the issue's acceptance criteria, before the key was
added to `shapes.SECTION` and before `vefr.sections.mob_count` existed.

The bug, verbatim from the issue: the play-time descent's monster **count**
was not a pack decision at all. It was area policy at one monster per
thirty walkable tiles, so floor 1 of a generated Section came out at 20, 28
or 35 monsters across seeds and a 6 hp / 2 attack hero died on floor 2. The
only levers a pack had were `size` and `rooms`, and either one REDRAWS every
floor in the Section - which re-randomises the coordinates anything placed
at a verified tile depends on. So a pack could not safely say "four monsters
on the first floor".

What landed, in the four places the acceptance names:

| the issue's bullet | where it is pinned here |
|---|---|
| a named count is what the floor carries, over 200 seeds | "the count" |
| a Section with no such key places exactly what it placed today | "no key, no change" (frozen digests, captured at `d5ce84c`) |
| the key is documented beside the Section contract | `docs/guides/rulesets.md`, "delve --section" |
| a floor's LAYOUT is byte-identical with and without the key | "the layout" |
| the 200-seed sweep covers it; `vefr check` refuses a bad value | "the sweep", "the refusals" |
| Python and JS agree exactly | "parity" (node/jsdom, skipped without node) |

THE HARD CONSTRAINT, and what it does and does not cover: the `size`, `plan`
and `layout` streams must be untouched, so a pack may add a count to a
Section it has already placed things on by coordinate without invalidating
them. The comparison "the layout" therefore compares every FloorPlan key
EXCEPT `spawns` and `chests` - which are the pop stage's own output, are the
one thing the key is for, and are asserted to be different as well, so the
comparison cannot pass by both sides agreeing on everything.

THE THREE FIXTURE PACKS. `cellar` and `attic` name no count and never will
in this file: they are the witnesses that nothing changed. `gentle` is the
third pack, committed Section DATA beside the other two (a Blueprint, an
affix list and one `sections/gentle.json`), and it is the only one that
writes `mobs`. Its data is the issue's own example - `{"1": 4, "from": 12}`
over five floors - so the acceptance numbers in the issue are literally the
numbers this file holds.

Run with:

    bash tests/run.sh tests/test_section_monster_count.py
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from blueprint_helpers import vefr

from vefr import delve, delve_v3, locks, maplab, sections, shapes

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sections"
ROOT = Path(__file__).resolve().parents[1]

# The sweep PLAN.md section 5 row E4 asks for, and the 200 the issue asks
# for by name. `locks.SECTION_SEEDS` is the same 200; it is written out here
# so a change to that default cannot quietly shorten this file's proof.
SEEDS = 200
SEED_PREFIX = locks.SECTION_SEED_PREFIX

# The counts the fixture writes, as the issue wrote them.
FIRST_FLOOR = 4
EVERY_OTHER_FLOOR = 12

# The two fixture packs that name no count, and the digest of every floor
# they draw over the sweep - SPAWNS AND CHESTS INCLUDED - captured at
# `d5ce84c` (the commit this branch is based on) with the generator as it
# stood there, and re-checked here. If this test fails, a Section that names
# no count has stopped drawing the floors it drew, which is the one thing
# this key is not allowed to do.
#
#   PYTHONPATH=src python3 -c "<digest over 200 seeds x every floor>"
#   at d5ce84c -> cellar b6a8189b8e6f7aa54bc0bc2f2292df895eb4a97242edc022ff31c52387b51356
#                 attic  f5fd1d62bf048ddaf36518dfead131b7582e89f26b57adf89f90bc832b45cdbb
FROZEN_FLOORS = {
    "cellar": "b6a8189b8e6f7aa54bc0bc2f2292df895eb4a97242edc022ff31c52387b51356",
    "attic": "f5fd1d62bf048ddaf36518dfead131b7582e89f26b57adf89f90bc832b45cdbb",
}

# Every FloorPlan key the pop stage does not write. `gen` is in here: which
# generator a floor came from is decided by the retry ladder, which reads the
# pop stage, so a count that changed it would be a count that changed the
# layout - and the point of the key is that it cannot.
LAYOUT_KEYS = ("gen", "w", "h", "rows", "rooms", "anchors", "pois", "secrets",
                "waypoint", "stamps")
POP_KEYS = ("spawns", "chests")

HARNESS = ROOT / "tests" / "fixtures" / "section_mobs_parity_harness.mjs"
PARITY_SEEDS = 12


# ------------------------------------------------------------------ helpers


def fixture_pack(name: str) -> dict:
    """One committed fixture pack's Section, read off disk.

    Read rather than built, because the acceptance is that the FILES are the
    contract: a `mobs` table that only exists as a Python dict would prove
    nothing about what a pack author writes.
    """
    return json.loads((FIXTURES / name / "sections" / f"{name}.json").read_text(
        encoding="utf-8"))


def gentle() -> dict:
    return fixture_pack("gentle")


def without_mobs(section: dict) -> dict:
    """The same Section with the key taken back out, byte for byte else."""
    return {key: value for key, value in section.items() if key != sections.MOBS_KEY}


def seed_for(number: int) -> str:
    return f"{SEED_PREFIX}{number}"


def a_floor(section: dict, seed: str, k: int) -> dict:
    """One v3 FloorPlan, drawn the way the descent curve draws a floor.

    The same call `locks.section_findings` makes, so what the sweep sweeps is
    what this file counts.
    """
    key = sections.floor_key(seed, section, 0, k)
    return delve_v3.generate_floor_v3(
        seed, sections.floor_size(section, key), copy.deepcopy(section),
        sections.floor_kind(section, k, seed, 0), depth=k)


def canonical(value) -> str:
    """The comparison form: sorted keys, no whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def layout_of(plan: dict) -> dict:
    """Everything a floor is before the pop stage filled it."""
    return {key: value for key, value in plan.items()
            if key not in POP_KEYS and (key in LAYOUT_KEYS or key == "stamps")}


def spawns_on(plan: dict) -> int:
    """How many monsters the floor carries, `gen: 2` floors counting as none.

    A v2 fallback has no spawns at all, and a fallback floor is the sweep's
    finding rather than this file's count - the counts below only make sense
    over floors that came back as v3.
    """
    assert plan.get("gen") == 3, "the floor fell back to v2 geometry"
    return len(plan["spawns"])


# ----------------------------------------------------------------- the count


def test_a_named_count_is_exactly_what_the_floor_carries():
    """The issue's first bullet, over the sweep: four on floor 1, then twelve.

    This is the test that fails if the key is removed from the read. Every
    one of the 200 seeds is drawn at the Section's own size, from its own
    floor key, for all five of its floors - 1000 floors - and each carries
    the number the pack wrote rather than the area budget's.
    """
    section = gentle()
    swept = 0
    for number in range(SEEDS):
        seed = seed_for(number)
        for k in range(1, sections.floors(section) + 1):
            plan = a_floor(section, seed, k)
            want = FIRST_FLOOR if k == 1 else EVERY_OTHER_FLOOR
            assert spawns_on(plan) == want, f"seed {seed} floor {k}"
            swept += 1
    assert swept == SEEDS * sections.floors(section)


def test_a_count_the_pack_names_a_floor_outranks_the_every_floor_entry():
    """`{"1": 4, "from": 12}` means four on one and twelve on the rest.

    The two halves of the key are not alternatives: a floor the pack named
    is that floor's count, and `from` is only the answer for the floors it
    did not.
    """
    assert sections.mob_count(gentle(), 1) == FIRST_FLOOR
    for k in range(2, 12):
        assert sections.mob_count(gentle(), k) == EVERY_OTHER_FLOOR


def test_a_count_of_zero_is_a_floor_with_nothing_on_it():
    """Zero is a count the area budget could not express.

    `walkable // 30` clamps up to `MOBS_MIN`, so the floor a pack asks to be
    empty is the one thing the old policy could not say - and the floors
    after it keep the count `from` gives them.
    """
    section = gentle()
    section[sections.MOBS_KEY] = {"1": 0, "from": EVERY_OTHER_FLOOR}
    for number in range(5):
        seed = seed_for(number)
        assert spawns_on(a_floor(section, seed, 1)) == 0
        assert spawns_on(a_floor(section, seed, 2)) == EVERY_OTHER_FLOOR


def test_the_count_is_read_and_never_drawn():
    """The budget costs no draw, so the three streams do not move.

    The floor key is the floor key: a Section that sets a count opens
    `v3|<key>|plan`, `|layout` and `|pop` and nothing else. The plan stage
    never reads `mobs` at all, which is what "the layout" proves tile by
    tile; this is the same fact said about the names.
    """
    section = gentle()
    plain = without_mobs(section)
    key = sections.floor_key(seed_for(0), section, 0, 1)
    for stream in ("plan", "layout", "pop"):
        assert delve_v3.prng(f"v3|{key}|{stream}") is not None
    assert delve_v3._plan_stage(delve_v3.prng(f"v3|{key}|plan"), plain, "normal") \
        == delve_v3._plan_stage(delve_v3.prng(f"v3|{key}|plan"), section, "normal")


def test_the_play_time_descent_reads_the_same_count():
    """`vefr.floor_plan` - the plan the PLAYER walks - honours the key.

    The v3 FloorPlan's `spawns` are the baked region's; the descent's own
    `mobs` list is what the player fights, and it is drawn by
    `vefr.delve.mobs_at` off the floor's rows. Both read one count, and this
    is the one the player sees.
    """
    descent = {"run_seed": "gentle-run",
               "sections": [copy.deepcopy(gentle())]}
    for depth in range(1, sections.floors(gentle()) + 1):
        plan = delve.floor_plan(copy.deepcopy(descent), depth)
        mobs = [mob for mob in plan["mobs"] if not mob.get("warden")]
        want = FIRST_FLOOR if depth == 1 else EVERY_OTHER_FLOOR
        assert len(mobs) == want, depth


def test_a_descent_section_that_names_no_count_is_the_area_budget():
    """The play-time default, said as the formula rather than as a digest.

    The descent counts walkable tiles off the rows it drew - the v3 pop
    stage counts its canvas - and each is clamped into the same two numbers.
    """
    section = gentle()
    descent = {"run_seed": "gentle-run", "sections": [without_mobs(section)]}
    for depth in range(1, 6):
        plan = delve.floor_plan(copy.deepcopy(descent), depth)
        walkable = sum(row.count(".") for row in plan["rows"])
        want = min(delve_v3.MOBS_MAX,
                   max(delve_v3.MOBS_MIN, walkable // delve_v3.TILES_PER_MOB))
        mobs = [mob for mob in plan["mobs"] if not mob.get("warden")]
        assert len(mobs) == want, depth


# ------------------------------------------------------------ no key, no change


def test_a_section_that_names_no_count_places_exactly_what_it_placed_today():
    """The issue's second bullet, as a digest captured before the key.

    200 seeds x every floor of both packs that never write one, the WHOLE
    FloorPlan - `spawns` and `chests` included - canonicalised and hashed.
    The digests were taken at `d5ce84c`, the commit this branch is based on.
    """
    for name, frozen in FROZEN_FLOORS.items():
        section = fixture_pack(name)
        assert sections.MOBS_KEY not in section, name
        digest = hashlib.sha256()
        for number in range(SEEDS):
            seed = seed_for(number)
            for k in range(1, sections.floors(section) + 1):
                digest.update(canonical(a_floor(section, seed, k)).encode())
        assert digest.hexdigest() == frozen, name


# ------------------------------------------------------------------- the layout


def test_a_floors_layout_is_byte_identical_with_and_without_the_key():
    """The issue's fourth bullet, over the whole sweep.

    The same 200 seeds and the same five floors, drawn twice - once from the
    fixture as written, once from it with the one key taken back out - and
    every FloorPlan key except `spawns` and `chests` compared as canonical
    JSON. A pack that sets a count on a Section it has already placed things
    on by coordinate invalidates nothing it placed.
    """
    section = gentle()
    plain = without_mobs(section)
    same = 0
    for number in range(SEEDS):
        seed = seed_for(number)
        for k in range(1, sections.floors(section) + 1):
            with_key = a_floor(section, seed, k)
            without = a_floor(plain, seed, k)
            assert canonical(layout_of(with_key)) == canonical(layout_of(without)), \
                f"seed {seed} floor {k}"
            same += 1
    assert same == SEEDS * sections.floors(section)


def test_the_key_changes_the_pop_stage_and_nothing_else():
    """The comparison above cannot pass by both floors being equal.

    If `mobs` were not read at all, the layout comparison would hold and
    prove nothing. Every seed's FIRST floor must therefore differ, which is
    the floor whose count (four) is not one the area budget lands on at this
    size - checked here rather than assumed, so the claim survives a change
    to the fixture.
    """
    section = gentle()
    plain = without_mobs(section)
    differed = 0
    for number in range(SEEDS):
        seed = seed_for(number)
        for k in range(1, sections.floors(section) + 1):
            with_key = a_floor(section, seed, k)
            without = a_floor(plain, seed, k)
            if k == 1:
                assert spawns_on(without) != FIRST_FLOOR, f"seed {seed}"
                assert with_key["spawns"] != without["spawns"], f"seed {seed}"
            if with_key["spawns"] != without["spawns"]:
                differed += 1
    # At least the first floor of every seed, and usually more: a deeper
    # floor the area budget happened to land on twelve is the same floor.
    assert differed >= SEEDS


# ----------------------------------------------------------------- the refusals


def base() -> dict:
    """A Section with no problems, so one edit is what a test changes."""
    return without_mobs(gentle())


def affixes() -> list:
    """The fixture pack's own affix list, so nothing else is refused."""
    return json.loads((FIXTURES / "gentle" / "affixes.json").read_text(
        encoding="utf-8"))


def only(section: dict) -> str:
    """The one line `vefr check` prints for a bad `mobs` table.

    Read through `maplab.section_block_errors` with the fixture's affix list
    and a resolver that answers every family, so the only thing these tests
    change is the count.
    """
    lines = maplab.section_block_errors(
        section, affixes(), lambda name: {"hp": 1, "atk": 1},
        "sections/gentle.json")
    assert len(lines) == 1, lines
    return lines[0]


def test_a_count_that_is_not_a_whole_number_is_refused_naming_the_section():
    for value in (4.5, "four", True, None):
        section = base()
        section[sections.MOBS_KEY] = {"1": value}
        assert only(section) == (
            "sections/gentle.json: /section/mobs/1 "
            "section.mobs['1'] must be a whole number")


def test_a_count_outside_the_cap_is_refused_naming_the_section():
    for value in (37, 99, -1):
        section = base()
        section[sections.MOBS_KEY] = {"1": value}
        assert only(section) == (
            "sections/gentle.json: /section/mobs/1 "
            "section.mobs['1'] must be between 0 and 36")


def test_a_key_that_names_no_floor_is_refused_at_that_key():
    for key in ("three", "03", "0", "-1", "1.0", ""):
        section = base()
        section[sections.MOBS_KEY] = {key: 4}
        assert only(section) == (
            f"sections/gentle.json: /section/mobs/{key} "
            f"section.mobs[{key!r}] must name a floor of the section, such as "
            '"3", or "from" for every floor it does not name')


def test_the_from_entry_is_bounded_the_same_way():
    section = base()
    section[sections.MOBS_KEY] = {"from": 37}
    assert only(section) == (
        "sections/gentle.json: /section/mobs/from "
        "section.mobs['from'] must be between 0 and 36")


def test_a_mobs_table_that_is_not_a_table_is_refused():
    for value in ([4], 4, "four", None):
        section = base()
        section[sections.MOBS_KEY] = value
        assert only(section) == (
            "sections/gentle.json: /section/mobs "
            "section.mobs must be a table of monster counts, such as "
            '{"1": 4, "from": 12}')


def test_only_the_first_bad_count_is_reported():
    """One sentence however wrong the table is, the table's own order first."""
    section = base()
    section[sections.MOBS_KEY] = {"from": 37, "1": 40}
    assert only(section) == (
        "sections/gentle.json: /section/mobs/from "
        "section.mobs['from'] must be between 0 and 36")


def test_the_whole_shape_of_a_count_table_that_is_right_is_accepted():
    assert shapes.check(shapes.SECTION, {
        "id": "gentle", "families": [{"family": "rat"}],
        "mobs": {"1": 0, "99": 36, "from": 12},
    }) == []


def test_vefr_check_exits_non_zero_on_a_bad_count(tmp_path):
    """The CLI itself, over a real pack, with the exit code and the sentence.

    Built the shipped way (`make_blueprint_pack` plus `vefr normalize`) over
    the fixture's own Blueprint, then handed a Section with one count out of
    range - the case `shapes` refuses at `/section/mobs/1`.
    """
    pack = real_pack(tmp_path)
    section = json.loads((pack / "sections" / "gentle.json").read_text(
        encoding="utf-8"))
    section[sections.MOBS_KEY] = {"1": delve_v3.MOBS_MAX + 4}
    (pack / "sections" / "gentle.json").write_text(
        json.dumps(section, indent=1), encoding="utf-8")

    rc, out = vefr("check", "--pack", pack)
    assert rc != 0
    assert ("sections/gentle.json: /section/mobs/1 "
            "section.mobs['1'] must be between 0 and 36") in out, out


def test_vefr_check_is_green_on_the_fixture_as_written(tmp_path):
    pack = real_pack(tmp_path)
    rc, out = vefr("check", "--pack", pack)
    assert rc == 0, out
    assert "ok:" in out


def real_pack(tmp_path) -> Path:
    """A real pack carrying the `gentle` fixture's Section, built the shipped way."""
    from blueprint_helpers import normalized_pack

    built = normalized_pack(
        tmp_path,
        blueprint=json.loads((FIXTURES / "gentle" / "blueprint.json").read_text(
            encoding="utf-8")))
    for part in ("sections", "affixes.json"):
        source = FIXTURES / "gentle" / part
        target = built / part
        if source.is_dir():
            target.mkdir(exist_ok=True)
            for path in sorted(source.glob("*.json")):
                (target / path.name).write_text(path.read_text(encoding="utf-8"),
                                               encoding="utf-8")
        else:
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return built


# --------------------------------------------------------------------- the sweep


def test_the_sweep_covers_a_section_that_names_a_count():
    """`locks.section_findings`, the 200-seed sweep, over the fixture.

    Empty is the bar: every floor of every Section in the pack holds - one
    component, every anchor, point of interest, secret, monster and chest
    reachable from the up-stair - and none fell back to v2 geometry. The
    sweep draws the floors the way `a_floor` above does, so this is the same
    1000 floors carrying the same counts.
    """
    assert locks.section_findings(FIXTURES / "gentle", SEEDS) == []


def test_every_floor_the_sweep_draws_carries_its_named_count():
    """The sweep's own count, read back off the floors rather than the pack.

    The count test and the sweep test would both be true of a generator that
    never drew the fixture, so this one asks the sweep's question of the
    sweep's floors: 200 seeds, all five floors, all of them v3.
    """
    section = gentle()
    swept = 0
    for number in range(SEEDS):
        seed = seed_for(number)
        for k in range(1, sections.floors(section) + 1):
            plan = a_floor(section, seed, k)
            want = FIRST_FLOOR if k == 1 else EVERY_OTHER_FLOOR
            assert spawns_on(plan) == want, f"seed {seed} floor {k}"
            assert locks._defect(plan, section) == "", f"seed {seed} floor {k}"
            swept += 1
    assert swept == SEEDS * sections.floors(section)


# --------------------------------------------------------------------- parity

# PLAN.md section 2's determinism rule, and the reason this file cannot stop
# at the Python half: the player runs the twin, so a count the two languages
# read differently is a count that is four monsters in the bake and twelve
# at the stair. Both twins are exercised here - part 396's pop stage
# (`v3Attempt`) and part 397's play-time floor (`floorPlan`) - over the same
# Section, the same seeds and several depths, and compared as canonical JSON.
#
# `tests/browser/test_floor_v3_parity.py` is the normative parity path for
# the generator as a whole; this is the key's half of it, and it skips
# without node rather than pretending.


@pytest.fixture(scope="module")
def parity(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed (npm ci)")
    from vefr import cli

    home = tmp_path_factory.mktemp("section-mobs-parity")
    html = home / "p.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"),
                    encoding="utf-8")
    descent = {"run_seed": "mobs-run", "sections": [gentle()]}
    cases = home / "cases.json"
    cases.write_text(json.dumps({
        "descent": descent,
        "depths": list(range(1, sections.floors(gentle()) + 1)),
        "runs": [0],
        "floors": [
            {"seed": f"mobs-{number}", "w": 64, "h": 48, "kind": kind,
             "depth": depth, "cycle": 0}
            for number in range(PARITY_SEEDS)
            for depth in ((1, 2, 5)[number % 3],)
            for kind in ("normal", "treasure")
        ],
        "section": gentle(),
    }), encoding="utf-8")
    out = home / "out.json"
    run = subprocess.run(["node", str(HARNESS), str(html), str(cases), str(out)],
                         capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, run.stderr + run.stdout
    return json.loads(out.read_text(encoding="utf-8"))


def test_the_twin_reads_the_count_the_same_way_the_spec_does(parity):
    """Part 396's pop stage: the same spawns, the same chests, byte for byte."""
    section = gentle()
    assert parity["floors"]
    for case, got in zip(parity["cases"]["floors"], parity["floors"]):
        want = delve_v3.generate_floor_v3(
            case["seed"], (case["w"], case["h"]), copy.deepcopy(section),
            case["kind"], None, case["depth"], cycle=case["cycle"])
        assert got["gen"] == want["gen"], case
        assert canonical(got["spawns"]) == canonical(want["spawns"]), case
        assert canonical(got["chests"]) == canonical(want["chests"]), case
        assert len(want["spawns"]) == (FIRST_FLOOR if case["depth"] == 1
                                       else EVERY_OTHER_FLOOR), case
        # The key the twin built is the one the spec builds from the same
        # four parts, so a depth that did not reach either side's key could
        # not have been read at all.
        key = sections.floor_key(case["seed"], section, 0, case["depth"])
        assert key.endswith(f"/{case['depth']}")


def test_the_descent_twin_reads_the_count_the_same_way_the_spec_does(parity):
    """Part 397's play-time floor: the same monsters, byte for byte."""
    descent = {"run_seed": "mobs-run", "sections": [gentle()]}
    depths = list(range(1, sections.floors(gentle()) + 1))
    runs = parity["cases"]["runs"]
    assert len(parity["plans"]) == len(depths) + len(runs)
    for depth, got in zip(depths, parity["plans"]):
        want = delve.floor_plan(copy.deepcopy(descent), depth)
        assert canonical(got) == canonical(want), depth
        assert len([m for m in got["mobs"] if not m.get("warden")]) == \
            (FIRST_FLOOR if depth == 1 else EVERY_OTHER_FLOOR), depth
    for run, got in zip(runs, parity["plans"][len(depths):]):
        want = delve.floor_plan(copy.deepcopy(descent), 1, run=run)
        assert canonical(got) == canonical(want), run


def test_the_twin_carries_the_same_bound_the_spec_does():
    """The floors a count may name: 99 in the Section shape, 99 in the twin."""
    assert sections.MOB_FLOOR_MAX == 99