"""sections - Sections: the depth curve, the floor pattern, the landings.

PLAN.md section 2 is the spec. A Section is a pack file, `sections/<id>.json`,
holding everything one descent is made of: how many floors it has, how big
they are, what lives on them, and what each floor is FOR. This module is
the engine's read of that file, and it is pure - no clock, no model call,
no global, no dictionary iterated while a draw is consumed.

Everything here is one of four things:

- **where a floor is.** `locate(depth, pack)` turns a global depth into
  `(cycle, section, k)`, and `floor_key(run_seed, section, cycle, k)` names
  it. PLAN.md section 2 writes both, and the story is cycle 0.
- **what a floor is.** `pattern`, `slot`, `floor_kind` and `floor_size`:
  the four things a floor is drawn from, each on its own stream.
- **what the hero can get back to.** `landings`, `landing_flag` and
  `recorded_landings` are the elevator rule of PLAN.md section 4: two
  landings a Section, recorded permanently, and no lift down past a floor
  the hero has not reached.
- **what a floor is the same as.** `content_hash` and `identity` are the
  floor identity of PLAN.md section 2 - `(gen version, section content
  hash, floor_key)` - so that editing a pack's Section data invalidates
  that Section's floors rather than replaying old deltas onto new maps.

THE FLOOR KEY AND `delve_v3`

`floor_key` is what this slice means by a floor's name, and it is the
floor key `delve_v3.generate_floor_v3` builds for itself: that function
takes the RUN SEED as its `seed` and writes
`f"{seed}/{section.id}/{cycle}/{depth}"`, exactly the key
`floor_key(run_seed, section, cycle, k)` returns. The two are one string,
so `floor_key` here is the read and `delve_v3` is the writer of the same
identity - a caller must NOT hand `floor_key(...)` in as the seed, which
would build `run_seed/section.id/cycle/k/section.id/cycle/k` and name a
floor nothing else names. `floor_key` is what a caller still needs on its
own side: it is the key the size draw is salted with, and the key written
into the baked contract so a stair-time regeneration can name the floor.
Slice E3's JavaScript twin has to take the same key.

THE SIZE AND THE SPECIAL FLOOR

Two draws that are not in PLAN.md section 2's list of streams, both on
their own stream and both off the floor key:

- `|size` draws the floor's `w` then its `h` inside the Section's own
  `size` range. It is its own stream so that a pack that edits its room
  quota does not move a wall: the sub-seed rule of section 2 is the whole
  reason the stages do not share a stream.
- `|special` draws which of the Section's `specials` a `special` slot is,
  the way PLAN.md section 4's three kinds are meant to appear.

Both are one `floor(rng() * n)` draw with `n < 2^31`, which is the only
float PLAN.md section 2 allows, and both read a list that is already in
pack order.

TOUCH POINTS (written down before the first edit, as the slice asks)

| what | where |
|---|---|
| the Section pack shape | `shapes.SECTION` and its sub-blocks; `shapes.check_section` |
| the validator door | `maplab.section_block_errors`, called by `maplab.section_errors` |
| this module | `sections.py` |
| the sweep over Sections | `locks.section_findings`, printed by `cmd_map` |
| the bake | `cmd_delve --section`, which wires the doors and records the landings |
| the golden | `tests/golden/validator/cases.json`, block `section` |
| the tests | `tests/test_sections_e4.py`, the packs under `tests/fixtures/sections/` |
| what a kill pays | `sections.xp_for` here; `mobs_at` in `delve.py`; the twin in the descent part |
| the `xp` it reads | `shapes.FAMILY`'s `xp` key and `shapes._family_xp_problems` |

THE MOB COUNT

`mob_count` is the pack's own answer to how many monsters a floor carries,
and it is read before the first draw of the pop stage rather than drawn:
`{"1": 4, "from": 12}` is four on the first floor and twelve on every other
floor of the Section, and a Section that writes no `mobs` key at all is the
area budget it always was (`walkable // 30`, clamped to 4..36) - the same
number in Python (`delve_v3.mob_budget`) and in the player's twin
(`mobBudget` in part 396, which part 397 calls). It changes the POP stream
and nothing else: the `size`, `plan` and `layout` streams do not read it, so
a pack that sets a count on a Section it has already placed things on by
coordinate invalidates nothing it placed.

NOT IN THIS SLICE

The endless board itself - the tavern desk a hero chooses omens at, the
star each finished Section earns, and the collection rewards behind them -
is the slice after this one. This module answers the two questions the
board asks of the data: WHERE a depth past the story is (`cycle_locate`),
and WHAT the chosen omens do to the Section it is standing on
(`modifier`). The three special floor kinds are E9's - E4 draws WHICH of
them a special slot is and leaves the rest to `delve_v3`, which already
knows all three.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .delve import DEFAULT_FOG_RADIUS, prng
from .mob_stats import cycle_pct

# The Section directory inside a pack, and the file name pattern under it.
SECTIONS_DIR = 'sections'

# The pattern PLAN.md section 4 writes for a nine-floor Section: a landing
# to come down to, two special floors, a landing on the fifth, and the
# warden with its vault on the ninth. A Section that names no pattern gets
# this one, padded with `n` to as many floors as it has.
DEFAULT_PATTERN = ('entry', 'n', 'n', 'special', 'landing', 'n', 'special',
                   'n', 'warden')

# The slots a pattern may name, and the two of them that are a landing.
# `entry` is a landing too: it is the floor a hero comes down to, and
# PLAN.md section 4 counts the first floor of a Section as one of its two.
PATTERN_SLOTS = ('entry', 'n', 'special', 'landing', 'warden')
LANDING_SLOTS = ('entry', 'landing')

# The floor kind every slot but `special` is. `special` draws one of the
# Section's own `specials` instead, which is the same four kinds the
# generator already knows.
ORDINARY_KIND = 'normal'

# What a Section gets when it names nothing: nine floors, and the two
# sizes of PLAN.md section 3 that are a candidate default rather than the
# stress size.
DEFAULT_FLOORS = 9
DEFAULT_SIZE = ((64, 64), (48, 48))

# The closed range a Section's size may be in, which is the range of
# PLAN.md section 3's table plus a little. A pack outside it has been
# refused by `vefr check`; the clamp here is for a Section read off disk
# without its check, and a floor the generator can actually lay is better
# than an exception from inside a sweep.
SIZE_BOUNDS = ((32, 128), (24, 96))

# The flag a reached landing sets, and the prefix of every one of them. The
# id has to name the Section and the floor and nothing else, because it is
# written once and kept forever (PLAN.md section 2, save deltas).
LANDING_FLAG = 'landing-{section}-{k}'

# The region name the bake gives floor `k` of a Section.
REGION_NAME = '{section}-{k}'


# ------------------------------------------------------------- reading a pack


def section_id(section: dict) -> str:
    """The id a Section is named by, or the empty string when it has none."""
    if not isinstance(section, dict):
        return ''
    value = section.get('id')
    return value if isinstance(value, str) else ''


def section_label(section: dict) -> str:
    """The name a Section is shown by: its label when it has one, else its id."""
    label = section.get('label') if isinstance(section, dict) else None
    return label if isinstance(label, str) and label else section_id(section)


def load(pack_dir) -> list[dict]:
    """Every Section pack in `pack_dir/sections`, sorted by id.

    The same leniency `vefr.stamp_check` reads sections with: a file that
    cannot be read is left out rather than stopping the read, because the
    validator is what says so out loud and a sweep that stops on the first
    broken Section checks none of the rest. Returns the dicts as they are
    on disk, with no id filled in from the file name: a pack whose file and
    id disagree is `vefr check`'s sentence, not this module's guess.
    """
    directory = Path(pack_dir) / SECTIONS_DIR
    if not directory.is_dir():
        return []
    out: list[dict] = []
    for path in sorted(directory.glob('*.json')):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict):
            out.append(value)
    return ordered(out)


def ordered(sections) -> list[dict]:
    """A pack's Sections in the order the dungeon descends through them.

    By the Section's own number first and its id second, so a pack that
    numbers its Sections the way PLAN.md section 6 does descends in that
    order whatever the files are named. The id breaks a tie, and Python's
    sort is stable, so two Sections that share both keep the order they
    were read in - a list, never a dictionary, for the reason PLAN.md
    section 2 gives.
    """
    def rank(section):
        number = section.get('section') if isinstance(section, dict) else None
        return (number if isinstance(number, int) and not isinstance(number, bool)
                else 0, section_id(section))
    return sorted([s for s in sections if isinstance(s, dict)], key=rank)


def floors(section: dict) -> int:
    """How many floors a Section has, defaulting to nine."""
    value = section.get('floors') if isinstance(section, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return DEFAULT_FLOORS


def specials(section: dict) -> tuple[str, ...]:
    """The floor kinds a `special` slot may draw, in pack order.

    PLAN.md section 4 names three - treasure, infested, hub - and a pack
    that names its own draws from those instead. An empty list falls back
    to the three, so a Section that wrote `specials: []` is swept rather
    than skipped; `vefr check` is what tells the author about the empty
    list itself.
    """
    raw = section.get('specials') if isinstance(section, dict) else None
    if isinstance(raw, list):
        named = [kind for kind in raw if isinstance(kind, str) and kind]
        if named:
            return tuple(named)
    return ('treasure', 'infested', 'hub')


def _pair(value, fallback: tuple[int, int]) -> tuple[int, int]:
    """A `[lo, hi]` pair of whole numbers, ordered, or `fallback`."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        if all(isinstance(n, int) and not isinstance(n, bool) for n in value):
            return (min(value), max(value))
    return fallback


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    return max(bounds[0], min(bounds[1], value))


# --------------------------------------------------------------- the pattern


def pattern(section: dict) -> tuple[str, ...]:
    """The Section's pattern, one slot per floor, ending at its last floor.

    A Section that names no pattern gets `DEFAULT_PATTERN`; a pattern
    shorter than the Section is padded with `n`, and one longer than it is
    kept whole rather than cut, so a Section with more slots than floors
    keeps the warden its last slot names. Neither direction raises: the
    validator is what says a pattern that does not match its Section is
    wrong, and this module is what lays out whatever is on disk.
    """
    raw = section.get('pattern') if isinstance(section, dict) else None
    slots = [slot for slot in raw
             if isinstance(slot, str) and slot in PATTERN_SLOTS] \
        if isinstance(raw, list) else list(DEFAULT_PATTERN)
    count = floors(section)
    if len(slots) < count:
        slots.extend(['n'] * (count - len(slots)))
    return tuple(slots)


def slot(section: dict, k: int) -> str:
    """What floor `k` of a Section is FOR, 1-based.

    A floor past the end of the pattern is an ordinary one: the pattern is
    what a Section says about its floors, and a floor it did not describe
    is described here rather than raising in the middle of a descent.
    """
    slots = pattern(section)
    if isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= len(slots):
        return slots[k - 1]
    return 'n'


def is_landing(section: dict, k: int) -> bool:
    """Whether floor `k` is one of the Section's landings."""
    return slot(section, k) in LANDING_SLOTS


def landings(section: dict) -> tuple[int, ...]:
    """The floors of a Section a hero can climb back to town from.

    PLAN.md section 4: the first floor and the fifth, which is Stardew's
    every-five. Here they are the pattern's own `entry` and `landing`
    slots, in pattern order, so a Section that moves a landing has said so
    in its data rather than in this module.
    """
    return tuple(k for k, name in enumerate(pattern(section), 1)
                 if name in LANDING_SLOTS)


def landing_flag(section: dict, k: int) -> str:
    """The rule flag that records floor `k` of a Section as reached."""
    return LANDING_FLAG.format(section=section_id(section), k=k)


def recorded_landings(section: dict, flags) -> tuple[int, ...]:
    """The landings of a Section the hero has reached, in pattern order.

    The set of flags is a set: it has no order two languages would agree
    on, so the answer is the pattern's order every time (PLAN.md section 2,
    the forbidden-list rule). A flag for a floor that is not a landing of
    this Section is not one of them.
    """
    reached = flags if isinstance(flags, (set, frozenset)) else set(flags or ())
    return tuple(k for k in landings(section)
                 if landing_flag(section, k) in reached)


# ------------------------------------------------------------- the depth curve


def locate(depth: int, pack) -> tuple[int, dict, int]:
    """Where a global `depth` is: `(cycle, section, k)`.

    Pure, and derived only from the pack's Section list - PLAN.md section 2
    says so, and it is what lets the player locate a floor it has not
    loaded without loading the pack's floors. Depth 1 is the first floor of
    the first Section; the Sections are walked in `ordered` order, each for
    as many floors as it has.

    `pack` is a list of Sections or a pack directory. The story is cycle 0;
    a depth past the last floor of it raises `ValueError`, because
    clamping would answer with a floor that is not there. `cycle_locate`
    below is the endless read, and it wraps rather than clamps - but only
    past the story end, which is what makes a descent endless rather than
    a pack that quietly answers for floors nobody wrote.
    """
    if isinstance(pack, (str, Path)):
        pack = load(pack)
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
        raise ValueError(f'depth must be a whole number of 1 or more, and it is {depth!r}')
    for section in ordered(pack or ()):
        count = floors(section)
        if depth <= count:
            return 0, section, depth
        depth -= count
    raise ValueError(
        'that depth is past the last floor of the story, so it is an '
        'endless depth; read it with sections.cycle_locate')


def depth(section: dict, k: int, pack=None) -> int | None:
    """The global depth of floor `k` of `section` - `locate`'s inverse.

    `pack` is the Section list the depth is counted within and defaults to
    the Section itself. `None` when `section` is not one of them, or when
    `k` is not one of its floors: a depth that cannot be counted is not a
    depth of zero, and zero is floor one.
    """
    target = section_id(section)
    walked = 0
    for candidate in ordered(pack if pack is not None else [section]):
        if section_id(candidate) == target:
            return walked + k if 1 <= k <= floors(candidate) else None
        walked += floors(candidate)
    return None


# ------------------------------------------------------------- floor identity


def floor_key(run_seed: str, section: dict, cycle: int = 0, k: int = 1) -> str:
    """`run_seed/section.id/cycle/k`, the name of one floor.

    PLAN.md section 2 writes it exactly like this, and it is the key
    `delve_v3.generate_floor_v3` builds for itself from the run seed it is
    given - see the module docstring for why a caller keeps this read and
    never hands it in as the seed.
    """
    return f'{run_seed}/{section_id(section)}/{cycle}/{k}'


def floor_region(section: dict, k: int) -> str:
    """The region name floor `k` of a Section is baked as.

    `<section id>-<k>`, in the Section's own order, so the depth curve and
    the pack's region directory say the same thing about the same floor.
    """
    return REGION_NAME.format(section=section_id(section), k=k)


def content_hash(section: dict) -> str:
    """A digest over one Section's data, and nothing else.

    Sixteen hex characters of a SHA-256 over the record with its keys
    sorted, so two reads of the same file hash the same however the file
    was written. This is the middle of PLAN.md section 2's floor identity:
    editing any key of a Section changes the identity of every floor in it,
    which is what tells the save to regenerate those floors instead of
    replaying deltas recorded on maps that no longer exist.
    """
    text = json.dumps(section, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def identity(gen: int, section: dict, floor_key_: str) -> str:
    """The identity triple of one floor, as one string: `v<gen>:<hash>:<key>`."""
    return f'v{gen}:{content_hash(section)}:{floor_key_}'


# ------------------------------------------------------------- drawing a floor


def size_range(section: dict) -> tuple[int, int, int, int]:
    """A Section's own floor size range: `(w_lo, w_hi, h_lo, h_hi)`.

    Both halves of both pairs, clamped into `SIZE_BOUNDS` so a Section read
    off disk without its check still asks for a floor the generator can
    lay. `vefr stamp check` reads the same `size` key and measures a stamp
    against the SMALL end of it, so the two ends mean the same thing here.
    """
    raw = section.get('size') if isinstance(section, dict) else None
    width = _pair(raw.get('w') if isinstance(raw, dict) else None,
                  DEFAULT_SIZE[0])
    height = _pair(raw.get('h') if isinstance(raw, dict) else None,
                   DEFAULT_SIZE[1])
    return (_clamp(width[0], SIZE_BOUNDS[0]), _clamp(width[1], SIZE_BOUNDS[0]),
            _clamp(height[0], SIZE_BOUNDS[1]),
            _clamp(height[1], SIZE_BOUNDS[1]))


def floor_size(section: dict, floor_key_: str) -> tuple[int, int]:
    """The `(w, h)` of one floor, drawn from the Section's range.

    On the `v3|<floor key>|size` stream: the width first, then the height,
    each one `lo + floor(rng() * (hi - lo + 1))`. A Section whose two ends
    are the same number draws that number every time, which is what a pack
    asking for one fixed size is asking for.
    """
    w_lo, w_hi, h_lo, h_hi = size_range(section)
    rng = prng(f'v3|{floor_key_}|size')
    width = w_lo + int(rng() * (w_hi - w_lo + 1))
    height = h_lo + int(rng() * (h_hi - h_lo + 1))
    return width, height


def floor_kind(section: dict, k: int, run_seed: str, cycle: int = 0) -> str:
    """Which of the four floor kinds floor `k` of a Section is.

    Every slot but `special` is an ordinary floor - a landing and a warden
    floor are floors like any other to the generator, and what makes them
    those things is the Section's data rather than the geometry. A
    `special` slot draws one of the Section's own `specials` on the
    `v3|<floor key>|special` stream: one `floor(rng() * n)` draw, so the
    same floor key is the same kind in both languages.
    """
    if slot(section, k) != 'special':
        return ORDINARY_KIND
    kinds = specials(section)
    rng = prng(f'v3|{floor_key(run_seed, section, cycle, k)}|special')
    return kinds[int(rng() * len(kinds))]


# ------------------------------------------------------------ the mob count

# The key a Section writes its own monster count into, and the one entry of
# that key which is not a floor. A count may be written against one floor of
# the Section (`"1": 4` - four monsters on the floor a hero comes down to) or
# against every floor the Section did not name (`"from": 12`), and the two
# answers together are what a pack writes when the first floor is gentle and
# the rest are not: `{"1": 4, "from": 12}`.
MOBS_KEY = 'mobs'
MOBS_EVERY = 'from'

# The floors a count may name, which is the range `floors` itself is held to:
# a Section has at most ninety-nine floors, so a count against a hundredth
# is a count no floor can read, and `vefr check` refuses it rather than
# letting a pack believe it is thinning a floor it does not have.
MOB_FLOOR_MAX = 99


def _floor_number(key) -> int | None:
    """A `mobs` table's key as a floor number, or None when it names none.

    The one rule, and it is the same rule in both languages: the key is a
    floor only if it is the decimal spelling of that floor - `"3"` is three
    and `"03"`, `"+3"`, `" 3"` and `"three"` are nothing at all, so a key a
    floor would never look up is not quietly a floor either.

    ASCII digits only: `str.isdigit` is true of `"٣"` and `"²"` as well, and
    `int("²")` raises rather than answering.
    """
    if not isinstance(key, str) or not key.isascii() or not key.isdigit():
        return None
    number = int(key)
    if number < 1 or number > MOB_FLOOR_MAX or str(number) != key:
        return None
    return number


def mobs_of(section: dict) -> tuple[dict[int, int], int | None]:
    """A Section's own `mobs` table: `(count by floor, every other floor)`.

    `({"1": 4, "from": 12})` is `({1: 4}, 12)`; a Section that names no
    count at all is `({}, None)`, which is every Section written before
    this key existed and is not an error. An entry that is not a whole
    number of monsters is left out rather than raised: `vefr check` is what
    says a bad count out loud, and a sweep that stopped on one would check
    none of the other floors - the same rule `load` and `size_range` follow.
    """
    raw = section.get(MOBS_KEY) if isinstance(section, dict) else None
    by_floor: dict[int, int] = {}
    every: int | None = None
    if not isinstance(raw, dict):
        return by_floor, every
    for key, value in raw.items():
        if not isinstance(value, int) or isinstance(value, bool):
            continue
        if key == MOBS_EVERY:
            every = value
            continue
        number = _floor_number(key)
        if number is not None:
            by_floor[number] = value
    return by_floor, every


def mob_count(section: dict, k: int) -> int | None:
    """The monsters floor `k` of a Section carries because the pack said so.

    `None` is the whole of the answer for a Section that names nothing for
    that floor, and the caller reads it as "use the area budget" - which is
    what every floor of every Section written before this key did, and what
    every floor a Section names only some of still does. A floor the pack
    named wins over `from`, `from` wins over the area budget, and neither
    is a draw: the count is read off the pack before the first draw of the
    pop stream, so a Section that sets it draws exactly the monsters the
    floor has room for on the same stream it always used.
    """
    by_floor, every = mobs_of(section)
    if not by_floor and every is None:
        return None
    if isinstance(k, int) and not isinstance(k, bool) and k in by_floor:
        return by_floor[k]
    return every


# ------------------------------------------------------------------ families


def families(section: dict, resolve=None) -> list[dict]:
    """A Section's family table with each family's base record attached.

    A Section names Blueprint families by id and carries no record of its
    own (ADR 0014), so the base - `hp`, `atk`, `xp`, `sight` - comes from
    `vefr.blueprint.resolve_family` behind the `resolve` callable this
    module takes rather than imports. The Section's own keys win: a family
    id, a weight and a depth range are the Section's to write, and a
    Blueprint that happened to carry a `weight` would not get to overwrite
    one.

    A family the Blueprint does not have comes back as the entry alone, with
    no base - `vefr check` refuses that Section with `/families/0/family`,
    so a caller that never validated its pack still lays a floor rather
    than raising inside a sweep.
    """
    raw = section.get('families') if isinstance(section, dict) else None
    entries = [entry for entry in raw if isinstance(entry, dict)] \
        if isinstance(raw, list) else []
    out: list[dict] = []
    for entry in entries:
        name = entry.get('family')
        base = resolve(name) if resolve is not None and isinstance(name, str) \
            and name else None
        out.append(dict(base) if isinstance(base, dict) else {})
        out[-1].update(entry)
    return out


# ------------------------------------------- the endless cycles (slice E10)
#
# PLAN.md section 4 is the spec, and its two numbers are the ones this
# module is not allowed to soften:
#
# - "The monster multiplier is `min(1 + 0.2*c, 1.6)`." That arithmetic is
#   ADR 0014's `cycle pct`, and it lives in `vefr.mob_stats` where the
#   stat formulas read it. `monster_multiplier` here is the same number
#   under the name the plan uses, delegated rather than written twice,
#   because two copies of a cap is one cap too many.
# - "The loot tier caps at Section 3's tier + 1." `loot_tier_cap` is that
#   cap, and `cycle_loot_tier` holds every depth to it in code rather
#   than in a comment - which is what makes `scripts/balance_report.py`
#   a gate rather than a printout.
#
# "The hero's level cap does not move" is stated here rather than
# enforced, because the hero's level lives in the save and not in a
# Section pack: a Section has no key that could raise it, which is the
# strongest form the guarantee takes on this side.

# The multiplier's ceiling, in whole hundredths. PLAN.md section 4
# writes 1.6 and ADR 0014 writes `cycle pct = min(100 + 20*c, 160)`;
# those are the same cap, and this constant is the plan's number under
# the name the rest of the engine uses. `scripts/balance_report.py`
# holds its own copy too - on purpose, because a gate that reads the
# number it is checking checks nothing - and the two are compared there.
MULTIPLIER_CAP = 160

# What a Section whose `loot` block says nothing drops at. The plan does
# not write a default tier, and a Section that names none has always
# been a Section with no loot table of its own; 1 is the smallest tier
# the `loot` block admits, so it is also the smallest honest answer.
DEFAULT_LOOT_TIER = 1

# How far past the deepest Section's tier the loot may go in an endless
# cycle. PLAN.md section 4: "The loot tier caps at Section 3's tier + 1",
# and in a three-Section story Section 3 IS the deepest Section - so the
# cap is read off the pack's own last Section rather than off a hard
# number, which is what makes the same line true for a two-Section pack
# and for the fourth Section Cottage may add later.
LOOT_TIER_STEP = 1


def cycle_locate(depth: int, pack) -> tuple[int, dict, int]:
    """Where a global `depth` is, story and endless alike: `(cycle, section, k)`.

    The same read as `locate`, past the story's last floor instead of
    raising: the Sections are walked in `ordered` order and the descent
    starts again in cycle 1, then cycle 2, so depth 28 of a nine-floor
    Section is `(1, <first Section>, 1)`.

    This is PLAN.md section 2's determinism rule with one addition and
    none removed. It is still pure and still derived only from the
    Section list, so a floor can be located without loading it, and
    cycle 0 is bit-for-bit what `locate` answers for every depth it
    accepts - which the tests pin rather than assert in prose, because a
    second read of the depth curve that disagreed with the first would be
    two depth curves and one save.

    `pack` is a list of Sections or a pack directory, as everywhere in
    this module. A pack with no Sections has no depth to name and raises,
    which is what `locate` does and for the same reason.
    """
    if isinstance(pack, (str, Path)):
        pack = load(pack)
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
        raise ValueError(f'depth must be a whole number of 1 or more, and it is {depth!r}')
    walked = ordered(pack or ())
    if not walked:
        raise ValueError('that pack names no Sections, so it has no depth')
    total = sum(floors(section) for section in walked)
    cycle, within = divmod(depth - 1, total)
    for section in walked:
        count = floors(section)
        if within < count:
            return cycle, section, within + 1
        within -= count
    # Unreachable while `total` is the sum of the counts above; said out
    # rather than left to fall off the end of the function.
    raise ValueError(f'no Section answers for depth {depth}')


def monster_multiplier(cycle: int) -> int:
    """The endless multiplier for cycle `c`, in whole hundredths.

    `min(1 + 0.2*c, 1.6)`, in hundredths: `cycle_pct(0) == 100`, one
    hundredth below neutral nothing and `cycle_pct(3) == 160`, the cap.
    Cycle 3 and cycle 300 are the same number, and that is the whole
    point of PLAN.md section 1.3: "Endless at higher scaling is the
    power-creep failure." Past cycle 3 the difficulty comes from omens.

    The arithmetic is `vefr.mob_stats.cycle_pct`, delegated rather than
    written a second time, and it never returns more than
    `MULTIPLIER_CAP`. `scripts/balance_report.py` sweeps depths 1 to 300
    and refuses the engine if it ever does.
    """
    c = cycle if isinstance(cycle, int) and not isinstance(cycle, bool) else 0
    return cycle_pct(c if c >= 0 else 0)


def loot_tier(section: dict) -> int:
    """The loot tier a Section's own `loot` block names, or the default."""
    block = section.get('loot') if isinstance(section, dict) else None
    value = block.get('tier') if isinstance(block, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    return DEFAULT_LOOT_TIER


def loot_tier_cap(pack) -> int:
    """The highest loot tier any depth of this pack may drop.

    PLAN.md section 4: "The loot tier caps at Section 3's tier + 1." Read
    off the pack's deepest Section rather than hard-written, because in
    the three-Section story the plan is written about the deepest Section
    IS Section 3 - and a fourth Section added later moves the cap with
    the same line.

    An empty pack has no cap to speak of and gets the default tier plus
    the step, which is the same answer a one-Section pack gets.
    """
    walked = pack if isinstance(pack, (list, tuple)) else (
        load(pack) if isinstance(pack, (str, Path)) else [])
    deepest = ordered(walked or [])
    base = loot_tier(deepest[-1]) if deepest else DEFAULT_LOOT_TIER
    return base + LOOT_TIER_STEP


def cycle_loot_tier(section: dict, cycle: int, pack=None) -> int:
    """The loot tier of one Section in one cycle, held to `loot_tier_cap`.

    The cap is applied HERE, in code, which is what makes it a guarantee
    rather than a convention: a pack whose Sections disagree about their
    own tiers cannot drop a deeper one in an endless cycle, because the
    deeper answer never leaves this function.

    The story is cycle 0 and is not clamped - a Section 1 that declares
    the same tier as Section 3 drops what it has always dropped, and
    `scripts/balance_report.py` is what says out loud that such a pack is
    asking for more than the plan allows rather than quietly hiding it.
    """
    tier = loot_tier(section)
    c = cycle if isinstance(cycle, int) and not isinstance(cycle, bool) else 0
    return tier if c <= 0 else min(tier, loot_tier_cap(pack or [section]))


# ------------------------------------- omens as modifiers (slice E10, §4)
#
# "At each Section stair, the player picks 0-3 omens", and "each omen
# changes only its stated field". The second sentence is the whole of
# this half's design, so the API is shaped to make it provable rather than
# merely intended:
#
# - `omen_field(omen)` answers the ONE field an omen moves, and refuses
#   an omen that names none or two. `vefr check` says the same thing
#   with a sentence; this is what the engine would do about it.
# - `omen_delta(section, omens, field)` is the sum of the chosen omens'
#   deltas for ONE field, so nothing in this module can move two fields
#   by accident: there is no call here that returns a whole Section.
# - `modifier(section, cycle, omens)` is the one read that hands back
#   several fields at once, and it reads them each through its own
#   delta. A golden diff of `modifier` with and without one omen is the
#   acceptance test of the slice, and it shows one key moving.
#
# The three fields are `shapes.OMEN_FIELDS` and nothing else: the fog a
# Section sees by, the groups a floor may carry, and the affixes an
# endless cycle's warden draws (ADR 0015's `endless.affixes`, on the
# `loot|w` stream in cycles `c >= 1`). The other two omens PLAN.md
# section 4 lists by example - Restless and Lean - name fields this
# engine has no key for, and are not declared until one lands.

def omens(section: dict) -> list[dict]:
    """A Section's own omen list, in pack order, exactly as written."""
    block = section.get('endless') if isinstance(section, dict) else None
    raw = block.get('omens') if isinstance(block, dict) else None
    return [omen for omen in raw if isinstance(omen, dict)] \
        if isinstance(raw, list) else []


def picks(section: dict) -> int:
    """How many omens a player may pick at this Section's stair.

    `vefr.sections` reads the pack's `endless.picks` and holds it to the
    ceiling PLAN.md section 4 writes, because the plan's "0-3" is the
    rule and a pack is not the place to relax it.
    """
    from .shapes import OMEN_PICKS_MAX
    block = section.get('endless') if isinstance(section, dict) else None
    value = block.get('picks') if isinstance(block, dict) else None
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value:
        return min(value, OMEN_PICKS_MAX)
    return OMEN_PICKS_MAX


def omen_field(omen: dict) -> tuple[str, int] | None:
    """The one field an omen moves and by how much, or None.

    None when the omen is not a record, or names none of the three
    fields, or names more than one - the last of which is refused by
    `vefr check` with a sentence, and dropped here rather than guessed
    at. Guessing would be the one way an omen could change a field
    nobody chose.
    """
    from .shapes import OMEN_FIELDS
    if not isinstance(omen, dict):
        return None
    named = [field for field in OMEN_FIELDS if field in omen]
    if len(named) != 1:
        return None
    field = named[0]
    delta = omen[field]
    if not isinstance(delta, int) or isinstance(delta, bool):
        return None
    return field, delta


def chosen_omens(section: dict, chosen) -> list[dict]:
    """The omens a player actually picked, in the pack's own order.

    `chosen` is the ids the player chose, in any order and with any
    repeats; the answer is the pack's records for those ids, each once,
    in the order the pack lists them - a list, never a set, for the
    reason PLAN.md section 2 gives. An id this Section does not offer is
    not one of them, so a save written against a pack that has since
    dropped an omen plays rather than raises.
    """
    wanted = [name for name in (chosen or ()) if isinstance(name, str)]
    out: list[dict] = []
    for omen in omens(section):
        name = omen.get('id')
        if isinstance(name, str) and name in wanted and omen not in out:
            out.append(omen)
    return out


def omen_delta(section: dict, chosen, field: str) -> int:
    """What the chosen omens do to ONE field: their deltas, summed.

    A field no chosen omen names is unchanged, which is `0`. Two omens
    on the same field add - the plan lets a player take up to three, and
    forbids nothing about two of them naming the same field.
    """
    total = 0
    for omen in chosen_omens(section, chosen):
        pair = omen_field(omen)
        if pair is not None and pair[0] == field:
            total += pair[1]
    return total


def _bounded(value: int, lo: int, hi: int) -> int:
    return lo if value < lo else (hi if value > hi else value)


def fog_radius(section: dict, chosen=None) -> int:
    """The Section's lit radius, with Darker taken off it.

    The floor is `FOG_RADIUS_MIN` (2) - the low end the `fog` block
    admits, and a one-tile ring is not fog - and the ceiling is what the
    Section asked for. Three Darkers on a Section that asks for 2 leave
    it at 2, which is the honest answer: an omen cannot take away light
    the floor does not have.
    """
    from .shapes import FOG_RADIUS_MIN
    block = section.get('fog') if isinstance(section, dict) else None
    radius = block.get('radius') if isinstance(block, dict) else None
    base = radius if isinstance(radius, int) and not isinstance(radius, bool) \
        and radius >= FOG_RADIUS_MIN else DEFAULT_FOG_RADIUS
    return _bounded(base + omen_delta(section, chosen, 'fog_radius'),
                    FOG_RADIUS_MIN, base)


def groups_per_floor(section: dict, chosen=None) -> tuple[int, int]:
    """The Section's `[lo, hi]` groups per floor, with Crowded added.

    Both halves move together and both stop at the `groups` block's own
    ceiling of 3 a floor, because a floor with four groups is the
    density cap of PLAN.md section 1.4 and an omen does not get to be
    the thing that breaks it.
    """
    from .shapes import GROUPS_PER_FLOOR_MAX
    block = section.get('groups') if isinstance(section, dict) else None
    raw = block.get('per_floor') if isinstance(block, dict) else None
    pair = _pair(raw, (0, 0))
    delta = omen_delta(section, chosen, 'groups_per_floor')
    return (_bounded(pair[0] + delta, 0, GROUPS_PER_FLOOR_MAX),
            _bounded(pair[1] + delta, 0, GROUPS_PER_FLOOR_MAX))


def warden_affixes(section: dict, cycle: int = 0, chosen=None) -> int:
    """How many affixes this cycle's warden draws, with Proud added.

    ADR 0015: "In cycles `c >= 1` it draws `endless.affixes` affixes on
    the `loot|w` stream". Cycle 0 is the story and draws the warden's
    own ordinary affixes, so a Section that names no `endless` gets 0
    here in the story and whatever it wrote in every cycle after it.

    The ceiling is `shapes.ELITES`'s own: two affixes on one monster is
    the cap ADR 0014 wrote, and a warden is a monster.
    """
    from .shapes import AFFIXES_MAX
    c = cycle if isinstance(cycle, int) and not isinstance(cycle, bool) else 0
    warden = section.get('warden') if isinstance(section, dict) else None
    record = warden.get('endless') if isinstance(warden, dict) else None
    base = record.get('affixes') if isinstance(record, dict) else None
    base = base if isinstance(base, int) and not isinstance(base, bool) else 0
    if c < 1:
        base = 0
    return _bounded(base + omen_delta(section, chosen, 'warden_affixes'),
                    0, AFFIXES_MAX)


# The three fields `modifier` answers, in table order. A golden diff of
# `modifier` names its keys, and this tuple is what keeps the two in
# step - the same reason `shapes.OMEN_FIELDS` exists there.
MODIFIER_FIELDS = ('fog_radius', 'groups_per_floor', 'warden_affixes')


def modifier(section: dict, cycle: int = 0, chosen=None) -> dict:
    """Everything the chosen omens do to a Section, as one flat record.

    The one read a caller takes instead of three, and the shape the
    golden diff is taken over: `{"fog_radius": 4, "groups_per_floor": [1, 3],
    "warden_affixes": 1}`. Every value is read through its own
    `omen_delta`, so an omen that moves one field moves one key here and
    no other - which is exactly what the acceptance test diffs.

    No omens and no `endless` block both answer the Section's own data,
    unchanged. That is the whole backward-compatibility promise of the
    block, and it is why a pack that has never heard of an omen needs no
    edit to keep playing.
    """
    return {
        'fog_radius': fog_radius(section, chosen),
        'groups_per_floor': list(groups_per_floor(section, chosen)),
        'warden_affixes': warden_affixes(section, cycle, chosen),
    }


# ------------------------------------------------- the board's hook (E10)
#
# "The Deep Ledger" (PLAN.md section 4, owner-gated) is a board in the
# tavern that opens once the story ends - `vefr.delve.board_open` answers
# that, because the flag is `descent.story_end` and E8c wrote it. What
# the board then does is ask a Section a question, and this is that
# question answered as DATA:
#
#     sections.board_offer(cellar)
#     -> {'section': 'cellar', 'picks': 3, 'stars': 3, 'omens': [...]}
#
# No drawing, no model, no clock - the same rule as the rest of this
# module. The board UI, the stars the player has already earned, and the
# collection rewards behind them are a later slice; this is the hook they
# will hang on, and it is the whole of what a pack author needs in order
# to see their omens the way the engine reads them.

def board_offer(section: dict) -> dict | None:
    """What the board offers at this Section's stair, or None for no board.

    None rather than an empty offer, because the two are different facts:
    a Section that names no `endless` has no board at its stair, and one
    that names an empty `omens` list has a board offering nothing. A
    caller can tell them apart, and an empty dict could not.

    Each omen comes back as its id, its label if the pack wrote one, and
    the ONE field it moves with the delta it moves it by - the three
    things a player needs to read before choosing, and the whole of what
    choosing does. An omen that names no field or two is skipped here,
    because `vefr check` refuses such a pack and the board must not
    offer a choice it cannot honour.
    """
    offered: list[dict] = []
    for omen in omens(section):
        pair = omen_field(omen)
        if pair is None:
            continue
        field, delta = pair
        name = omen.get('id')
        offered.append({
            'id': name,
            'label': omen.get('label') if isinstance(omen.get('label'), str)
                     and omen['label'] else name,
            'field': field,
            'delta': delta,
        })
    if not offered:
        return None
    limit = picks(section)
    return {
        'section': section_id(section),
        'picks': limit,
        # "Each omen adds a star when the Section is finished" - a star
        # per omen, so the most a player can take from one Section is the
        # number of picks. `stars` is that maximum and nothing more: what
        # the player has already earned is the save's business.
        'stars': limit,
        'omens': offered,
    }


# What one kill is worth. A family may declare its own `xp` - the
# Blueprint's base record or the Section's own row, the Section's row
# winning the merge above - and that number is the kill, exactly.
# A family that declares none gets the default below rather than
# nothing at all, because a hero who walks four Sections and is exactly
# as strong on the fourth floor as on the first has been told the truth
# about nothing.
#
# The default is a ramp on DEPTH, the Section's own floor counted from
# the top of the descent: `XP_BASE` on the first floor, `XP_PER_DEPTH`
# more for every floor below it. Depth is the number the player already
# reads (a floor's `k`, and the Section it belongs to), it is pure -
# no draw, no clock, nothing the determinism rule of PLAN.md section 2
# forbids - and because `locate` walks the Sections in order, a deeper
# Section is a deeper depth and pays more. That is the whole curve.
XP_BASE = 1
XP_PER_DEPTH = 2


def xp_for(family: dict, depth: int = 1) -> int:
    """What one kill of `family` on floor `depth` is worth, in experience.

    A family's own `xp` wins, whole or not: the number it declares is
    the number a kill pays, because a pack that wrote a reward wrote a
    reward, and `vefr check` has already refused one that is not a
    whole number in range. Everything else - a family that says
    nothing, and a Section naming a family the Blueprint does not have,
    which carries no record at all - takes the documented default
    above.

    Pure, and takes no argument this module cannot read off its own:
    the family record and the depth. No draw is consumed, so adding it
    moves no tile, no monster and no drop on any floor.
    """
    declared = family.get('xp') if isinstance(family, dict) else None
    if isinstance(declared, int) and not isinstance(declared, bool) \
            and declared >= 0:
        return declared
    floor = depth if isinstance(depth, int) and not isinstance(depth, bool) \
        and depth >= 1 else 1
    return XP_BASE + XP_PER_DEPTH * (floor - 1)
