"""Blueprint A5: the versioned conformance corpus for format 1.

Each valid case dir holds `blueprint.json` and `expected.json`; each invalid case
dir holds `blueprint.json` and `expected-error.txt` (line 1: a substring of the
error, case-insensitive; line 2, optional: the JSON pointer the error names).
"""

from pathlib import Path

import pytest

from blueprint_helpers import mk

V1 = Path(__file__).parent / "fixtures" / "blueprint" / "v1"
VALID = sorted(p for p in (V1 / "valid").iterdir() if p.is_dir())
INVALID = sorted(p for p in (V1 / "invalid").iterdir() if p.is_dir())



@pytest.mark.parametrize("case", VALID, ids=lambda p: p.name)
def test_valid_case_expands_to_expected(case, tmp_path):
    import json
    from vefr import blueprint

    pack = mk.build(tmp_path)
    got = blueprint.expand(blueprint.read(case / "blueprint.json"), pack_dir=pack)
    assert got == json.loads((case / "expected.json").read_text())


@pytest.mark.parametrize("case", INVALID, ids=lambda p: p.name)
def test_invalid_case_fails_with_a_plain_sentence(case, tmp_path):
    from vefr import blueprint

    lines = (case / "expected-error.txt").read_text().splitlines()
    needle, pointer = lines[0].lower(), (lines[1] if len(lines) > 1 else "")
    pack = mk.build(tmp_path)
    with pytest.raises(blueprint.BlueprintError) as err:
        blueprint.expand(blueprint.read(case / "blueprint.json"), pack_dir=pack)
    assert needle in str(err.value).lower()
    if pointer:
        assert err.value.pointer == pointer


def test_flat_shape_pack_is_refused(tmp_path):
    """A flat-shape pack (no acts/) cannot carry a Blueprint: format 1 is acts-shape only."""
    import json
    import shutil
    from vefr import blueprint

    pack = mk.build(tmp_path)
    shutil.rmtree(pack / "acts")
    (pack / "blueprint.json").write_text(json.dumps(mk.STD_BLUEPRINT))
    errors = blueprint.check_errors(pack)
    assert errors and any("acts" in e.lower() for e in errors)


def test_reader_registry_and_closed_sets():
    from vefr import blueprint

    assert set(blueprint.READERS) == {1, 2, 3}
    assert blueprint.TOP_KEYS == {"blueprint", "families", "regions", "things"}
    assert blueprint.FAMILY_KEYS == {"defaults", "extends"}
    assert blueprint.FIELD_KEYS == {"name", "sprite", "hp", "atk", "xp", "sight", "drops",
                                    "guard", "drop_chance", "gold", "skills"}
    assert blueprint.REGION_KEYS == {"enemies", "places"}
    assert blueprint.INSTANCE_KEYS == {"id", "family", "at", "properties"}
