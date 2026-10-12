"""The interface lives inside the game's stage (docs/plans/interface/PLAN.md). FROZEN CONTRACT.

Rylee, 2026-10-04: "anything running 'inside the game' [should] be in a themed ui for that game and only controls and
such ... the map section icons go into the 'background' of the page." Today the HUD and buttons are placed against the
whole browser window, so on a small map they float on the dark page beside the drawn map.

The contract:
  - `window.VEFR_STAGE` = {x, y, w, h} (CSS pixels, in the viewport): the rectangle of the drawn map, clipped to the
    window. A map bigger than the window gives the window itself.
  - Every visible HUD piece and control (the health/level/gold panels, the bag strip, the Menu button, the message
    panels, the Interact button and the small action buttons, and the touch d-pad when it is shown) lies inside that
    rectangle, within 1 pixel, at every size below, desktop and phone.
  - Nothing sideways-scrolls the page.
  - Narrow portrait windows (width <= 600 and taller than wide): the map is letterboxed with spare room above and
    below it, so the stage grows to the whole window and `VEFR_STAGE.map` = {x, y, w, h} is the drawn map inside it. The
    controls (the touch cluster, or the d-pad and the action row) sit in the spare room, NOT on the map; no piece covers the map. On every other
    window `VEFR_STAGE` is the map rectangle as above and `VEFR_STAGE.map` equals it.
Uses the interact fixture (an 11x7 map: small on purpose, so it is letterboxed on any window).
"""

import socket  # noqa: F401  (kept for parity with the sibling files)
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
MAKE = ROOT / "tests" / "fixtures" / "make_interact_pack.py"

SIZES = [(1920, 1080, False), (1366, 768, False), (1280, 720, False), (1024, 600, False),
         (844, 390, True), (390, 844, True), (360, 640, True)]

COLLECT = """() => {
  const sel = '#play .hud .glass, #play .hud button, #play .gbtn, #play .toasts p, #play .toasts-toggle, #dpad button, #play #interact, #play .actions button';
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || el.hidden || el.closest('[hidden]')) continue;
    if (el.classList.contains('sr-only') || el.closest('.sr-only')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    out.push({id: el.id || el.className.toString().split(' ')[0] || el.tagName, l: r.left, t: r.top, r: r.right, b: r.bottom});
  }
  return {stage: window.VEFR_STAGE || null, els: out, sw: document.documentElement.scrollWidth, iw: innerWidth};
}"""

# `COLLECT` returns innerWidth as `iw`; the UI3c containment case also needs the window height.
INNER_HEIGHT = "() => innerHeight"


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    d = tmp_path_factory.mktemp("stage")
    out = subprocess.run([sys.executable, str(MAKE), str(d)], capture_output=True, text=True, check=True).stdout.strip()
    pack = Path(out.splitlines()[-1])
    # A full HUD: levels (the level chip) and gold (the gold chip), as a real game shows them.
    import json
    wj = pack / "world.json"
    cfg = json.loads(wj.read_text(encoding="utf-8"))
    cfg["growth"] = {"mode": "levels", "levels": {"xp": [0, 3, 6], "gain": {"hp": 2, "atk": 1}}}
    cfg["player"]["gold"] = 128
    wj.write_text(json.dumps(cfg), encoding="utf-8")
    html = d / "stage.html"
    html.write_text(cli.weave_html(pack), encoding="utf-8")
    return html


ROOT_SAMPLE = ROOT / "worlds" / "sample-world"


@pytest.fixture(scope="module")
def woven_sample(tmp_path_factory):
    """The shipped sample world, woven as-is: its small map is the UI3c case."""
    d = tmp_path_factory.mktemp("stage-sample")
    html = d / "sample.html"
    html.write_text(cli.weave_html(ROOT_SAMPLE), encoding="utf-8")
    return html


def _overlaps(els):
    """Pairs of pieces that cover each other by more than a few pixels (a piece may contain its own children)."""
    bad = []
    for i, a in enumerate(els):
        for b in els[i + 1:]:
            ox = min(a["r"], b["r"]) - max(a["l"], b["l"])
            oy = min(a["b"], b["b"]) - max(a["t"], b["t"])
            if ox > 4 and oy > 4:
                inside = ((a["l"] <= b["l"] + 1 and a["t"] <= b["t"] + 1 and a["r"] >= b["r"] - 1 and a["b"] >= b["b"] - 1)
                          or (b["l"] <= a["l"] + 1 and b["t"] <= a["t"] + 1 and b["r"] >= a["r"] - 1 and b["b"] >= a["b"] - 1))
                if not inside:
                    bad.append((a["id"], b["id"]))
    return bad


@pytest.mark.parametrize("w,h,touch", SIZES)
def test_no_two_pieces_cover_each_other(browser, woven, w, h, touch):
    """Rylee, 2026-10-04 (phone): a Messages button sat on top of the gold counter. Pieces may touch, not overlap."""
    ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(500)
        info = page.evaluate(COLLECT)
        bad = _overlaps(info["els"])
        assert not bad, f"pieces cover each other at {w}x{h}: {bad[:5]}"
    finally:
        ctx.close()


PHONES = [(390, 844, True), (360, 640, True)]


@pytest.mark.parametrize("w,h,touch", PHONES)
def test_on_a_phone_the_controls_sit_beside_the_map_not_on_it(browser, woven, w, h, touch):
    ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(500)
        info = page.evaluate(COLLECT)
        st = info["stage"]
        assert st and st.get("map"), "VEFR_STAGE.map is not published"
        assert st["h"] >= 0.9 * h and st["w"] >= 0.95 * w, f"the stage should grow to the window on a phone: {st}"
        m = st["map"]
        for e in info["els"]:
            if e["id"] in ("dpad", "acts", "interact", "talk", "whisper", "bagbtn", "explore",
                           "touch-smart", "touch-bag", "touch-b") or "gbtn" in str(e["id"]):
                inter_x = min(e["r"], m["x"] + m["w"]) - max(e["l"], m["x"])
                inter_y = min(e["b"], m["y"] + m["h"]) - max(e["t"], m["y"])
                assert not (inter_x > 4 and inter_y > 4 and e["id"] not in ("menu-open",)), \
                    f"{e['id']} covers the map at {w}x{h}: {e} vs {m}"
    finally:
        ctx.close()


@pytest.mark.parametrize("w,h,touch", SIZES)
def test_every_control_is_inside_the_stage(browser, woven, w, h, touch):
    ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(500)
        info = page.evaluate(COLLECT)
        st = info["stage"]
        assert st is not None, "window.VEFR_STAGE is not published"
        assert st["w"] > 50 and st["h"] > 50
        assert info["sw"] <= info["iw"], "the page scrolls sideways"
        outside = [e for e in info["els"]
                   if e["l"] < st["x"] - 1 or e["t"] < st["y"] - 1
                   or e["r"] > st["x"] + st["w"] + 1 or e["b"] > st["y"] + st["h"] + 1]
        assert not outside, f"{len(outside)} piece(s) outside the stage {st}: {outside[:4]}"
    finally:
        ctx.close()


# UI3c (Rylee, 2026-10-04): the sample world's map is small, so after I1+I2 the
# stage rectangle is the map rectangle and the HUD frame is drawn straight over
# map tiles. Frozen before the fix: no HUD piece may cover the drawn map.
@pytest.mark.parametrize("w,h,touch", SIZES + PHONES)
def test_no_hud_piece_covers_a_map_tile(browser, woven_sample, w, h, touch):
    ctx = browser.new_context(viewport={"width": w, "height": h}, has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    try:
        page.goto(woven_sample.as_uri())
        page.click("#ts-enter")
        if page.is_visible("#config"):
            page.click("#cfg-save")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(500)
        info = page.evaluate(COLLECT)
        st = info["stage"]
        assert st, "window.VEFR_STAGE is not published"
        m = st.get("map")
        assert m, f"VEFR_STAGE.map is not published: {st}"
        for e in info["els"]:
            ox = min(e["r"], m["x"] + m["w"]) - max(e["l"], m["x"])
            oy = min(e["b"], m["y"] + m["h"]) - max(e["t"], m["y"])
            assert not (ox > 4 and oy > 4), \
                f"{e['id']} covers a map tile at {w}x{h}: rect={e} map={m}"
        ih = page.evaluate(INNER_HEIGHT)
        outside = [e for e in info["els"]
                   if e["l"] < -1 or e["t"] < -1
                   or e["r"] > info["iw"] + 1 or e["b"] > ih + 1]
        assert not outside, f"{len(outside)} piece(s) outside the window at {w}x{h}: {outside[:4]}"
    finally:
        ctx.close()
