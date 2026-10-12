"""A ground that blends: a legend entry's `edges` (vefr#422).

`"edges": "lane-edges"` names ONE 4 x 4 picture in the region's `tiles/`. The player draws piece `mask`
(cell `mask % 4`, row `mask // 4`) over a tile, where the mask is which neighbours share the tile's symbol:
north 1, east 2, south 4, west 8, a neighbour past the map's edge counting as the same; mask 15 draws
nothing. These tests cover the real player function (run in node), the bake, the compatibility rule (a
pack with no edges bakes and validates exactly as before) and the validator's sentences.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from vefr import cli, maplab

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"
PACKAGED = ROOT / "web" / "packaged.html"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "edge_harness.mjs"
TOWN = Path("acts") / "act-1" / "town"


def _webp(marker: bytes) -> bytes:
    return b"RIFF\x00\x00\x00\x00WEBPVP8 " + marker


def _baked(html: str, name: str):
    prefix = f"window.{name} = "
    line = next(ln for ln in html.splitlines() if ln.startswith(prefix))
    return json.loads(line[len(prefix):].rstrip(";"))


def _pack(tmp_path: Path, edges=None, pictures=()) -> Path:
    """The sample world, with the lane symbol `p` naming `edges` (when given) and these tiles/ files."""
    pack = tmp_path / "sample-world"
    shutil.copytree(SAMPLE, pack)
    region = pack / TOWN
    if pictures:
        (region / "tiles").mkdir()
        for name in pictures:
            (region / "tiles" / name).write_bytes(_webp(name.encode()))
    if edges is not None:
        contract = json.loads((region / "contract.json").read_text(encoding="utf-8"))
        contract["legend"]["p"]["edges"] = edges
        (region / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    return pack


def _validate(pack: Path) -> list[str]:
    return maplab.validate(maplab.load_pack(pack), pack_dir=pack)


# ---- the real player function: which piece ----

def _expected(rows: list[str], x: int, y: int) -> int:
    def same(nx, ny):
        if ny < 0 or ny >= len(rows) or nx < 0 or nx >= len(rows[ny]):
            return True
        return rows[ny][nx] == rows[y][x]
    return (same(x, y - 1) * 1) | (same(x + 1, y) * 2) | (same(x, y + 1) * 4) | (same(x - 1, y) * 8)


def _masks(rows: list[str]) -> list[list[int]]:
    out = subprocess.run(["node", str(HARNESS), str(PACKAGED), json.dumps(rows)],
                         capture_output=True, text=True, check=True, timeout=30).stdout
    return json.loads(out)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_piece_is_the_mask_of_the_neighbours_that_share_the_symbol():
    # A plus of lane in grass, a lone lane tile, and a lane running off the map's edge.
    rows = [".........p",
            "....p....p",
            "...ppp...p",
            "....p.....",
            ".p........"]
    got = _masks(rows)
    assert got[2][4] == 15                 # the plus's middle: all four the same, nothing drawn
    assert got[1][4] == 4                  # its top arm: only south is lane
    assert got[2][3] == 2                  # its left arm: only east
    assert got[2][5] == 8                  # its right arm: only west
    assert got[3][4] == 1                  # its bottom arm: only north
    assert got[4][1] == 4                  # a lone lane on the bottom row: past the edge counts as same
    assert got[0][9] == 1 | 2 | 4          # the top-right lane: north and east are past the edge
    assert got[2][9] == 1 | 2              # its end: south is grass
    for y, row in enumerate(rows):         # and every other cell, against the documented rule
        for x in range(len(row)):
            assert got[y][x] == _expected(rows, x, y), (x, y)


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_one_of_the_sixteen_masks_is_reachable():
    rows = ["#.#.#", ".....", "#.#.#", ".#.#.", "#####"]
    seen = {m for row in _masks(rows) for m in row}
    rows2 = [".#.", "###", ".#.", "...", "#.#"]
    seen |= {m for row in _masks(rows2) for m in row}
    rows3 = ["...", ".#.", "...", "##.", "#..", "...", ".##", "...", "##.", ".#."]
    seen |= {m for row in _masks(rows3) for m in row}
    assert seen == set(range(16)), sorted(set(range(16)) - seen)


def test_the_player_draws_the_masked_piece_over_the_tile():
    """The loader and draw wiring ships in the page (asserted from source, like the grid wiring)."""
    src = PACKAGED.read_text(encoding="utf-8")
    assert "window.VEFR_TILE_EDGES = {{tile_edges_json}};" in src
    assert "var mask = edgeMask(town.map, x, y);" in src
    assert ("ctx.drawImage(edgeImg, (mask % 4) * ew, Math.floor(mask / 4) * eh, ew, eh, "
            "x * T, y * T, T, T);") in src


# ---- the bake ----

def test_a_pack_with_no_edges_bakes_exactly_as_before(tmp_path):
    """The sample world names no edges: the edges table is empty and the ground tables are the ones
    the tile functions alone produce, so the drawn ground is unchanged."""
    html = cli.weave_html(SAMPLE)
    assert _baked(html, "VEFR_TILE_EDGES") == {}
    pack = _pack(tmp_path, edges="lane-edges", pictures=["lane-edges.webp"])
    with_edges = cli.weave_html(pack)
    assert _baked(with_edges, "VEFR_TILES") == _baked(html, "VEFR_TILES")
    assert _baked(with_edges, "VEFR_REGION_TILES") == _baked(html, "VEFR_REGION_TILES")


def test_a_named_edges_sheet_is_baked_per_region_and_symbol(tmp_path):
    pack = _pack(tmp_path, edges="lane-edges", pictures=["lane-edges.webp"])
    pic = _webp(b"lane-edges.webp")
    expect = "data:image/webp;base64," + base64.b64encode(pic).decode()
    assert _baked(cli.weave_html(pack), "VEFR_TILE_EDGES") == {"town": {"p": expect}}


# ---- the validator ----

def test_good_edges_validate(tmp_path):
    assert _validate(_pack(tmp_path, edges="lane-edges", pictures=["lane-edges.webp"])) == []


def test_the_sample_world_names_no_edges_and_stays_green():
    assert not [e for e in _validate(SAMPLE) if "edges" in e]


@pytest.mark.parametrize("bad", [7, "", "  ", ["lane-edges"], {"src": "x"}, "../lane-edges"])
def test_an_edges_value_that_is_not_a_name_is_refused_naming_the_symbol(tmp_path, bad):
    errors = _validate(_pack(tmp_path, edges=bad, pictures=["lane-edges.webp"]))
    hits = [e for e in errors if "symbol 'p'" in e and "not a picture name" in e]
    assert hits, errors


@pytest.mark.parametrize("pictures", [(), ("grass.webp",)])
def test_edges_naming_no_picture_is_refused_naming_the_symbol(tmp_path, pictures):
    errors = _validate(_pack(tmp_path, edges="lane-edges", pictures=pictures))
    assert any("symbol 'p'" in e and "names edges 'lane-edges'" in e and "not a picture" in e
               for e in errors), errors


@pytest.mark.parametrize("pictures", [("lane-edges.webp", "lane-edges.2.webp"),
                                      ("lane-edges.grid4x4.webp",)])
def test_edges_must_be_one_plain_picture(tmp_path, pictures):
    errors = _validate(_pack(tmp_path, edges="lane-edges", pictures=pictures))
    assert any("symbol 'p'" in e and "must be ONE picture" in e for e in errors), errors
