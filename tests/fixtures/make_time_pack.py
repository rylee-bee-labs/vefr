"""Build the neutral time fixture pack (vefr E3: time that costs something).

Two packs from one builder, both engine-test canon only - no story text
from any pitch:

  * `time-test` - declares `"time": {"rest": true, "rail": "locked",
    "persist": true}`, three phases, and two rules: one that says a
    line on every `phase-changes` (so a Rest press is visible), and one
    whose `if` reads the STANDING phase (so it can only fire while the
    watch is at `highwater`).
  * `no-time-test` - the very same pack with no `time` block at all: the
    free phase rail, no Rest verb, and nothing extra written to storage.

    hero start ........ [1, 1]
    speaker "watcher" . [3, 1]   stand at [2, 1] and Interact: distance 1
    phases ............ whispers -> lowwater -> highwater (-> whispers)
"""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PHASES = {
    "whispers": "the hour the harbour talks to itself",
    "lowwater": "the hour the mud is bare",
    "highwater": "the hour the boats can come in",
}

TOWN_MAP = [
    "#####",
    "#...#",
    "#####",
]

# The one rule that fires on every turn of the watch, so a Rest press is
# visible in the WHY log whatever the phase is.
TURN_RULE = {
    "id": "the-watch-turns",
    "when": {"phase-changes": {"to": "lowwater"}},
    "once": False,
    "then": [{"say": "The tide goes out."}],
}

# The rule that reads the STANDING phase: it says nothing in whispers or
# lowwater, and its line only appears while the watch is at highwater.
HIGHWATER_RULE = {
    "id": "boats-may-come-in",
    "when": {"comes-near": {"who": "watcher", "distance": 2}},
    "if": [{"phase": "highwater"}],
    "then": [{"say": "The boats can come in now."}],
}

WATCHER_FRAGMENTS = (
    "- The water keeps its own hours.\n"
    "- Count from the low, never from the bells.\n"
)


def _legend() -> dict:
    return {
        ".": {"base": ["#212a20"]},
        "#": {"base": ["#2a3a33"], "solid": True},
    }


def _world(name: str, time_block) -> dict:
    world = {
        "name": name,
        "title": "Time Test",
        "description": "A minimal fixture pack with a time block.",
        "surface": "combat",
        "phases": PHASES,
        "town": {
            "tile": 32,
            "bg": "#131311",
            "hero_start": [1, 1],
            "watch": {
                "tower": [1, 1],
                "r_by_phase": {k: 1 for k in PHASES},
                "overlay": "rgba(0,0,0,0.3)",
            },
            "sanctuary_tiles": ["."],
            "water_by_phase": {k: "low" for k in PHASES},
            "flood_tiles": [],
            "legend": _legend(),
            "hero_color": "#e8e5df",
            "map": TOWN_MAP,
            "pois": {},
        },
        "speakers": {
            "watcher": {
                "name": "The Watcher",
                "at": [3, 1],
                "near": "the mooring post",
                "voice_file": "voices/watcher.md",
                "seeds": {k: "The water keeps its own hours." for k in PHASES},
            }
        },
        "rules": [TURN_RULE, HIGHWATER_RULE],
    }
    if time_block is not None:
        world["time"] = time_block
    return world


def build(dest: Path, *, name: str = "time-test",
          time_block={"rest": True, "rail": "locked", "persist": True}) -> Path:
    """Write the pack and return its path. `time_block=None` leaves the
    `time` key out entirely, which is the pack that must play as before."""
    pack = dest / "worlds" / name
    if pack.exists():
        shutil.rmtree(pack)
    (pack / "voices").mkdir(parents=True)
    (pack / "world.json").write_text(
        json.dumps(_world(name, time_block), indent=1), encoding="utf-8")
    (pack / "voices" / "watcher.md").write_text("# The Watcher\n",
                                               encoding="utf-8")
    (pack / "voices" / "watcher.fragments.md").write_text(
        WATCHER_FRAGMENTS, encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(str(build(Path(sys.argv[1]))))