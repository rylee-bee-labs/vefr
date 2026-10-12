"""The phone camera, on a pack that names `display.phone_tile` (P2CAM, docs/guides/world-creation.md).

One lit map, the sample town tiled 6 across and 4 down, so it cannot read whole on a phone (390x844). Its hero starts
on the bottom-right walkable tile.

- On a phone (`?camera=phone`) the map draws at the pack's 52 px, not the 32 px a desktop draws it at.
- The camera may pass the map's edge by three tiles, so the hero, standing at the bottom-right, sits clear of the
  160 px wide corner the lower-right controls take. The hero's figure is measured as a T/3 radius, the player's own
  dot; a sprite a little wider than that is not measured here.
- `?camera=desk` on the same pack keeps the old camera: 32 px, and the camera stops at the map's edge.

Run with: uv run pytest tests/browser/test_phone_camera.py
"""

import json
import shutil
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"
PHONE_W, PHONE_H = 390, 844
TILE = 52
CORNER_W = 160
TILES_ACROSS, TILES_DOWN = 6, 4


@pytest.fixture(scope="module")
def phone_pack(tmp_path_factory):
    home = tmp_path_factory.mktemp("phone-camera")
    pack = home / "pack"
    shutil.copytree(SAMPLE, pack)
    town = pack / "acts" / "act-1" / "town"
    rows = [row for row in (town / "map.md").read_text(encoding="utf-8").splitlines() if row.strip()]
    big = [row * TILES_ACROSS for row in rows] * TILES_DOWN
    (town / "map.md").write_text("\n".join(big) + "\n", encoding="utf-8")
    contract = town / "contract.json"
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    cfg.pop("fog", None)
    legend = cfg["legend"]
    cols, height = len(big[0]), len(big)
    start = next((x, y) for y in range(height - 1, -1, -1) for x in range(cols - 1, -1, -1)
                 if not legend.get(big[y][x], {}).get("solid"))
    cfg["hero_start"] = list(start)
    contract.write_text(json.dumps(cfg), encoding="utf-8")
    world = pack / "world.json"
    wj = json.loads(world.read_text(encoding="utf-8"))
    wj["display"] = {"phone_tile": TILE}
    world.write_text(json.dumps(wj), encoding="utf-8")
    html = home / "phone.html"
    html.write_text(cli.weave_html(pack), encoding="utf-8")
    return html, start, (cols, height)


def open_game(browser, html, query, w=PHONE_W, h=PHONE_H):
    ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    page.goto(html.as_uri() + query)
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(500)
    return ctx, page


def test_a_large_lit_map_on_a_phone_draws_at_the_pack_tile(browser, phone_pack):
    html, (x, y), _ = phone_pack
    ctx, page = open_game(browser, html, "?camera=phone")
    try:
        assert page.evaluate("window.VEFR_STAGE.tile") == TILE
        assert page.evaluate("window.VEFR_MOTION().drawn") == [x, y]
    finally:
        ctx.close()


def test_the_hero_on_the_bottom_right_tile_is_clear_of_the_lower_right_corner(browser, phone_pack):
    html, (x, y), (cols, _) = phone_pack
    ctx, page = open_game(browser, html, "?camera=phone")
    try:
        cam = page.evaluate("window.VEFR_CAMERA()")
        hero_cx = x * TILE + TILE / 2 - cam["x"]
        assert hero_cx + TILE / 3 <= PHONE_W - CORNER_W, f"the hero's figure reaches the corner: centre {hero_cx}"
        # with the 3-tile margin the camera can keep her centred even on the last walkable tile: it follows her
        # past the map's edge, and never further than the margin allows
        assert cam["x"] == pytest.approx(x * TILE + TILE / 2 - PHONE_W / 2), "the camera does not keep her centred"
        assert cam["x"] > cols * TILE - PHONE_W, "the camera stopped at the map's edge instead of passing it"
        assert cam["x"] <= cols * TILE - PHONE_W + 3 * TILE, "the camera passed the edge by more than 3 tiles"
    finally:
        ctx.close()


def test_a_desk_visit_of_the_same_map_keeps_the_old_camera(browser, phone_pack):
    html, _, (cols, _) = phone_pack
    ctx, page = open_game(browser, html, "?camera=desk")
    try:
        assert page.evaluate("window.VEFR_STAGE.tile") == 32
        cam = page.evaluate("window.VEFR_CAMERA()")
        assert cam["x"] == pytest.approx(cols * 32 - PHONE_W), "the desk camera passes the map's edge"
    finally:
        ctx.close()
