"""A neutral pack that rolls its loot AND reads it in town
(ADR 0017, T3 slice 2).

The rolled-loot fixture (`make_rolled_pack`) already builds a pack whose
loot is drawn; this one is the same pack plus the one thing slice 2 adds:
a speaker who reads things. `build(dest, reader=...)` writes that speaker
into the act's own world.json, exactly where a pack author would, and the
default reader is the good one - `"identify": "true"`, a tile of its own,
and the phase seeds every other speaker of the pack carries.

Pass `reader` to write something broken instead: the three refusals in
`tests/test_identify.py` are proved on this fixture with each of the three
wrong declarations, so a refusal is tested against the shape a pack would
really have rather than a dict invented for the test.

Neutral engine-test canon only, like every other fixture here: the people
are the Keeper and the Reader, the things are a pebble, a ring and a
cloudy potion.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

ACT_WORLD = ("acts", "act-1", "world.json")

# The good declaration: a speaker one tile from the Keeper who reads the
# things the hero carries. `at` is a walkable, reachable tile of the
# sample's own town and `seeds` cover the pack's two phases, so a pack
# carrying this validates for the reasons it should and no others.
# `voice_file` is part of the speaker contract (maplab refuses a speaker
# with no voice), so the fixture writes that file beside the others.
READER = {
    "name": "The Reader",
    "at": [6, 4],
    "near": "the lamp",
    "voice_file": "voices/reader.md",
    "seeds": {
        "dusk": "The lamp burns low. Set it down and I will look.",
        "dawn": "Daylight is honest enough. Give it here.",
    },
    "identify": "true",
}

# What the reader says of their own trade, and nothing more. It names no
# trait and says no trait is worth anything: what a trait MEANS is not this
# slice's question, and no fixture may answer it by writing the words a
# model would otherwise have had to invent.
VOICE = """You are the Reader of the lamp in Emberfield. You read what is
handed to you, and you say only what you can see in it.

- Speak in short sentences: 1-3 of them.
- Name what you read, plainly, in the order it is written.
- Never guess, and never say what a word is worth.
- You are speaking TO the one who handed it over."""


def build(dest: Path, reader=None, reader_key: str = "reader",
          voice: bool = True) -> Path:
    """The rolled-loot fixture plus a reader.

    `reader=None` writes the good one; pass a dict (or `reader=False` for
    no reader at all) to write something else. `reader_key` names the
    speaker, so a refusal test can put the same broken declaration on a
    different key. `voice=False` leaves the voice file unwritten, for the
    one test that wants to see what that refusal says.
    """
    sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
    import make_rolled_pack as mk

    pack = mk.build(dest)
    if reader is False:
        return pack
    act = pack.joinpath(*ACT_WORLD)
    world = json.loads(act.read_text(encoding="utf-8"))
    speakers = world.setdefault("speakers", {})
    speakers[reader_key] = json.loads(json.dumps(
        READER if reader is None else reader))
    act.write_text(json.dumps(world), encoding="utf-8")
    if voice:
        (pack / "voices" / f"{reader_key}.md").write_text(VOICE, encoding="utf-8")
    return pack


if __name__ == "__main__":
    import tempfile
    print(str(build(Path(tempfile.mkdtemp()))))