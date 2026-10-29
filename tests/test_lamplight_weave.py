"""Lamplight's normal maps in the weave: `tiles/<name>.normal.png` beside a tile is baked by region and symbol into
`window.VEFR_TILE_NORMALS`, in the same three shapes the tile itself takes (one picture, a list of variants, or a
grid). A pack without any bakes `{}` and its tiles bake exactly as before.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
from pathlib import Path

from vefr import cli, maplab

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"
TOWN = Path("acts") / "act-1" / "town"


def _webp(marker: bytes) -> bytes:
    return b"RIFF\x00\x00\x00\x00WEBPVP8 " + marker


def _uri(name: str) -> str:
    return "data:image/webp;base64," + base64.b64encode(_webp(name.encode())).decode()


def _baked(html: str, name: str):
    prefix = f"window.{name} = "
    line = next(ln for ln in html.splitlines() if ln.startswith(prefix))
    return json.loads(line[len(prefix):].rstrip(";"))


def _pack(tmp_path: Path, pictures) -> Path:
    """The sample world with these files in the town's tiles/. Its wall symbol `#` is the `stone-wall` tile."""
    pack = tmp_path / "sample-world"
    shutil.copytree(SAMPLE, pack)
    tiles = pack / TOWN / "tiles"
    tiles.mkdir()
    for name in pictures:
        (tiles / name).write_bytes(_webp(name.encode()))
    return pack


def test_a_tile_with_a_normal_map_bakes_it_by_symbol(tmp_path):
    pack = _pack(tmp_path, ["stone-wall.webp", "stone-wall.normal.webp"])
    assert _baked(cli.weave_html(pack), "VEFR_TILE_NORMALS") == {"town": {"#": _uri("stone-wall.normal.webp")}}


def test_variants_bake_a_list_in_order(tmp_path):
    pack = _pack(tmp_path, ["stone-wall.normal.webp", "stone-wall.normal.2.webp"])
    assert _baked(cli.weave_html(pack), "VEFR_TILE_NORMALS") == {
        "town": {"#": [_uri("stone-wall.normal.webp"), _uri("stone-wall.normal.2.webp")]}}


def test_a_grid_bakes_its_cells(tmp_path):
    pack = _pack(tmp_path, ["stone-wall.normal.grid2x2.webp"])
    assert _baked(cli.weave_html(pack), "VEFR_TILE_NORMALS") == {
        "town": {"#": {"src": _uri("stone-wall.normal.grid2x2.webp"), "cols": 2, "rows": 2}}}


def test_a_pack_without_normals_bakes_an_empty_table():
    assert "window.VEFR_TILE_NORMALS = {};" in cli.weave_html(SAMPLE).splitlines()


def test_normal_maps_change_nothing_else_the_weave_bakes(tmp_path):
    plain = cli.weave_html(SAMPLE)
    lit = cli.weave_html(_pack(tmp_path, ["stone-wall.normal.webp"]))
    for name in ("VEFR_TILES", "VEFR_REGION_TILES", "VEFR_TILE_EDGES"):
        assert _baked(lit, name) == _baked(plain, name)


# The sample world's region tiles, measured before the bake was split into `_legend_tile_name` and `_tile_shape`
# (re-measure: sha256 of json.dumps(_baked(cli.weave_html(SAMPLE), "VEFR_REGION_TILES"), sort_keys=True)).
REGION_TILES_SHA256 = "4f4e1b08fa4e189974e4abb9bad235bdd72feed25b194981a8aa2e7c619e3a4d"


def test_the_sample_worlds_tiles_bake_as_they_did():
    tiles = json.dumps(_baked(cli.weave_html(SAMPLE), "VEFR_REGION_TILES"), sort_keys=True)
    assert hashlib.sha256(tiles.encode()).hexdigest() == REGION_TILES_SHA256


def test_a_pack_with_normal_maps_still_validates(tmp_path):
    pack = _pack(tmp_path, ["stone-wall.webp", "stone-wall.normal.webp", "stone-wall.normal.2.webp"])
    assert maplab.validate(maplab.load_pack(pack), pack_dir=pack) == []
