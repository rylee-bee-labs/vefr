"""The cases the delve v3 parity test replays, and the Python side of them.

Shared by `tests/test_floor_v3_parity.py` (the node/jsdom path `tests/run.sh`
links) and `tests/browser/test_floor_v3_parity.py` (the normative Chromium
measurement), so the two paths replay exactly the same floors and compare
exactly the same strings.

Three things live here:

1. **The sweep.** 200 seeds x every size of PLAN.md section 3 x every floor
   kind, which is the cell count PLAN.md section 2 names for the parity test,
   plus a stamped half at the two smallest sizes (E5b's JS half - the spec can
   place stamped rooms and the twin has to place the same one).
2. **The Python reference**, `staged()`: one attempt of one floor key, kept at
   its stage boundaries. It is `delve_v3._attempt` line for line with the
   stage outputs kept instead of thrown away, so the harness can compare
   plan, then layout, then graph, then pop, and a mismatch names the stage it
   starts in rather than only saying the floor differs.
3. **The canonical form**, `canonical()`: `json.dumps` with sorted keys and no
   whitespace on this side, and `tests/fixtures/floor_plan_canon.mjs` on the
   other. Every value in a FloorPlan is an ASCII key, a whole number, a
   boolean, null, or a string of ASCII glyphs, so the two serialisations are
   byte-identical for equal values - which is what makes "the same bytes after
   canonicalisation" a comparison and not a hope.
"""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from vefr import delve_v3, stamps

ROOT = Path(__file__).resolve().parents[1]

# The four sizes of PLAN.md section 3, with the room quota each one carries.
# The twin of this list lives in tests/test_floor_v3_properties.py and in
# tests/browser/bench_floor_play.py; change all three together.
SIZES = [(48, 32, 16), (64, 48, 18), (96, 64, 24), (128, 96, 32)]

FLOOR_KINDS = ("normal", "treasure", "infested", "hub")

# PLAN.md section 2's cell count: 200 seeds.
SEED_COUNT = 200
SEEDS = tuple(f"sweep-{i}" for i in range(SEED_COUNT))

# The stamped half of the sweep. Stamps are placed at all four sizes by the
# spec, but the stamped parity runs at the two smallest ones: it is here to
# prove the twin places the same stamped room (E5b's JS half), and the two
# small sizes are where placement is hardest - a stamp that does not fit, or a
# corridor that cannot reach one, shows there first.
STAMP_SIZES = SIZES[:2]
STAMP_TAGS = ["cellar", "any"]
# `k`, the floor's 1-based position in its Section; inside every fixture
# stamp's own depth range.
STAMP_DEPTH = 3

# The descent cycle the sweep belongs to, the 0 of PLAN.md section 2's
# `run_seed/section.id/cycle/k`. The sweep is one story, so it is 0 here.
CYCLE = 0

# The nonzero cycles. `cycle` is a quarter of the floor key, so a sweep that
# only ever drew cycle 0 never showed that quarter: a twin that dropped it, or
# read it as 0, or formatted it differently, would have matched every other
# case in the file and broken only after the first endless descent. These
# cases are drawn by BOTH languages - the spec here, the twin in the harness
# and in Chromium - so the segment is compared rather than assumed.
#
# A small block, not a second sweep: the cycle is a string in a key, so what
# has to be proved is that it reaches the streams on both sides, and a few
# seeds at every size and both stamp settings do that.
CYCLE_SEED_COUNT = 8
CYCLE_SEEDS = SEEDS[:CYCLE_SEED_COUNT]
CYCLE_KINDS = ("normal", "hub")
CYCLES = (1, 2)

STAMP_FIXTURES = Path(__file__).parent / "fixtures" / "stamps"

# The budget of PLAN.md section 3, per size cell: generate + validate, p95 over
# the sweep. The desktop figure is the gate; the Chromium test in
# tests/browser/ is the normative measurement and adds the phone proxy.
BUDGET_DESKTOP_MS = 40.0


def section(kind: str, rooms: int, with_stamps: bool = False) -> dict:
    """A valid Section pack for one floor kind and one size's room quota.

    The same pack `tests/test_floor_v3_properties.py` builds, so the parity
    sweep and the property sweep measure the same floors: a floor that passes
    parity but fails a property is a parity harness that compared the wrong
    thing. Only `id`, `rooms`, `families`, `elites`, `groups`, `pois`, `stamps`
    and `vault` are read by the generator; the rest is here because a real
    pack carries it.
    """
    pack = {
        "section": 1,
        "id": f"cellar-{kind}",
        "rooms": [rooms, rooms],
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
    if with_stamps:
        pack["stamps"] = list(STAMP_TAGS)
    return pack


@lru_cache(maxsize=None)
def stamp_pack() -> tuple:
    """The fixture stamps, read by the real reader, in sorted id order."""
    return tuple(stamps.load(STAMP_FIXTURES))


@lru_cache(maxsize=None)
def _pack(kind: str, rooms: int, with_stamps: bool) -> dict:
    return section(kind, rooms, with_stamps)


@lru_cache(maxsize=None)
def _records(with_stamps: bool) -> tuple:
    return stamp_pack() if with_stamps else ()


def floor_key(seed: str, kind: str, cycle: int = CYCLE) -> str:
    """The floor key the spec builds: `run_seed/section.id/cycle/k`."""
    return f"{seed}/{_pack(kind, 12, False)['id']}/{cycle}/{STAMP_DEPTH}"


def canonical(value) -> str:
    """The comparison form: sorted keys, no whitespace, ASCII-escaped.

    `json.dumps` here and `canon` in `tests/fixtures/floor_plan_canon.mjs`
    produce the same bytes for equal values, because every key is ASCII and
    every number in a FloorPlan is a whole number Python and JavaScript both
    print the same way.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


# Bounded, not unbounded: the sweep is ~4800 floors and every one of them
# keeps its rows, so an unbounded cache would hold a few hundred megabytes of
# FloorPlan for the length of the session. A small cache still collapses the
# three passes over the sweep (the stage comparison, the end-to-end one and
# `reached`) into a handful of generations each.
@lru_cache(maxsize=256)
def staged(seed: str, width: int, height: int, kind: str,
           with_stamps: bool = False, pinned: bool = False,
           cycle: int = CYCLE) -> dict:
    """One attempt of one floor key, with every stage kept.

    `delve_v3._attempt` line for line, with the stage outputs kept instead of
    thrown away, so the harness can compare plan -> layout -> graph -> pop in
    that order. `failed` is `_attempt`'s own second element, verbatim: "" for a
    floor that came through and for one that gave up for an ordinary reason,
    and "stamp:<role>" for a required stamp that would not place, which is the
    one defect the spec reports and the one ADR 0013 asks a caller to hear
    about. Where an attempt stopped is read from the stage it did not reach
    (`graph`, `pop` and `floor` are None), not from that string.
    """
    pack = copy.deepcopy(_pack(kind, _quota(width), with_stamps))
    records = list(_records(with_stamps))
    key = f"{seed}/{pack['id']}/{cycle}/{STAMP_DEPTH}"

    plan = delve_v3._plan_stage(delve_v3.prng(f"v3|{key}|plan"), pack, kind)
    canvas = delve_v3.Canvas(width, height)
    pool = delve_v3._stamp_pool(pack, records, STAMP_DEPTH)
    spine, missing = delve_v3._layout_stage(
        delve_v3.prng(f"v3|{key}|layout"), canvas, plan, pool, pinned)

    out = {
        "plan": plan,
        "layout": {
            "rows": canvas.rows(),
            "rooms": [list(room) for room in canvas.rooms],
            "stamps": canvas.stamps,
            "spine": list(spine),
            "missing": list(missing),
        },
        "graph": None,
        "pop": None,
        "floor": None,
        "failed": "",
    }
    if len(spine) < 2 or missing:
        out["failed"] = f"stamp:{missing[0]}" if missing else ""
        return out

    graph, anchors, pois, secrets = delve_v3._graph_stage(canvas, spine, plan, pack)
    out["graph"] = {
        "anchors": anchors,
        "pois": pois,
        "secrets": secrets,
        "main": list(graph.main),
        "mainRooms": list(graph.main_rooms),
        "depth": list(graph.depth),
        "roomAdj": [sorted(n) for n in graph.room_adj],
        "adj": [sorted(n) for n in graph.adj],
    }
    if graph.room_count < delve_v3.ROOMS_FLOOR:
        return out

    up = (anchors["up"][0], anchors["up"][1])
    down = (anchors["down"][0], anchors["down"][1])
    spawns, chests = delve_v3._pop_stage(
        delve_v3.prng(f"v3|{key}|pop"), canvas, graph, plan, pack,
        up, down, secrets, key, STAMP_DEPTH)

    floor = {
        "gen": 3,
        "w": width,
        "h": height,
        "rows": canvas.rows(),
        "rooms": [list(room) for room in canvas.rooms],
        "anchors": anchors,
        "pois": pois,
        "secrets": secrets,
        "spawns": spawns,
        "chests": chests,
        "waypoint": plan["waypoint"],
    }
    if canvas.stamps:
        floor["stamps"] = canvas.stamps
    out["pop"] = {"spawns": spawns, "chests": chests}
    out["floor"] = floor
    # `_attempt` refuses a floor the checks reject and the ladder draws that
    # floor key again under `|try{n}`, so the twin has to refuse the same one.
    if not delve_v3._validate(floor, canvas, graph, pack):
        out["floor"] = None
    return out


@lru_cache(maxsize=256)
def end_to_end(seed: str, width: int, height: int, kind: str,
               with_stamps: bool = False, cycle: int = CYCLE) -> dict:
    """`generate_floor_v3` itself: the retry ladder and the v2 fallback."""
    return delve_v3.generate_floor_v3(
        seed, (width, height),
        copy.deepcopy(_pack(kind, _quota(width), with_stamps)),
        kind, list(_records(with_stamps)) or None, STAMP_DEPTH, cycle=cycle)


def _quota(width: int) -> int:
    """The room quota a size carries, so a case can name its Section pack."""
    for w, _h, rooms in SIZES:
        if w == width:
            return rooms
    raise ValueError(f"no size in SIZES is {width} wide")


def pack_key(kind: str, width: int, with_stamps: bool) -> str:
    """The name a Section pack is filed under in the cases file."""
    return f"{kind}|{width}|{int(with_stamps)}"


def case_file() -> dict:
    """The whole sweep as the harness reads it: the packs, then the cases.

    One file for both halves of the sweep, so the plain and the stamped cases
    run in one process and are compared against the same packs. Every Section
    pack the twin sees is a pack this module built - there is no second copy of
    the sweep data on the JavaScript side to drift from.
    """
    cases: list[dict] = []
    packs: dict[str, dict] = {}

    def add(seed: str, width: int, height: int, kind: str,
            with_stamps: bool, cycle: int) -> None:
        key = pack_key(kind, width, with_stamps)
        packs[key] = section(kind, _quota(width), with_stamps)
        cases.append({
            "i": len(cases),
            "seed": seed,
            "w": width,
            "h": height,
            "kind": kind,
            "size": f"{width}x{height}",
            "stamped": with_stamps,
            "pack": key,
            "cycle": cycle,
        })

    for with_stamps, sizes in ((False, SIZES), (True, STAMP_SIZES)):
        for width, height, _rooms in sizes:
            for kind in FLOOR_KINDS:
                for seed in SEEDS:
                    add(seed, width, height, kind, with_stamps, CYCLE)
    # The nonzero-cycle block: the same sizes and the same seeds as the sweep,
    # at every size and both stamp settings, so `cycle` reaches the streams in
    # both languages rather than only ever being 0.
    for cycle in CYCLES:
        for with_stamps, sizes in ((False, SIZES), (True, STAMP_SIZES)):
            for width, height, _rooms in sizes:
                for kind in CYCLE_KINDS:
                    for seed in CYCLE_SEEDS:
                        add(seed, width, height, kind, with_stamps, cycle)
    return {
        "packs": packs,
        "stamps": [dict(record) for record in stamp_pack()],
        "depth": STAMP_DEPTH,
        "cycle": CYCLE,
        "cases": cases,
    }


def expected_case_count() -> int:
    """How many cases `case_file` is supposed to build, worked out here.

    Written as arithmetic rather than read back off the file, so a case that
    quietly stops being added is a failing count and not a smaller sweep that
    nobody notices: the sweep, then the nonzero-cycle block.
    """
    sizes = len(SIZES) + len(STAMP_SIZES)
    sweep = SEED_COUNT * sizes * len(FLOOR_KINDS)
    cycles = len(CYCLES) * CYCLE_SEED_COUNT * len(CYCLE_KINDS) * sizes
    return sweep + cycles


def expected_stages(case: dict) -> dict[str, str]:
    """What the twin has to return for one case, stage by stage."""
    got = staged(case["seed"], case["w"], case["h"], case["kind"],
                 case["stamped"], cycle=case["cycle"])
    return {
        "plan": canonical(got["plan"]),
        "layout": canonical(got["layout"]),
        "graph": "" if got["graph"] is None else canonical(got["graph"]),
        "pop": "" if got["pop"] is None else canonical(got["pop"]),
        "floor": "" if got["floor"] is None else canonical(got["floor"]),
        "failed": got["failed"],
    }


def where(case: dict) -> str:
    """The `(seed, size, kind, stamps, cycle)` stamp every failure carries.

    The cycle is in it because the nonzero-cycle cases are otherwise
    indistinguishable from the sweep cases they sit next to: a mismatch at
    `seed=sweep-0 size=48x32 kind=normal cycle=0` says one floor and nothing
    about the cycle.
    """
    stamp = " stamped" if case["stamped"] else ""
    return (f"seed={case['seed']} size={case['size']} kind={case['kind']}"
            f"{stamp} cycle={case['cycle']}")


def first_difference(want: str, got: str) -> str:
    """Where two canonical strings part company, in one plain sentence.

    The two canonical forms are the same length for the same value, so the
    first index that differs names the field: the tail around it is quoted so
    the message says which room, which spawn or which row moved.
    """
    for index, (a, b) in enumerate(zip(want, got)):
        if a != b:
            lo = max(0, index - 60)
            return (f"at character {index}: python {want[lo:index + 60]!r} "
                    f"vs twin {got[lo:index + 60]!r}")
    return (f"python is {len(want)} characters and the twin is {len(got)}; "
            f"python ends {want[-80:]!r}, the twin ends {got[-80:]!r}")

# ------------------------------------------------------------- the comparison
# Shared by both parity paths, so the node/jsdom harness and the Chromium test
# fail in the same words when the twin draws something else.

# How many mismatches are quoted before the list is cut. One is enough to fix
# a port; twenty is enough to see whether a stage is wrong in one place or
# everywhere.
REPORTED = 20

STAGES = ("plan", "layout", "graph", "pop", "floor")


def _note(bucket: list, message: str) -> None:
    if len(bucket) < REPORTED:
        bucket.append(message)


def compare_stages(records: list[dict], by_index: dict[int, dict]) -> dict:
    """Compare one harness record per case, stage by stage, against the spec.

    A stage the spec never reached on this case is not compared - it is
    compared by `compare_full` instead, where the retry ladder has drawn the
    floor again - but the count of what WAS compared comes back, so a run that
    compared almost nothing cannot pass.
    """
    compared = {stage: 0 for stage in STAGES}
    mismatches: list[str] = []
    seen = 0
    for got in records:
        case = by_index[got["i"]]
        seen += 1
        want = expected_stages(case)
        for stage in STAGES:
            if not got.get(stage):
                continue
            compared[stage] += 1
            if got[stage] != want[stage]:
                _note(mismatches, f"{where(case)} stage={stage}: "
                                  f"{first_difference(want[stage], got[stage])}")
        if got.get("failed") != want["failed"]:
            _note(mismatches, f"{where(case)} stage=failed: the twin reported "
                              f"{got.get('failed')!r} and the spec reported "
                              f"{want['failed']!r}")
    return {"cases": seen, "compared": compared, "mismatches": mismatches}


def compare_full(records: list[dict], by_index: dict[int, dict]) -> dict:
    """Compare the public floor of every case, retry ladder included.

    The harness sends the whole floor only where the stage comparison could
    not already have covered it: a v2 fallback, or a floor whose first attempt
    gave up and the ladder then drew. Everything else is covered by its `gen`
    and by the stage comparison; a floor the ladder redrew is the ladder's
    whole job and is compared here in full.
    """
    compared = 0
    gen_mismatches: list[str] = []
    floor_mismatches: list[str] = []
    fallbacks = 0
    for got in records:
        case = by_index[got["i"]]
        compared += 1
        want = end_to_end(case["seed"], case["w"], case["h"], case["kind"],
                          case["stamped"], cycle=case["cycle"])
        if got["gen"] != want["gen"]:
            _note(gen_mismatches, f"{where(case)}: the twin returned gen "
                                 f"{got['gen']} and the spec returned gen "
                                 f"{want['gen']}")
            continue
        if want["gen"] != 3:
            fallbacks += 1
        if not got.get("floor"):
            continue
        text = canonical(want)
        if got["floor"] != text:
            _note(floor_mismatches, f"{where(case)} public floor: "
                                    f"{first_difference(text, got['floor'])}")
    return {"compared": compared, "gen_mismatches": gen_mismatches,
            "floor_mismatches": floor_mismatches, "fallbacks": fallbacks}


def reached() -> dict:
    """How far each stage gets on the SPEC side, case by case.

    A floor whose first attempt gave up - a required stamp that would not
    place, a layout that could not be laid out - stops at the stage where it
    stopped, and the ladder draws it again under `|try{n}`. So the count the
    twin is held to is measured here, against the spec, and not against a
    number the twin chose.
    """
    file = case_file()
    counts = {"cases": len(file["cases"])}
    for stage in STAGES:
        counts[stage] = 0
    for case in file["cases"]:
        got = staged(case["seed"], case["w"], case["h"], case["kind"],
                     case["stamped"], cycle=case["cycle"])
        counts["plan"] += 1
        counts["layout"] += 1
        if got["graph"] is not None:
            counts["graph"] += 1
        if got["pop"] is not None:
            counts["pop"] += 1
        if got["floor"] is not None:
            counts["floor"] += 1
    return counts


def by_index() -> dict[int, dict]:
    """The cases of `case_file`, by index, for the reader on either path."""
    return {case["i"]: case for case in case_file()["cases"]}


def as_lines(problems: list[str]) -> str:
    """The mismatch list as a failure message, cut at `REPORTED`."""
    return "\n".join(problems)
