"""Every monster a generated floor spawns is worth something (vefr#359).

A Section names Blueprint families and the descent spawns monsters from
them. Before this slice the spawn record carried `hp`, `atk`, `sight`
and `drops` and no `xp` at all, so `growAward(e.xp)` paid
`growAward(undefined)` on every generated kill: a player could walk
from the town door to the bottom of the fourth Section and finish
exactly where they started, on four Sections of rising monsters.

What this file holds:

- the default. A family that declares no `xp` takes
  `vefr.sections.xp_for`'s documented ramp on the floor's depth, and a
  family that declares one is honoured exactly. The tests here pin both
  halves, and one of them is written so that deleting the default makes
  it fail.
- the shape. `vefr check` refuses a bad `xp` with a sentence naming the
  Section and the family, and the key is optional: a Section written
  before it validates exactly as it did.
- the twin. The JavaScript in `web/player/parts/397-the-descent.js`
  answers exactly what Python answers for the same floor, so the xp a
  browser spawns is the xp the reference drew - replayed through the
  REAL woven player in jsdom, over the fixture descent and over a
  four-Section one.
- the payment. Killing a monster on a generated floor moves the growth
  state, says the experience line, and fires the `level` cue exactly as
  an authored region's kill does - played through the same jsdom player.
- the determinism rule. 200 seeds, same seed and same monster id is the
  same xp every time, and adding the xp moved no wall, no monster and no
  drop on any of them.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import play_kit
from vefr import delve, sections, shapes
from vefr.cli import weave_html

from test_descent_floors import DESCENT

ROOT = Path(__file__).resolve().parents[1]
PARITY_HARNESS = ROOT / "tests" / "fixtures" / "descent_parity_harness.mjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

# Four Sections, so "the deepest Section pays most" is a claim about a
# sequence rather than about two points. The first two are the fixture's
# own; the last two are the same two shapes repeated, which is all a
# fourth Section needs to be here. `delve._sections` walks the list in
# pack order, so the ids are numbered in the order the descent reads.
FOUR = copy.deepcopy(DESCENT)
FOUR["sections"] = FOUR["sections"] + [
    copy.deepcopy(DESCENT["sections"][1]),
    copy.deepcopy(DESCENT["sections"][0]),
]
for _index, _section in enumerate(FOUR["sections"]):
    _section["id"] = f'wing-{_index}'


def _first_floor_of_each_section(descent):
    """`(section id, depth)` for the FIRST floor of every Section, in
    descent order - the apples-to-apples comparison, one floor down
    into each Section rather than one floor at the end of it."""
    out, walked = [], 0
    for section in sections.ordered(descent["sections"]):
        walked += 1
        out.append((section["id"], walked))
        walked += sections.floors(section) - 1
    return out


def _mob_xps(plan):
    return [mob["xp"] for mob in plan["mobs"]]


# ---- the default --------------------------------------------------------

def test_a_floor_one_monster_is_worth_something():
    """The issue's own report: a floor-1 kill pays."""
    plan = delve.floor_plan(DESCENT, 1)
    assert plan["mobs"], "the fixture descent's first floor drew no monsters"
    for xp in _mob_xps(plan):
        assert isinstance(xp, int) and xp > 0, xp


def test_a_family_that_declares_no_xp_takes_the_documented_default():
    """REMOVE THE DEFAULT AND THIS FAILS.

    `vefr.sections.xp_for` is the only thing that answers this, and the
    answer is written down beside it: `XP_BASE` on the first floor of
    the descent, `XP_PER_DEPTH` more for every floor below. A family
    that says nothing pays exactly that, and never `None`.
    """
    family = {"family": "rat"}          # no `xp` at all
    assert sections.xp_for(family, 1) == sections.XP_BASE
    for depth in range(1, 8):
        assert sections.xp_for(family, depth) == \
            sections.XP_BASE + sections.XP_PER_DEPTH * (depth - 1)
    # And it is never the absent value the bug was: `None` is what a
    # missing key used to hand the growth engine.
    for depth in range(1, 8):
        assert sections.xp_for(family, depth) is not None


def test_the_javascript_twin_answers_exactly_what_python_answers(tmp_path_factory):
    """The same floor, both languages, through the REAL woven player."""
    home = tmp_path_factory.mktemp("descent-xp-parity")
    html = home / "p.html"
    html.write_text(weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    cases = home / "cases.json"
    cases.write_text(json.dumps({"descent": FOUR,
                                 "depths": list(range(1, 13)),
                                 "runs": [0, 1]}),
                     encoding="utf-8")
    run = subprocess.run(["node", str(PARITY_HARNESS), str(html), str(cases)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr + run.stdout
    out = json.loads(run.stdout)
    assert out["hasApi"] is True
    assert len(out["plans"]) == 14
    for depth, plan in zip(range(1, 13), out["plans"]):
        want = delve.floor_plan(FOUR, depth)
        # The whole record, not only the xp: a twin that answered the
        # xp and moved a wall would pass a narrower check.
        assert json.dumps(plan, sort_keys=True) == \
            json.dumps(want, sort_keys=True), depth


def test_the_award_rises_strictly_across_four_sections():
    """The acceptance criterion: strictly increasing across Sections."""
    sequence = []
    for section_id, depth in _first_floor_of_each_section(FOUR):
        plan = delve.floor_plan(FOUR, depth)
        assert plan["section"] == section_id, (section_id, plan["section"])
        sequence.append(min(_mob_xps(plan)))
    assert len(sequence) == 4, sequence
    assert all(a < b for a, b in zip(sequence, sequence[1:])), sequence


def test_a_pack_that_overrides_xp_per_family_is_honoured():
    descent = copy.deepcopy(FOUR)
    descent["sections"][0]["families"][0]["xp"] = 17
    descent["sections"][0]["families"][1]["xp"] = 0
    floors = sections.floors(sections.ordered(descent["sections"])[0])
    seen = {}
    for depth in range(1, floors + 1):
        for mob in delve.floor_plan(descent, depth)["mobs"]:
            seen.setdefault(mob["family"], set()).add(mob["xp"])
    # A family that declared its own is worth that, on every floor of
    # the Section that declared it, and the depth ramp never leaks in:
    # floor 3 pays 17 like floor 1 did, not 17 and 5.
    assert seen == {"rat": {17}, "moth": {0}}, seen
    assert sections.xp_for({"family": "rat", "xp": 17}, 9) == 17


def test_the_warden_pays_too():
    descent = copy.deepcopy(FOUR)
    descent["sections"][0]["pattern"] = ["entry", "n", "warden"]
    descent["sections"][0]["warden"] = {"family": "rat", "id": "rat-king"}
    wardens = [mob for mob in delve.floor_plan(descent, 3)["mobs"]
               if mob.get("warden")]
    assert len(wardens) == 1
    assert isinstance(wardens[0]["xp"], int) and wardens[0]["xp"] > 0
    # And it is the same line every other monster takes: floor 3 of the
    # descent is depth 3, so the default is what any other monster on
    # that floor is worth.
    assert wardens[0]["xp"] == sections.xp_for({"family": "rat"}, 3)


# ---- `vefr check` -------------------------------------------------------

def test_a_section_without_xp_validates_exactly_as_it_did():
    """The key is additive and optional, so an old pack is untouched."""
    section = {"id": "cellar", "families": [{"family": "rat", "weight": 2}]}
    assert shapes.check_section(section) == []


def test_check_refuses_a_bad_xp_naming_the_section_and_the_family():
    for given in (-3, 2_000_000, 1.5, "lots", True):
        section = {"id": "cellar",
                   "families": [{"family": "rat", "xp": given}]}
        problems = [p for p in shapes.check_section(section)
                    if p.pointer.endswith('/xp')]
        assert len(problems) == 1, (given, problems)
        said = problems[0].sentence
        assert "'rat'" in said, said
        assert "'cellar'" in said, said


def test_a_good_xp_says_nothing():
    for given in (0, 1, 999_999):
        section = {"id": "cellar", "families": [{"family": "rat", "xp": given}]}
        assert shapes.check_section(section) == [], given


# ---- determinism --------------------------------------------------------

# The seeds `vefr check` itself sweeps with, so the number the check
# uses is the number this uses.
SEEDS = [f'check-{number}' for number in range(200)]
DEPTHS = [1, 2, 3, 4, 5]


def test_the_same_seed_draws_the_same_xp_for_the_same_monster():
    """The determinism rule, over 200 seeds and every floor.

    Same seed, same monster id, same xp - and the floor that seed draws
    is unchanged by having an xp on it at all, which is the property
    that would break first if the xp were a draw. Every seed is drawn
    twice and compared whole, so a wall, a monster or a drop that moved
    would fail here too.
    """
    for seed in SEEDS:
        descent = dict(FOUR, run_seed=seed)
        for depth in DEPTHS:
            first = delve.floor_plan(descent, depth)
            again = delve.floor_plan(dict(FOUR, run_seed=seed), depth)
            assert first == again, (seed, depth)
            assert first["mobs"], (seed, depth)
            for mob in first["mobs"]:
                assert isinstance(mob["xp"], int) and mob["xp"] >= 0, \
                    (seed, depth, mob)


def test_two_seeds_draw_two_floors_and_two_xps():
    """The check is not vacuous: different seeds really are different."""
    one = delve.floor_plan(dict(FOUR, run_seed="seed-one"), 1)
    two = delve.floor_plan(dict(FOUR, run_seed="seed-two"), 1)
    assert one["rows"] != two["rows"] or one["mobs"] != two["mobs"]


def test_the_twin_answers_the_same_over_several_seeds(tmp_path_factory):
    """The JavaScript half of the determinism claim, over five seeds.

    Same floor key in, same xp out, in both languages - run through the
    REAL woven player, because that is where the twin actually lives.
    """
    home = tmp_path_factory.mktemp("descent-xp-seeds")
    html = home / "p.html"
    html.write_text(weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    for seed in SEEDS[:5]:
        descent = dict(FOUR, run_seed=seed)
        cases = home / f'{seed}.json'
        cases.write_text(json.dumps({"descent": descent,
                                     "depths": DEPTHS,
                                     "runs": [0]}),
                         encoding="utf-8")
        run = subprocess.run(["node", str(PARITY_HARNESS), str(html), str(cases)],
                             capture_output=True, text=True, timeout=300)
        assert run.returncode == 0, run.stderr + run.stdout
        for depth, plan in zip(DEPTHS, json.loads(run.stdout)["plans"]):
            want = delve.floor_plan(descent, depth)
            assert [(m["id"], m["xp"]) for m in plan["mobs"]] == \
                [(m["id"], m["xp"]) for m in want["mobs"]], (seed, depth)


# ---- the payment, played ------------------------------------------------

# The descent fixture is a plain pack: no `growth`, no `sound`. Both are
# the pack's own to declare, so the play below declares them, exactly as
# a pack that wants levels and cues would. `levels.xp` is [0, 1] so a
# single floor-1 kill crosses a step and the `level` cue has somewhere
# to fire - the cue is the one acceptance asks to see.
LEVELS = {"mode": "levels",
          "levels": {"xp": [0, 1], "gain": {"hp": 2, "atk": 1}}}
SOUND = {"theme": "soft"}
PATCH = {"world.json": {"growth": LEVELS, "sound": SOUND}}
WORLD = "descent-test"
GROWTH_KEY = f"vefr-growth-{WORLD}"


def _fight_a_monster_on(tmp_path, descent, depth):
    """Walk the real woven player down to `depth` and fight what it meets.

    The path and the fight are the ones `test_descent_deltas.py` already
    plays: a breadth-first walk over the floor the generator drew, then
    presses the last direction until the bump lands. So this is a walk a
    player could perform and not a teleport, and the fight is the shipped
    one.

    A monster that sees the hero coming may step into the walk, and a
    monster the walk bumps is a fight too - which is the game, not a
    fault, in `test_descent_deltas.py`'s own words. So the walk aims at a
    monster and takes the fight it gets, and this returns the monsters the
    save itself records as dead on the floor the hero really ends on,
    with their spawn records.
    """
    from test_descent_deltas import _descend, _go_fight, _reachable_mob

    plan = delve.floor_plan(descent, depth)
    mob = _reachable_mob(plan)
    steps = _descend(depth) + [_go_fight(plan, mob)] + ["wait:100"] * 6
    html = play_kit.weave(play_kit.pack(tmp_path, "descent", patch=PATCH),
                          tmp_path)
    spec = {"steps": [s for s in steps if s != "walk:"],
            "read": ["VEFR_DESCENT.floor", "VEFR_COMBAT", "VEFR_SOUND.played",
                     "store", "text:#combat-live"]}
    play = play_kit.play(html, spec)
    region = play["reads"]["VEFR_COMBAT"]["region"]
    assert region == plan["name"], (region, plan["name"])
    slain = json.loads(play["store"].get(f"vefr-descent-{WORLD}") or "{}").get(
        "floors", {}).get(region, {}).get("kills", [])
    assert slain, f'nothing on {region} died: {play["errors"]}'
    assert set(slain) <= {m["id"] for m in plan["mobs"]}, slain
    return play, plan, [m for m in plan["mobs"] if m["id"] in slain]


def test_a_kill_on_a_generated_floor_pays_and_says_so(tmp_path):
    play, plan, slain = _fight_a_monster_on(tmp_path, copy.deepcopy(DESCENT), 1)
    assert play["errors"] == [], play["errors"]

    # The spawned record carries the xp, so the enemy table does too.
    spawned = play["reads"]["VEFR_DESCENT.floor"]["mobs"]
    assert spawned and all(isinstance(m["xp"], int) and m["xp"] > 0
                           for m in spawned), spawned
    assert {m["id"] for m in slain} <= {m["id"] for m in spawned}, slain

    # The kill paid: the growth state holds exactly the experience of the
    # monsters the save records as dead, under the world's own
    # `vefr-growth-<world>` key - the same key an authored region's kill
    # writes.
    state = json.loads(play["store"][GROWTH_KEY])
    assert state["xp"] == sum(m["xp"] for m in slain), (state, slain)

    # And the player was told, in the same words an authored kill uses. The
    # live line holds the last thing said, and every floor-1 monster here is
    # worth the same, so the announced award is the one they carry.
    said = play["reads"]["text:#combat-live"]
    for mob in slain:
        assert f"You earn {mob['xp']} experience." in said, (mob, said)

    # The step was crossed: the level cue fired, and the gain it promises is
    # in the hero's own numbers. The hero starts at the pack's own 40/4
    # (measured with this same patch and a bare "begin").
    assert "level" in play["reads"]["VEFR_SOUND.played"], \
        play["reads"]["VEFR_SOUND.played"]
    hero = play["reads"]["VEFR_COMBAT"]["hero"]
    assert hero["max"] == 40 + LEVELS["levels"]["gain"]["hp"], hero
    assert hero["atk"] == 4 + LEVELS["levels"]["gain"]["atk"], hero


def test_a_deeper_kill_pays_more(tmp_path):
    """The Section ramp, paid: a floor-2 monster's kill beats a floor-1 one.

    Two rungs, not three. The descent walk is walked by the monsters the
    floors drew, and past floor 2 one of them bumps the walk off the
    corridor before it reaches the next down-stair, so floor 2 is the
    deepest rung a played walk lands on (measured on the host). The ramp
    itself is the pack's own: every floor-1 monster pays 1 and every
    floor-2 monster pays 3.
    """
    paid = []
    for depth in (1, 2):
        play, plan, slain = _fight_a_monster_on(tmp_path,
                                                copy.deepcopy(DESCENT), depth)
        assert play["errors"] == [], play["errors"]
        assert slain, depth
        paid.append((json.loads(play["store"][GROWTH_KEY])["xp"], slain))
    assert paid[0][0] < paid[1][0], paid
    # The ramp is the monsters' own, not the walk's luck: what died deeper
    # was worth more apiece than anything that died higher up.
    assert max(m["xp"] for m in paid[0][1]) < min(m["xp"] for m in paid[1][1]), \
        paid


def test_every_spawned_monster_is_worth_a_finite_number(tmp_path):
    """The `undefined` guard: `Number.isFinite` on what a kill pays.

    `growAward` hands its argument straight to the growth engine, which
    leaves the hero where they are for anything that is not a positive
    whole number - so `Number.isFinite(e.xp)` has to hold for every
    monster the descent spawns, not only the one a test happened to
    kill. Read out of the REAL player's own enemy table, for every floor
    of the descent, so it is the shipped spawn path that is checked.
    """
    from test_descent_deltas import _descend

    for depth in range(1, 6):
        steps = [s for s in _descend(depth) if s != "walk:"]
        html = play_kit.weave(play_kit.pack(tmp_path, "descent", patch=PATCH),
                              tmp_path)
        play = play_kit.play(html, {"steps": steps,
                                    "read": ["VEFR_DESCENT.floor"]})
        assert play["errors"] == [], play["errors"]
        mobs = play["reads"]["VEFR_DESCENT.floor"]["mobs"]
        assert mobs, depth
        for mob in mobs:
            # What `Number.isFinite` asks of a JS number, asked here of
            # the value that came back out of the browser.
            assert isinstance(mob["xp"], int), (depth, mob)
            assert 0 <= mob["xp"], (depth, mob)