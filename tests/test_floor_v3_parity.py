"""delve v3: the JavaScript twin draws exactly the floor Python draws, stage by stage.

PLAN.md section 2's parity constraint, and this file is its frozen acceptance
test (slice E3). `src/vefr/delve_v3.py` is the spec and the JS part is the
runtime; every floor of the sweep is drawn by BOTH and the two are compared as
canonical JSON. It is written before the twin, on purpose: a parity harness
written after the port records whatever the port happens to do.

The sweep is the cell count PLAN.md section 2 names: **200 seeds x every size x
every floor kind**, plus a stamped half at the two smallest sizes, because the
spec places stamped rooms (E5a) and a twin that cannot place them is not a
twin. Plus a small nonzero-cycle block, because `cycle` is a quarter of the
floor key and a sweep of cycle-0 floors cannot tell a twin that reads the cycle
apart from one that ignores it. Every case is compared at four stage boundaries - plan, layout, graph,
pop - so a mismatch names the stage it starts in instead of only saying the
floor differs. Then the public `generateFloorV3` is compared end to end, retry
ladder and v2 fallback included.

The parity runs through the REAL woven player (`cli.weave_html` of the sample
pack, then `window.VEFR_DELVE` inside it), in jsdom, over the node path
`tests/run.sh` links. `tests/browser/test_floor_v3_parity.py` is the normative
measurement - the same cases in Chromium, and the perf budget of PLAN.md
section 3 at desktop and at the 4x phone proxy. This file measures the budget
on the same engine and asserts the same desktop figure, because a port that is
tens of times over budget in node is tens of times over budget in a browser.

Nothing here reduces the seed count, skips a case, or compares a checksum
where it can compare the floor.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from vefr import cli, delve_v3, sections, stamps

import floor_v3_parity_cases as cases

ROOT = cases.ROOT
HARNESS = ROOT / "tests" / "fixtures" / "floor_v3_parity_harness.mjs"
TWIN_PART = ROOT / "web" / "player" / "parts" / "396-engine-delve-v3.js"

# The constants the determinism rule names in both languages, read off the spec
# rather than written out, so a change to `delve_v3` moves this list with it.
# `LEASH_*` is the one the player's own part 420 names too: the leash is the
# pack's to write and the player's to enforce, so the two ends of it are named
# once per language and have to agree.
EXPECTED_CONSTANTS = {
    "WALL": delve_v3.WALL,
    "FLOOR": delve_v3.FLOOR,
    "UP": delve_v3.UP,
    "DOWN": delve_v3.DOWN,
    "FLOOR_KINDS": list(delve_v3.FLOOR_KINDS),
    "MAX_TRIES": delve_v3.MAX_TRIES,
    "LOOPS_MIN": delve_v3.LOOPS_MIN,
    "LOOPS_MAX": delve_v3.LOOPS_MAX,
    "ROOMS_FLOOR": delve_v3.ROOMS_FLOOR,
    "STAIR_CLEAR": delve_v3.STAIR_CLEAR,
    "WANDER_DIRS": [list(step) for step in delve_v3.WANDER_DIRS],
    "WANDER_REACH": delve_v3.WANDER_REACH,
    "WANDER_AWAY": delve_v3.WANDER_AWAY,
    "WANDER_APART": delve_v3.WANDER_APART,
    "TILES_PER_MOB": delve_v3.TILES_PER_MOB,
    "MOBS_MIN": delve_v3.MOBS_MIN,
    "MOBS_MAX": delve_v3.MOBS_MAX,
    # The Section shape's own floor bound, held by the twin so the two agree
    # on how deep a `mobs` count may be written (vefr#357).
    "MOB_FLOOR_MAX": sections.MOB_FLOOR_MAX,
    "LONE_ELITES_MAX": delve_v3.LONE_ELITES_MAX,
    "GROUPS_MAX": delve_v3.GROUPS_MAX,
    "GROUP_MEMBERS_MAX": delve_v3.GROUP_MEMBERS_MAX,
    "ROOMS_PER_ELITE_GROUP": delve_v3.ROOMS_PER_ELITE_GROUP,
    "STAMP_ROOMS": list(delve_v3.STAMP_ROOMS),
    "MINION_REACH": delve_v3.MINION_REACH,
    "LEASH_MIN": delve_v3.LEASH_MIN,
    "LEASH_MAX": delve_v3.LEASH_MAX,
    "LEASH_DEFAULT": delve_v3.LEASH_DEFAULT,
    "CHEST_TABLES": list(delve_v3.CHEST_TABLES),
    "SHAPES": list(delve_v3.SHAPES),
    "FALLBACK_POIS": list(delve_v3.FALLBACK_POIS),
    "DEFAULT_ROOMS": list(delve_v3.DEFAULT_ROOMS),
    "FLAVOURS": delve_v3.FLAVOURS,
    "STAMP_ROUTE_ENDS": delve_v3.STAMP_ROUTE_ENDS,
    "STAMP_ATTEMPTS": stamps.ATTEMPTS,
    "STAMP_REQUIRED_ROLES": list(stamps.REQUIRED_ROLES),
    "STAMP_ANY_TAG": stamps.ANY_TAG,
}

# The three draw shapes a twin is allowed, and no others: the whole number
# `lo + floor(rng() * (hi - lo + 1))`, the index `floor(rng() * n)`, and the one
# comparison `_link` makes when it picks the side of a bend. PLAN.md section 2
# forbids any other use of a float.
ALLOWED_DRAW = re.compile(r"Math\.floor\(rng\(\) \* [^)]*\)|rng\(\) < 0\.5")

# What the twin may never reach for, by name. `Math.random`, the clock and
# globals are the three the determinism rule forbids; storage and the network
# are here because a generator that can read the page is not deterministic.
FORBIDDEN = (
    "Math.random", "Date.now", "new Date", "performance.now",
    "localStorage", "sessionStorage", "fetch(", "XMLHttpRequest",
    "crypto.getRandomValues",
)


@pytest.fixture(scope="module")
def replay(tmp_path_factory):
    """Draw the whole sweep through the woven player, and compare it here.

    The comparison happens inside the fixture, while the harness output streams
    past, so the whole case file costs one line of memory rather than the
    result set - and so a mismatch is reported with the seed, the size, the
    floor kind and the stage it starts in, which is what a port needs.
    """
    if shutil.which("node") is None:
        pytest.skip("node not installed (npm ci); tests/browser/"
                    "test_floor_v3_parity.py is the normative path")
    home = tmp_path_factory.mktemp("floor-v3-parity")
    html = home / "p.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    case_file = cases.case_file()
    case_path = home / "cases.json"
    case_path.write_text(json.dumps(case_file), encoding="utf-8")
    out = home / "replay"
    run = subprocess.run(
        ["node", str(HARNESS), str(html), str(case_path), str(out)],
        capture_output=True, text=True, timeout=3600)
    meta_path = Path(str(out) + ".meta.json")
    assert meta_path.is_file(), (
        f"the harness wrote no meta file (exit {run.returncode}):\n"
        f"{run.stdout[-4000:]}\n{run.stderr[-4000:]}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert run.returncode == 0 and meta["hasApi"], (
        "the woven player carries no v3 twin: window.VEFR_DELVE.v3Attempt and "
        f".generateFloorV3 are missing (harness exit {run.returncode}):\n"
        f"{run.stderr[-4000:]}")

    index = cases.by_index()
    stages = _read_jsonl(Path(f"{out}.stages.jsonl"))
    return {
        "meta": meta,
        "records": stages,
        "stages": cases.compare_stages(stages, index),
        "full": cases.compare_full(_read_jsonl(Path(f"{out}.e2e.jsonl")), index),
        "reached": cases.reached(),
    }


def _read_jsonl(path: Path) -> list[dict]:
    """One record per line, read whole: the harness wrote them in order."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_the_twin_is_in_the_woven_player(replay):
    """The player is one file; the twin has to be in it, loaded and callable."""
    assert replay["meta"]["hasApi"] is True


def test_the_whole_sweep_was_replayed(replay):
    """Every case ran, both halves. A comparison of nothing is not a pass."""
    expected = cases.expected_case_count()
    assert replay["reached"]["cases"] == expected, (
        f"the spec reached {replay['reached']['cases']} cases and the sweep is "
        f"meant to be {expected}: the sweep, then the nonzero-cycle block")
    assert replay["stages"]["cases"] == expected, (
        f"the harness replayed {replay['stages']['cases']} of {expected} cases")
    assert replay["full"]["compared"] == expected, (
        f"the harness replayed {replay['full']['compared']} of {expected} floors "
        "end to end")
    for stage in cases.STAGES:
        assert replay["stages"]["compared"][stage] == replay["reached"][stage], (
            f"{replay['stages']['compared'][stage]} cases reached the {stage} "
            f"stage and the spec took {replay['reached'][stage]} there")


def test_the_cycle_segment_of_the_key_is_exercised(replay):
    """The parity sweep really does compare nonzero cycles, in both languages.

    `cycle` is a quarter of the floor key, so a sweep made only of cycle-0
    cases would pass against a twin that read the cycle as 0, dropped it, or
    formatted it differently - every case would still agree. This holds that
    the file carries nonzero-cycle cases at all four sizes, both stamp
    settings, that the harness replayed them, and that each one was compared
    stage by stage and end to end rather than skipped.
    """
    by_cycle: dict[int, list[dict]] = {}
    for case in cases.case_file()["cases"]:
        by_cycle.setdefault(case["cycle"], []).append(case)
    nonzero = sorted(c for c in by_cycle if c != 0)
    assert nonzero, "the case file carries no nonzero-cycle case at all"
    assert nonzero == list(cases.CYCLES), (
        f"the case file carries cycles {nonzero}, the sweep defines "
        f"{list(cases.CYCLES)}")
    replayed = {got["i"] for got in replay["records"]}
    for cycle in nonzero:
        block = by_cycle[cycle]
        sizes = {case["size"] for case in block}
        assert sizes == {f"{w}x{h}" for w, h, _ in cases.SIZES}, (
            f"cycle {cycle} covers sizes {sorted(sizes)}, not all four")
        assert {case["stamped"] for case in block} == {False, True}, (
            f"cycle {cycle} does not cover both the plain and stamped halves")
        missing = [case["i"] for case in block if case["i"] not in replayed]
        assert not missing, (
            f"cycle {cycle}: {len(missing)} of {len(block)} cases were not "
            f"replayed by the harness, first {missing[:5]}")
    # And the comparison itself: a nonzero-cycle case has to have been
    # compared at the plan stage, or the block exists and proves nothing.
    compared = replay["stages"]["compared"]["plan"]
    assert compared == replay["reached"]["cases"], (
        f"{compared} cases reached the plan stage and the spec took "
        f"{replay['reached']['cases']} there, so a case was never compared")


def test_a_nonzero_cycle_moves_the_floor():
    """The same seed at another cycle is another floor, on the spec side.

    The half of the key a cycle-0 sweep cannot show: hold the seed, the size,
    the kind and the depth, and change only the cycle. A generator that built
    `run_seed/section.id/k` and left the cycle out would draw the same floor
    for every cycle, and this is what catches it.
    """
    same = []
    for w, h, rooms in cases.SIZES:
        for kind in cases.CYCLE_KINDS:
            pack = cases.section(kind, rooms)
            zero = delve_v3.generate_floor_v3(
                "sweep-0", (w, h), copy.deepcopy(pack), kind,
                None, cases.STAMP_DEPTH, cycle=0)
            for cycle in cases.CYCLES:
                other = delve_v3.generate_floor_v3(
                    "sweep-0", (w, h), copy.deepcopy(pack), kind,
                    None, cases.STAMP_DEPTH, cycle=cycle)
                if json.dumps(zero, sort_keys=True) == json.dumps(other, sort_keys=True):
                    same.append(f"{w}x{h} {kind} cycle={cycle}")
    assert not same, (
        "the cycle is not reaching the floor key: cycle 0 and a nonzero "
        f"cycle drew the same floor at {', '.join(same[:5])}")


def test_every_stage_matches(replay):
    """200 seeds x every size x every floor kind, stage by stage."""
    problems = replay["stages"]["mismatches"]
    assert not problems, (
        f"{len(problems)} stage mismatches (first {cases.REPORTED} shown):\n"
        + cases.as_lines(problems))


def test_every_floor_matches_end_to_end(replay):
    """`generateFloorV3` and `generate_floor_v3` return the same floor."""
    problems = replay["full"]["gen_mismatches"] + replay["full"]["floor_mismatches"]
    assert not problems, (
        f"{len(problems)} end-to-end mismatches:\n" + cases.as_lines(problems))
    print(f"\nv3 parity: {replay['full']['compared']} floors end to end, "
          f"{replay['full']['fallbacks']} of them v2 fallbacks")


def test_the_twin_honours_the_determinism_rule(replay):
    """The rule of PLAN.md section 2, checked in the twin's own text.

    Three parts, and all three are mechanical: the constants the two languages
    share are one list of numbers, the three stream names are the floor key and
    a stage name, and the only float a twin may consume is
    `floor(rng() * n)` with `0 <= n < 2^31`.
    """
    assert replay["meta"]["constants"] == EXPECTED_CONSTANTS, (
        "the twin's constants are not the spec's: "
        + json.dumps({name: value for name, value
                      in replay["meta"]["constants"].items()
                      if EXPECTED_CONSTANTS.get(name) != value}, sort_keys=True))
    key = cases.floor_key("sweep-0", "normal")
    assert replay["meta"]["streams"] == {
        "plan": f"v3|{key}|plan",
        "layout": f"v3|{key}|layout",
        "pop": f"v3|{key}|pop",
    }
    text = TWIN_PART.read_text(encoding="utf-8")
    found = [word for word in FORBIDDEN if word in text]
    assert not found, f"the twin reaches for {found}"
    draws = [f"line {number}: {line.strip()}" for number, line
             in enumerate(text.splitlines(), 1)
             if "rng()" in line and not ALLOWED_DRAW.search(line)]
    assert not draws, "a draw is not floor(rng() * n):\n" + "\n".join(draws)


def test_generation_stays_inside_the_budget(replay):
    """PLAN.md section 3: generate + validate, p95 over the sweep, <= 40 ms.

    Measured here in node/jsdom, which is the same V8 the browser runs and is
    the path `tests/run.sh` links; `tests/browser/test_floor_v3_parity.py` is
    the normative measurement and adds the 4x phone proxy (150 ms).
    """
    perf = replay["meta"]["perf"]
    report = ", ".join(f"{label} p50 {cell['ms_p50']:.2f} ms / "
                       f"p95 {cell['ms_p95']:.2f} ms"
                       for label, cell in sorted(perf.items()))
    print(f"\nv3 twin budget (node/jsdom): {report}")
    assert perf, "the harness measured no generation time at all"
    # How many cases land in one size cell: the sweep's seeds at every floor
    # kind, plus the nonzero-cycle block's seeds at `CYCLE_KINDS`. Counted
    # from the case file's own labels rather than from a formula here, so this
    # assertion follows the sweep instead of restating it.
    per_label: dict[str, int] = {}
    for case in cases.case_file()["cases"]:
        label = case["size"] + ("-stamped" if case["stamped"] else "")
        per_label[label] = per_label.get(label, 0) + 1
    assert set(perf) == set(per_label), (
        f"the harness measured {sorted(perf)} and the case file has "
        f"{sorted(per_label)}")
    for label, cell in sorted(perf.items()):
        assert cell["seeds"] == per_label[label], (
            f"{label}: {cell['seeds']} samples, {per_label[label]} expected")
        if cell["ms_p95"] > cases.BUDGET_DESKTOP_MS:
            pytest.fail(
                f"{label}: generate + validate p95 is {cell['ms_p95']:.2f} ms over "
                f"{cell['seeds']} seeds, and the budget "
                f"is {cases.BUDGET_DESKTOP_MS:.0f} ms (PLAN.md section 3)")