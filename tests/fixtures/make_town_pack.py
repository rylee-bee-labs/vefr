"""Build the town-states fixture pack (sample-world + a descent + town states).

Slice E8c (ADR 0015): the per-game `story_end` flag, the list-form
`town_states`, the town gate and the progress walk.

The pack is the sample's own town plus three more authored regions, two
Sections in `sections/`, a `descent` naming them by id, and two rules that
record the two vault notes. Every state region is an ordinary authored
region - a copy of the sample's town - because that is the whole claim
`town_states` makes: no patch, no new runtime language.

Neutral engine-test canon only: a town, a tavern, and two Sections whose
wardens are named creatures. The story ends on the second Section's note,
which is what makes the default `king-slain` reachable by the walk.
"""

import copy
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"
STAMPS = ROOT / "tests" / "fixtures" / "stamps"

# The sample town's own threshold tile, the same one the descent fixture
# uses (make_descent_pack.ENTRY_AT).
ENTRY_AT = [7, 5]

# The regions that carry the story. `town` is the sample's own; the rest
# are copies of it with a background the test can tell apart, so a test
# that reads the map back knows which face of the town it loaded.
STATE_REGIONS = {
    "town-act-2": {"bg": "#141a14"},
    "town-after": {"bg": "#1a1410"},
    "tavern": {"bg": "#161218"},
}

# One block per region that changes. The list form is ADR 0015 Amendment 1
# section 3; the single-block form is what the ADR wrote first, and both
# are the same records.
TOWN_STATES = [
    {"region": "town", "states": [
        {"id": "act-2", "when": "vault-1-read", "use": "town-act-2"},
        {"id": "after-the-end", "when": "king-slain", "use": "town-after"},
    ]},
    {"region": "tavern", "states": [
        {"id": "full", "when": "vault-1-read", "use": "tavern"},
    ]},
]

FLAGS = {
    "vault-1-read": "the note behind the first vault door has been read",
    "king-slain": "the story is over",
}

# One rule per vault note: reading it records that the vault has been read
# (ADR 0015's vault record, `sets`). These are the setters the progress
# walk looks for, and the only rules this pack carries.
RULES = [
    {"id": "the-first-note-is-read", "when": {"opens": {"what": "the-first-note"}},
     "then": [{"set": "vault-1-read"}], "once": True},
    {"id": "the-second-note-is-read", "when": {"opens": {"what": "the-second-note"}},
     "then": [{"set": "king-slain"}], "once": True},
]

BOOKS = {
    "the-first-note": ("A note in the first vault", "cellar-0-3", "vault-note",
                       "The first of what was kept."),
    "the-second-note": ("A note in the second vault", "hollow-0-3", "vault-note",
                        "The last of what was kept."),
}


def section(index, ident, sets, warden):
    """One Section pack: three floors, the third of them the warden floor."""
    return {
        "section": index,
        "id": ident,
        "floors": 3,
        "size": {"w": [48, 56], "h": [36, 44]},
        "rooms": [10, 14],
        "pattern": ["entry", "landing", "warden"],
        "families": [{"family": "rat", "weight": 2, "depth": [1, 3]}],
        "stamps": ["cellar"],
        "warden": warden,
        "vault": {"stamp": "vault-cellar", "sets": sets},
    }


SECTIONS = {
    "cellar": section(1, "cellar", "vault-1-read", "cellar-boss"),
    "hollow": section(2, "hollow", "king-slain", "hollow-warden"),
}

DESCENT = {
    "run_seed": "run-a",
    "entry": {"region": "town", "at": list(ENTRY_AT)},
    "sections": ["cellar", "hollow"],
}


def _named_stamps(sections: dict) -> set[str]:
    """The stamps the Sections can draw, by the engine's own rule.

    A Section names its stamps by tag and its vault by id, and the
    question a floor asks is `delve_v3`'s, so the answer is the rooms the
    pack's own Sections can place and none of the ones they cannot. A
    stamp no Section names never draws, and the fit rule `vefr check`
    runs (vefr#346) would refuse the pack over a room it never uses:
    `throne-hall` is 21x21 and these floors start at 48x36.
    """
    from vefr import delve_v3, stamps
    records = stamps.load(STAMPS)
    named = set()
    for section in sections.values():
        floors = section.get("floors")
        depths = range(1, int(floors) + 1) \
            if isinstance(floors, int) and not isinstance(floors, bool) and floors > 0 \
            else range(1, 2)
        for depth in depths:
            named.update(record["id"]
                         for record in delve_v3.stamp_pool(section, records, depth))
    return named


def stamp_records(pack: Path):
    """The pack's stamp records, the way the weave carries them.

    `vefr.sections`/`vefr.delve` read them from a descent block; a test
    that draws a floor in Python needs them there too, exactly as
    `weave_html` writes them in."""
    from vefr import stamps
    return json.loads(json.dumps(stamps.load(Path(pack) / "stamps")))


def _region(pack: Path, name: str, bg: str):
    """One more authored region, copied from the sample's own town."""
    act = pack / "acts" / "act-1"
    shutil.copytree(act / "town", act / name)
    path = act / name / "contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["bg"] = bg
    path.write_text(json.dumps(contract, indent=2), encoding="utf-8")


def build(dest: Path, town_states=None, sections=None, descent=None,
          rules=None, story_end=None) -> Path:
    """Build the pack into `dest`, overriding any part of it."""
    pack = Path(dest) / "town-test"
    if pack.exists():
        shutil.rmtree(pack)
    pack.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SAMPLE, pack)

    for name, spec in STATE_REGIONS.items():
        _region(pack, name, spec["bg"])
    act_world = pack / "acts" / "act-1" / "world.json"
    act = json.loads(act_world.read_text(encoding="utf-8"))
    act["regions"] = ["town"] + sorted(STATE_REGIONS)
    act_world.write_text(json.dumps(act, indent=2), encoding="utf-8")

    (pack / "sections").mkdir(exist_ok=True)
    built = sections if sections is not None else SECTIONS
    for ident, record in built.items():
        (pack / "sections" / f"{ident}.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8")

    # The stamp pack the Sections draw their warden hall and vault from
    # (ADR 0013): the same committed stamps E8b's fixtures use, carrying
    # only the rooms these Sections name (`_named_stamps`), so the pack
    # ships no room it can never place.
    named = _named_stamps(built)
    (pack / "stamps").mkdir()
    for path in sorted(STAMPS.glob("*.json")):
        if path.stem in named:
            shutil.copy(path, pack / "stamps" / path.name)

    library = pack / "library"
    library.mkdir(exist_ok=True)
    for ident, (title, region, place, text) in BOOKS.items():
        (library / f"{ident}.md").write_text(
            f"---\ntitle: {title}\nfound: map\nregion: {region}\n"
            f"place: {place}\n---\n{text}\n", encoding="utf-8")

    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    # This catalog replaces the sample's, so the pack can no longer hand
    # over what the inherited chest book promises: a chest that drops ids
    # world.json does not declare opens on nothing, which `vefr check`
    # refuses by name (D114). The one item here is the pebble the walk's
    # `give` test needs and nothing else, so that book goes - the fixture
    # is about town states, not about a satchel.
    world["items"] = {"pebble": {"name": "a grey pebble", "value": 1}}
    (pack / "library" / "a-travellers-satchel.md").unlink()
    world["player"] = {"hp": 40, "atk": 4, "gold": 0,
                       "wake": {"region": "town", "at": [3, 4]}}
    world["flags"] = copy.deepcopy(FLAGS)
    world["rules"] = copy.deepcopy(RULES if rules is None else rules)
    world["town_states"] = copy.deepcopy(
        TOWN_STATES if town_states is None else town_states)
    block = copy.deepcopy(DESCENT if descent is None else descent)
    if story_end is not None:
        block["story_end"] = story_end
    world["descent"] = block
    world_json.write_text(json.dumps(world), encoding="utf-8")
    return pack


if __name__ == "__main__":
    print(str(build(Path(sys.argv[1]))))