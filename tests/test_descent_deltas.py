"""Play-time floors, save deltas: the save is a set of deltas, never a grid.

A floor that was never baked at weave time is generated when the hero
reaches the stair, and what is remembered about it is a handful of bytes:
who was killed, what was taken, what was dropped where, which secrets
were found, and the explored bitset. Nothing else, and never the map
itself. This is acceptance 2 of the slice - the budgets of PLAN §3, the
40-floor cap and its eviction - played through the REAL woven file in
jsdom, with the trim and the byte counts taken by the player's own code.

Also the jsdom half of acceptance 1: the same seed after a reload draws
the same floor. (The Chromium half is tests/browser/test_descent_reload.py.)

One honest limit of the harness, the same one the shipped game has: the
save remembers the floors, not where the hero stood, so every session
starts at the town's own wake point and walks the whole descent again.
The walks below are therefore planned against the very floor the
generator drew, and a fixture with nothing in it is used where the walk
itself is what is being proved.
"""

import base64
import copy
import json
import shutil
import subprocess
from collections import deque
from pathlib import Path

import pytest

import play_kit
from vefr import delve

from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

ROOT = Path(__file__).resolve().parents[1]
DOC_HARNESS = ROOT / "tests" / "fixtures" / "descent_doc_harness.mjs"
WORLD = "descent-test"
DOC_KEY = "vefr-descent-" + WORLD
TOWN_HERO = [3, 4]

# The biggest floor the plan allows (PLAN §3: 96x64 is the candidate for
# late floors), so the budgets are measured on the largest thing the save
# can carry rather than on a convenient small one.
BIG = {"w": 96, "h": 64}

READS = ["VEFR_COMBAT.region", "VEFR_COMBAT.hero",
         "VEFR_DESCENT.floor", "VEFR_DESCENT.doc", "store"]

DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def _rows(plan):
    return plan["rows"]


def _walkable(plan, x, y):
    return 0 <= y < plan["h"] and 0 <= x < plan["w"] and _rows(plan)[y][x] != "#"


def _path(plan, start, goal, avoid=()):
    """The shortest walkable path from `start` to `goal`, as direction names.

    Breadth-first over the floor the generator drew, so the walk a test
    performs is one a player could perform. A monster's tile is a wall to
    the search: the fight belongs to the player, and the tests that mean
    to fight bump into it on purpose.
    """
    blocked = {tuple(a) for a in avoid}
    seen = {tuple(start)}
    queue = deque([(tuple(start), [])])
    while queue:
        (x, y), steps = queue.popleft()
        if (x, y) == tuple(goal):
            return steps
        for name, (dx, dy) in DIRS.items():
            nxt = (x + dx, y + dy)
            if nxt in seen or nxt in blocked or not _walkable(plan, *nxt):
                continue
            seen.add(nxt)
            queue.append((nxt, steps + [name]))
    return []


def _go(plan, start, goal, avoid=()):
    return "walk:" + ",".join(_path(plan, start, goal, avoid))


def _go_fight(plan, mob):
    """Walk from the up stair to `mob` around the others, then keep pressing the
    last direction: a monster that saw the hero coming may have stepped a tile
    up its corridor, and a bump is what starts a fight."""
    others = [m["at"] for m in plan["mobs"] if m["at"] != mob["at"]]
    path = _path(plan, plan["anchors"]["up"], mob["at"], others)
    return "walk:" + ",".join(path + [path[-1]] * 3)


def _reachable_mob(plan):
    """The first monster the hero can walk to from the up stair without bumping another.

    A v3 floor (E8-0) joins its rooms with corridors, so the first monster in
    the list may sit behind another one; a fight test needs one it can reach.
    """
    for mob in plan["mobs"]:
        others = [m["at"] for m in plan["mobs"] if m["at"] != mob["at"]]
        if _path(plan, plan["anchors"]["up"], mob["at"], others):
            return mob
    raise AssertionError("no monster on this floor can be reached cleanly")


TOWN = {"rows": (ROOT / "worlds" / "sample-world" / "acts" / "act-1" / "town"
                 / "map.md").read_text(encoding="utf-8").splitlines(),
        "w": 12, "h": 10}


def _descend(depth, at=None, avoid_mobs=True, descent=None):
    """The steps that walk from the town down to `depth`, one stair at a time.

    Every floor in between is walked to its own down-stair and used, so
    the run is a real descent rather than a jump into the last floor.

    `descent` is the descent to walk, for a caller whose pack carries one
    other than the fixture's own (`DESCENT`). The floors are planned from
    it, so the walk is planned against exactly the floors the player will
    draw - and `avoid_mobs` only ever removes tiles from a plan, so a walk
    over floors nothing lives on is still a walk a player could make.
    """
    walked = descent if descent is not None else DESCENT
    steps = ["begin"]
    here = list(at) if at else list(TOWN_HERO)
    for d in range(1, depth + 1):
        if d == 1:
            steps.append(_go(TOWN, here, walked["entry"]["at"]))
        else:
            plan = delve.floor_plan(walked, d - 1)
            mobs = [m["at"] for m in plan["mobs"]] if avoid_mobs else []
            steps.append(_go(plan, here, plan["anchors"]["down"], mobs))
        steps += ["click:#interact", "wait:150"]
        here = list(delve.floor_plan(walked, d)["anchors"]["up"])
    return [s for s in steps if s != "walk:"]


def _off_and_back(plan):
    """Step off the floor's up-stair and back onto it (vefr#465).

    A stair landing is set aside until the hero has stepped off it, so a
    test that means to climb home straight off an arrival walks the hero
    off the stair and back, the way a player does. The step out is to a
    tile that is open and holds no monster, so it is a step and not a
    bump.
    """
    up = plan["anchors"]["up"]
    mobs = [m["at"] for m in plan["mobs"]]
    back = {"up": "down", "down": "up", "left": "right", "right": "left"}
    away = next(name for name, (dx, dy) in DIRS.items()
                if [up[0] + dx, up[1] + dy] not in mobs
                and _walkable(plan, up[0] + dx, up[1] + dy))
    return [f"walk:{away}", f"walk:{back[away]}"]


def _play(tmp_path, steps, store=None, pack=None, patch=None):
    html = play_kit.weave(play_kit.pack(tmp_path, pack or "descent", patch=patch),
                          tmp_path)
    spec = {"steps": steps, "read": list(READS)}
    if store:
        spec["store"] = store
    return play_kit.play(html, spec)


def _doc(play):
    raw = play["store"].get(DOC_KEY)
    return json.loads(raw) if raw else None


def _json_store(doc):
    return {DOC_KEY: json.dumps(doc)}


# ---- a virtual region ---------------------------------------------------

def test_a_floor_that_was_never_baked_loads_and_plays(tmp_path):
    html = play_kit.weave(play_kit.pack(tmp_path, "descent"), tmp_path)
    baked = play_kit.play(html, {"steps": ["begin"],
                                 "read": ["VEFR_REGIONS.cellar-0-1"]})
    assert baked["reads"]["VEFR_REGIONS.cellar-0-1"] is None, \
        "the fixture must not bake the floors it generates"

    play = _play(tmp_path, _descend(1))
    assert play["errors"] == [], play["errors"]
    assert play["reads"]["VEFR_COMBAT.region"] == "cellar-0-1"
    floor = play["reads"]["VEFR_DESCENT.floor"]
    assert floor["rows"] and len(floor["rows"]) == floor["h"]
    assert floor["identity"]["gen"] == delve.GEN_VERSION
    assert _doc(play)["floors"]["cellar-0-1"]["n"] == 1


# ---- acceptance 1, the jsdom half ---------------------------------------

def test_the_same_seed_after_a_reload_draws_the_same_floor(tmp_path):
    first = _play(tmp_path, _descend(2))
    assert first["errors"] == [], first["errors"]
    store = first["store"]

    again = _play(tmp_path, _descend(2), store=store)
    assert again["errors"] == [], again["errors"]
    assert again["reads"]["VEFR_DESCENT.floor"]["rows"] == \
        first["reads"]["VEFR_DESCENT.floor"]["rows"]
    assert again["reads"]["VEFR_COMBAT.region"] == "cellar-0-2"
    # And the remembered deltas survived the reload untouched.
    assert _doc(again)["floors"]["cellar-0-2"]["fog"] == \
        _doc(first)["floors"]["cellar-0-2"]["fog"]


# ---- the save is deltas, not a grid ------------------------------------

def test_the_save_carries_the_deltas_and_never_the_floor(tmp_path):
    play = _play(tmp_path, _descend(1))
    record = _doc(play)["floors"]["cellar-0-1"]
    assert set(record) >= {"g", "h", "k", "n", "s", "kills", "chests",
                           "drops", "secrets", "fog"}
    assert record["fog"], "the floor the hero walked must be remembered"
    raw = play["store"][DOC_KEY]
    for row in play["reads"]["VEFR_DESCENT.floor"]["rows"][:4]:
        assert row not in raw, "the save may not carry the grid"


def test_the_descent_lives_in_one_store_key(tmp_path):
    play = _play(tmp_path, _descend(1))
    keys = [k for k in play["store"] if k.startswith("vefr-")]
    assert DOC_KEY in keys
    assert not [k for k in keys if "cellar-0-1" in k], keys


# ---- acceptance 2, the budgets -------------------------------------------

def test_a_visited_floor_stays_inside_its_byte_budget(tmp_path):
    play = _play(tmp_path, _descend(2))
    for name, record in _doc(play)["floors"].items():
        size = len(json.dumps(record, ensure_ascii=False).encode("utf-8"))
        assert size <= delve.FLOOR_BYTES, (name, size)


def test_the_whole_save_at_forty_floors_stays_inside_the_budget(tmp_path):
    # A fully explored 96x64 floor is the worst case the save can carry:
    # one bit per tile is 768 bytes, 1024 characters of base64.
    bits = (BIG["w"] * BIG["h"] + 7) // 8
    assert len(base64.b64encode(b"\xff" * bits)) < delve.FLOOR_BYTES
    forty = doc_for(40)
    assert len(json.dumps(forty).encode("utf-8")) <= delve.SAVE_BYTES

    # And the player's own trim keeps a save over the count cap inside both.
    got = _trim(tmp_path, doc_for(45))
    assert got["floors"] == delve.FLOOR_CAP
    assert got["bytesAfter"] <= delve.SAVE_BYTES


def test_at_most_forty_floors_are_kept_and_the_oldest_go_first(tmp_path):
    over = _trim(tmp_path, doc_for(45))
    assert over["floors"] == delve.FLOOR_CAP
    assert over["order"][0] == doc_name(5), over["order"][:3]
    assert over["order"][-1] == doc_name(44)
    assert over["fogs"] == over["order"], "what is kept keeps its memory"

    under = _trim(tmp_path, doc_for(12))
    assert under["floors"] == 12, "a save under the cap keeps every floor"
    assert under["fogs"] == under["order"]


def test_a_save_over_the_byte_budget_loses_the_oldest_bitsets_first(tmp_path):
    # Under the count cap but over the byte budget: the bitsets are the
    # big part of a floor, so they are the first thing to go, oldest first.
    fat = doc_for(40)
    for record in fat["floors"].values():
        record["fog"] = base64.b64encode(b"\xff" * 7000).decode()
    assert len(json.dumps(fat)) > delve.SAVE_BYTES

    got = _trim(tmp_path, fat)
    assert got["floors"] == 40, "the count cap is not the byte budget's job"
    assert got["bytesAfter"] <= delve.SAVE_BYTES
    kept = set(got["fogs"])
    assert kept, "some memory must survive"
    assert kept == set(got["order"][-len(kept):]), got["fogs"][:3]


# ---- the lifecycle ------------------------------------------------------

# How many live on a floor is the generator's area budget and not a pack
# key, so a pack cannot ask for a floor to hold exactly one. The fight
# this test stages is therefore staged against the roster the generator
# drew: the hero walks up to the monster it picked, and a monster it
# bumps on the way is a fight too - which is the game, not a fault.
DESCENT_PATCH = {"world.json": {"descent": copy.deepcopy(DESCENT)}}


def test_returning_to_town_clears_the_kills_and_keeps_the_memory(tmp_path):
    # The fight, then the way home. They are two sessions because that is
    # what they are: the save remembers the floor, not where the hero
    # stood, so the second session walks in on the dead monster - which is
    # exactly why the walk home is a clean one.
    plan = delve.floor_plan(DESCENT, 1)
    mob = _reachable_mob(plan)
    fight = ["begin", _go(TOWN, TOWN_HERO, DESCENT["entry"]["at"]),
             "click:#interact", "wait:150"]
    fight.append(_go_fight(plan, mob))
    fight += ["wait:100"] * 6
    killed = _play(tmp_path, fight, patch=DESCENT_PATCH)
    assert killed["errors"] == [], killed["errors"]
    record = _doc(killed)["floors"]["cellar-0-1"]
    # The monster the walk aimed at is dead, and nothing outside the floor
    # the generator drew is: a bump kills what it touched, never more.
    assert mob["id"] in record["kills"], record["kills"]
    assert set(record["kills"]) <= {m["id"] for m in plan["mobs"]}
    assert killed["reads"]["VEFR_COMBAT.hero"]["hp"] > 0

    # Now walk home: off the landing the descent put the hero on, back
    # onto its up-stair, and up into the town (vefr#465: the stair on a
    # landing is not the stair back until the hero has stepped off).
    home = _play(tmp_path, _descend(1) + _off_and_back(plan) +
                 ["click:#interact", "wait:200"],
                 store=killed["store"], patch=DESCENT_PATCH)
    assert home["reads"]["VEFR_COMBAT.region"] == "town"
    record = _doc(home)["floors"]["cellar-0-1"]
    assert record["kills"] == [], "returning to town resets the Section"
    assert record["fog"], "the explored bitset is kept"


def test_an_identity_mismatch_regenerates_the_floor_and_keeps_the_story(tmp_path):
    play = _play(tmp_path, _descend(1))
    stale = copy.deepcopy(_doc(play))
    stale["floors"]["cellar-0-1"]["h"] = "0123456789ab"
    stale["floors"]["cellar-0-1"]["kills"] = ["m0"]
    stale["flags"] = {"warden-killed": True}

    again = _play(tmp_path, ["begin", "wait:250"], store=_json_store(stale))
    assert again["errors"] == [], again["errors"]
    after = _doc(again)
    assert after["floors"]["cellar-0-1"]["h"] != "0123456789ab"
    assert after["floors"]["cellar-0-1"]["kills"] == []
    assert after["flags"]["warden-killed"] is True, "story flags are never lost"


def test_the_story_flags_are_kept_in_the_descent_save(tmp_path):
    play = _play(tmp_path, ["begin", "wait:100"])
    doc = _doc(play)
    assert isinstance(doc["flags"], dict)
    assert doc["card"] == delve.GEN_VERSION


# ---- the document, built for the two budget tests ------------------------

def doc_name(i):
    return "cellar-0-1-%d" % i


def doc_for(count, fog_bytes=None):
    """A save of `count` visited floors, each as big as one can honestly be."""
    bits = fog_bytes or ((BIG["w"] * BIG["h"] + 7) // 8)
    doc = {"v": 1, "gen": delve.GEN_VERSION, "run": 0,
           "seed": DESCENT["run_seed"], "order": [], "floors": {},
           "flags": {}, "card": delve.GEN_VERSION}
    for i in range(count):
        name = doc_name(i)
        doc["floors"][name] = {
            "g": delve.GEN_VERSION,
            "h": delve.section_hash(DESCENT["sections"][0]),
            "k": "%s/cellar/0/%d" % (DESCENT["run_seed"], i + 1),
            "n": i + 1, "s": "cellar",
            "kills": ["m0", "m1"], "chests": [], "secrets": [],
            "drops": [{"at": [10, 10], "item": "pebble"}],
            "fog": base64.b64encode(b"\xff" * bits).decode(),
        }
        doc["order"].append(name)
    return doc


def _trim(tmp_path, doc):
    """The player's own trim, run in the woven file (twice, for the cache)."""
    html = play_kit.weave(play_kit.pack(tmp_path, "descent"), tmp_path)
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"descent": DESCENT, "docs": [doc]}))
    run = subprocess.run(["node", str(DOC_HARNESS), str(html), str(cases)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr + run.stdout
    out = json.loads(run.stdout)
    assert out["hasApi"] is True
    return out["results"][0]


def _beside(plan, at):
    """A walkable neighbour of `at`, for standing next to a monster."""
    x, y = at
    for name, (dx, dy) in DIRS.items():
        if _walkable(plan, x + dx, y + dy):
            return [x + dx, y + dy]
    raise AssertionError("no neighbour")


def _toward(plan, here, there):
    """The direction that steps from `here` onto `there`."""
    for name, (dx, dy) in DIRS.items():
        if [here[0] + dx, here[1] + dy] == list(there):
            return name
    raise AssertionError("not adjacent")

# ---- the New-descent control -------------------------------------------

def test_the_new_descent_control_starts_a_fresh_run(tmp_path):
    # The pause menu's Descent panel is the way into a run without walking
    # to the stair, and the way into the *next* one. A run is the same
    # Sections with a fresh, counted seed - no clock, no chance.
    line = _play(tmp_path, ["begin", "menu:descent", "wait:150"])
    assert line["reads"]["VEFR_DESCENT.doc"]["run"] == 0
    run = _play(tmp_path, ["begin", "menu:descent", "wait:150",
                           "click:#descent-new", "wait:400"])
    assert run["errors"] == [], run["errors"]
    assert run["reads"]["VEFR_COMBAT.region"] == "cellar-0-1"
    doc = _doc(run)
    assert doc["run"] == 1
    assert doc["seed"] == "run-a/run-1"
    assert doc["floors"]["cellar-0-1"]["k"] == "run-a/run-1/cellar/0/1"


def test_a_pack_with_no_descent_offers_no_descent_menu(tmp_path):
    html = play_kit.weave(play_kit.pack(tmp_path, "interact"), tmp_path)
    play = play_kit.play(html, {"steps": ["begin", "menu:journal", "wait:100"],
                                "read": ["visible:#menu-descent-row"]})
    assert play["errors"] == [], play["errors"]
    assert play["reads"]["visible:#menu-descent-row"] is False
