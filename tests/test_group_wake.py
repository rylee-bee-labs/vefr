"""E7.3: waking a group, the free turn that follows, noise, and the warden.

ADR 0014 ("Monster AI", JS only) plus its owner decisions of 2026-10-04
add four things to E0d's sleeping monsters:

  1. **Wake-all.** Waking one member of a linked group marks every other
     living member of that group awake in the SAME monster phase. A
     member 14 tiles from the hero - far outside its own wake radius of
     10 and its own sight of 6 - is awake because the group's leader
     woke, and that is what `test_the_group_wakes_all_together` proves.
  2. **Wake grace.** A monster the group's wake caught spends the phase
     it woke in doing nothing and acts from the next one, so a group
     wakes together and never lands its first blow together. A monster
     that woke on its own - in sight, hit, or woken by noise - has no
     free turn and acts at once, which is E0d's behaviour exactly and
     is what keeps `tests/test_monster_sleep.py` green.
  3. **Noise.** A loud thing the hero does wakes every sleeper within
     earshot: fighting 12, doors 6, chests 6, stairs 8, breaking 8
     tiles, measured Chebyshev. Fighting's call site is `heroAttack`
     here; the doors, chests and stairs are wired in the interaction
     dispatch (`web/player/parts/480-town-input-and-turns.js`) and the
     last section below proves each one through the real woven player.
     Breaking has no call site: the player has no break action to
     attach it to, so the `break` row of the table is reached only by
     calling `makeNoise('break')` directly, which is what the reader
     test below does.
  4. **The warden** is awake and never sleeps, so it hunts before
     anything else on the floor does.

The group ids, the leader mark, the leash and the warden mark are read
by the player off the baked spawn records in `window.VEFR_ENEMIES`, and
the baker (`src/vefr/cli.py`) carries them through: every fixture here
is a real pack, woven the shipped way, with the roster in the region's
own contract. Nothing about the player is stubbed - these are the real
woven player, the real turn loop, the real flood.

Every fixture is a fixed map with fixed numbers - no randomness, no
wall-clock, no mocks. Run with:

    bash tests/run.sh tests/test_group_wake.py
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from play_kit import pack, play, weave

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

ROOT = Path(__file__).resolve().parents[1]
PARTS = ROOT / "web" / "player" / "parts"

# One big open room: 30x11 with a solid border, the hero starting in the
# corner at [1, 1]. Every tile inside is walkable, so a walking distance
# and a straight line agree and the numbers below can be read off the
# map by eye.
WIDTH, HEIGHT = 30, 11
LEGEND = {".": {"base": ["#212a20"]}, "#": {"base": ["#2a2e33"], "solid": True}}

# ---- the noise table, as the owner fixed it on 2026-10-04 ----
# kind -> radius in tiles, Chebyshev from the hero.
NOISE = {"fight": 12, "door": 6, "chest": 6, "stair": 8, "break": 8}

# ---- the fixtures ----

# A group of three, well east of the hero, all of it asleep at the
# start. The leader's spawn tile is the group's home. Every member has
# the default sight of 6, so each one's own wake radius is the default
# 10 and E0d's Manhattan rule and the ADR's Chebyshev sight rule agree
# about every tile in this fixture.
GROUP = [
    {"id": "g1-leader", "name": "a group leader", "at": [20, 1],
     "hp": 4, "atk": 1, "sprite": "rat",
     "group": "g1", "leader": True, "leash": 3},
    {"id": "g1-kin-a", "name": "a group kin", "at": [22, 1],
     "hp": 4, "atk": 1, "sprite": "rat", "group": "g1"},
    {"id": "g1-kin-b", "name": "another group kin", "at": [23, 1],
     "hp": 4, "atk": 1, "sprite": "rat", "group": "g1"},
]

# A fight next to the hero and one sleeper ten tiles up the row: 11
# tiles away, which is one tile past E0d's wake radius of 10 and five
# tiles past its sight of 6, and four tiles inside the fighting noise
# radius of 12. Nothing but the noise can wake it.
FIGHT = [
    {"id": "bump-target", "name": "a bump target", "at": [2, 1],
     "hp": 4, "atk": 1, "sprite": "rat"},
    {"id": "far-ear", "name": "a far ear", "at": [12, 1],
     "hp": 4, "atk": 1, "sight": 6, "sprite": "rat"},
]

# The warden and one ordinary monster two tiles EAST of it - the side
# away from the hero, so the two answers a monster out of the hero's
# sight can give are two tiles apart and one turn cannot be both.
#
# The hero ends this fixture at [2, 1], ten tiles from the warden: the
# default wake radius is 10, so the warden is awake, and its own sight
# of 6 is four tiles short, so the hero is out of it. The guard is
# twelve tiles from the hero - outside that same wake radius and far
# outside its sight - so it is asleep, and it is the only other living
# monster. The warden therefore has exactly one choice to make: walk
# west at the hero, which is what ADR 0014's owner decision 2 says it
# does, or drift east toward the guard, which is what every other
# awake monster out of sight does.
WARDEN = [
    {"id": "hall-warden", "name": "the hall warden", "at": [12, 1],
     "hp": 4, "atk": 1, "sight": 6, "sprite": "rat", "warden": True},
    {"id": "hall-guard", "name": "a hall guard", "at": [14, 1],
     "hp": 4, "atk": 1, "sight": 6, "sprite": "rat"},
]

# The same two monsters, same tiles, same numbers - and no warden mark
# on the first. This is the control for the test below: it is awake and
# out of the hero's sight in exactly the same way, so whatever it does
# is the drift every other awake monster has always done.
DRIFTER = [
    {"id": "hall-watcher", "name": "a hall watcher", "at": [12, 1],
     "hp": 4, "atk": 1, "sight": 6, "sprite": "rat"},
    {"id": "hall-guard", "name": "a hall guard", "at": [14, 1],
     "hp": 4, "atk": 1, "sight": 6, "sprite": "rat"},
]

READS = [
    "VEFR_COMBAT.hero.at", "VEFR_COMBAT.hero.hp",
    "VEFR_COMBAT.enemies.0.at", "VEFR_COMBAT.minds.0.awake",
    "VEFR_COMBAT.enemies.1.at", "VEFR_COMBAT.minds.1.awake",
    "VEFR_COMBAT.enemies.2.at", "VEFR_COMBAT.minds.2.awake",
    "text:#combat-live",
]


def open_room(tmp_path, enemies):
    """The combat fixture with its town swapped for the big open room.
    The act keeps its regions; only the town's map, contract and enemies
    are the test's own. The hero starts in the corner at [1, 1]."""
    p = pack(tmp_path, "combat")
    town = p / "acts" / "act-1" / "town"
    wall = "#" * WIDTH
    row = "#" + "." * (WIDTH - 2) + "#"
    rows = [wall] + [row] * (HEIGHT - 2) + [wall]
    (town / "map.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    contract = {
        "tile": 32, "bg": "#131311", "hero_start": [1, 1],
        "sanctuary_tiles": ["."],
        "water_by_phase": {"dusk": "low", "dawn": "low"},
        "flood_tiles": [], "pois": {}, "legend": LEGEND,
        "enemies": enemies,
    }
    (town / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    return p


def baked_enemies(html_path):
    """The `window.VEFR_ENEMIES` a woven player carries, read back.

    The literal is JSON, so it is decoded the way it was written rather
    than scraped with a regex: the first closing bracket the decoder
    stops at is the end of the object, and everything after it is the
    rest of the player.
    """
    html = Path(html_path).read_text(encoding="utf-8")
    marker = "window.VEFR_ENEMIES = "
    at = html.index(marker) + len(marker)
    return json.JSONDecoder().raw_decode(html, at)[0]


def walk_right(n):
    return ["begin", "walk:" + ",".join(["right"] * n)]


# ---- 0. the bake carries the keys ----

def test_the_bake_carries_the_five_mind_keys(tmp_path):
    """A pack that writes a group, a leash, an affix or a warden into
    its contract's `enemies` gets all of it into the woven file.

    The player reads `group`, `leader`, `leash` and `warden` off the
    baked spawn record and nothing else tells it a spawn is an elite
    (`prepareMinds` and `groupLeash`, part 420). The baker used to keep
    only id/name/at/hp/atk/sprite/drops/sight/xp, so every one of those
    was dropped on the way to the file: a shipped pack could name a
    group and still get a floor where wake-all, the leash and the
    warden could never fire, because the record that told the player
    about them was never written.

    Each of the five rides along only when the record names it, on the
    same rule as `xp`, so a pack that names none bakes the exact bytes
    it always did. The second half of this test is that half: `FIGHT`
    names none of the five, and not one of them appears.
    """
    mind_keys = ("group", "leader", "leash", "elite", "warden")
    # One roster that names all five: an elite leader of a group, a
    # plain member, and the warden. Every key is on the record that
    # would carry it in a real FloorPlan.
    roster = [
        {"id": "m0", "name": "a broad one", "at": [20, 1], "hp": 4, "atk": 1,
         "sprite": "rat", "group": "g0", "leader": True, "leash": 7,
         "elite": "big"},
        {"id": "m1", "name": "a group kin", "at": [22, 1], "hp": 4, "atk": 1,
         "sprite": "rat", "group": "g0"},
        {"id": "m2", "name": "the hall warden", "at": [16, 1], "hp": 4,
         "atk": 1, "sight": 6, "sprite": "rat", "warden": True},
    ]
    baked = baked_enemies(weave(open_room(tmp_path, roster), tmp_path))["town"]
    assert [e["id"] for e in baked] == ["m0", "m1", "m2"]
    assert baked[0]["group"] == "g0", "the group id rides in"
    assert baked[0]["leader"] is True, "the leader mark rides in"
    assert baked[0]["leash"] == 7, "the leash rides in"
    assert baked[0]["elite"] == "big", "the elite's affix id rides in"
    assert baked[1]["group"] == "g0", "a plain member carries its group too"
    assert "leader" not in baked[1], "an absent key stays absent"
    assert "leash" not in baked[1]
    assert "elite" not in baked[1]
    assert baked[2]["warden"] is True, "the warden mark rides in"
    # The control: the same pack with a roster that names none of the
    # five bakes none of them, so a pack written before E7 is byte for
    # byte the player it always got.
    plain = baked_enemies(weave(open_room(tmp_path, FIGHT), tmp_path))["town"]
    assert [e["id"] for e in plain] == ["bump-target", "far-ear"]
    for record in plain:
        for key in mind_keys:
            assert key not in record, \
                f"{record['id']} gained {key!r} without naming it"


# ---- 1. wake-all and the free turn ----

def test_the_group_wakes_all_together(tmp_path):
    html = weave(open_room(tmp_path, GROUP), tmp_path)
    # Nine steps: the hero stands at [10, 1], ten tiles from the leader -
    # exactly its wake radius, so the leader is awake - and twelve and
    # thirteen tiles from the two kins, well outside both of their own
    # wake radii and sights. Nothing else can wake them.
    out = play(html, {"steps": walk_right(9), "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.hero.at"] == [10, 1]
    assert reads["VEFR_COMBAT.minds.0.awake"] is True, \
        "the hero ended a turn inside the leader's wake radius"
    assert reads["VEFR_COMBAT.minds.1.awake"] is True, \
        "a group member wakes with the group, not with the hero's radius"
    assert reads["VEFR_COMBAT.minds.2.awake"] is True, \
        "the far member wakes in the same phase as the one in earshot"
    # The leader woke on its own and acted at once: ten tiles out is
    # outside its sight of 6, so it walks home, and it is already home.
    assert reads["VEFR_COMBAT.enemies.0.at"] == [20, 1]
    # The two kins woke by the group and spent the free turn: they are
    # exactly where they spawned. This is the grace, and it is also the
    # proof that the group's wake reached 12 and 13 tiles.
    assert reads["VEFR_COMBAT.enemies.1.at"] == [22, 1], \
        "a member woken by its group does not act on the turn it woke"
    assert reads["VEFR_COMBAT.enemies.2.at"] == [23, 1], \
        "the far member is awake and still exactly where it spawned"
    assert reads["VEFR_COMBAT.hero.hp"] == 3, \
        "nothing struck the hero on the turn the group woke"


def test_the_free_turn_is_spent_and_the_group_acts_next(tmp_path):
    html = weave(open_room(tmp_path, GROUP), tmp_path)
    # One step further: the hero is at [11, 1] and the free turn is
    # spent. Both kins are out of sight, so each walks one tile home -
    # the leader's spawn tile is [20, 1] and a member stops within one
    # tile of it, so the nearer kin stops at [21, 1] and the further one
    # at [22, 1].
    out = play(html, {"steps": walk_right(10), "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.hero.at"] == [11, 1]
    assert reads["VEFR_COMBAT.enemies.1.at"] == [21, 1], \
        "the nearer kin acts the turn after the one it woke on"
    assert reads["VEFR_COMBAT.enemies.2.at"] == [22, 1], \
        "the further kin acts too, so the group moves as one"
    assert all(reads[f"VEFR_COMBAT.minds.{i}.awake"] for i in range(3))


def test_a_lone_monster_wakes_and_acts_on_the_same_turn(tmp_path):
    """The guard on the grace rule: the free turn belongs to the group
    wake, not to waking at all. A monster that wakes on its own acts at
    once - E0d's rule, and the reason tests/test_monster_sleep.py still
    passes. The two monsters here stand where the group's members stood
    and are the same shape; only the group id is missing."""
    alone = [
        {"id": "solo-leader", "name": "a lone leader", "at": [20, 1],
         "hp": 4, "atk": 1, "sprite": "rat"},
        {"id": "solo-kin", "name": "a lone kin", "at": [22, 1],
         "hp": 4, "atk": 1, "sprite": "rat"},
    ]
    html = weave(open_room(tmp_path, alone), tmp_path)
    out = play(html, {"steps": walk_right(9), "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.minds.0.awake"] is True
    # Ten tiles out, so it is awake and out of its own sight: it drifts
    # one tile toward the nearest other monster, the way an awake
    # monster out of sight always has. It acted on the turn it woke.
    assert reads["VEFR_COMBAT.enemies.0.at"] == [21, 1], \
        "a monster that woke on its own has no free turn"
    # The second one is twelve tiles out, outside even the wake radius,
    # so with no group to wake it there it sleeps exactly as it did
    # before this slice: a lone monster keeps today's behaviour.
    assert reads["VEFR_COMBAT.minds.1.awake"] is False, \
        "with no group id there is nothing to spread a wake to"
    assert reads["VEFR_COMBAT.enemies.1.at"] == [22, 1]


# ---- 2. noise ----

def test_fighting_wakes_a_sleeper_out_of_sight_and_out_of_range(tmp_path):
    """The hero bumps the monster next to it. A fight is 12 tiles of
    noise, so the sleeper at [12, 1] - Chebyshev 11 from the hero, one
    tile past E0d's Manhattan wake radius of 10 and five past its own
    sight of 6 - wakes, and acts at once because the hero's turn is not
    a monster phase."""
    html = weave(open_room(tmp_path, FIGHT), tmp_path)
    out = play(html, {"steps": ["begin", "walk:right"], "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.hero.at"] == [1, 1], "the bump does not move the hero"
    assert reads["VEFR_COMBAT.enemies.0.at"] == [2, 1]
    assert reads["VEFR_COMBAT.minds.1.awake"] is True, \
        "a fight 11 tiles away is inside the 12-tile noise radius"
    assert reads["VEFR_COMBAT.enemies.1.at"] == [11, 1], \
        "a monster woken by noise acts on the hero's turn, not a turn later"


def test_walking_away_leaves_the_same_sleeper_asleep(tmp_path):
    """The control for the noise test: the same two monsters, the same
    hero, one turn spent - and no fight. The sleeper at [12, 1] is now
    Chebyshev 12 from a hero at [1, 2], so even the fighting radius does
    not reach it, and it stays exactly where it spawned."""
    html = weave(open_room(tmp_path, FIGHT), tmp_path)
    out = play(html, {"steps": ["begin", "walk:down"], "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.hero.at"] == [1, 2]
    assert reads["VEFR_COMBAT.minds.1.awake"] is False, \
        "a quiet turn wakes nobody"
    assert reads["VEFR_COMBAT.enemies.1.at"] == [12, 1]


# ---- the five loud events, straight at the reader ----

def test_every_loud_event_is_called_and_none_is_wrapped():
    """The noise table and the player's call sites, read off the parts.

    Two things, and both are about the table not lying. `makeNoise` is
    the only way a loud event reaches the floor, so a row of the table
    that nothing names is a number nothing ever asks: `fight`, `door`,
    `chest` and `stair` each have a call site in the shipped player and
    `break` is the one exception, named here with its reason (the player
    has no break action to attach one to). And a per-kind wrapper -
    `heardFight` and its four sisters - is a name nothing ever spells
    and a function nothing ever calls, so there are none: `inEarshot`
    and `makeNoise` are the whole of the surface.
    """
    parts = "\n".join(path.read_text(encoding="utf-8")
                      for path in sorted(PARTS.glob("*.js")))
    called = set(re.findall(r"makeNoise\('([a-z]+)'\)", parts))
    assert called == {"fight", "door", "chest", "stair"}, \
        ("the loud events the player actually makes changed; a new one "
         "belongs in this set, and 'break' only once the player has a "
         "break action to call it from")
    assert set(NOISE) - called == {"break"}, \
        "a row of the table with no call site must be the one named here"
    for kind in NOISE:
        assert f"NOISE_{kind.upper()}" in parts, \
            f"the {kind} radius is not in the table at all"
    wrappers = re.findall(r"function heard[A-Z]\w*\(", parts)
    assert not wrappers, \
        (f"{wrappers} are dead: nothing in the player calls them, and "
         "`makeNoise`/`inEarshot` are the whole of the surface")


# The three AI parts verbatim, in a node vm, with the rest of the player
# stubbed the way tests/browser/bench_floor_play.py stubs it for the
# same measurement. Nothing here rewrites the engine: `noiseRadius` and
# `makeNoise` are the shipped functions, called directly, because
# `break` - the one loud event with no call site - is reached by asking
# `makeNoise` for it, and the four that do have call sites are proved
# through the real player in the section above.
NOISE_DRIVER = """
import fs from 'node:fs';
import vm from 'node:vm';

const partsDir = process.argv[2];
const spec = JSON.parse(process.argv[3]);
const parts = ['410-the-living-hazards.js', '420-how-a-monster-thinks.js',
               '425-the-elements.js', '430-loot-on-the-floor.js']   // 425: damage types (vefr#497)
  .map(n => fs.readFileSync(partsDir + '/' + n, 'utf8')).join('\\n');

const size = spec.size;
const wall = '#'.repeat(size);
const row = '#' + '.'.repeat(size - 2) + '#';
const rows = [wall];
for (let i = 0; i < size - 2; i++) rows.push(row);
rows.push(wall);

const sandbox = {
  window: { VEFR_WORLD: { name: 'noise' } },
  document: {},
  store: { get: () => null, set: () => {},
           getJSON: (k, d) => d, setJSON: () => {} },
  regionName: 'noise',
  town: { map: rows, legend: { '#': { solid: true } }, hero_start: [1, 1] },
  hero: [1, 1], HERO_HP: 9, DEATH_LINE: 'down', XP_WORD: 'renown',
  draw() {}, flushGrowth() {}, sayGrowth() {}, practiceSuffix: s => s,
  combatSay() {}, soundCue() {}, saveHeroHp() {}, renderHp() {},
  heroMax: () => 9, heroAtk: () => 2, heroGold: () => 0,
  bagItems: () => [], bagAdd: () => false, itemName: () => '',
  itemCatalog: () => ({}), fireRule() {}, growBump: () => 1,
  growAward: () => null, levelSuffix: () => '', enterRegion() {},
};
sandbox.window.VEFR_ENEMIES = {};
vm.createContext(sandbox);
vm.runInContext(parts, sandbox);

const out = { radii: {}, kinds: {} };
for (const kind of Object.keys(spec.kinds)) {
  out.radii[kind] = sandbox.noiseRadius(kind);
  out.kinds[kind] = [];
  for (const at of spec.kinds[kind]) {
    const roster = [{ id: 'ear', name: 'an ear', at: at.slice(),
                      hp: 4, atk: 1, sight: 6, drops: [] }];
    sandbox.window.VEFR_ENEMIES = { noise: roster };
    sandbox.enemiesByRegion = { noise: roster };
    sandbox.loadEnemies();
    sandbox.prepareMinds();
    sandbox.makeNoise(kind);
    out.kinds[kind].push({ at: at, awake: sandbox.enemies[0].awake });
  }
}
console.log(JSON.stringify(out));
"""


def noise_read(tmp_path, spec):
    driver = Path(tmp_path) / "noise_driver.mjs"
    driver.write_text(NOISE_DRIVER, encoding="utf-8")
    run = subprocess.run(["node", str(driver), str(PARTS), json.dumps(spec)],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def test_the_five_loud_events_carry_the_owners_radii(tmp_path):
    """One number per loud event, in one place, each reachable on its
    own: fighting 12, doors and chests 6, stairs and breaking 8. The
    boundary is measured on the diagonal, so a rule that counted
    straight-line-plus would call every one of these tiles out of
    earshot and fail."""
    kinds = {}
    for kind, radius in NOISE.items():
        # [1, 1] + (radius, radius) is Chebyshev `radius` and Manhattan
        # twice that; one tile further is one tile out of earshot.
        kinds[kind] = [[1 + radius, 1 + radius], [2 + radius, 2 + radius]]
    out = noise_read(tmp_path, {"size": 40, "kinds": kinds})
    for kind, radius in NOISE.items():
        assert out["radii"][kind] == radius, \
            f"the {kind} noise radius is {radius} tiles"
        heard = out["kinds"][kind]
        assert heard[0]["awake"] is True, \
            f"a {kind} {radius} tiles away is inside earshot"
        assert heard[1]["awake"] is False, \
            f"a {kind} {radius + 1} tiles away is not"


# ---- the wired call sites, through the real interaction dispatch ----
#
# The reader above is proved on its own; these four are the other half of
# the same claim - that the player actually MAKES each noise, at the
# moment the hero does the loud thing. Every fixture is the big open room
# with the hero standing still on [1, 1] and the one thing to interact
# with one tile east at [2, 1] (reach one, so no turn is spent reaching
# it, and nothing else in the room is in reach: no speaker, no chest
# book, no second transition, so `pickTarget` has exactly one candidate
# and the hero's facing cannot change which one it names).
#
# The two sleepers are placed past everything but the noise: each is
# more than ten tiles from the hero in a straight line, so E0d's
# Manhattan wake radius leaves it asleep, and each carries sight 4, so
# the ADR's own-sight rule leaves it asleep too. Nothing in these four
# tests can wake a sleeper but the noise it is named for.

# Doors and chests carry 6 tiles. `near-ear` is Chebyshev 6 from the
# hero's [1, 1] - twelve tiles away in a straight line - and `far-ear`
# is one tile further out, so exactly one of them is in earshot.
SIX_TILES = [
    {"id": "near-ear", "name": "a near ear", "at": [7, 7],
     "hp": 4, "atk": 1, "sight": 4, "sprite": "rat"},
    {"id": "far-ear", "name": "a far ear", "at": [8, 7],
     "hp": 4, "atk": 1, "sight": 4, "sprite": "rat"},
]

# Stairs carry 8. The same pair two tiles further east: `near-ear` is
# Chebyshev 8 from the hero and `far-ear` is 9.
EIGHT_TILES = [
    {"id": "near-ear", "name": "a near ear", "at": [9, 7],
     "hp": 4, "atk": 1, "sight": 4, "sprite": "rat"},
    {"id": "far-ear", "name": "a far ear", "at": [10, 7],
     "hp": 4, "atk": 1, "sight": 4, "sprite": "rat"},
]

# A door and a stair are the same transition, told apart by the region's
# own naming of the tile (a `pois` that mentions a stair). Both open
# into `beyond`, which this pack declares no region for: the door really
# opens and really is loud, and the arrival has nowhere to go, so the
# run stays in the room and the wake is read in the region the hero
# stood in when the noise was made.
BEYOND = [{"from": "town", "at": [2, 1], "to": "beyond", "to_at": [1, 1]}]

LOUD_READS = [
    "VEFR_COMBAT.region", "VEFR_COMBAT.hero.at",
    "VEFR_COMBAT.minds.0.awake", "VEFR_COMBAT.minds.1.awake",
    "VEFR_COMBAT.enemies.0.at", "VEFR_COMBAT.enemies.1.at",
    "text:#combat-live",
]

INTERACT = ["begin", "key:e", "wait:200"]

# A door and a stair open into `beyond` and refresh no snapshot of their
# own - the arrival is the only thing that publishes a combat window,
# and there is no arrival - so the run takes one quiet step south to end
# on a snapshot taken AFTER the noise. That step cannot wake a sleeper
# by itself: from the hero's [1, 2] the near ear is still eleven tiles
# away in a straight line (thirteen, for the stairs) - past E0d's
# Manhattan wake radius of ten - and the far ear further still, and
# neither has the near eye (sight 4) to see the hero. The wake the run
# reports is still the noise's alone.
AFTER_NOISE = ["dir:down", "wait:200"]


def loud_room(tmp_path, roster, transitions, pois=None):
    """`open_room`'s room with nothing else in reach but the one thing
    this test interacts with: no speakers, no chest book, and only the
    transitions it names."""
    p = open_room(tmp_path, roster)
    town = p / "acts" / "act-1" / "town"
    contract = json.loads((town / "contract.json").read_text(encoding="utf-8"))
    contract["pois"] = pois or {}
    (town / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    for book in (p / "library").iterdir():
        book.unlink()
    act_path = p / "acts" / "act-1" / "world.json"
    act = json.loads(act_path.read_text(encoding="utf-8"))
    act["speakers"] = {}
    act["transitions"] = transitions
    act_path.write_text(json.dumps(act), encoding="utf-8")
    return p


def test_opening_a_door_wakes_the_sleeper_in_earshot(tmp_path):
    """The hero opens the door beside it. A door carries 6 tiles, so
    `near-ear` - Chebyshev 6 away, twelve in a straight line, asleep for
    that alone - wakes, and `far-ear` at 7 does not. Opening the door
    spends no turn and the one step the run ends on cannot wake either
    of them, so nothing else is a candidate reason."""
    html = weave(loud_room(tmp_path, SIX_TILES, BEYOND), tmp_path)
    out = play(html, {"steps": INTERACT + AFTER_NOISE, "read": LOUD_READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.region"] == "town", \
        "the door opened with nowhere to go, so the fight is still this one"
    assert reads["VEFR_COMBAT.hero.at"] == [1, 2]
    assert reads["VEFR_COMBAT.minds.0.awake"] is True, \
        "opening a door 6 tiles away is inside the door's earshot"
    assert reads["VEFR_COMBAT.minds.1.awake"] is False, \
        "one tile past the door's 6 is out of earshot"
    assert reads["VEFR_COMBAT.enemies.1.at"] == [8, 7], \
        "a sleeper the noise missed is still exactly where it spawned"


def test_opening_a_chest_wakes_the_sleeper_in_earshot(tmp_path):
    """A chest is 6 tiles of noise exactly as a door is, and it is a
    chest being opened whether the note inside it is a library book or
    not. The chest's own line in the combat log says it opened."""
    pack_dir = loud_room(tmp_path, SIX_TILES, [])
    (pack_dir / "library" / "side-cache.md").write_text(
        "---\ntitle: A Side Cache\nfound: map\nat: [2, 1]\n"
        "chest: yes\ndrops: cloudy-potion\nkind: note\n---\n"
        "A note left beside the wall.\n", encoding="utf-8")
    html = weave(pack_dir, tmp_path)
    out = play(html, {"steps": INTERACT, "read": LOUD_READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.region"] == "town"
    assert reads["VEFR_COMBAT.hero.at"] == [1, 1]
    assert "cloudy" in (reads["text:#combat-live"] or ""), \
        "the chest opened and handed over what it held"
    assert reads["VEFR_COMBAT.minds.0.awake"] is True, \
        "opening a chest 6 tiles away is inside the chest's earshot"
    assert reads["VEFR_COMBAT.minds.1.awake"] is False, \
        "one tile past the chest's 6 is out of earshot"
    assert reads["VEFR_COMBAT.enemies.0.at"] == [7, 7]
    assert reads["VEFR_COMBAT.enemies.1.at"] == [8, 7]


def test_using_stairs_wakes_the_sleeper_in_earshot(tmp_path):
    """Stairs carry 8, so the pair stands two tiles further east than
    the doors': `near-ear` is Chebyshev 8 away and wakes, `far-ear` at 9
    does not. The tile is a stair because the region's `pois` names it
    one - the same rule the player's own candidate list reads - and
    using it spends no turn either."""
    p = loud_room(tmp_path, EIGHT_TILES, BEYOND, {"2,1": "the stair down"})
    html = weave(p, tmp_path)
    out = play(html, {"steps": INTERACT + AFTER_NOISE, "read": LOUD_READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.region"] == "town", \
        "the stair was used with nowhere to go, so the fight is this one"
    assert reads["VEFR_COMBAT.hero.at"] == [1, 2]
    assert reads["VEFR_COMBAT.minds.0.awake"] is True, \
        "using stairs 8 tiles away is inside the stair's earshot"
    assert reads["VEFR_COMBAT.minds.1.awake"] is False, \
        "one tile past the stair's 8 is out of earshot"
    assert reads["VEFR_COMBAT.enemies.1.at"] == [10, 7], \
        "a sleeper the noise missed is still exactly where it spawned"


def test_an_unknown_loud_event_carries_nothing(tmp_path):
    """A kind nobody declared is not a noise: the table is closed, so a
    typo in a call site wakes nobody rather than waking the floor."""
    out = noise_read(tmp_path, {"size": 20, "kinds": {"sneeze": [[1, 3], [1, 4]]}})
    assert out["radii"].get("sneeze") in (None, 0)
    assert [e["awake"] for e in out["kinds"]["sneeze"]] == [False, False]


# ---- 3. the warden ----

def test_the_warden_is_awake_and_hunts_the_hero_out_of_sight(tmp_path):
    """The warden does not sleep, and it hunts (ADR 0014, owner
    decision 2 of 2026-10-04).

    Two separate claims, and this fixture is built so one turn can only
    satisfy one of them at a time. The hero ends at [2, 1], ten tiles
    from the warden: awake, because ten is the default wake radius, and
    out of the hero's sight, because the warden's own is six. So the
    generic "out of sight" branch is the one that runs - and the
    ordinary monster beside it is asleep, twelve tiles out, so the drift
    toward a neighbour is the other answer and not the only one.

    Hunted: the warden walks WEST, one tile closer to the hero at
    [2, 1], from [12, 1] to [11, 1]. Drifted: it would have walked
    EAST, to [13, 1] toward the guard. `test_an_ordinary_monster_drifts`
    below puts the same two monsters on the same tiles with no warden
    mark and gets the east step, so this turn is the mark and nothing
    else."""
    html = weave(open_room(tmp_path, WARDEN), tmp_path)
    out = play(html, {"steps": ["begin", "walk:right"], "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.hero.at"] == [2, 1]
    assert reads["VEFR_COMBAT.minds.0.awake"] is True, \
        "the warden is awake without the hero ever coming near it"
    assert reads["VEFR_COMBAT.enemies.0.at"] == [11, 1], \
        "an awake warden out of the hero's sight walks at the hero, not " \
        "at its neighbour: [11, 1] is toward the hero, [13, 1] is the " \
        "drift every other awake monster does"
    assert reads["VEFR_COMBAT.minds.1.awake"] is False, \
        "the guard beside it is an ordinary sleeper and stays asleep"
    assert reads["VEFR_COMBAT.enemies.1.at"] == [14, 1]


def test_an_ordinary_monster_drifts(tmp_path):
    """The control: the same room, the same two monsters, the same
    numbers, and no warden mark on the first.

    It is awake for the same reason and out of the hero's sight for the
    same reason, so the only thing that could differ is the mark - and
    it drifts east toward the sleeping guard, exactly as it always has.
    A warden rule that reached past the mark, or one that changed the
    drift for everybody, fails here."""
    html = weave(open_room(tmp_path, DRIFTER), tmp_path)
    out = play(html, {"steps": ["begin", "walk:right"], "read": READS})
    assert out["errors"] == []
    reads = out["reads"]
    assert reads["VEFR_COMBAT.minds.0.awake"] is True, \
        "the first monster is awake in exactly the same way the warden was"
    assert reads["VEFR_COMBAT.enemies.0.at"] == [13, 1], \
        "an ordinary awake monster out of sight drifts toward its " \
        "neighbour, which is what the warden no longer does"
    assert reads["VEFR_COMBAT.minds.1.awake"] is False
    assert reads["VEFR_COMBAT.enemies.1.at"] == [14, 1]
