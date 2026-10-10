"""Can this pack be finished? Follow the locks from the start region.

`findings(pack_dir)` returns plain sentences naming a lock whose key
cannot be reached before it; an empty list means every item-locked door
can be opened with a key the hero can obtain first. A pack with no
`requires` at all produces no findings.

`section_findings(pack_dir, seeds)` is the second half, and it came with
the Sections (E4, PLAN.md section 5 row E4): the PLAN.md section 7
property proof run over Sections rather than over one floor kind. Every
Section in the pack is swept over `seeds` check seeds - every floor of
it, at the Section's own size, drawn from its own floor key - and each
floor has to hold: one component, every anchor, point of interest,
secret, monster and chest reachable from the up-stair, and a vault anchor
on a Section that names a vault. A floor that fell back to v2 geometry is
counted and reported as a rate, because a Section whose floors fall back
is a Section that validated green and then drew v2.

The model is the pack's own data, read through the loaders the rest of
the engine already uses: the acts tree (`maplab.load_pack`), the
Library's books (`library.load_library`), the item catalog, and the
Section packs (`vefr.sections`). A key can be obtained from an enemy's
`drops`, a book/chest's `drops` on the map, a shop's `stock`, or a rule
that `give`s it (rules are not regional). Reachability and obtainability
are grown to a fixpoint.

Flag locks (`requires: {"flag": ...}`) are out of scope: a rule may set
the flag, so they are treated as always open and never reported. No
model call, no write, no clock - this is a deterministic surface.

The third question, ADR 0015 checks 4 and 5, is `progress_findings`: a
flag-only walk over the Sections that asks whether a pack's story can
actually be finished. It runs inside `section_findings` - the same 200-seed
door `vefr check` opens onto the Sections - and reads the descent's own
Sections rather than the ones a sweep draws floors from, because a story
is a descent and a sweep is a floor.
"""

from __future__ import annotations

from pathlib import Path

from . import delve, delve_v3, library, sections, stamps
from .maplab import load_pack

# How many check seeds the Section sweep draws, and what it calls them. The
# same `check-<n>` names `vefr stamp check` sweeps, so a floor that fails
# here can be looked at with the tool that sweeps floors.
SECTION_SEEDS = 200
SECTION_SEED_PREFIX = 'check-'


def _item_ids(value) -> list[str]:
    """The item ids a `drops`/`stock` value names.

    An enemy `drops` is a list; a book's is a comma-separated string in
    its front matter. A shop `stock` may be either, or a mapping whose
    keys are the ids. Blank parts are skipped, first-seen order kept.
    """
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    elif isinstance(value, dict):
        parts = list(value)
    else:
        return []
    out: list[str] = []
    for part in parts:
        pid = str(part).strip()
        if pid and pid not in out:
            out.append(pid)
    return out


def _rule_gives(rules) -> set[str]:
    """Every item a rule `give`s. Rules are not regional, so these count
    as obtainable from the start."""
    given: set[str] = set()
    if not isinstance(rules, list):
        return given
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        effects = rule.get("then")
        if not isinstance(effects, list):
            continue
        for effect in effects:
            if not isinstance(effect, dict):
                continue
            item = effect.get("give")
            if isinstance(item, str) and item:
                given.add(item)
    return given


def _region_sources(acts, books) -> dict[str, set[str]]:
    """Every item obtainable by visiting a region: enemy drops, a
    book/chest's drops, and a shop's stock, keyed by region name."""
    sources: dict[str, set[str]] = {}

    def add(region, ids):
        if not region:
            return
        sources.setdefault(region, set()).update(i for i in ids if i)

    for act in acts:
        regions = act.get("regions")
        if not isinstance(regions, dict):
            continue
        names = list(regions)
        first = names[0] if names else None
        for name, rdata in regions.items():
            contract = (rdata or {}).get("contract") if isinstance(rdata, dict) else None
            contract = contract if isinstance(contract, dict) else {}
            for enemy in (contract.get("enemies") or []):
                if isinstance(enemy, dict):
                    add(name, _item_ids(enemy.get("drops")))
        speakers = act.get("speakers")
        if isinstance(speakers, dict):
            for speaker in speakers.values():
                if not isinstance(speaker, dict) or "shop" not in speaker:
                    continue
                region = speaker.get("region")
                if not isinstance(region, str) or not region:
                    region = first
                add(region, _item_ids(speaker.get("stock")))

    for book in books:
        if not isinstance(book, dict):
            continue
        extra = book.get("extra") if isinstance(book.get("extra"), dict) else {}
        region = book.get("region")
        if not isinstance(region, str) or not region:
            region = "town"
        add(region, _item_ids(extra.get("drops")))
    return sources


def _opens(requires, obtainable: set[str]) -> bool:
    """Whether a transition's `requires` is satisfied.

    No `requires`, a flag lock, or an unknown shape all open (only item
    locks can hold the hero back here); an item lock opens once its id
    has been obtained.
    """
    if not isinstance(requires, dict):
        return True
    if "flag" in requires:
        return True
    item = requires.get("item")
    if isinstance(item, str):
        return item in obtainable
    return True


def _closure(transitions, sources, start, rule_items, *, skip=(), force=()):
    """Grow reachable regions and obtainable items to a fixpoint.

    `skip` holds transition indices treated as shut; `force` holds ones
    opened without their key (used to ask what lies behind a lock).
    Returns `(reachable_regions, obtainable_items)`.
    """
    reachable: set[str] = {start} if start else set()
    obtainable: set[str] = set(rule_items)
    skip = set(skip)
    force = set(force)
    while True:
        changed = False
        for region in list(reachable):
            for item in sources.get(region, ()):  # type: ignore[arg-type]
                if item not in obtainable:
                    obtainable.add(item)
                    changed = True
        for i, t in enumerate(transitions):
            if i in skip:
                continue
            frm, to = t.get("from"), t.get("to")
            if not isinstance(frm, str) or not isinstance(to, str):
                continue
            if frm not in reachable or to in reachable:
                continue
            if i in force or _opens(t.get("requires"), obtainable):
                reachable.add(to)
                changed = True
        if not changed:
            break
    return reachable, obtainable


def _acts(world: dict) -> list[dict]:
    return [a for a in (world.get("acts") or []) if isinstance(a, dict)]


def findings(pack_dir) -> list[str]:
    """Every lock-reachability problem in `pack_dir`, as plain sentences.

    Empty when the pack carries no `requires`, when every item lock's
    key can be obtained in a region reached before it, and when no key
    has a `value` (which would let a trader buy the way forward).

    A key that exists only behind its own lock is reported as "behind
    its own lock" rather than a second "unreachable" finding.
    """
    pack = Path(pack_dir)
    if not (pack / "world.json").is_file():
        return []
    try:
        world = load_pack(pack)
    except (OSError, ValueError, KeyError, SystemExit):
        return []

    acts = _acts(world)
    if not acts:
        return []

    regions: list[str] = []
    transitions: list[dict] = []
    for act in acts:
        act_regions = act.get("regions")
        if isinstance(act_regions, dict):
            for name in act_regions:
                if name not in regions:
                    regions.append(name)
        for t in (act.get("transitions") or []):
            if isinstance(t, dict):
                transitions.append(t)

    locks = [(i, t) for i, t in enumerate(transitions)
             if isinstance(t.get("requires"), dict)
             and isinstance(t["requires"].get("item"), str)
             and t["requires"]["item"]]
    if not locks:
        return []

    player = world.get("_player") if isinstance(world.get("_player"), dict) else {}
    wake = player.get("wake") if isinstance(player.get("wake"), dict) else {}
    start = wake.get("region")
    if not isinstance(start, str) or start not in regions:
        start = regions[0] if regions else None
    if start is None:
        return []

    books = library.load_library(pack)
    sources = _region_sources(acts, books)
    rule_items = _rule_gives(world.get("rules"))

    items = world.get("items") if isinstance(world.get("items"), dict) else {}

    out: list[str] = []
    seen: set[str] = set()
    key_items: list[str] = []

    def emit(sentence: str) -> None:
        if sentence not in seen:
            seen.add(sentence)
            out.append(sentence)

    for i, t in locks:
        key = t["requires"]["item"]
        if key not in key_items:
            key_items.append(key)
        frm, to = t.get("from"), t.get("to")
        _reach, before = _closure(transitions, sources, start, rule_items,
                                  skip=(i,))
        if key in before:
            continue  # the key can be obtained before this lock: fine
        _reach, behind = _closure(transitions, sources, start, rule_items,
                                  force=(i,))
        where = f"from '{frm}' to '{to}'"
        if key in behind:
            emit(f"the key '{key}' can only be found behind its own lock, "
                 f"at the door {where}")
        else:
            emit(f"the key '{key}' is unreachable: it cannot be obtained in "
                 f"any region reached before the door {where}")

    # A Section's own entry door is a door like any other, so its key
    # joins the reachability work above and the unsellable rule below. The
    # reachability is already done - the transition that requires it is in
    # `locks` - but the value rule below only walks the keys the
    # transitions named, and a Section door the author wrote is one of
    # them however far down the list it was found.
    for key in section_key_items(pack):
        if key not in key_items:
            key_items.append(key)

    for key in key_items:
        spec = items.get(key)
        value = spec.get("value") if isinstance(spec, dict) else None
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            emit(f"the key item '{key}' has a value, so it can be sold to a "
                 f"trader - a sold key would break the pack")
    return out


# ------------------------------------------------------------- the Sections


def section_key_items(pack_dir) -> list[str]:
    """Every item a Section's own entry door is locked behind.

    A Section's key is the item its door into the Section requires, and
    the door is a transition like any other: `vefr delve --section` wires
    the town's stair into the Section's first floor, and the author gates
    it with `requires`. So the two rules `findings` already follows apply
    to a Section exactly as they apply to a hand-written region - the key
    must be obtainable before its own door, and it must carry no `value`,
    because a key a trader will buy is a way past a whole Section.

    Read off the transitions rather than off the Section pack, because the
    Section pack does not name a key: PLAN.md section 2 gives the warden
    one (ADR 0015's), and that is E8's record, not E4's. A Section with
    no entry door contributes nothing, which is the same answer a region
    with no lock gets.
    """
    pack = Path(pack_dir)
    if not (pack / "world.json").is_file():
        return []
    try:
        world = load_pack(pack)
    except (OSError, ValueError, KeyError, SystemExit):
        return []
    entries = {sections.floor_region(section, 1)
               for section in sections.load(pack)}
    out: list[str] = []
    for act in _acts(world):
        for transition in (act.get("transitions") or []):
            if not isinstance(transition, dict):
                continue
            if transition.get("to") not in entries:
                continue
            requires = transition.get("requires")
            if isinstance(requires, dict):
                item = requires.get("item")
                if isinstance(item, str) and item and item not in out:
                    out.append(item)
    return out


def _stamp_pack(pack: Path) -> list[dict]:
    """The pack's stamps, already sorted by id, or none.

    `stamps.load` refuses rather than returning half a set, which is right
    for a floor and wrong for a check: a pack with one broken stamp should
    still have its other rooms swept, and `vefr stamp check` is what says
    the broken one out loud.
    """
    directory = pack / "stamps"
    if not directory.is_dir():
        return []
    records: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        try:
            records.append(stamps.read_v1(stamps.read(path), name=path.stem))
        except (stamps.StampError, OSError, ValueError):
            continue
    records.sort(key=lambda record: record["id"])
    return records


def _walkable(plan: dict) -> set[tuple[int, int]]:
    return {(x, y)
            for y in range(plan["h"])
            for x in range(plan["w"])
            if plan["rows"][y][x] in ".ud"}


def _reached(plan: dict, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Every walkable tile 4-connected to `start`."""
    rows, width, height = plan["rows"], plan["w"], plan["h"]
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height \
                    and rows[ny][nx] in ".ud" and (nx, ny) not in seen:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return seen


def _named_tiles(plan: dict):
    """Every tile the plan names, as `(what, tile)` - the reachability set."""
    for name, at in (plan.get("anchors") or {}).items():
        if at is not None:
            yield name, (at[0], at[1])
    for poi in plan.get("pois") or []:
        yield "point of interest", (poi["at"][0], poi["at"][1])
    for tile in plan.get("secrets") or []:
        yield "secret", (tile[0], tile[1])
    for spawn in plan.get("spawns") or []:
        yield "monster", (spawn["at"][0], spawn["at"][1])
    for chest in plan.get("chests") or []:
        yield "chest", (chest["at"][0], chest["at"][1])


def _defect(plan: dict, section: dict | None = None) -> str:
    """What is wrong with a floor that came back, or "".

    The properties of PLAN.md sections 2 and 4, read back out of the grid
    rather than taken on the generator's word: one component, every named
    tile reachable from the up-stair, and - for a Section that names a
    vault - a vault anchor, because an anchor is the Section's promise and
    one that points at nothing is worse than no anchor at all. A v2
    fallback floor has no `pois` and no `spawns` and is caught by the `gen`
    check instead.
    """
    up = plan.get("anchors", {}).get("up")
    if up is None:
        return "the floor has no up-stair"
    reached = _reached(plan, (up[0], up[1]))
    if len(reached) != len(_walkable(plan)):
        return "the floor is in two pieces"
    if isinstance(section, dict) and section.get("vault") \
            and (plan.get("anchors") or {}).get("vault") is None:
        return "the Section names a vault and the floor has no vault anchor"
    for what, tile in _named_tiles(plan):
        if tile not in reached:
            return f"the {what} at {tile[0]},{tile[1]} cannot be reached " \
                   "from the up-stair"
    return ""


def section_findings(pack_dir, seeds: int = SECTION_SEEDS) -> list[str]:
    """Every property a Section's floors break, and every way its story
    cannot be finished, as plain sentences.

    Empty when the pack ships no Sections and no descent, which is every
    pack in the tree today, and when every floor of every Section holds
    over `seeds` check seeds and the progress walk reaches the story end.

    The progress walk (`progress_findings`, ADR 0015 checks 4 and 5) runs
    first and is flag-only, so it costs no seeds at all.

    The sweep is the slow half of `vefr check` and it is the half PLAN.md
    section 5 row E4 asks for: every Section, every floor, every seed. A
    Section's own `size` range draws the floor's `w` and `h`, its pattern
    draws the floor kind, and the floor key is the Section's - so two
    floors of one Section are two floors, and a pack that edits its
    Section data sweeps a different set of floors than it did before.
    """
    pack = Path(pack_dir)
    # ADR 0015 checks 4 and 5 first: the progress walk is flag-only, so it
    # costs nothing and a pack whose story cannot be finished should hear
    # that before it hears about a floor that could not be drawn. It runs
    # here rather than beside `findings` because this is the same door
    # `vefr check` opens onto the Sections, and it is about the Sections.
    findings = progress_findings(pack)
    loaded = sections.load(pack)
    if not loaded:
        return findings
    records = _stamp_pack(pack)
    for section in loaded:
        name = sections.section_id(section) or "?"
        swept = 0
        fell_back = 0
        broken = 0
        for number in range(max(0, int(seeds))):
            run_seed = f"{SECTION_SEED_PREFIX}{number}"
            for k in range(1, sections.floors(section) + 1):
                key = sections.floor_key(run_seed, section, 0, k)
                plan = delve_v3.generate_floor_v3(
                    run_seed, sections.floor_size(section, key), section,
                    sections.floor_kind(section, k, run_seed, 0), records, k)
                swept += 1
                if plan.get("gen") != 3:
                    fell_back += 1
                    continue
                defect = _defect(plan, section)
                if not defect:
                    continue
                broken += 1
                if broken == 1:
                    findings.append(
                        f"section {name}: floor {k} at seed {run_seed} does "
                        f"not hold - {defect}")
        if fell_back:
            findings.append(
                f"section {name}: {fell_back} of {swept} floors fell back to "
                f"v2 geometry instead of being drawn as v3")
    return findings


# ---------------------------------------------------------- the progress walk


def _rule_setters(world) -> set[str]:
    """Every flag a pack rule `set`s, whatever event it fires on.

    Rules are not regional, so a flag any rule can set is settable from
    anywhere; this is the whole of what check 4 knows about setters, and
    it is deliberately about the flag rather than about whether the rule
    can actually fire - the walk is a flag-only simulation (ADR 0015)."""
    out: set[str] = set()
    rules = world.get('rules') if isinstance(world, dict) else None
    if not isinstance(rules, list):
        return out
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        for effect in rule.get('then') or []:
            if isinstance(effect, dict) and isinstance(effect.get('set'), str) \
                    and effect['set']:
                out.add(effect['set'])
    return out


def progress_findings(pack_dir, cycle: int = 0) -> list[str]:
    """Every way this pack's story cannot be finished, as plain sentences.

    This is ADR 0015 checks 4 and 5, and it is a flag-only simulation: it
    starts with no flags at all and walks the Sections in order, three
    steps each - complete the warden's challenge, read the note, enter
    town - and asks at the end whether the pack's `story_end` is reached.
    Only flags move; no floor is drawn, no rule is fired and no seed is
    read, so the whole walk is the same sentence every time.

    Empty when the pack ships no descent, which is every pack in the tree
    today, and when the walk finishes the story. A Section that names no
    vault flag gates nothing and is not one of these - the same answer a
    Section with no pattern gets."""
    pack = Path(pack_dir)
    if not (pack / "world.json").is_file():
        return []
    try:
        world = load_pack(pack)
        descent = delve.descent_of(world, pack)
    except (OSError, ValueError, KeyError, SystemExit):
        return []
    listed = (descent or {}).get('sections')
    if not isinstance(listed, list) or not listed:
        return []

    setters = _rule_setters(world)
    story_end = delve.story_end_of(descent)
    flags: dict[str, bool] = {}
    spoken: set[str] = set()
    findings: list[str] = []

    for section in listed:
        if not isinstance(section, dict):
            continue
        name = sections.section_id(section) or '?'
        # 1. Complete the warden's challenge (ADR 0015 Amendment 1 §4: the
        #    walk's first step is the challenge, not the killing). A
        #    `defeat` warden is beaten, so its flag is set. A `rule`
        #    warden is completed by the pack rule that sets its flag, so
        #    the walk asks for that setter the same way it asks for a
        #    note's - one sentence when there is none.
        warden = delve.warden_of(section)
        if warden:
            flag = delve.warden_flag(warden['id'], cycle)
            if delve.warden_challenge(warden) == 'rule':
                if flag in setters:
                    flags[flag] = True
                else:
                    findings.append(
                        f"section {name}: the warden {warden['id']!r} takes "
                        f"challenge 'rule' and no rule sets the flag "
                        f"{flag!r} that completes it, so nothing can ever "
                        f"pass it")
                    spoken.add(flag)
            else:
                flags[flag] = True
        # 2. Read the note: the flag the vault's `sets` names, which a
        #    pack rule records when the note is opened.
        vault = delve.vault_of(section)
        if vault and vault['sets']:
            if vault['sets'] in setters:
                flags[vault['sets']] = True
            else:
                # One sentence, naming the flag, the Section and what the
                # missing setter costs: the town gate below is guarded by
                # this flag, so a flag nobody sets is a stair that stays
                # shut for good. That consequence is the same fact, so it
                # is part of this sentence rather than a second one.
                findings.append(
                    f"section {name}: the flag '{vault['sets']}' has no "
                    f"setter - no rule sets it and no vault note records "
                    f"it, so the gate "
                    f"'{delve.town_seen_flag(name, cycle)}' can never open")
                spoken.add(vault['sets'])
                continue
        # 3. Enter town. This is the rule the Section expansion emits on
        #    `enters <town>`, guarded by the vault's flag above; it is
        #    what opens every Section after this one.
        if vault and vault['sets']:
            flags[delve.town_seen_flag(name, cycle)] = True

    # ADR 0015 check 4: every `when` a town state waits on has a setter
    # too. A state nobody can reach is a town that never changes.
    for block in delve.town_states_of(world):
        for state in block.get('states') or []:
            if not isinstance(state, dict):
                continue
            when = state.get('when')
            if isinstance(when, str) and when and when not in setters \
                    and when not in flags and when not in spoken:
                findings.append(
                    f"town states: the region '{block.get('region')}' waits "
                    f"on the flag '{when}', which no rule sets")
                spoken.add(when)

    # ADR 0015 check 5: the walk has to reach the story's end. A pack that
    # ends on its last vault note reaches it here; a pack that ends on any
    # other rule (Amendment 1's no-boss ending) is a rule's work, and the
    # only thing this can say is that no rule sets the flag at all.
    if flags.get(story_end) is not True and story_end not in setters \
            and story_end not in spoken:
        findings.append(
            f"the descent: its story_end flag '{story_end}' is never set - "
            f"no Section's vault note records it and no rule sets it")
    return findings
