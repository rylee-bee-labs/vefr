"""The spell table, Python against the player (ADR 0018), the way
`test_event_table.py` holds the event table.

A spell record is written down three times: the shape table that
`vefr check` holds a pack to (`shapes.SPELL` inside `shapes.SPELLS`), the
bake that hands it to the woven player (`cli._player_spells`), and the
player part that reads it (`web/player/parts/225-spells.js`). The other
spell tests read the JavaScript alone; this file holds the three to one
another, so a key added to one and not the others fails here:

  - every key the shape accepts on a spell is baked, in the same order,
    and nothing else is;
  - every field the player reads off a spell record is a key the shape
    accepts, and every key the shape accepts is read by the player;
  - the player reads the block's `spells` list, and the item key a book
    teaches with is the one `shapes.ITEM_TAUGHT` names.
"""

import re
from pathlib import Path

from vefr import cli, shapes

ROOT = Path(__file__).resolve().parents[1]
PART = ROOT / "web" / "player" / "parts" / "225-spells.js"
GOLD = ROOT / "web" / "player" / "parts" / "180-gold.js"

# A record that uses every key the shape has, so the bake has no reason to
# leave one out.
FULL = {"id": "ember-bolt", "name": "an ember bolt", "school": "ember",
        "level": 1, "heal": 3}


def _code(path: Path) -> str:
    """A part with its `//` comments cut, so a sentence about a field is not
    taken for a read of it."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cut = line.find("//")
        out.append(line if cut < 0 else line[:cut])
    return "\n".join(out)


def _record_fields_read() -> set[str]:
    """Every field the player reads off a spell record.

    In this part a record is only ever held as `r`, `spell`, `s` or
    `records[i]` (`spellRecords`, `spellById`, `spellsKnown`,
    `renderSpellList`); the test below fails if one of those names stops
    meaning a record and starts reading something else.
    """
    code = _code(PART)
    return set(re.findall(r"\b(?:r|spell|s|records\[i\])\.([a-z_]+)\b", code))


def _spell_keys() -> list[str]:
    return [k.name for k in shapes.SPELL.keys]


def test_the_block_holds_its_records_under_spells():
    assert [k.name for k in shapes.SPELLS.keys] == ["schools", "spells"]
    spells_key = next(k for k in shapes.SPELLS.keys if k.name == "spells")
    assert spells_key.sub is shapes.SPELL
    # The player reads the records from the block's `spells` list.
    assert "block.spells" in _code(PART)


def test_the_bake_carries_exactly_the_shapes_keys_in_order():
    baked = cli._player_spells({"spells": {"schools": ["ember"],
                                           "spells": [FULL]}})
    assert list(baked) == [k.name for k in shapes.SPELLS.keys]
    assert [list(r) for r in baked["spells"]] == [_spell_keys()]
    assert baked["spells"] == [FULL]


def test_the_player_reads_exactly_the_keys_the_shape_accepts():
    # Both directions: a key the shape accepts that the player never reads
    # is a promise the woven file does not keep, and a field the player
    # reads that the shape does not accept is one no checked pack can hold.
    assert _record_fields_read() == set(_spell_keys())


def test_a_book_teaches_with_the_item_key_the_shape_names():
    assert shapes.ITEM_TAUGHT == ("spell",)
    gold = _code(GOLD)
    assert "def.spell" in gold
    assert "learnSpellFromBook(def.spell)" in gold
