"""A Section may carry a display label; the id keeps naming every floor.

The label is for the player to read. Nothing the game keeps reads it:
`floor_key`, `floor_region` and the save keys are built from the id alone.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from vefr import sections, shapes

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sections"


def fixture_section(name: str = "cellar") -> dict:
    return json.loads((FIXTURES / name / "sections" / f"{name}.json").read_text(
        encoding="utf-8"))


def labelled(section: dict, label) -> dict:
    return dict(copy.deepcopy(section), label=label)


def only(problems) -> tuple[str, str]:
    assert len(problems) == 1, [p.sentence for p in problems]
    return problems[0].pointer, problems[0].sentence


def test_no_label_shows_the_id():
    assert sections.section_label({"id": "placeholder-a"}) == "placeholder-a"


def test_a_label_shows_the_label():
    section = {"id": "placeholder-a", "label": "Placeholder A"}
    assert sections.section_label(section) == "Placeholder A"


@pytest.mark.parametrize("label", ["A", "Placeholder A", "x" * 40])
def test_a_label_of_one_to_forty_characters_is_accepted(label):
    section = labelled(fixture_section(), label)
    assert shapes.check(shapes.SECTION, section) == []


@pytest.mark.parametrize("label", ["", "x" * 41])
def test_a_label_outside_one_to_forty_characters_is_refused_at_the_label(label):
    pointer, _ = only(shapes.check(shapes.SECTION, labelled(fixture_section(), label)))
    assert pointer == "/section/label"


@pytest.mark.parametrize("label", [1, 1.5, True, ["Placeholder A"], {"text": "A"}, None])
def test_a_non_string_label_is_refused_at_the_label(label):
    pointer, sentence = only(
        shapes.check(shapes.SECTION, labelled(fixture_section(), label)))
    assert pointer == "/section/label"
    assert sentence == "section.label must be a string, the name a player sees for this Section"


def test_floor_key_and_floor_region_ignore_the_label():
    plain = fixture_section()
    named = labelled(plain, "Placeholder A")
    assert sections.floor_key("seed-a", named, 2, 3) == sections.floor_key("seed-a", plain, 2, 3)
    assert sections.floor_region(named, 3) == sections.floor_region(plain, 3)
    assert sections.floor_region(named, 3) == f"{plain['id']}-3"
