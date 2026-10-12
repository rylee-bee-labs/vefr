"""A whole map keeps its corner tiles clear of the HUD buttons on a desktop (issue #424).

One fixture, built here and never shipped: the sample world with its fog lifted and a plain 22x13
town, which at 1280x720 reads whole (no scrolling) at a tile near 38 px with a band left above and
below it. The HUD's buttons hang off the stage's corners, so the hero is walked onto each of the
four corner tiles in turn and the hero's own tile rectangle must clear every visible button in the
HUD: the Menu button, the Interact/Talk/Whisper/Bag/Explore row, the Messages toggle, the fight
verbs. The tile and the map rectangle are read from `window.VEFR_STAGE`.
"""

import json
import shutil
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"

W, H = 1280, 720
COLS, ROWS = 22, 13
# The four corners of the drawn map, in one pass so the hero walks the map once.
CORNERS = [[0, 0], [COLS - 1, 0], [COLS - 1, ROWS - 1], [0, ROWS - 1]]
KEY = {"left": "ArrowLeft", "right": "ArrowRight", "up": "ArrowUp", "down": "ArrowDown"}

# The hero's drawn tile as a rectangle on screen, and every visible HUD button covering it.
COLLECT = """() => {
  const st = window.VEFR_STAGE, m = st.map, T = st.tile;
  const at = window.VEFR_MOTION().drawn;
  const tile = {l: m.x + at[0] * T, t: m.y + at[1] * T, r: m.x + (at[0] + 1) * T, b: m.y + (at[1] + 1) * T};
  const under = [];
  for (const el of document.querySelectorAll('#hud-frame button')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden || el.closest('[hidden]')) continue;
    if (el.classList.contains('sr-only') || el.closest('.sr-only')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const ox = Math.min(r.right, tile.r) - Math.max(r.left, tile.l);
    const oy = Math.min(r.bottom, tile.b) - Math.max(r.top, tile.t);
    if (ox > 1 && oy > 1) under.push({id: el.id || el.className, ox: Math.round(ox), oy: Math.round(oy)});
  }
  return {at: at, tile: tile, stage: st, under: under};
}"""


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The sample world as a wide, unlit 22x13 town: whole on a 1280x720 desktop, and no walls."""
    d = tmp_path_factory.mktemp("hud-bands")
    pack = d / "pack"
    shutil.copytree(SAMPLE, pack)
    town = pack / "acts" / "act-1" / "town"
    (town / "map.md").write_text("\n".join(["." * COLS] * ROWS) + "\n", encoding="utf-8")
    cfg = json.loads((town / "contract.json").read_text(encoding="utf-8"))
    cfg.pop("fog", None)          # a lit map: the whole-map fit, not the dark one
    cfg["hero_start"] = CORNERS[0]
    (town / "contract.json").write_text(json.dumps(cfg), encoding="utf-8")
    html = d / "whole.html"
    html.write_text(cli.weave_html(pack), encoding="utf-8")
    return html


def _walk(page, at, to):
    """Walk the hero one tile at a time, waiting for each settled tile (reduced motion: no hop)."""
    while at != to:
        dx, dy = to[0] - at[0], to[1] - at[1]
        step = [dx, 0] if abs(dx) >= abs(dy) else [0, dy]
        at = [at[0] + step[0], at[1] + step[1]]
        page.keyboard.press(KEY["right" if step[0] > 0 else "left" if step[0] < 0
                             else "down" if step[1] > 0 else "up"])
        page.wait_for_function("([at]) => window.VEFR_COMBAT.hero.at.join() === at.join()", arg=at)
    return at


def test_a_whole_map_keeps_its_corner_tiles_off_the_hud_buttons(browser, woven):
    ctx = browser.new_context(viewport={"width": W, "height": H}, reduced_motion="reduce")
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        if page.is_visible("#config"):
            page.click("#cfg-save")
        page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region", timeout=15000)
        page.wait_for_timeout(500)
        st = page.evaluate("window.VEFR_STAGE")
        assert st["map"]["w"] < W and st["map"]["h"] < H, \
            f"this fixture is meant to read whole, not scroll: {st}"
        at = page.evaluate("window.VEFR_COMBAT.hero.at")
        for corner in CORNERS:
            at = _walk(page, at, corner)
            info = page.evaluate(COLLECT)
            assert info["at"] == corner, f"the hero is on {info['at']}, not {corner}"
            assert not info["under"], \
                (f"the hero's corner tile at {corner} sits under {info['under']}: "
                 f"tile={info['tile']} stage={info['stage']}")
    finally:
        ctx.close()