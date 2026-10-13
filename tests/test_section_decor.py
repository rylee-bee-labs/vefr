"""vefr#442: a Section can dress its generated floors with decor pictures.

A Section's `decor` names small pictures from the pack's `props/` and where
on a generated floor they lie: `floor` (a walkable tile) or `wall` (a wall
face with a walkable tile right below it), about one for `every` tiles of
that place. Each test here is one acceptance bullet of the issue:

1. placement is drawn on its own `decor` stream, so it moves nothing else;
2. decor goes only where its place says, never twice on one tile, never on
   the vault's tiles, and no entry places more than `DECOR_MAX_EACH`;
3. a Section's `decor` is left out of its floor identity hash;
4. a Section with no `decor` draws byte-for-byte what it drew before;
5. `vefr check` refuses a bad entry and a picture the pack does not have;
6. the weave bakes each Section's decor pictures;
7. Python and the descent part draw the same decor (parity harness);
8. the player grows a floor that carries its decor and draws it.
"""

import copy
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import play_kit
from vefr import cli, delve, maplab, shapes

from test_descent_deltas import _descend
from test_descent_floors import DESCENT

needs_node = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "section_mobs_parity_harness.mjs"
# Any picture the engine ships stands in for the pack's own decor art: what
# is under test is where a picture goes, not what it shows.
STAND_IN = ROOT / "web" / "art" / "tiles" / "dungeon-floor.webp"

DECOR = [
    {"pic": "puddle", "on": "floor", "every": 40},
    {"pic": "torch", "on": "wall", "every": 12},
]


def dressed(descent: dict, decor=None) -> dict:
    """The descent with every Section carrying `decor`."""
    out = copy.deepcopy(descent)
    for section in out["sections"]:
        section["decor"] = copy.deepcopy(DECOR if decor is None else decor)
    return out


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def bare(plan: dict) -> dict:
    return {k: v for k, v in plan.items() if k != "decor"}


# ------------------------------------------------------------ the placement


def test_decor_moves_nothing_else_on_the_floor():
    """Bullets 1 and 4: the floor is the same floor, with decor laid on it."""
    plain, dressed_descent = DESCENT, dressed(DESCENT)
    for depth in range(1, 6):
        want = delve.floor_plan(copy.deepcopy(plain), depth)
        got = delve.floor_plan(copy.deepcopy(dressed_descent), depth)
        assert "decor" not in want, "a Section with no decor grew a decor key"
        assert got["decor"], depth
        assert canonical(bare(got)) == canonical(want), depth


def test_decor_lies_only_where_its_place_says():
    """Bullet 2: floor on `.`, wall on `#` over `.`, one picture a tile."""
    descent = dressed(DESCENT)
    for depth in range(1, 6):
        plan = delve.floor_plan(copy.deepcopy(descent), depth)
        rows = plan["rows"]
        seen = set()
        for d in plan["decor"]:
            x, y = d["at"]
            assert (x, y) not in seen, (depth, d)
            seen.add((x, y))
            if d["pic"] == "puddle":
                assert rows[y][x] == ".", (depth, d)
            else:
                assert rows[y][x] == "#" and rows[y + 1][x] == ".", (depth, d)
        floors = sum(row.count(".") for row in rows)
        puddles = [d for d in plan["decor"] if d["pic"] == "puddle"]
        assert len(puddles) == min(floors // 40, delve.DECOR_MAX_EACH), depth


def test_decor_is_drawn_from_its_own_stream_and_is_stable():
    descent = dressed(DESCENT)
    one = delve.floor_plan(copy.deepcopy(descent), 2)
    two = delve.floor_plan(copy.deepcopy(descent), 2)
    assert one["decor"] == two["decor"]
    other_run = delve.floor_plan(copy.deepcopy(descent), 2, run=1)
    assert other_run["decor"] != one["decor"]


def test_no_entry_places_more_than_the_cap():
    rows = ["#" * 42] + ["#" + "." * 40 + "#"] * 20 + ["#" * 42]
    section = {"decor": [{"pic": "dust", "on": "floor", "every": 4}]}
    assert len(delve.decor_at("k", section, rows)) == delve.DECOR_MAX_EACH


def test_the_vaults_tiles_are_never_dressed():
    section = {"decor": [{"pic": "p", "on": "floor", "every": 4}]}
    # Four free floor tiles at every 4 is one picture, and only the free one.
    rows = ["######", "#....#", "######"]
    placed = delve.decor_at("k", section, rows, [[1, 1], [2, 1], [3, 1]])
    assert placed == []
    placed = delve.decor_at("k", section, rows, [])
    assert len(placed) == 1


def test_decor_is_left_out_of_the_floor_identity():
    """Bullet 3: dressing a Section keeps the floors a save remembers."""
    for section in DESCENT["sections"]:
        with_decor = {**section, "decor": DECOR}
        assert delve.section_hash(with_decor) == delve.section_hash(section)
        assert delve.section_hash(with_decor, [{"id": "s"}]) == \
            delve.section_hash(section, [{"id": "s"}])


# ---------------------------------------------------------------- the check


def _errors(entry) -> list:
    return [p.sentence for p in shapes.check(shapes.SECTION, {
        "id": "cellar", "families": [{"family": "rat"}], "decor": [entry]})]


def test_a_well_formed_entry_is_accepted():
    assert _errors({"pic": "puddle", "on": "floor", "every": 60}) == []
    assert _errors({"pic": "torch", "on": "wall", "every": 4}) == []


def test_a_bad_entry_is_refused():
    assert _errors({"pic": "puddle", "on": "ceiling", "every": 60})
    assert _errors({"pic": "puddle", "on": "floor", "every": 3})
    assert _errors({"pic": "puddle", "on": "floor", "every": 2001})
    assert _errors({"on": "floor", "every": 60})
    assert _errors({"pic": "puddle", "on": "floor"})
    assert _errors({"pic": "puddle", "on": "floor", "every": 60, "size": 2})


def test_a_picture_the_pack_does_not_have_is_refused(tmp_path):
    """Bullet 5: named with the Section and the picture."""
    pack = tmp_path / "pack"
    (pack / "sections").mkdir(parents=True)
    (pack / "sections" / "cellar.json").write_text(json.dumps({
        "id": "cellar", "floors": 1, "size": {"w": [32, 32], "h": [24, 24]},
        "rooms": [6, 6], "families": [{"family": "rat", "weight": 1}],
        "decor": [{"pic": "puddle", "on": "floor", "every": 40}],
    }), encoding="utf-8")
    errors = maplab.section_errors(pack)
    assert len(errors) == 1, errors
    assert "cellar" in errors[0] and "'puddle'" in errors[0] \
        and "/decor/0/pic" in errors[0], errors[0]

    (pack / "props").mkdir()
    shutil.copy(STAND_IN, pack / "props" / "puddle.webp")
    assert maplab.section_errors(pack) == []


# ----------------------------------------------------------------- the weave


def _dressed_pack(tmp_path, descent):
    pack = play_kit.pack(tmp_path, "descent", patch={"world.json": {"descent": descent}})
    (pack / "props").mkdir(exist_ok=True)
    for name in ("puddle", "torch"):
        shutil.copy(STAND_IN, pack / "props" / f"{name}.webp")
    return pack


def _baked_descent(html: str) -> dict:
    line = next(row for row in html.splitlines()
                if row.startswith("window.VEFR_DESCENT_DEF = "))
    return json.loads(line.split(" = ", 1)[1].rstrip().rstrip(";"))


def test_the_weave_bakes_each_sections_decor_pictures(tmp_path):
    """Bullet 6."""
    pack = _dressed_pack(tmp_path, dressed(DESCENT))
    baked = _baked_descent(play_kit.weave(pack, tmp_path).read_text(encoding="utf-8"))
    table = baked["section_decor"]
    assert set(table) == {s["id"] for s in DESCENT["sections"]}
    for pictures in table.values():
        assert set(pictures) == {"puddle", "torch"}
        assert all(v.startswith("data:image/webp;base64,") for v in pictures.values())


def test_a_pack_with_no_decor_bakes_no_decor_key(tmp_path):
    pack = play_kit.pack(tmp_path, "descent", patch={"world.json": {"descent": DESCENT}})
    baked = _baked_descent(play_kit.weave(pack, tmp_path).read_text(encoding="utf-8"))
    assert "section_decor" not in baked


# ---------------------------------------------------------------- the twins


@needs_node
def test_the_descent_twin_draws_the_same_decor(tmp_path):
    """Bullet 7: part 397's `floorPlan` against `delve.floor_plan`."""
    descent = dressed({"run_seed": "decor-run", "sections": DESCENT["sections"]})
    html = tmp_path / "p.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    depths = list(range(1, 6))
    cases = tmp_path / "cases.json"
    cases.write_text(json.dumps({"descent": descent, "depths": depths,
                                 "runs": [1], "floors": [],
                                 "section": descent["sections"][0]}),
                     encoding="utf-8")
    out = tmp_path / "out.json"
    run = subprocess.run(["node", str(HARNESS), str(html), str(cases), str(out)],
                         capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, run.stderr + run.stdout
    plans = json.loads(out.read_text(encoding="utf-8"))["plans"]
    for depth, got in zip(depths, plans):
        want = delve.floor_plan(copy.deepcopy(descent), depth)
        assert want["decor"], depth
        assert canonical(got) == canonical(want), depth
    want = delve.floor_plan(copy.deepcopy(descent), 1, run=1)
    assert canonical(plans[len(depths)]) == canonical(want)


@needs_node
def test_the_player_grows_a_floor_with_its_decor_and_draws_it(tmp_path):
    """Bullet 8: the real player, walked down to the first floor."""
    # Dense floor decor, so some of it is lit around the stair on arrival.
    descent = dressed(DESCENT, [{"pic": "puddle", "on": "floor", "every": 4},
                                {"pic": "torch", "on": "wall", "every": 12}])
    for section in descent["sections"]:
        section["families"] = []          # a quiet walk (see test_section_tiles)
    pack = _dressed_pack(tmp_path, descent)
    html = play_kit.weave(pack, tmp_path)
    play = play_kit.play(html, {
        "steps": _descend(1, descent=descent) + ["wait:200"],
        "read": ["VEFR_REGIONS.cellar-0-1", "VEFR_DECOR_PICS", "VEFR_DECOR_DRAWN"],
    })
    assert play["errors"] == [], play["errors"]
    reads = play["reads"]
    region = reads["VEFR_REGIONS.cellar-0-1"]
    assert region, "the walk never reached the first floor"
    assert region["decor"] == delve.floor_plan(copy.deepcopy(descent), 1)["decor"]
    assert set(reads["VEFR_DECOR_PICS"]["cellar-0-1"]) == {"puddle", "torch"}
    assert isinstance(reads["VEFR_DECOR_DRAWN"], int) and reads["VEFR_DECOR_DRAWN"] > 0
