"""A whole map keeps its corner tiles clear of the HUD on a desktop (issue #424).

One fixture, built here and never shipped: the sample world with its fog lifted and a plain 22x13
town, which at 1280x720 reads whole (no scrolling). The HUD's pieces hang off the stage's corners, so
the hero is walked onto each of the four corner tiles in turn and the hero's own tile rectangle must
clear every visible HUD control: the Menu button, the Interact/Talk/Whisper/Bag/Explore row, the
Messages toggle, the health, level and gold chips. The tile and the map rectangle are read from
`window.VEFR_STAGE`. A second check holds the other half of the issue: a map too tall to leave the
bands clear at a readable tile scrolls instead.
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
KEY = {(1, 0): "ArrowRight", (-1, 0): "ArrowLeft", (0, 1): "ArrowDown", (0, -1): "ArrowUp"}

# The hero's drawn tile as a rectangle on screen, and every visible HUD control covering it.
COLLECT = """() => {
  const st = window.VEFR_STAGE, m = st.map, T = st.tile;
  const at = window.VEFR_COMBAT.hero.at;
  const tile = {l: m.x + at[0] * T, t: m.y + at[1] * T, r: m.x + (at[0] + 1) * T, b: m.y + (at[1] + 1) * T};
  const under = [];
  for (const el of document.querySelectorAll('#hud-frame button, #hud-frame .hud .glass')) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden || el.closest('[hidden]')) continue;
    if (el.classList.contains('sr-only') || el.closest('.sr-only')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const ox = Math.min(r.right, tile.r) - Math.max(r.left, tile.l);
    const oy = Math.min(r.bottom, tile.b) - Math.max(r.top, tile.t);
    if (ox > 1 && oy > 1) under.push({id: el.id || el.className, ox: Math.round(ox), oy: Math.round(oy)});
  }
  return {at: at.slice(), tile: tile, stage: st, under: under};
}"""


def _pack(tmp_path_factory, name, cols, rows, start):
    """The sample world as a plain, unlit cols x rows town with no walls."""
    d = tmp_path_factory.mktemp(name)
    pack = d / "pack"
    shutil.copytree(SAMPLE, pack)
    town = pack / "acts" / "act-1" / "town"
    (town / "map.md").write_text("\n".join(["." * cols] * rows) + "\n", encoding="utf-8")
    cfg = json.loads((town / "contract.json").read_text(encoding="utf-8"))
    cfg.pop("fog", None)          # a lit map: the whole-map fit, not the dark one
    cfg.pop("watch", None)
    cfg["pois"] = {}
    cfg["hero_start"] = start
    (town / "contract.json").write_text(json.dumps(cfg), encoding="utf-8")
    html = d / f"{name}.html"
    html.write_text(cli.weave_html(pack), encoding="utf-8")
    return html


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    return _pack(tmp_path_factory, "hud-bands", COLS, ROWS, CORNERS[0])


@pytest.fixture(scope="module")
def woven_tall(tmp_path_factory):
    # 40 rows read whole at 18 px in the full 720 px, but at 12 px once the two bands are left,
    # under the 16 px readable tile: so the map scrolls at a comfortable tile instead.
    return _pack(tmp_path_factory, "hud-bands-tall", 12, 40, [1, 1])


def _open(browser, html, w=W, h=H):
    ctx = browser.new_context(viewport={"width": w, "height": h}, reduced_motion="reduce")
    page = ctx.new_page()
    page.goto(html.as_uri())
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.hero", timeout=15000)
    page.wait_for_timeout(500)
    return ctx, page


def _walk(page, at, to):
    """Walk the hero one tile at a time, waiting for each step to land."""
    while at != to:
        dx, dy = to[0] - at[0], to[1] - at[1]
        step = (1 if dx > 0 else -1, 0) if dx else (0, 1 if dy > 0 else -1)
        nxt = [at[0] + step[0], at[1] + step[1]]
        page.keyboard.press(KEY[step])
        page.wait_for_function("(at) => window.VEFR_COMBAT.hero.at.join() === at.join()", arg=nxt,
                               timeout=5000)
        at = nxt
    return at


# The issue's size first; the other desktop sizes test_stage_containment walks, so the wider
# stage a band-fitted map keeps is checked where the HUD is most crowded too.
DESKTOPS = [(1280, 720), (1920, 1080), (1366, 768), (1024, 600)]


@pytest.mark.parametrize("w,h", DESKTOPS)
def test_a_whole_map_keeps_its_corner_tiles_off_the_hud(browser, woven, w, h):
    ctx, page = _open(browser, woven, w, h)
    try:
        st = page.evaluate("window.VEFR_STAGE")
        assert st["map"]["w"] <= w and st["map"]["h"] <= h, f"this fixture is meant to read whole, not scroll: {st}"
        assert st["tile"] >= 16, f"the whole map is below the readable tile: {st}"
        at = page.evaluate("window.VEFR_COMBAT.hero.at")
        for corner in CORNERS:
            at = _walk(page, at, corner)
            info = page.evaluate(COLLECT)
            assert info["at"] == corner, f"the hero is on {info['at']}, not {corner}"
            assert not info["under"], (f"the hero's corner tile at {corner} sits under {info['under']}: "
                                       f"tile={info['tile']} stage={info['stage']}")
    finally:
        ctx.close()


def test_a_map_too_tall_for_the_bands_scrolls(browser, woven_tall):
    ctx, page = _open(browser, woven_tall)
    try:
        st = page.evaluate("window.VEFR_STAGE")
        assert st["tile"] >= 16, f"the tall map shrank below the readable tile instead of scrolling: {st}"
        assert 40 * st["tile"] > H, f"the tall map reads whole, so its edge rows sit in the HUD bands: {st}"
    finally:
        ctx.close()
