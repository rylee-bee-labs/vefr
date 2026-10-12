"""Map props: what the validator refuses, what blocks walking, and what the bake ships.

A prop is a picture drawn over the ground. Its footprint can block walking.
"""

import json
import re
import sys
from pathlib import Path

import pytest

from vefr import cli, maplab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_props_pack as mk  # noqa: E402


def errors_of(pack):
    return maplab.validate(maplab.load_pack(pack), pack_dir=pack)


def prop(**kw):
    return {"pic": "stone", "at": [8, 8], **kw}


def test_a_sound_prop_validates(tmp_path):
    assert errors_of(mk.build(tmp_path)) == []


@pytest.mark.parametrize("props, pics, needles", [
    ([prop(pic="x/stone")], None,
     ["region 'town' prop 0 'x/stone'", "pic must be a picture's file name with no folder"]),
    ([prop(pic="rock")], None,
     ["region 'town' prop 0 'rock'", "no picture 'rock.webp' or 'rock.png'"]),
    ([prop(at=[8])], None,
     ["region 'town' prop 0 'stone'", "at must be [x, y] whole numbers"]),
    ([prop(size=[0, 1])], None,
     ["region 'town' prop 0 'stone'", "size must be [width, height] whole numbers of at least 1"]),
    ([prop(frames=13)], None,
     ["region 'town' prop 0 'stone'", "frames must be a whole number from 1 to 12"]),
    ([prop(layer="floor")], None,
     ["region 'town' prop 0 'stone'", 'layer must be "stand" (the default) or "ground"']),
    ([prop(fps=0)], None,
     ["region 'town' prop 0 'stone'", "fps must be a whole number from 1 to 12"]),
    ([prop(at=[11, 9], size=[2, 1])], None,
     ["region 'town' prop 0 'stone'", "leaves the map (12x10)"]),
    ([prop(size=[2, 1], block=["#"])], None,
     ["region 'town' prop 0 'stone'", "block must be 1 rows of 2 characters"]),
    ([prop(frames=2)], {"stone": (63, 32)},
     ["region 'town' prop 0 'stone'", "the picture is 63 px wide, which is not a whole number of 2 frames"]),
    ([prop(at=[7, 4])], None,
     ["region 'town' prop 0 'stone'", "covers speaker 'keeper' at 7,4"]),
    ([prop(at=[3, 4])], None,
     ["region 'town' prop 0 'stone'", "covers the hero's start at 3,4"]),
    ([prop(at=[2, 2])], None,
     ["region 'town' prop 0 'stone'", "covers the book 'A Note by the Path' at 2,2"]),
    ("stone", None,
     ["region 'town' props must be a list"]),
    (["stone"], None,
     ["region 'town' prop 0 must be an object with pic and at"]),
])
def test_each_bad_prop_is_named(tmp_path, props, pics, needles):
    errs = errors_of(mk.build(tmp_path, props=props, pics=pics))
    hit = [e for e in errs if all(n in e for n in needles)]
    assert hit, errs


def test_a_prop_whose_block_marks_its_cell_open_leaves_the_tile_walkable(tmp_path):
    w = maplab.load_pack(mk.build(tmp_path, props=[prop(block=["."])]))
    assert maplab.walkable(w, 8, 8)


def test_a_prop_with_no_block_blocks_its_whole_footprint(tmp_path):
    w = maplab.load_pack(mk.build(tmp_path, props=[prop(at=[9, 8], size=[2, 1])]))
    assert not maplab.walkable(w, 9, 8)
    assert not maplab.walkable(w, 10, 8)
    assert maplab.walkable(w, 8, 8)


def test_block_marks_only_the_hash_cells():
    props = [{"pic": "a", "at": [1, 1], "size": [2, 2], "block": ["#.", ".#"]}]
    assert maplab.prop_blocks(props, 1, 1)
    assert not maplab.prop_blocks(props, 2, 1)
    assert not maplab.prop_blocks(props, 1, 2)
    assert maplab.prop_blocks(props, 2, 2)
    assert not maplab.prop_blocks(props, 0, 0)


def data_line(html, name):
    m = re.search(rf"^window\.{name} = (.*);$", html, re.M)
    assert m, name
    return m.group(1)


def test_a_pack_without_props_bakes_an_empty_picture_table():
    html = cli.weave_html(mk.SAMPLE)
    assert "window.VEFR_PROP_PICS = {};" in html
    assert '"props"' not in data_line(html, "VEFR_REGIONS")


def test_a_props_pack_bakes_its_pictures_and_its_props(tmp_path):
    html = cli.weave_html(mk.build(tmp_path))
    pics = json.loads(data_line(html, "VEFR_PROP_PICS"))
    assert set(pics) == {"town"}
    assert set(pics["town"]) == {"stone"}
    assert pics["town"]["stone"].startswith("data:image/png;base64,")
    regions = json.loads(data_line(html, "VEFR_REGIONS"))
    entries = []
    stack = [regions]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if "props" in node:
                entries.append(node["props"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    assert entries == [[{"pic": "stone", "at": [8, 8], "frames": 2, "fps": 4}]]


def test_people_block_must_be_true_or_false():
    from vefr.maplab import _people_block_errors
    assert _people_block_errors({"player": {"people_block": True}}) == []
    assert _people_block_errors({"player": {}}) == []
    assert _people_block_errors({"player": {"people_block": "yes"}}) == ["player.people_block must be true or false"]
