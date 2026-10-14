"""E0d: sleeping monsters and a radius-bounded distance flood.

Before E0d every living monster takes a turn on every player turn: the
monster turn floods the whole floor (`distMap`) to path, and any monster
out of the hero's sight drifts toward its nearest ally. E0d bounds that
world in two ways:

  1. A monster is ASLEEP unless it is within max(10, its own sight)
     tiles (Manhattan) of the hero. An asleep monster does not move,
     does not attack and does no work at all. Every monster here carries
     the default sight of 6, so the wake radius is 10 tiles.
  2. The distance flood stops at (the wake distance) + 4 tiles around
     the hero - 14 tiles at sight 6 - instead of covering the whole
     floor.

To make the flood observable the implementation publishes
`window.VEFR_FLOOD_STATS` beside the other harness surfaces:
`{floods, tiles, maxSpan}`, reset at the start of every `enemyTurn()`
and updated by `distMap` for that turn only. The harness reads once at
the end of a run, so every read below is the LAST monster turn.

What is proven here:

  - two far monsters hold still while the hero walks five tiles; under
    the old code the pair drifts toward each other, so this fails today;
  - a lone far monster wakes and steps toward the hero when the hero
    comes within the wake radius; today it walks in as soon as the
    hero is inside its own sight - twelve tiles out, where this test
    wants it still asleep at eleven - so this fails today;
  - the flood stats are published and stay inside the radius; today the
    global does not exist and the flood covered the whole floor, so
    this fails today;
  - an awake monster inside the radius keeps chasing one step a turn;
  - the fight next to the hero (the pale thing walks in, the cellar rat
    hits back) is exactly what it was. That one passed before E0d too:
    it is the guard, not the proof.

Every fixture is a fixed map with fixed numbers - no randomness, no
wall-clock, no mocks. Run with: bash tests/run.sh tests/test_monster_sleep.py
"""

import json
import shutil

import pytest

from play_kit import pack, play, weave

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# The wake radius is max(10, the monster's own sight); the bounded
# flood may reach the wake radius plus four tiles from the hero.
WAKE = 10
RADIUS = WAKE + 4

# One big open room: 41x25 with a solid border, the hero starting in
# the corner at [1, 1]. Open tiles run all the way to the far corner,
# so a monster can stand far away and the hero can walk toward it.
WIDTH, HEIGHT = 41, 25

LEGEND = {".": {"base": ["#212a20"]}, "#": {"base": ["#2a2e33"], "solid": True}}

# Two monsters far from the hero's corner. Before E0d each monster out
# of the hero's sight walks toward its nearest ally, so the pair moves
# on the very first turn; asleep, neither ever moves.
FAR_PAIR = [
    {"id": "far-thing", "name": "a far thing", "at": [35, 19],
     "hp": 4, "atk": 1, "sprite": "rat"},
    {"id": "far-kin", "name": "a far kin", "at": [37, 21],
     "hp": 4, "atk": 1, "sprite": "rat"},
]

# A lone monster to the east with a sight of its own: 19 tiles from
# the hero's corner at the start. Sight 12 makes its wake radius
# max(10, 12) = 12, the same as its sight, so for this monster awake
# and in sight always coincide - E0d never has to make it charge the
# hero from outside its own sight.
LONER = [
    {"id": "distant-thing", "name": "a distant thing", "at": [20, 1],
     "hp": 4, "atk": 1, "sight": 12, "sprite": "rat"},
]

# A monster six tiles out: inside its own sight and inside the wake
# radius from the first turn, so it chases every turn.
CHASER = [
    {"id": "chasing-thing", "name": "a chasing thing", "at": [7, 1],
     "hp": 4, "atk": 1, "sight": 6, "sprite": "rat"},
]

# The flood test's monster: sight 6 explicitly, so the radius the test
# reads against is max(10, 6) + 4 = 14.
WATCHER = [
    {"id": "near-thing", "name": "a near thing", "at": [7, 1],
     "hp": 4, "atk": 1, "sight": 6, "sprite": "rat"},
]


def big_room(tmp_path, enemies):
    """The combat fixture with its town swapped for the big open room.
    The act keeps its regions; only the town's map, contract and
    enemies are the test's own. The hero starts in the corner."""
    p = pack(tmp_path, "combat")
    town = p / "acts" / "act-1" / "town"
    wall = "#" * WIDTH
    open_row = "#" + "." * (WIDTH - 2) + "#"
    rows = [wall] + [open_row] * (HEIGHT - 2) + [wall]
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


def walk_right(n):
    """Begin, then n steps to the right along the open top row."""
    return ["begin", "walk:" + ",".join(["right"] * n)]


def room_tiles(pack_dir, hero_at):
    """(tiles within the flood radius of `hero_at`, walkable tiles in
    the whole room). The room's only solid character is `#`."""
    rows = (pack_dir / "acts" / "act-1" / "town" / "map.md").read_text(
        encoding="utf-8").splitlines()
    within = 0
    walkable = 0
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if abs(x - hero_at[0]) + abs(y - hero_at[1]) <= RADIUS:
                within += 1
            if ch != "#":
                walkable += 1
    return within, walkable


def test_far_monsters_stay_asleep_while_the_hero_walks(tmp_path):
    html = weave(big_room(tmp_path, FAR_PAIR), tmp_path)
    out = play(html, {"steps": walk_right(5),
                      "read": ["VEFR_COMBAT.hero.at",
                               "VEFR_COMBAT.enemies.0.at",
                               "VEFR_COMBAT.enemies.1.at"]})
    assert out["errors"] == []
    assert out["reads"]["VEFR_COMBAT.hero.at"] == [6, 1]
    # The pair stands 47 and 51 tiles from the hero's new spot - far
    # beyond the wake radius - so both are asleep and hold still.
    # Before E0d they drift toward each other on the first turn and
    # neither tile stays put.
    assert out["reads"]["VEFR_COMBAT.enemies.0.at"] == [35, 19], \
        "a monster far beyond the wake radius does not move while the hero walks"
    assert out["reads"]["VEFR_COMBAT.enemies.1.at"] == [37, 21], \
        "the second far monster does not drift toward its ally either"


def test_a_far_monster_wakes_and_steps_toward_the_hero(tmp_path):
    html = weave(big_room(tmp_path, LONER), tmp_path)
    reads = ["VEFR_COMBAT.hero.at", "VEFR_COMBAT.enemies.0.at"]
    # Six steps: the hero stands at [7, 1], 13 tiles out - one tile
    # beyond this monster's wake radius, max(10, sight 12) = 12, still asleep.
    still = play(html, {"steps": walk_right(6), "read": reads})
    assert still["errors"] == []
    assert still["reads"]["VEFR_COMBAT.hero.at"] == [7, 1]
    assert still["reads"]["VEFR_COMBAT.enemies.0.at"] == [20, 1], \
        "one tile outside the wake radius the monster is still asleep"
    # One more step: [8, 1] is exactly 12 tiles from the monster, the
    # wake radius, so it wakes and steps one tile toward the hero.
    # Before E0d a lone monster out of its sight never moves at all.
    woken = play(html, {"steps": walk_right(7), "read": reads})
    assert woken["errors"] == []
    assert woken["reads"]["VEFR_COMBAT.hero.at"] == [8, 1]
    assert woken["reads"]["VEFR_COMBAT.enemies.0.at"] == [19, 1], \
        "the monster wakes and moves toward the hero on the wake turn"


def test_the_flood_stays_inside_the_wake_radius(tmp_path):
    p = big_room(tmp_path, WATCHER)
    html = weave(p, tmp_path)
    out = play(html, {"steps": walk_right(1),
                      "read": ["VEFR_COMBAT.hero.at", "VEFR_FLOOD_STATS"]})
    assert out["errors"] == []
    stats = out["reads"]["VEFR_FLOOD_STATS"]
    assert isinstance(stats, dict), \
        "the monster turn publishes window.VEFR_FLOOD_STATS for the harness"
    hero_at = out["reads"]["VEFR_COMBAT.hero.at"]
    assert hero_at == [2, 1]
    within, walkable = room_tiles(p, hero_at)
    assert stats["floods"] >= 1, "the chasing monster paid for a flood"
    assert stats["maxSpan"] <= RADIUS, \
        "no flood visits a tile past the wake radius plus four"
    assert stats["tiles"] <= within, \
        "the flood visits at most the tiles inside the radius"
    assert stats["tiles"] * 2 < walkable, \
        "the flood covers far less than the whole floor"


def test_an_awake_monster_keeps_chasing_inside_the_radius(tmp_path):
    html = weave(big_room(tmp_path, CHASER), tmp_path)
    reads = ["VEFR_COMBAT.hero.at", "VEFR_COMBAT.hero.hp",
             "VEFR_COMBAT.enemies.0.at"]
    one = play(html, {"steps": walk_right(1), "read": reads})
    two = play(html, {"steps": walk_right(2), "read": reads})
    three = play(html, {"steps": walk_right(3), "read": reads})
    assert one["errors"] == []
    assert two["errors"] == []
    assert three["errors"] == []
    # Six tiles at the start - inside both its sight and the wake
    # radius - so it steps one tile closer per hero turn, the short
    # way across the room.
    assert one["reads"]["VEFR_COMBAT.hero.at"] == [2, 1]
    assert one["reads"]["VEFR_COMBAT.hero.hp"] == 3
    assert one["reads"]["VEFR_COMBAT.enemies.0.at"] == [6, 1], \
        "the monster steps one tile closer after the first turn"
    assert two["reads"]["VEFR_COMBAT.enemies.0.at"] == [5, 1], \
        "and one more tile closer after the second turn"
    # Third turn it is adjacent: it hits instead of stepping.
    assert three["reads"]["VEFR_COMBAT.hero.at"] == [4, 1]
    assert three["reads"]["VEFR_COMBAT.hero.hp"] == 2, \
        "adjacent the monster hits the hero"
    assert three["reads"]["VEFR_COMBAT.enemies.0.at"] == [5, 1]


def test_the_fight_next_to_the_hero_is_unchanged(tmp_path):
    """The guard, not the proof: the combat fixture's own fight, pinned
    so E0d cannot change what happens right next to the hero. This one
    passes before the change too."""
    html = weave(pack(tmp_path, "combat"), tmp_path)
    out = play(html, {"steps": ["begin", "walk:right"], "read": [
        "VEFR_COMBAT.region", "VEFR_COMBAT.hero.at", "VEFR_COMBAT.hero.hp",
        "VEFR_COMBAT.enemies.0.id", "VEFR_COMBAT.enemies.0.at",
        "VEFR_COMBAT.enemies.0.hp", "VEFR_COMBAT.enemies.1.id",
        "VEFR_COMBAT.enemies.1.at", "text:#combat-live"]})
    assert out["errors"] == []
    reads = out["reads"]
    # The bump lands on the cellar rat without moving the hero, and
    # the rat hits back for 1 from the tile it stands on.
    assert reads["VEFR_COMBAT.region"] == "town"
    assert reads["VEFR_COMBAT.hero.at"] == [1, 1]
    assert reads["VEFR_COMBAT.hero.hp"] == 2
    assert reads["VEFR_COMBAT.enemies.0.id"] == "cellar-rat"
    assert reads["VEFR_COMBAT.enemies.0.at"] == [2, 1]
    assert reads["VEFR_COMBAT.enemies.0.hp"] == 2
    # The line ends with the one-time strike hint: this is the first
    # fight, and walking into an enemy is the attack (vefr #464).
    assert reads["text:#combat-live"] == (
        "a cellar rat hits you for 1. Walk into an enemy to strike it.")
    # The pale thing, six tiles out and inside its sight, walks one
    # tile toward the hero on the same turn.
    assert reads["VEFR_COMBAT.enemies.1.id"] == "pale-thing"
    assert reads["VEFR_COMBAT.enemies.1.at"] == [6, 1]
