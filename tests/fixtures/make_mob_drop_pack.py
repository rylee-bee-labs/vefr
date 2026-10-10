"""Build the Section-drops fixture pack (families whose drops must be real).

A generated floor's monsters are drawn from the Section's family table, and
each monster carries whatever `drops` its Blueprint family names - that is
`vefr.delve.mobs_at`, and it is the only way a kill on floor 12 pays
anything. So a family naming an item the pack never describes is a monster
that validates and then hands the player nothing.

This fixture is the door for that: `world.json` with a catalog, a
`blueprint.json` whose families carry `drops`, and one `sections/cellar.json`
naming those families by id - the three files `vefr check` reads. Every
argument is a default a real pack would keep, so a test that wants the
defect asks for exactly one wrong thing and changes nothing else.

Neutral engine-test canon only: the hazards are named creatures and the
place is a cellar, exactly as the other fixtures are.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

# The real `vefr` front door, in a subprocess: a lock is written by the
# front door or it is not a lock (blueprint_helpers.vefr is the same run).
CLI = ("import sys; from vefr.cli import vefr_main; "
       "sys.argv = ['vefr'] + sys.argv[1:]; sys.exit(vefr_main())")


def normalize(pack: Path) -> None:
    """Refresh the pack's Blueprint lock, the shipped way."""
    proc = subprocess.run([sys.executable, "-c", CLI, "normalize",
                           "--pack", str(pack), "--out", str(pack)],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr

# The catalog the player really gets: `pebble` is describable, `blank` has
# an entry and no name, so `cli._player_items` - the bake's own read -
# drops it before anything is offered to the player.
ITEMS = {
    "pebble": {"name": "a grey pebble", "sprite": "pebble", "value": 1},
    "blank": {"sprite": "orb"},
}

# The families the Section names. `drops` rides on the family record, so a
# Section gets it by naming the family - there is no other place to write it.
FAMILIES = {
    "rat": {"defaults": {"name": "a cellar rat", "sprite": "rat",
                         "hp": 3, "atk": 1, "xp": 2}},
    "moth": {"defaults": {"name": "a pale moth", "sprite": "moth",
                          "hp": 2, "atk": 1, "xp": 1, "sight": 3}},
}

# The Section that draws them, in the one Section contract: `id` and
# `families` are the only required keys.
SECTION = {
    "section": 1, "id": "cellar", "floors": 3,
    "size": {"w": [32, 36], "h": [24, 26]},
    "rooms": [6, 8],
    "families": [
        {"family": "rat", "weight": 2, "depth": [1, 3]},
        {"family": "moth", "weight": 1, "depth": [1, 3]},
    ],
}


def blueprint(families=None) -> dict:
    """A Blueprint carrying `families`, with no regions of its own."""
    return {"blueprint": 1, "families": dict(FAMILIES if families is None
                                              else families), "regions": {}}


def build(dest: Path, families=None, items=None, section=None,
          name="mob-drop-test", normalize_pack=True) -> Path:
    """The pack under `dest`, with the three files the check reads.

    `families` is the Blueprint's `families` object, `items` the catalog
    (`None` writes no `items` key at all - a pack that declares none), and
    `section` the Section pack written at `sections/cellar.json`.

    The lock is refreshed before the catalog and the Section are written,
    because `vefr normalize` validates the pack it is writing and refuses
    a bad drop before it has written anything - so a fixture whose whole
    point is a bad drop would never finish building. The Section and the
    catalog come last: the lock is about the Blueprint, and the pack the
    player bakes is the one written last.
    """
    pack = dest / "worlds" / name
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["name"] = name
    world_json.write_text(json.dumps(world), encoding="utf-8")

    (pack / "blueprint.json").write_text(
        json.dumps(blueprint(families)), encoding="utf-8")

    if normalize_pack:
        normalize(pack)

    world = json.loads(world_json.read_text(encoding="utf-8"))
    # The catalog is written OVER the sample's own, never instead of it:
    # the copied shelf's chest book drops `torch` and `chalked-map`, and
    # that book is removed below anyway, but a fixture that also tripped
    # the chest check would prove nothing about Section families.
    if items is not None:
        world["items"] = {**world.get("items", {}), **items}
    else:
        world.pop("items", None)
    world_json.write_text(json.dumps(world), encoding="utf-8")

    # The sample's shelf is not this fixture's subject: a chest book is
    # checked by its own rule (`library._chest_drop_errors`), and every
    # sentence here is about a Section family's drops.
    shutil.rmtree(pack / "library")

    (pack / "sections").mkdir(exist_ok=True)
    (pack / "sections" / "cellar.json").write_text(
        json.dumps(SECTION if section is None else section, indent=2) + "\n",
        encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(str(build(Path(sys.argv[1]))))