"""`vefr stamp check` - the gate a stamp pack passes before a floor uses it.

ADR 0013's Validation section, in four parts:

- **static** - the reader's own rules, one sentence each, and this is
  the check that owns the sentence an author reads first.
- **fit** - a required-role room has to be a third of the small side of
  every Section that uses it, or it can never be placed and the author
  would only find out over a hundred silent sweeps.
- **sweep** - lay the pack's floors and count how often each stamp came
  out. Required roles have to be on every floor they are eligible for;
  optional ones may be rare on purpose and have no minimum (owner
  decision 4); the sweep only reports how often they place. A floor that
  fell back to v2 over a stamp carries the role that would not place in
  `stamp_defect`, and the sweep reports that too: a share says how often,
  the defect says why.
- **graph** - read a floor back and complain about a stamped room with
  no door in use, or with an anchor the hero cannot walk to.

Everything here measures the generator rather than reimplementing it:
the sweep asks `delve_v3` the same questions a floor asks, so a check
that passes means the floor works and not that a second copy of the
placer agrees with the first.

The report is one sentence per problem and a count at the end. A pack
with nothing wrong says so in a line, because a check that only speaks
when it is unhappy is a check nobody runs.
"""

from __future__ import annotations

from . import delve_v3
from . import stamps

# Re-exported so a caller that came here for the check has the reader in
# hand, and so `vefr stamp check` and a caller that wants one stamp's
# problems reach the same function.
__all__ = [
    "stamps",
    "REQUIRED_BAR",
    "FIT_SHARE",
    "SEED_PREFIX",
    "placement_sentence",
    "across_sentence",
    "rate_findings",
    "fit_findings",
    "section_findings",
    "graph_findings",
    "vault_reach_findings",
    "read_pack",
    "sweep",
    "report",
]

# The sweep's bar. A required role is on every floor it is eligible for or the
# check fails (ADR 0013, Validation). Optional rooms have no minimum: they may be
# rare on purpose (owner decision 4, confirmed by Rylee 2026-10-04); the sweep
# only reports how often they place.
REQUIRED_BAR = 100

# A required room has to be at most a third of the small side of the
# floor it lands on. Measured on width and height separately, not on
# area: a 15x20 room on a 64x48 floor is 3% of the area and never fits.
FIT_SHARE = stamps.FIT_SHARE

# The sweep's seeds are named, not numbered, so a report line can be
# pasted into `vefr craft delve --seed` and redrawn.
SEED_PREFIX = "check-"

# The three exit codes, the same numbers `vefr.cli` uses for every other
# command. Spelled out here rather than imported so the check can be run
# from a test, a script or the twin without pulling in the CLI.
OK = 0      # the pack holds up
ERROR = 1   # something is wrong with it, and the report says what
USAGE = 2   # there is no pack to check at all

# The tiles a hero cannot stand on. Every other glyph in a FloorPlan's
# `rows` is floor: v3 draws walls, floor, the two stairs and nothing
# else, and the things that live on the floor (chests, points of
# interest, the warden) are lists beside the grid, not glyphs in it.
_BLOCKING = frozenset({"#", " "})


# ------------------------------------------------------------- the sentences


def placement_sentence(who: str, placed: int, eligible: int, section: str,
                       width: int, min_width: int, bar: int) -> str:
    """The ADR's second example sentence, to the digit.

    `placed on 171 of 200 cellar floors (85%)` is the author's only
    handle on how rare a room became, and the rest of the line is the
    reason it is that rare: the room is 15 wide and cellar floors start
    at 64. The number in brackets is the truncated share, so it can read
    lower than the bar it actually met - 189 of 200 prints as 94 and
    meets 95, and an author who wants to know that sees both numbers.
    """
    share = placed * 100 // eligible if eligible > 0 else 0
    return stamps.sentence(
        who,
        f"placed on {placed} of {eligible} {section} floors ({share}%); "
        f"it needs {bar}%. It is {width} wide and {section} floors start "
        f"at {min_width}.",
        "/rows")


def across_sentence(who: str, placed: int, eligible: int, sections: list[str],
                    width: int, min_width: int, bar: int) -> str:
    """The same sentence for a room that is eligible in more than one Section.

    A rate over four Sections belongs to none of them, so naming the
    first one would be a sentence whose numbers and whose name disagree -
    worse than no sentence. This says "floors", names them all, and
    keeps the share, the bar and the reason. One Section is the ADR's own
    sentence, and comes back unchanged.
    """
    if len(sections) <= 1:
        return placement_sentence(who, placed, eligible,
                                  sections[0] if sections else "this pack's",
                                  width, min_width, bar)
    share = placed * 100 // eligible if eligible > 0 else 0
    named = ", ".join(sections[:-1])
    where = f"{named} and {sections[-1]}" if named else sections[-1]
    return stamps.sentence(
        who,
        f"placed on {placed} of {eligible} floors across {where} ({share}%); "
        f"it needs {bar}%. It is {width} wide and those floors start "
        f"at {min_width}.",
        "/rows")


def _meets(placed: int, eligible: int, bar: int) -> bool:
    """Whether `placed` of `eligible` floors clears a bar given in percent.

    100% is every floor and no rounding at all: one floor in a hundred
    that loses its warden hall is a floor the hero walks into an empty
    hall. Any other bar is read to the nearest whole percent, half up,
    which is how the bar is written - 95% means "nearly every floor",
    and 189 of 200 is 94.5%, which is nearly every floor. The rule is
    `(placed * 2 / eligible)` rounded, as integers, so the answer is the
    same in every language the check is twinned into.
    """
    if bar >= 100:
        return placed >= eligible
    return (placed * 200 + eligible) >= (2 * bar) * eligible


def rate_findings(stats: dict, records: dict) -> list[str]:
    """The sweep's share findings, one sentence per stamp under its bar.

    `stats` is what the sweep counted - `placed`, `eligible`, the
    Sections the stamp was eligible in, its width and the smallest of
    those Sections' widths. `records` is what the reader made, keyed the
    same way, and only its `role` is read: required roles must place on
    every eligible floor; optional roles have no minimum (owner decision 4).

    A stamp no Section can use is not measured. A rate over zero
    eligible floors is not a rate, and printing 0% for a room nobody
    asked for would be a complaint about the wrong thing.
    """
    found = []
    for name in sorted(stats):
        entry = stats.get(name) or {}
        eligible = int(entry.get("eligible", 0) or 0)
        if eligible <= 0:
            continue
        role = (records.get(name) or {}).get("role", "")
        if role not in stamps.REQUIRED_ROLES:
            continue   # owner decision 4: optional rooms may be rare on purpose; no minimum
        bar = REQUIRED_BAR
        if _meets(int(entry.get("placed", 0) or 0), eligible, bar):
            continue
        sections = list(entry.get("sections") or [])
        placed_n = int(entry.get("placed", 0) or 0)
        width = int(entry.get("width", 0) or 0)
        smallest = int(entry.get("min_width", 0) or 0)
        if len(sections) > 1:
            found.append(across_sentence(
                name, placed_n, eligible, sections, width, smallest, bar))
        else:
            found.append(placement_sentence(
                name, placed_n, eligible,
                sections[0] if sections else "this pack's",
                width, smallest, bar))
    return found


# ------------------------------------------------------------------ the fit


def _smallest(size: dict) -> tuple[int, int] | None:
    """The smallest floor a Section's `size` allows, or None.

    `{"w": [lo, hi], "h": [lo, hi]}` - the shape `delve_v3` reads - and
    `lo` is the floor that has to hold the room.
    """
    if not isinstance(size, dict):
        return None
    width, height = size.get("w"), size.get("h")
    for side in (width, height):
        if (not isinstance(side, (list, tuple)) or len(side) != 2
                or not all(isinstance(item, int) and not isinstance(item, bool)
                           for item in side)):
            return None
    return int(width[0]), int(height[0])


def section_findings(sections: list[dict]) -> list[str]:
    """Sections the sweep cannot lay a floor on.

    A Section that does not say how big its floors are has no smallest
    width to fit a room against and no floor to place one on, so the
    check says so rather than quietly sweeping nothing.
    """
    found = []
    for section in sections:
        section_id = str(section.get("id", "") or "") or "?"
        if _smallest(section.get("size")) is None:
            found.append(
                f"section {section_id}: no size, so its floors cannot be "
                f"swept; give it a size of "
                f"{{'w': [lo, hi], 'h': [lo, hi]}}. /size")
    return found


def fit_findings(records: dict, sections: list[dict]) -> list[str]:
    """The fit findings: a required room that no floor of a Section can hold.

    Only the required roles are measured. An optional stamp that is too
    big for a Section simply never comes up there, which is allowed;
    a warden hall that is too big is a Section that draws a floor with
    no warden hall in it.
    """
    found = []
    sizes = []
    for section in sections:
        section_id = str(section.get("id", "") or "")
        small = _smallest(section.get("size"))
        if small is not None:
            sizes.append((section_id, small[0], small[1]))
    for name in sorted(records):
        record = records.get(name) or {}
        if record.get("role") not in stamps.REQUIRED_ROLES:
            continue
        rows = record.get("rows") or []
        if not rows:
            continue
        width, height = len(rows[0]), len(rows)
        for section_id, min_width, min_height in sizes:
            if width * FIT_SHARE <= min_width and height * FIT_SHARE <= min_height:
                continue
            found.append(stamps.sentence(
                name,
                f"{width} wide and {height} tall, but {section_id} floors "
                f"start at {min_width}x{min_height}, so a required room has "
                f"to be a third of the small side or smaller",
                "/rows"))
    return found


# ----------------------------------------------------------------- the graph


def _flood(rows: list[str], start, blocked=frozenset()) -> set:
    """Every tile a walk from `start` reaches, four steps at a time.

    `blocked` is the secret sockets when the caller is asking whether a
    route can be walked without opening one; the default is nothing
    blocked, which is the plain "can the hero get there" question.
    """
    height, width = len(rows), len(rows[0]) if rows else 0
    if not isinstance(start, (list, tuple)) or len(start) != 2:
        return set()
    here = (int(start[0]), int(start[1]))
    if not (0 <= here[0] < width and 0 <= here[1] < height):
        return set()
    if rows[here[1]][here[0]] in _BLOCKING or here in blocked:
        return set()
    seen = {here}
    queue = [here]
    while queue:
        x, y = queue.pop()
        for step in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + step[0], y + step[1])
            if nxt in seen or nxt in blocked:
                continue
            if not (0 <= nxt[0] < width and 0 <= nxt[1] < height):
                continue
            if rows[nxt[1]][nxt[0]] in _BLOCKING:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def graph_findings(plan: dict) -> list[str]:
    """What is wrong with a floor's stamped rooms, read back off the grid.

    Three questions, in the ADR's order:

    1. does every placed room have a socket the corridor came in
       through, and
    2. is every anchor of a stamped room walkable from `up` at all, and
    3. for a `warden` and for the vault, is it walkable from `up`
       *without opening a secret* (ADR 0013, Graph). Everywhere else a
       secret counts as passable: a chest in an ordinary room may sit
       past another room's secret, and finding the wall is the reward.
       The warden and the vault door are the two things the floor owes
       the hero, so every secret on the floor is closed to their walk.
       A room whose own used socket was a secret is exempt altogether -
       that room is behind a wall by the author's own drawing, and
       holding its anchors to the rule would report every secret room
       on every floor it appeared in.

    A floor with no stamped rooms says nothing, because most floors have
    none and a check that complained about them would always fail.
    """
    placements = plan.get("stamps") or []
    if not placements:
        return []
    rows = plan.get("rows") or []
    if not rows:
        return []
    anchors = plan.get("anchors") or {}
    secrets = {tuple(spot) for spot in (plan.get("secrets") or [])
               if isinstance(spot, (list, tuple)) and len(spot) == 2}
    up = anchors.get("up")
    # Secrets count as passable for the plain question and as walls for
    # the one the ADR puts a rule on (the warden and the vault door), so
    # both walks start from the same up-stair and differ only in what
    # they may step on.
    open_tiles = _flood(rows, up)
    honest_tiles = _flood(rows, up, secrets)
    found = []
    for index, placement in enumerate(placements):
        if not isinstance(placement, dict):
            continue
        who = str(placement.get("id", "") or "?")
        at = placement.get("at") or [0, 0]
        if not placement.get("socket"):
            found.append(stamps.sentence(
                who,
                f"placed at {at[0]},{at[1]} with no door in use, so nothing "
                f"can reach it",
                f"/stamps/{index}/socket"))
        owed = "secret" not in placement
        vault = placement.get("role") == "vault"
        for name in sorted(placement.get("anchors") or {}):
            tile = tuple(placement["anchors"][name])
            if tile not in open_tiles:
                found.append(stamps.sentence(
                    who,
                    f"its {name} at {tile[0]},{tile[1]} cannot be reached "
                    f"from up at all",
                    f"/stamps/{index}/anchors/{name}"))
            elif owed and (name == "warden" or vault) and tile not in honest_tiles:
                found.append(stamps.sentence(
                    who,
                    f"its {name} at {tile[0]},{tile[1]} cannot be reached "
                    f"from up without opening a secret",
                    f"/stamps/{index}/anchors/{name}"))
    for name in ("down", "warden", "vault", "landmark"):
        tile = anchors.get(name)
        if tile is None:
            continue
        spot = tuple(tile)
        if spot not in open_tiles:
            found.append(stamps.sentence(
                "floor",
                f"the {name} at {spot[0]},{spot[1]} cannot be reached from up",
                f"/anchors/{name}"))
    return found


def vault_reach_findings(plan: dict, section_id: str) -> list[str]:
    """Check 2 (ADR 0015): the vault's note, chest and home, walked from its door.

    The walk starts at the vault door, the socket the corridor came in by,
    and closes the secret sockets exactly as check 1 does. A vault has no
    secret socket of its own, so the door is never one.
    """
    rows = plan.get("rows") or []
    secrets = {tuple(spot) for spot in (plan.get("secrets") or [])
               if isinstance(spot, (list, tuple)) and len(spot) == 2}
    found = []
    for index, placement in enumerate(plan.get("stamps") or []):
        if not isinstance(placement, dict) or placement.get("role") != "vault":
            continue
        door = placement.get("socket")
        honest_tiles = _flood(rows, door, secrets)
        open_tiles = _flood(rows, door)
        anchors = placement.get("anchors") or {}
        for name in ("note", "chest", "home"):
            tile = tuple(anchors[name])
            if tile in honest_tiles:
                continue
            if tile in open_tiles:
                how = "can only be reached from the vault door by opening a secret"
            else:
                how = "cannot be reached from the vault door at all"
            found.append(
                f"section {section_id}: its {name} at {tile[0]},{tile[1]} {how} "
                f"/stamps/{index}/anchors/{name}")
    return found


# ------------------------------------------------------------------- a sweep


def read_pack(directory) -> tuple[list[dict], list[dict], list[str]]:
    """A pack's `stamps/` and `sections/`, and what is wrong with them.

    The stamps come back as the records `delve_v3` places, in sorted id
    order; the Sections as the dicts they are on disk. A stamp that
    cannot be read is reported and left out - the sweep lays floors
    with the stamps that are sound rather than refusing to sweep at all,
    because a pack with one broken room in it is exactly the pack whose
    other rooms need checking.
    """
    from pathlib import Path

    root = Path(directory)
    stamp_dir = root / "stamps"
    section_dir = root / "sections"
    if not stamp_dir.is_dir():
        return [], [], [f"no stamps directory in {root} (ADR 0013 puts one "
                        f"stamp per file in stamps/<id>.json)"]
    if not section_dir.is_dir():
        return [], [], [f"no sections directory in {root}"]

    found = []
    records = []
    for path in sorted(stamp_dir.glob("*.json")):
        name = path.stem
        try:
            source = stamps.read(path)
        except stamps.StampError as err:
            found.append(str(err))
            continue
        if isinstance(source, dict) and source.get("id") not in (None, "", name):
            found.append(stamps.sentence(
                str(source.get("id")),
                f"the file is named {name}, and the id and the file name are "
                f"the same name or the Section content hash misses the edit",
                "/id"))
            continue
        problems = stamps.problems(source, name)
        if problems:
            found.extend(problems)
            continue
        records.append(stamps.read_v1(source, name=name))
    records.sort(key=lambda record: record["id"])

    sections = []
    for path in sorted(section_dir.glob("*.json")):
        try:
            section = stamps.read(path)
        except stamps.StampError as err:
            found.append(str(err))
            continue
        if isinstance(section, dict):
            sections.append(section)
    sections.sort(key=lambda section: str(section.get("id", "") or ""))
    return records, sections, found


def sweep(records: list[dict], sections: list[dict], seeds: int
          ) -> tuple[dict, list[str], int]:
    """Lay the pack's floors and count what each stamp did on them.

    Seed `check-<n>`, every Section, every `k` the Section has floors
    for, and every floor kind - the ADR's sweep. The floor is drawn at
    the Section's *smallest* size, because that is the floor a room has
    to fit on and the one the fit rule is measured against; a stamp that
    places on 48x32 and not on 80x56 is a stamp that will not place at
    all.

    Returns the per-stamp stats, the graph findings, and how many floors
    were laid. A floor that came back as v2 is not a floor: it is
    counted in the stats as eligible and not placed, which is what makes
    a room that cannot place show up as the 0% it is - and the floor
    carries `stamp_defect` naming the role that would not place, so the
    sweep reports that too (ADR 0013, Placement 4). A share on its own
    says how often; the defect says why.
    """
    stats: dict[str, dict] = {}
    for record in records:
        rows = record.get("rows") or [""]
        stats[record["id"]] = {
            "role": record["role"],
            "width": len(rows[0]),
            "placed": 0,
            "eligible": 0,
            "sections": [],
            "min_width": 0,
        }
    findings: list[str] = []
    swept: dict[str, int] = {}
    defects: dict[tuple[str, str], int] = {}
    laid = 0
    for number in range(max(0, int(seeds))):
        seed = f"{SEED_PREFIX}{number}"
        for section in sections:
            small = _smallest(section.get("size"))
            if small is None:
                continue
            section_id = str(section.get("id", "") or "")
            floors = section.get("floors")
            depths = range(1, int(floors) + 1) \
                if isinstance(floors, int) and not isinstance(floors, bool) and floors > 0 \
                else range(1, 2)
            for depth in depths:
                eligible = delve_v3.stamp_pool(section, records, depth)
                if not eligible:
                    continue
                for kind in delve_v3.FLOOR_KINDS:
                    trace: dict = {}
                    plan = delve_v3.generate_floor_v3(
                        seed, small, section, kind, records, depth, trace=trace)
                    laid += 1
                    swept[section_id] = swept.get(section_id, 0) + 1
                    defect = str(plan.get("stamp_defect") or "")
                    if defect:
                        # A v2 floor that fell back over a stamp, counted by
                        # the role it names: one sentence for the hundred
                        # floors that all fell back the same way.
                        key = (section_id, defect)
                        defects[key] = defects.get(key, 0) + 1
                    # ADR 0013's eligibility is three things, and the
                    # third is "its role is wanted on the floor": a floor
                    # that drew no secret has no slot for a secret room,
                    # and charging that room for a floor it was never
                    # wanted on is a rate about the wrong thing.
                    wanted = trace.get("slots") or set(stamps.ORDER)
                    placed = {entry.get("id") for entry in plan.get("stamps") or []}
                    for record in eligible:
                        name = record["id"]
                        if record["role"] not in wanted:
                            continue
                        entry = stats[name]
                        entry["eligible"] += 1
                        if name in placed:
                            entry["placed"] += 1
                        if section_id not in entry["sections"]:
                            entry["sections"].append(section_id)
                        if not entry["min_width"] or small[0] < entry["min_width"]:
                            entry["min_width"] = small[0]
                    for line in graph_findings(plan) + vault_reach_findings(plan, section_id):
                        if line not in findings:
                            findings.append(line)
    # The defects lead: they are the cause of the share findings the
    # report prints after them, and a rate with no cause behind it is the
    # complaint an author cannot act on.
    findings[:0] = [
        stamps.sentence(
            defect.split(":", 1)[-1] or defect,
            f"did not place on {count} of {swept.get(section_id, count)} "
            f"{section_id} floors the sweep laid, so each of them fell back "
            f"to v2 and carries no stamped room at all",
            "/stamp_defect")
        for (section_id, defect), count in sorted(defects.items())
    ]
    return stats, findings, laid


# -------------------------------------------------------------------- a run


def _plural(count: int, word: str) -> str:
    """`1 seed` and `2 seeds`, so a report never says "1 seeds"."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


# The two sentences that are a usage error rather than a stamp problem:
# there is no pack to check at all, so the sweep is not run and the
# command's own exit code says so.
_USAGE = ("no stamps directory", "no sections directory")


def report(pack: str, seeds: int = 200) -> tuple[int, list[str]]:
    """Check a pack; return the exit code and the lines to print.

    The lines are in the order the problems were found, because that is
    the order an author can fix them in: the reader's refusals first
    (nothing else means anything until the pack parses), then the
    Sections that cannot be swept, then the fit, then the sweep's
    shares, then the floors read back. A pack with nothing wrong says so
    in a line, because a check that only speaks when it is unhappy is a
    check nobody runs.
    """
    seeds = max(0, int(seeds))
    records, sections, found = read_pack(pack)
    problems: list[str] = []
    laid = 0
    if any(line.startswith(_USAGE) for line in found):
        problems.extend(found)
    else:
        problems.extend(found)
        problems.extend(section_findings(sections))
        problems.extend(fit_findings(
            {record["id"]: record for record in records}, sections))
        stats, graph, laid = sweep(records, sections, seeds)
        # The sweep's stats carry each stamp's role, which is all the
        # rate check reads out of the records.
        problems.extend(rate_findings(stats, stats))
        for line in graph:
            if line not in problems:
                problems.append(line)

    header = (f"stamp check: {pack} - "
              f"{_plural(len(records), 'stamp')}, "
              f"{_plural(len(sections), 'section')}, "
              f"{_plural(seeds, 'seed')}, "
              f"{_plural(laid, 'floor')} swept")
    if any(line.startswith(_USAGE) for line in problems):
        code = USAGE
    else:
        code = ERROR if problems else OK
    return code, [header, *problems, _plural(len(problems), "problem")]
