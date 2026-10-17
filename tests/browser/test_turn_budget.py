"""ADR 0014's turn budget: 37 awake monsters on a 128x96 floor.

ADR 0014's Acceptance names this file:

    tests/browser/test_turn_budget.py: with 37 awake monsters on a
    128x96 floor, a turn takes at most 8 ms on desktop and at most
    30 ms on the phone proxy.

It is a gate, not a bench. `tests/browser/bench_floor_play.py` measures
the same thing across sizes and monster counts and writes a report; that
one is skipped unless `VEFR_BENCH=1`, because a bench is not a contract.
This one is the contract, so it runs with the rest of the browser suite
and skips only when Chromium is not installed (the `browser` fixture in
fixtures.py), exactly like every other test in this directory.

What is measured is the shipped AI, verbatim: parts 410, 420 and 430 are
concatenated into a page and their `enemyTurn` is timed with everything
else they call stubbed to no-ops. No shipped line is edited, no AI is
reimplemented here, and the measurement is the same `performance.now()`
window around the same call `docs/research/endless-e0.md` measured.

The floor is a real one. `vefr.delve_v3` draws a 128x96 floor, and the
37 awake monsters stand on that floor's own spawn tiles: the 36 the pop
stage drew plus the warden on its hall anchor, which is ADR 0014's "36
monsters, plus the warden". The room count is 40 rather than the 32 of
PLAN.md section 3's 128x96 row, because the budget is
`clamp(walkable // 30, 4, 36)` and 32 rooms leave 976 walkable tiles,
which budgets 32 monsters. 40 rooms leave 1,109, which reaches the cap
- this test needs a floor that is actually full.

Two things make the number mean what it says:

  - **Every sample is a whole turn.** The roster is reset to its spawn
    tiles, awake, before each sample, and the harness counts how many
    monsters `enemyAct` was called for. That count has to be 37 on every
    sample. A turn that ended on the first monster - a hero cornered by
    its own floor - is the fastest turn there is and would pass any
    budget while measuring nothing, so the count is asserted, not
    assumed. Nothing starts next to the hero either: the pop stage keeps
    every spawn `STAIR_CLEAR` (7) tiles off the stairs, and the test says
    so out loud rather than trusting it.
  - **The phone proxy is a 4x CPU throttle**, `Emulation.setCPUThrottlingRate`,
    the same proxy `docs/research/endless-e0.md` and
    `tests/browser/bench_floor_play.py` use, rather than a phone-sized
    viewport. A narrower window changes layout, not CPU.

The gate is on the p95 of 40 samples, not the slowest of 40. The ADR's
"at most 8 ms" is about the turn that has to fit a frame, and a single
sample carries whatever the machine was doing; the same rule the
generator's own budget test uses (`tests/test_floor_perf.py`). p50 and
the worst sample are printed, so a budget that is being scraped is
visible in the output rather than only in the pass.
"""

from __future__ import annotations

from math import floor
from pathlib import Path

from vefr import delve_v3

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT / "web" / "player" / "parts"

# The three parts under test, concatenated in the order the player
# concatenates them. The order matters: 420 opens the maps 430's turn
# floods through.
AI_PARTS = ("410-the-living-hazards.js",
            "420-how-a-monster-thinks.js",
            "425-the-elements.js",          # damage types, which 410 and 430 call (vefr#497)
            "430-loot-on-the-floor.js")

# The floor: PLAN.md section 3's largest size, and a room count that
# fills the pop stage's budget to ADR 0014's cap of 36.
WIDTH, HEIGHT, ROOMS = 128, 96, 40

# One fixed seed, so the floor under test is the same floor every run
# and a change in the number is a change in the AI, not a redraw.
# `budget-1`, not `budget-0`: the floor-key change redrew every floor, and
# `budget-0` no longer reaches the pop stage's cap - 34 monsters, where the
# test needs 36. The seed was re-picked the way the two cramped fixtures in
# `tests/test_elite_groups_pop.py` were: by drawing the sweep with the
# Section THIS module builds (`section()`, 40 rooms, 128x96) and keeping the
# floors that reach the cap. `budget-1` is the first of them; it draws 36
# monsters and a warden, and the nearest of the 37 stands 16 tiles from the
# stairs, so no sample can end on a first-monster attack.
SEED = "budget-1"
FLOOR_KIND = "normal"

# 36 monsters plus the warden, which is ADR 0014's "37 at most" awake.
AWAKE = 37

# The ADR's two numbers, and the throttle that makes a desktop browser
# stand in for a phone.
DESKTOP_BUDGET_MS = 8.0
PHONE_BUDGET_MS = 30.0
PHONE_THROTTLE = 4

# 10 warm-up samples (the JIT has to see the turn before it is timed)
# and 40 timed ones, which is the sample count the E0a bench used.
WARMUP, SAMPLES = 10, 40

VIEWPORT = {"width": 1280, "height": 800}


def section() -> dict:
    """A Section pack of the kind `delve_v3` reads, in the golden shape.

    The same pack `tests/test_floor_perf.py` builds for its 128x96
    golden, so the floor measured here is the same kind of floor the
    goldens pin, with one change: 40 rooms, so the budget reaches 36.
    """
    return {
        "section": 1,
        "id": "cellar-normal",
        "rooms": [ROOMS, ROOMS],
        "families": [
            {"family": "rat", "weight": 5, "depth": [1, 6]},
            {"family": "moth", "weight": 3, "depth": [1, 9]},
            {"family": "beetle", "weight": 2, "depth": [3, 9]},
        ],
        "elites": {"per_floor": [1, 2], "affixes": ["big", "quick", "glowing"]},
        "groups": {"per_floor": [1, 2], "minions": [2, 3]},
        "loot": {"tier": 1},
        "pois": ["the drowned well", "the ash alcove", "the rusted grate"],
        "warden": "ashwing",
        "vault": "vault-cellar",
    }


def floor_plan() -> dict:
    """The floor under test: a real v3 draw at 128x96."""
    plan = delve_v3.generate_floor_v3(
        SEED, (WIDTH, HEIGHT), section(), FLOOR_KIND)
    assert plan["gen"] == 3, (
        f"seed {SEED} fell back to v2 geometry; pick a seed that draws a "
        "v3 floor at 128x96 or this test measures a floor that never "
        "went through the pop stage")
    return plan


def roster(plan: dict) -> list[dict]:
    """The 37 awake monsters, as the records the player bakes.

    One record per spawn on the floor's own spawn tile, carrying the
    `group` and `leader` marks through, and the warden on its hall
    anchor. `loadEnemies` copies six fields onto the live record and
    `prepareMinds` reads the group keys off these, so a roster that
    dropped them would measure 37 loose monsters instead of the 36
    monsters and a warden ADR 0014 describes.
    """
    out = []
    for spawn in plan["spawns"]:
        out.append({
            "id": spawn["id"],
            "name": f"a {spawn['family']}",
            "at": list(spawn["at"]),
            "hp": 3,
            "atk": 1,
            "sight": 6,
            "drops": [],
            "group": spawn.get("group", ""),
            "leader": spawn.get("leader", False),
        })
    out.append({
        "id": "w",
        "name": "the warden",
        "at": list(plan["anchors"]["warden"]),
        "hp": 12,
        "atk": 3,
        "sight": 10,
        "drops": [],
        "warden": True,
    })
    return out


def manhattan(a: list[int], b: list[int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


# ---- the page: the shipped AI, and stubs for everything it calls ----

# The same stub list `tests/browser/bench_floor_play.py` uses, for the
# same reason: the AI parts under test are inlined verbatim, so every
# name they call from the rest of the player is stubbed here and named
# exactly as the parts call it. The roster is handed in rather than
# placed, so the monsters stand where the generator put them.
HARNESS = """
(function () {
  var out = {};
  var regionName = 'cellar';
  var hero = [1, 1];
  var HERO_HP = 1000000;
  var regions = {};
  var DEATH_LINE = 'dead';
  var XP_WORD = 'renown';
  var town = null;
  function draw() {}
  var store = { get: function () { return null; }, set: function () {},
                getJSON: function (k, d) { return d; }, setJSON: function () {} };
  function flushGrowth() {}
  function sayGrowth() {}
  function combatSay() {}
  function soundCue() {}
  function saveHeroHp() {}
  function renderHp() {}
  function heroMax() { return HERO_HP; }
  function heroAtk() { return 2; }
  function heroGold() { return 0; }
  function bagItems() { return []; }
  function bagAdd() { return false; }
  function itemName() { return ''; }
  function itemCatalog() { return {}; }
  function fireRule() {}
  function growBump() { return 1; }
  function growAward() { return null; }
  function levelSuffix() { return ''; }
  function enterRegion() {}
  window.VEFR_ENEMIES = {};
__PARTS__
  // How many monsters took a turn. `enemyAct` is a function declaration
  // in the same closure `enemyTurn` calls it from, so rebinding the
  // name here is what the call site resolves - the same seam
  // bench_floor_play.py wraps `distMap` through.
  var realAct = enemyAct;
  var acted = 0;
  enemyAct = function (e, maps) { acted += 1; return realAct(e, maps); };

  out.load = function (rows, at, rosterIn) {
    town = { map: rows, legend: { '#': { solid: true } }, hero_start: at };
    hero = at.slice();
    window.VEFR_ENEMIES = { cellar: rosterIn };
    enemiesByRegion = { cellar: rosterIn };
    regionName = 'cellar';
    loadEnemies();
    out.reset();
    return { loaded: enemies.length, hero: hero.slice() };
  };
  // Every sample starts from the same turn: 37 monsters on their spawn
  // tiles, all of them awake, none of them owing a group a free turn.
  // This is the state ADR 0014 costs, so it is the state that is timed.
  out.reset = function () {
    for (var i = 0; i < enemies.length; i++) {
      var spawn = enemiesByRegion[regionName][i];
      enemies[i].at = spawn.at.slice();
      enemies[i].alive = true;
      enemies[i].hp = enemies[i].hp0;
      enemies[i].awake = true;
      enemies[i].grace = false;
      enemies[i].wakeSpread = false;
    }
    hero = town.hero_start.slice();
    HERO_HP = 1000000;
  };
  out.state = function () {
    return {
      total: enemies.length,
      awake: enemies.filter(function (e) { return e.awake && e.alive; }).length,
      alive: enemies.filter(function (e) { return e.alive; }).length
    };
  };
  out.turn = function (samples, warmup) {
    var times = [], acts = [];
    for (var i = 0; i < warmup + samples; i++) {
      out.reset();
      acted = 0;
      var t0 = performance.now();
      enemyTurn();
      var t1 = performance.now();
      if (i >= warmup) { times.push(t1 - t0); acts.push(acted); }
    }
    return { times: times, acts: acts };
  };
  window.__ai = out;
  return out;
})()
"""


def _percentile(samples: list[float], p: float) -> float:
    """The nearest-rank percentile `sorted[floor(p * (n - 1))]`.

    The rule `docs/research/endless-e0.md` states, so a number printed
    here reads against that document's table without a conversion.
    """
    ordered = sorted(samples)
    return ordered[floor(p * (len(ordered) - 1))]


def _ai_source() -> str:
    return HARNESS.replace(
        "__PARTS__",
        "\n".join((PARTS / name).read_text(encoding="utf-8") for name in AI_PARTS))


def test_the_fixture_reaches_the_warden_cap():
    """The floor under test still carries 36 monsters and a warden.

    The gate below needs a floor that is actually full: the budget is
    `clamp(walkable // 30, 4, 36)`, and a floor that only reached 34 would
    time a cheaper turn and call it a pass. That precondition is checked
    here, in Python and without a browser, because the floor key is a
    per-seed thing: a redraw of the seed is a broken fixture, and a broken
    fixture is not a browser failure. When this fails, the seed is re-picked
    by drawing the sweep with this module's own `section()` and keeping the
    floors that reach the cap - never by lowering `AWAKE`.
    """
    plan = floor_plan()
    roster_in = roster(plan)
    assert len(roster_in) == AWAKE, (
        f"seed {SEED} at {WIDTH}x{HEIGHT} drew {len(roster_in) - 1} monsters "
        f"and a warden, not {AWAKE - 1} monsters and a warden; the budget is "
        "clamp(walkable // 30, 4, 36) and this floor does not reach the cap")


def test_turn_budget_with_37_awake_monsters(browser):
    """One turn of 37 awake monsters: p95 <= 8 ms desktop, <= 30 ms throttled.

    The desk number is the gate and the phone number is the gate; both
    are measured on the same floor, the same roster and the same
    shipped `enemyTurn`.
    """
    plan = floor_plan()
    roster_in = roster(plan)
    hero_at = list(plan["anchors"]["up"])
    assert len(roster_in) == AWAKE, (
        f"the floor drew {len(roster_in) - 1} monsters and a warden, not "
        f"{AWAKE - 1} monsters and a warden; the budget is clamp("
        "walkable // 30, 4, 36) and this floor did not reach the cap")

    # Nothing starts next to the hero. A monster one tile away attacks
    # and ends the turn there, and the rest of the floor never gets a
    # turn at all - the sample would be fast and meaningless.
    nearest = min(manhattan(entry["at"], hero_at) for entry in roster_in)
    assert nearest >= 2, (
        f"a monster spawned {nearest} tile(s) from the hero at {hero_at}; "
        "the turn would end on its attack before 37 monsters acted")

    pg = browser.new_context(viewport=VIEWPORT).new_page()
    pg.evaluate(_ai_source())
    loaded = pg.evaluate(
        "([rows, at, rosterIn]) => window.__ai.load(rows, at, rosterIn)",
        [plan["rows"], hero_at, roster_in])
    assert loaded["loaded"] == AWAKE, (
        f"the player loaded {loaded['loaded']} monsters, not {AWAKE}")

    state = pg.evaluate("() => window.__ai.state()")
    assert state["awake"] == AWAKE, (
        f"{state['awake']} of the {state['total']} monsters are awake; the "
        "budget is a budget for 37 of them")

    client = pg.context.new_cdp_session(pg)
    client.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    desk = pg.evaluate("([n, w]) => window.__ai.turn(n, w)", [SAMPLES, WARMUP])
    client.send("Emulation.setCPUThrottlingRate", {"rate": PHONE_THROTTLE})
    slow = pg.evaluate("([n, w]) => window.__ai.turn(n, w)", [SAMPLES, WARMUP])
    client.send("Emulation.setCPUThrottlingRate", {"rate": 1})

    # Every timed sample was a whole 37-monster turn. Without this the
    # budget is measured against a turn that stopped early.
    for label, run in (("desktop", desk), (f"{PHONE_THROTTLE}x", slow)):
        acted = sorted(set(run["acts"]))
        assert acted == [AWAKE], (
            f"{label}: the monsters that took a turn per sample were "
            f"{acted[:5]}, not [{AWAKE}]; a turn that ended early is not "
            "the turn this budget is about")

    desk_p50 = _percentile(desk["times"], 0.50)
    desk_p95 = _percentile(desk["times"], 0.95)
    slow_p50 = _percentile(slow["times"], 0.50)
    slow_p95 = _percentile(slow["times"], 0.95)
    print(
        f"\n{WIDTH}x{HEIGHT} {AWAKE} awake monsters, seed {SEED}: "
        f"desktop p50 {desk_p50:.2f} ms / p95 {desk_p95:.2f} ms / "
        f"max {max(desk['times']):.2f} ms; "
        f"phone {PHONE_THROTTLE}x p50 {slow_p50:.2f} ms / p95 {slow_p95:.2f} ms / "
        f"max {max(slow['times']):.2f} ms over {SAMPLES} samples "
        f"(budgets {DESKTOP_BUDGET_MS:.0f} / {PHONE_BUDGET_MS:.0f} ms)"
    )

    assert desk_p95 <= DESKTOP_BUDGET_MS, (
        f"{AWAKE} awake monsters on a {WIDTH}x{HEIGHT} floor: the desktop "
        f"p95 is {desk_p95:.2f} ms over {SAMPLES} samples and the budget is "
        f"{DESKTOP_BUDGET_MS:.0f} ms; p50 {desk_p50:.2f} ms, max "
        f"{max(desk['times']):.2f} ms")
    assert slow_p95 <= PHONE_BUDGET_MS, (
        f"{AWAKE} awake monsters on a {WIDTH}x{HEIGHT} floor under a "
        f"{PHONE_THROTTLE}x throttle: the p95 is {slow_p95:.2f} ms over "
        f"{SAMPLES} samples and the budget is {PHONE_BUDGET_MS:.0f} ms; "
        f"p50 {slow_p50:.2f} ms, max {max(slow['times']):.2f} ms")
