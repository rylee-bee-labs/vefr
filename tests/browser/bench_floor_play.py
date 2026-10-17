"""E0a floor bench, played in Chromium - measurement only.

Skipped unless ``VEFR_BENCH=1`` (a bench is not a gate). Runs only what
needs a real browser, all against the shipped player and the shipped
generator twin:

1. **JS generation time** - `generateFloorV2` from
   `web/player/parts/390-engine-delve-v2.js`, verbatim, over the
   `bench-*` seeds at all four sizes, desktop and under a 4x CPU
   throttle. Each sample is one seed's mean of 10 back-to-back
   generations (Chromium's `performance.now()` resolves ~0.1 ms, too
   coarse for a single sub-millisecond floor). An FNV-1a checksum per
   seed is compared against Python's, so the timings provably come from
   the twin. `norns delve` and the pack validators are not involved:
   the 20..64 size limits in `design/random-floors.md` are a *proposed*
   validator and nothing in `src/vefr/` enforces them.

2. **Monster turn cost** - the real AI, verbatim: parts 410, 420 and
   430 (`enemyTurn`) run inside a bench closure with the rest of the
   player stubbed to no-ops (rendering is measured in item 4 below; the
   stubs are `draw`, `combatSay`, `soundCue`, the growth/bag/gold
   helpers and `localStorage` writes). N awake monsters stand on a real
   generated floor, are reset to their spawn tiles before each sample,
   and one player turn is timed. Floods per turn are counted by
   wrapping `distMap`; one flood alone is timed as the fallback number.

3. **The floor, played** - one woven player per size (a copy of the
   sample pack with the bench region added; nothing tracked is edited):
   frame intervals and main-thread time while autoexplore scrolls the
   camera (desktop and `cdp.Emulation.setCPUThrottlingRate(4)`), turns
   for autoexplore to clear the floor, and the bytes of
   ``vefr-fog-<world>-bench`` once every walkable tile is explored.

Results land in ``bench/runs/endless-e0-play.json`` (override with
``VEFR_BENCH_OUT``); the report ``docs/research/endless-e0.md`` cites
the numbers this produced. Timings vary run to run; counts (turns, fog
bytes, flood counts, checksums) are deterministic and asserted.

Run:
    uv run playwright install chromium          # once
    VEFR_BENCH=1 uv run pytest -q tests/browser/bench_floor_play.py -s
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli as vefr_cli
from vefr import delve

ROOT = Path(__file__).resolve().parents[2]
PARTS = ROOT / "web" / "player" / "parts"

# The four sizes under consideration (PLAN.md §3). The twin of this
# list lives in scripts/bench_floors.py; change both together.
SIZES: list[tuple[int, int, int]] = [(48, 32, 16), (64, 48, 18),
                                     (96, 64, 24), (128, 96, 32)]
SEED_PREFIX = "bench-"

# One seed per size is played (a floor is minutes of play, not a
# microbenchmark); the 200-seed sweep is the generator bench in
# scripts/bench_floors.py.
PLAY_SEED = "bench-0"

# A dark floor: the contract's fog radius. The player defaults to 6
# when a pack writes `"fog": true`, and every size gets the same one so
# the sizes compare.
FOG_RADIUS = 6

VIEWPORT = {"width": 1280, "height": 800}
FRAME_SECONDS = 6

OUT_PATH = Path(os.environ.get("VEFR_BENCH_OUT")
                or (ROOT / "bench" / "runs" / "endless-e0-play.json"))

pytestmark = pytest.mark.skipif(
    os.environ.get("VEFR_BENCH") != "1",
    reason="floor play bench; run with VEFR_BENCH=1 (needs: "
           "uv run playwright install chromium)")

RESULTS: dict = {
    "bench": "vefr-floor-play-bench",
    "version": 1,
    "sizes": [list(s) for s in SIZES],
    "play_seed": PLAY_SEED,
    "viewport": [VIEWPORT["width"], VIEWPORT["height"]],
    "fog_radius": FOG_RADIUS,
    "command": "VEFR_BENCH=1 uv run pytest -q "
               "tests/browser/bench_floor_play.py -s",
    "results": {},
}


def _record(section: str, key: str, data: dict) -> None:
    """Park one measurement in the report and flush the JSON so far."""
    RESULTS["results"].setdefault(section, {})[key] = data
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(RESULTS, indent=2) + "\n", encoding="utf-8")


# ---- small shared helpers (twins of scripts/bench_floors.py) ----

def pct(values: list[float], p: float) -> float:
    """Nearest-rank percentile: sorted[floor(p * (n - 1))]."""
    if not values:
        raise ValueError("pct() of an empty sample")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(p * (len(ordered) - 1)))]


def walkable_keys(rows: list[str]) -> set[str]:
    """Every non-wall tile as "x,y" - the fog key shape."""
    return {f"{x},{y}"
            for y, row in enumerate(rows)
            for x, ch in enumerate(row) if ch != "#"}


def fnv1a(text: str) -> int:
    """32-bit FNV-1a over the string's characters (ASCII == UTF-16)."""
    h = 0x811C9DC5
    for ch in text:
        h = ((h ^ ord(ch)) * 0x01000193) & 0xFFFFFFFF
    return h


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---- building the bench pack: a copy of the sample pack + one floor ----

def build_play_pack(dest: Path, width: int, height: int, rooms: int,
                    seed: str) -> Path:
    """A pack whose start region is one generated floor of this size.

    Copies `worlds/sample-world`, drops a `bench` region in (map.md +
    the generator's own contract + fog), and points the act's `start`
    there. Nothing tracked is touched: the copy lives under `dest`.
    """
    pack = dest / "worlds" / "bench-play"
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "worlds" / "sample-world", pack)

    rows = delve.generate_floor_v2(seed, width, height, rooms)
    up = down = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "u":
                up = (x, y)
            elif ch == "d":
                down = (x, y)
    assert up is not None and down is not None

    act_dir = pack / "acts" / "act-1"
    act = json.loads((act_dir / "world.json").read_text(encoding="utf-8"))
    act["regions"] = list(act.get("regions") or []) + ["bench"]
    act["start"] = {"region": "bench", "at": list(up)}
    (act_dir / "world.json").write_text(json.dumps(act), encoding="utf-8")

    region = act_dir / "bench"
    region.mkdir(parents=True, exist_ok=True)
    (region / "map.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    contract = delve.contract(width, height, (up, down), down_at=down)
    contract["fog"] = {"radius": FOG_RADIUS}
    (region / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    return pack


def weave(pack: Path, out: Path) -> None:
    """Weave the pack into one HTML file (the shipped packaging path)."""
    rc = vefr_cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(out), pool=0, with_bundle=False, from_live=None))
    assert rc == 0, f"weave failed for {pack}"


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """One woven player per size, served over http for the whole module."""
    home = tmp_path_factory.mktemp("floor-bench")
    urls = {}
    for width, height, rooms in SIZES:
        key = f"{width}x{height}x{rooms}"
        pack = build_play_pack(home, width, height, rooms, PLAY_SEED)
        out = home / f"bench-{key}.html"
        weave(pack, out)
        urls[key] = out

    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
         "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            urllib.request.urlopen(base + "/bench-48x32x16.html", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the bench server never came up; see {home / 'server.log'}")

    yield {key: f"{base}/{path.name}" for key, path in urls.items()}
    proc.terminate()
    proc.wait(timeout=10)


# ---- what the page gets: counters, no shipped code edited ----

# Count every `window.VEFR_COMBAT = {...}` write: the player writes one
# per turn (move -> enemyTurn -> combatSnapshot), so the delta is an
# exact turn count no matter how fast the explore timer runs.
INSTALL_COUNTER = """
window.__turns = 0;
(function () {
  var snap = window.VEFR_COMBAT;
  Object.defineProperty(window, 'VEFR_COMBAT', {
    configurable: true,
    get: function () { return snap; },
    set: function (v) { snap = v; window.__turns += 1; }
  });
})();
"""

# Frame intervals: one rAF loop that only records timestamps.
INSTALL_FRAMES = """
window.__frames = [];
window.__framesOn = false;
window.__last = 0;
(function loop(t) {
  if (window.__framesOn) {
    if (window.__last) window.__frames.push(t - window.__last);
    window.__last = t;
  } else { window.__last = 0; }
  requestAnimationFrame(loop);
})(0);
window.startFrames = function () {
  window.__frames = []; window.__last = 0; window.__framesOn = true;
};
window.stopFrames = function () {
  window.__framesOn = false; return window.__frames.slice();
};
"""

# Autoexplore paces itself at EXPLORE_PACE (80 ms) - the only 80 ms
# timer in the player. Rewriting that one delay to 0 changes the *wall
# time* of a run, never the path or the turn count, and keeps a full
# floor's explore inside a bench's patience.
PACE_PATCH = """
window.__origSetTimeout = window.setTimeout;
window.setTimeout = function (fn, ms) {
  return window.__origSetTimeout(fn, ms === 80 ? 0 : ms);
};
"""

STOPPED_JS = "() => document.getElementById('explore-status').textContent " \
             "!== 'Exploring...'"


def _metrics(client) -> dict:
    sent = client.send("Performance.getMetrics")
    return {m["name"]: m["value"] for m in sent["metrics"]}


def _frames(pg, client, seconds: int, rate: int | None) -> dict:
    """Frame intervals + main-thread time over one scroll window.

    The window is live only if autoexplore actually moved: the turn
    counter has to advance, or the numbers would be an idle page.
    """
    if rate:
        client.send("Emulation.setCPUThrottlingRate", {"rate": rate})
    turns0 = pg.evaluate("window.__turns")
    m0 = _metrics(client)
    pg.evaluate("window.startFrames()")
    pg.wait_for_timeout(seconds * 1000)
    frames = pg.evaluate("window.stopFrames()")
    m1 = _metrics(client)
    turns = pg.evaluate("window.__turns") - turns0
    if rate:
        client.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    assert turns > 0, "autoexplore did not move during the frame window"
    assert len(frames) > 30, f"only {len(frames)} frames recorded"
    task_ms = (m1["TaskDuration"] - m0["TaskDuration"]) * 1000
    script_ms = (m1["ScriptDuration"] - m0["ScriptDuration"]) * 1000
    label = "throttled4x" if rate else "desktop"
    return {
        "label": label,
        "seconds": seconds,
        "frames": len(frames),
        "turns": turns,
        "interval_ms": {"p50": round(pct(frames, 0.50), 3),
                        "p95": round(pct(frames, 0.95), 3)},
        "task_ms_per_frame": round(task_ms / len(frames), 3),
        "task_ms_per_turn": round(task_ms / turns, 3),
        "script_ms_per_frame": round(script_ms / len(frames), 3),
    }


def _finish_explore(pg, max_rounds: int = 200) -> tuple[int, str]:
    """Keep autoexplore running until the floor reports it is clear.

    The 400-step cap (EXPLORE_CAP) stops a big floor part-way; a fresh
    click resumes with the cap reset, exactly as a player's would.
    Returns (restarts, final status line).
    """
    restarts = 0
    status = ""
    for _ in range(max_rounds):
        status = pg.locator("#explore-status").inner_text()
        if "Nothing left" in status:
            return restarts, status
        if "Exploring" in status:
            try:
                pg.wait_for_function(STOPPED_JS, timeout=60_000)
            except Exception as exc:  # noqa: BLE001 - a stuck timer
                pytest.fail(f"autoexplore never paused: {exc}")
            continue
        pg.locator("#explore").click()
        restarts += 1
        after = pg.locator("#explore-status").inner_text()
        if "Exploring" not in after:
            pytest.fail(f"autoexplore refused to start: {after!r}")
    pytest.fail(f"autoexplore never cleared the floor; last status {status!r}")
    return restarts, status  # unreachable; keeps the type checker honest


def _open_player(ctx, url: str):
    pg = ctx.new_page()
    pg.goto(url)
    pg.get_by_role("button", name="Begin").click()
    pg.wait_for_function(
        "window.VEFR_COMBAT && window.VEFR_COMBAT.region === 'bench'")
    return pg


# ---- 1. JS generation time + Python/JS parity ----

def test_js_generation_time_in_chromium(browser):
    """generateFloorV2's own clock, 200 seeds per size, both CPU rates."""
    pg = browser.new_context(viewport=VIEWPORT).new_page()
    delve_src = (PARTS / "390-engine-delve-v2.js").read_text(encoding="utf-8")
    pg.add_script_tag(content=delve_src)
    client = pg.context.new_cdp_session(pg)

    seeds = [f"{SEED_PREFIX}{i}" for i in range(200)]
    for width, height, rooms in SIZES:
        key = f"{width}x{height}x{rooms}"
        rows_of = [delve.generate_floor_v2(s, width, height, rooms)
                   for s in seeds]
        expected = [fnv1a("\n".join(r)) for r in rows_of]

        client.send("Emulation.setCPUThrottlingRate", {"rate": 1})
        desk = pg.evaluate(JS_GEN, [width, height, rooms, seeds, 10])
        client.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        slow = pg.evaluate(JS_GEN, [width, height, rooms, seeds, 10])
        client.send("Emulation.setCPUThrottlingRate", {"rate": 1})

        mismatches = sum(1 for a, b in zip(expected, desk["checksums"])
                         if a != b)
        assert mismatches == 0, f"Python and JS drew different floors at {key}"
        # Not every sample is > 0: a fast seed's 10 generations can fall
        # under `performance.now()`'s resolution and land on exactly 0.
        # The clock works if the bulk of the samples are real.
        positive = sum(1 for t in desk["times"] if t > 0)
        assert positive >= len(seeds) * 9 // 10, (
            f"timer measured nothing at {key}: {positive}/{len(seeds)} samples")

        _record("js_generation", key, {
            "seeds": len(seeds),
            "sample": "mean of 10 generations of one seed",
            "ms": {"p50": round(pct(desk["times"], 0.50), 4),
                   "p95": round(pct(desk["times"], 0.95), 4)},
            "ms_throttled4x": {"p50": round(pct(slow["times"], 0.50), 4),
                               "p95": round(pct(slow["times"], 0.95), 4)},
            "python_js_checksum_mismatches": mismatches,
        })


JS_GEN = """
([w, h, rooms, seeds, repeats]) => {
  function fnv1a(s) {
    var hv = 0x811c9dc5;
    for (var i = 0; i < s.length; i++) {
      hv ^= s.charCodeAt(i);
      hv = Math.imul(hv, 0x01000193) >>> 0;
    }
    return hv >>> 0;
  }
  const times = [], checksums = [];
  for (const seed of seeds) {
    let rows = window.VEFR_DELVE.generateFloorV2(seed, w, h, rooms);
    const t0 = performance.now();
    for (let r = 0; r < repeats; r++) {
      rows = window.VEFR_DELVE.generateFloorV2(seed, w, h, rooms);
    }
    times.push((performance.now() - t0) / repeats);
    checksums.push(fnv1a(rows.join('\\n')));
  }
  return { times: times, checksums: checksums };
}
"""


# ---- 2. the monster turn, with the shipped AI verbatim ----

# The three parts under test are inlined verbatim. Everything the rest
# of the woven player would supply is stubbed here; the stubs are named
# exactly as the parts call them and none of the three parts declares
# these names itself.
AI_HARNESS = """
(function () {
  var out = {};
  var regionName = 'bench';
  var hero = [1, 1];
  var HERO_HP = 1000000;
  var regions = {};
  var DEATH_LINE = 'dead';
  var XP_WORD = 'renown';
  var town = null;
  function draw() {}
  var store = { get: function () { return null; }, set: function () {}, getJSON: function (k, d) { return d; }, setJSON: function () {} };
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
  // Count floods: `distances` resolves this binding per call, so the
  // wrapper sees every flood the turn really pays for.
  var realDistMap = distMap;
  var floods = 0;
  distMap = function (x, y) { floods += 1; return realDistMap(x, y); };

  out.loadFloor = function (rows, at) {
    town = { map: rows, legend: { '#': { solid: true } }, hero_start: at };
    hero = at.slice();
  };
  out.spawn = function (count) {
    var tiles = [];
    for (var y = 0; y < town.map.length && tiles.length < count; y++) {
      for (var x = 0; x < town.map[0].length && tiles.length < count; x++) {
        if (town.map[y][x] === '#') continue;
        if (x === hero[0] && y === hero[1]) continue;
        tiles.push([x, y]);
      }
    }
    var roster = tiles.map(function (t, i) {
      return { id: 'm' + i, name: 'bench monster ' + i, at: t.slice(),
               hp: 3, atk: 1, sight: 6, drops: [] };
    });
    window.VEFR_ENEMIES = { bench: roster };
    enemiesByRegion = { bench: roster };
    regionName = 'bench';
    loadEnemies();
    return { spawned: enemies.length, awake: enemies.filter(
      function (e) { return e.alive; }).length };
  };
  out.reset = function () {
    for (var i = 0; i < enemies.length; i++) {
      enemies[i].at = window.VEFR_ENEMIES.bench[i].at.slice();
      enemies[i].alive = true;
      enemies[i].hp = enemies[i].hp0;
    }
    hero = town.hero_start.slice();
    HERO_HP = 1000000;
  };
  out.turn = function (samples, warmup) {
    var times = [], counts = [];
    for (var i = 0; i < warmup + samples; i++) {
      out.reset();
      floods = 0;
      var t0 = performance.now();
      enemyTurn();
      var t1 = performance.now();
      if (i >= warmup) { times.push(t1 - t0); counts.push(floods); }
    }
    return { times: times, floods: counts };
  };
  out.flood = function (samples) {
    var times = [];
    for (var i = 0; i < samples; i++) {
      var t0 = performance.now();
      realDistMap(hero[0], hero[1]);
      times.push(performance.now() - t0);
    }
    return times;
  };
  window.__ai = out;
  return out;
})()
"""


def test_monster_turn_cost_in_chromium(browser):
    """One player turn with 10/25/45 awake monsters, per size."""
    pg = browser.new_context(viewport=VIEWPORT).new_page()
    parts = "\n".join((PARTS / name).read_text(encoding="utf-8")
                      for name in ("410-the-living-hazards.js",
                                   "420-how-a-monster-thinks.js",
                                   "425-the-elements.js",
                                   "430-loot-on-the-floor.js"))
    pg.evaluate(AI_HARNESS.replace("__PARTS__", parts))
    client = pg.context.new_cdp_session(pg)

    for width, height, rooms in SIZES:
        key = f"{width}x{height}x{rooms}"
        rows = delve.generate_floor_v2(PLAY_SEED, width, height, rooms)
        up = next([x, y] for y, row in enumerate(rows)
                  for x, ch in enumerate(row) if ch == "u")
        pg.evaluate("([rows, at]) => window.__ai.loadFloor(rows, at)",
                    [rows, up])
        for count in (10, 25, 45):
            spawned = pg.evaluate("(n) => window.__ai.spawn(n)", count)
            assert spawned["spawned"] == count, f"{key}: {spawned}"

            client.send("Emulation.setCPUThrottlingRate", {"rate": 1})
            desk = pg.evaluate("() => window.__ai.turn(40, 10)")
            floods = pg.evaluate("() => window.__ai.flood(40)")
            client.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            slow = pg.evaluate("() => window.__ai.turn(40, 10)")
            client.send("Emulation.setCPUThrottlingRate", {"rate": 1})

            counts = set(desk["floods"])
            assert len(counts) == 1, f"floods per turn varied: {counts}"
            flood_per_turn = counts.pop()
            assert flood_per_turn >= 1

            _record("monster_turn", f"{key}:{count}", {
                "monsters": count,
                "placement": "first walkable tiles, row-major, seed "
                             + PLAY_SEED + "; reset before every sample",
                "awake": spawned["awake"],
                "floods_per_turn": flood_per_turn,
                "turn_ms": {"p50": round(pct(desk["times"], 0.50), 3),
                            "p95": round(pct(desk["times"], 0.95), 3)},
                "flood_ms": {"p50": round(pct(floods, 0.50), 3),
                             "p95": round(pct(floods, 0.95), 3)},
                "turn_ms_throttled4x": {"p50": round(pct(slow["times"], 0.50), 3),
                                        "p95": round(pct(slow["times"], 0.95), 3)},
            })


# ---- 3. the floor, played: frames, explore turns, fog bytes ----

@pytest.mark.parametrize("size", SIZES,
                         ids=[f"{w}x{h}" for w, h, _ in SIZES])
def test_play_measurements(browser, woven, size):
    """Scroll frames (desktop + 4x), autoexplore turns, fog bytes."""
    width, height, rooms = size
    key = f"{width}x{height}x{rooms}"
    rows = delve.generate_floor_v2(PLAY_SEED, width, height, rooms)
    walkable = walkable_keys(rows)

    ctx = browser.new_context(viewport=VIEWPORT)
    pg = _open_player(ctx, woven[key])
    try:
        pg.evaluate(INSTALL_COUNTER)
        pg.evaluate(INSTALL_FRAMES)
        client = ctx.new_cdp_session(pg)
        client.send("Performance.enable")

        # Frames while the camera scrolls: autoexplore walks at the
        # shipped 80 ms pace through both windows.
        turns0 = pg.evaluate("window.__turns")
        pg.locator("#explore").click()
        desktop = _frames(pg, client, FRAME_SECONDS, rate=None)
        throttled = _frames(pg, client, FRAME_SECONDS, rate=4)

        # Now the same run, finished fast: the pace patch changes no
        # path and no count, only the wall clock.
        pg.evaluate(PACE_PATCH)
        restarts, status = _finish_explore(pg)
        turns = pg.evaluate("window.__turns") - turns0

        fog_key = pg.evaluate(
            "() => 'vefr-fog-' + window.VEFR_WORLD.name + '-bench'")
        fog_text = pg.evaluate("(k) => localStorage.getItem(k)", fog_key)
        assert fog_text, "the floor never wrote its explored tiles"
        fog_tiles = set(json.loads(fog_text))
        missed = walkable - fog_tiles
        assert not missed, f"{len(missed)} walkable tiles never explored"

        floor_key = pg.evaluate(
            "() => 'vefr-floor-' + window.VEFR_WORLD.name")
        floor_text = pg.evaluate("(k) => localStorage.getItem(k)", floor_key)

        _record("play", key, {
            "seed": PLAY_SEED,
            "map_tiles": width * height,
            "walkable_tiles": len(walkable),
            "explore_turns_to_clear": turns,
            "explore_restarts_after_cap": restarts,
            "final_status": status,
            "fog_bytes": len(fog_text.encode("utf-8")),
            "fog_tiles": len(fog_tiles),
            "fog_tiles_pct_of_map": round(100 * len(fog_tiles)
                                          / (width * height), 1),
            "walkable_tiles_explored": len(walkable),
            "floor_loot_bytes": (len(floor_text.encode("utf-8"))
                                 if floor_text else 0),
            "frames": {"desktop": desktop, "throttled4x": throttled},
        })
    finally:
        ctx.close()


@pytest.mark.parametrize("size", SIZES[:1],
                         ids=[f"{SIZES[0][0]}x{SIZES[0][1]}"])
def test_explore_counts_repeat(browser, woven, size):
    """The deterministic half: two fresh runs clear the same floor in
    the same number of turns and leave the same fog bytes."""
    width, height, rooms = size
    key = f"{width}x{height}x{rooms}"
    counts = []
    for _ in range(2):
        ctx = browser.new_context(viewport=VIEWPORT)
        pg = _open_player(ctx, woven[key])
        try:
            pg.evaluate(INSTALL_COUNTER)
            pg.evaluate(PACE_PATCH)
            turns0 = pg.evaluate("window.__turns")
            pg.locator("#explore").click()
            _finish_explore(pg)
            turns = pg.evaluate("window.__turns") - turns0
            fog_key = pg.evaluate(
                "() => 'vefr-fog-' + window.VEFR_WORLD.name + '-bench'")
            fog_text = pg.evaluate("(k) => localStorage.getItem(k)", fog_key)
            counts.append((turns, len(fog_text.encode("utf-8")),
                           len(json.loads(fog_text))))
        finally:
            ctx.close()
    assert counts[0] == counts[1], f"autoexplore counts moved: {counts}"
    _record("explore_repeatability", key,
            {"runs": counts, "identical": True})
