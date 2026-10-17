"""S0 (tighten-shapes). FROZEN: validator sentences are byte-identical across the schema-table migration.
The golden was captured on main before shapes.py existed (tests/golden/validator/gen.py). A change here needs a
written reason in the PR.

S2 added the `rules` and `album` blocks to FN, before the event migration and with none of the
captured values edited: the two `when` validators were the sentences this slice moves onto one
table and no case covered them. See tests/test_event_table.py.

E4 added the `section` block to FN, before `src/vefr/shapes.py` grew it and with none of the
captured values edited: the Section pack is the whole of PLAN.md section 2's data shapes, and no
case covered a single one of its refusals. Its expected sentences were written out by hand from the
table's own defaults and put in cases.json before the block existed, then re-captured from the code
afterwards to prove the block says them (tests/golden/validator/gen.py). A `section` case is not a
world block, so it carries a `section` and the pack's affix list and the resolver a Blueprint would
give, and FN is called with the whole case rather than with `c["world"]` - a change to how the
runner is called, not to any sentence it pins.

vefr #364 changed ONE case here, "a fog radius out of range": the ceiling on a Section's
`fog.radius` moved from 8 to a quarter of the widest floor `SIZE` allows (32), so the case's
value moved from 9 to 33 and its sentence from "between 2 and 8" to "between 2 and 32". That is
the whole of the written reason: the case still pins the same pointer, the same sentence shape and
the same place in the order - only the number the sentence quotes moved, and it moved because the
number in the table did. Every other case's bytes are untouched, including the low end.

E10 added the `endless` block to the `section` table, and ONE captured sentence moved: the
unknown-key sentence of two cases names every key the table holds, and it now ends "vault and
endless" because `endless` is a key of that table. No value changed, no pointer changed, no case
was dropped, and the new key was put LAST in the table so that every other name in that sentence
keeps the order and the position it always had. Five cases were ADDED for a block that did not
exist before ("an endless block with three one-field omens", "an omen that names two fields",
"omens with wrong values and an unknown key", "a warden's endless record, right and wrong" and
"a warden's endless affixes out of range"); their expected sentences were written out by hand from
the table's own defaults and then re-captured from the code, exactly as E4's were.

E2 (mending) changed ONE captured sentence the same way the event table's own twin test was
changed with it: the unknown-event sentence of the rules case '{"bogus": {}}' names every event
the table holds, and `mends` is now one of them, appended LAST so every other name keeps its
place. That is the whole of the written reason - the vocabulary grew by one declared-thing event
(`tests/test_event_table.py` pins the same growth), and no other byte moved."""
import json
from pathlib import Path

import pytest

from vefr import maplab

CASES = json.loads((Path(__file__).parent / "golden" / "validator" / "cases.json").read_text())


def _resolve(family_id: str):
    """The one family the golden's Blueprint has. See gen.py."""
    if family_id != "rat":
        return None
    return {"name": "a rat", "hp": 2, "atk": 1, "xp": 1}


FN = {"saves": lambda c: maplab.saves_errors(c["world"]),
      "sound": lambda c: maplab.sound_errors(c["world"]),
      "rules": lambda c: maplab.rules_errors(c["world"]),
      "album": lambda c: maplab.album_errors(c["world"]),
      "section": lambda c: maplab.section_block_errors(
          c["section"], c["affixes"], _resolve, "sections/cellar.json")}


@pytest.mark.parametrize("c", CASES, ids=lambda c: f"{c['block']}:{c['case']}")
def test_validator_sentences_and_order_do_not_change(c):
    assert FN[c["block"]](c) == c["errors"]