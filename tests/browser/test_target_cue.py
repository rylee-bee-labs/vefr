"""The cue on the smart action's target, in a real browser (Chromium).

vefr#486: before F (or the touch layer's smart button) is pressed, the
tile it will act on carries a cue on the map. The cue is a soft glow
PLUS a non-colour cue - four corner brackets, a shape - so nothing here
depends on telling the gold from the ground. The glow breathes only
when motion is allowed; under `prefers-reduced-motion: reduce` it is
drawn once, still, with the brackets unchanged.

This file weaves the interact fixture pack (tests/fixtures/
make_interact_pack.py) the same way tests/browser/test_interact_button.py
does and walks the same pinned route to the resident's spot [4, 2],
where the porter stands on [4, 3] and is what Interact would act on.

Two engines read the cue, and neither replaces the other:

  - `window.VEFR_TARGET_CUE` - what the player says the cue is: the
    tile, the label, the glow's alpha and whether it is breathing.
  - the canvas pixels - what the player actually sees: the gold marks
    sit in the tile's four CORNERS and nowhere else (the shape, proven
    from pixels rather than from the snapshot), and a pixel inside the
    halo changes between frames while the glow breathes and does not
    change at all while it is still.

Without `uv run playwright install chromium` these skip - that is the
expected result on a machine with no browser (fixtures.py's browser
fixture), not a failure.
"""

import argparse
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
MAKE = ROOT / "tests" / "fixtures" / "make_interact_pack.py"

# The pinned walk from tests/browser/test_interact_button.py, to the
# resident's spot [4, 2]. The porter stands one tile north on [4, 3],
# which is the tile the hero faces, so that is the cue's tile.
TO_RESIDENT = ["down", "down", "right", "right", "up", "right"]
# On to the empty spot [1, 5] - three tiles west, three south - where
# nothing is in reach in any direction, so there is no target and no
# cue. The route never steps beside the fixture's rat at [2, 1].
TO_EMPTY = TO_RESIDENT + ["left"] * 3 + ["down"] * 3


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """A woven single-file player for the interact fixture pack, served
    over http (so localStorage behaves the way it does for a player)."""
    home = tmp_path_factory.mktemp("target-cue-home")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "interact.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/interact.html"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def open_woven(page, url):
    """Open the woven file, pin the save seed and step past the title
    screen - the same door every other browser scenario walks through."""
    page.goto(url)
    page.evaluate("localStorage.setItem('vefr-save-seed', '42')")
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    page.evaluate("document.activeElement && document.activeElement.blur()")


def walk(page, dirs):
    for d in dirs:
        page.keyboard.press(f"Arrow{d.capitalize()}")
    page.evaluate(
        "() => new Promise(r => "
        "requestAnimationFrame(() => requestAnimationFrame(r)))")


# ---- reading the cue out of the canvas, in the page -------------------
#
# One read of the target tile's own pixels: the tile rectangle in the
# canvas's device pixels, the gold pixels inside it split by which
# corner they fall in, and one pixel's colour from inside the halo but
# off every stroke (the top edge's midpoint, between the two top
# brackets). Four corners carrying the gold, and the gold almost
# nowhere else, is the shape cue read from pixels - not from the
# snapshot, which only claims it.
READ = r"""() => {
  const cue = window.VEFR_TARGET_CUE();
  if (!cue) return null;
  const cv = document.getElementById('town-canvas');
  const g = cv.getContext('2d');
  const d = window.devicePixelRatio || 1;
  const rect = cv.getBoundingClientRect();
  const T = window.VEFR_STAGE.tile;
  const map = window.VEFR_STAGE.map;
  const x = Math.round((map.x - rect.left + cue.at[0] * T) * d);
  const y = Math.round((map.y - rect.top + cue.at[1] * T) * d);
  const w = Math.round(T * d);
  const img = g.getImageData(x, y, w, w).data;
  // The marks' own gold (#D8AA4E) and its antialiased edge. The window
  // is the mark colour and nothing else on this tile: the ground here
  // is a warm tan that a loose "is it goldy" test would sweep up whole.
  const BOX = 0.34;
  const isGold = (px, py) => {
    const i = (py * w + px) * 4;
    return Math.abs(img[i] - 216) < 26 && Math.abs(img[i + 1] - 170) < 26
        && Math.abs(img[i + 2] - 78) < 30;
  };
  const inBox = (px, py, sx, sy) =>
    (sx ? px >= w * (1 - BOX) : px <= w * BOX)
    && (sy ? py >= w * (1 - BOX) : py <= w * BOX);
  let gold = 0, inCorners = 0;
  const corners = [0, 0, 0, 0];
  for (let py = 0; py < w; py++) {
    for (let px = 0; px < w; px++) {
      if (!isGold(px, py)) continue;
      gold += 1;
      [[0, 0], [0, 1], [1, 0], [1, 1]].forEach(([sx, sy], k) => {
        if (inBox(px, py, sx, sy)) { corners[k] += 1; inCorners += 1; }
      });
    }
  }
  const mx = Math.floor(w / 2), my = Math.round(w * 0.08);
  const mi = (my * w + mx) * 4;
  return { cue, w, gold, corners,
           outside: gold - inCorners,
           halo: [img[mi], img[mi + 1], img[mi + 2]] };
}"""


def read(page):
    return page.evaluate(READ)


def halo_series(page, count=3, gap=350, repaint=True):
    """The same halo pixel, `count` times, `gap` ms apart, with a forced
    repaint (`window.VEFR_REDRAW`, the player's own redraw) before each
    reading after the first. Under reduced motion nothing else asks for
    a repaint, so without this the reading would prove only that
    nothing moved - which is what the still cue is FOR. Asking for the
    frames makes the comparison one the glow has to survive on its own."""
    out = []
    for i in range(count):
        if i:
            if repaint:
                page.evaluate("window.VEFR_REDRAW()")
            page.wait_for_timeout(gap)
        got = read(page)
        out.append(got["halo"] if got else None)
    return out


def test_the_cue_sits_on_the_tile_the_button_will_act_on(page, woven):
    """At the resident's spot the cue's tile is the porter's own tile -
    the tile the hero faces - and the words agree with the button the
    press will read: "Talk to the porter"."""
    open_woven(page, woven)
    walk(page, TO_RESIDENT)
    assert page.evaluate("window.VEFR_COMBAT.hero.at") == [4, 2]
    cue = page.evaluate("window.VEFR_TARGET_CUE")
    assert cue is not None, "no cue with a target in reach"
    assert cue["at"] == [4, 3]
    assert cue["kind"] == "resident"
    assert cue["label"] == "Talk to the porter"
    assert page.text_content("#interact-label") == "Talk to the porter"
    assert page.text_content("#use-hint") == "Talk to the porter"


def test_the_cue_draws_four_corner_marks_not_a_fill(page, woven):
    """The non-colour cue, read from pixels: the gold sits in all four
    corners of the target tile and almost nowhere else. That is a shape
    - four brackets - so the cue survives with the colour taken away,
    and the thing it marks stays readable underneath."""
    open_woven(page, woven)
    walk(page, TO_RESIDENT)
    got = read(page)
    assert got is not None
    assert got["gold"] > 20, f"only {got['gold']} gold pixels in the target tile"
    assert all(n > 4 for n in got["corners"]), (
        f"the marks are not in the four corners: {got['corners']}")
    assert got["outside"] <= got["gold"] * 0.2, (
        f"{got['outside']} of {got['gold']} gold pixels are outside the "
        f"corner boxes {got['corners']}: that is a fill or a ring, "
        "not four corner marks")


def test_nothing_in_reach_means_no_cue(page, woven):
    """Out on the empty spot there is no target, so there is no cue:
    the snapshot is null and the Interact button dims as it always did."""
    open_woven(page, woven)
    walk(page, TO_EMPTY)
    assert page.evaluate("window.VEFR_COMBAT.hero.at") == [1, 5]
    assert page.evaluate("window.VEFR_TARGET_CUE") is None
    assert page.text_content("#use-hint") == "Nothing near you to use yet."


def test_the_glow_breathes_while_motion_is_allowed(page, woven):
    """With motion allowed the halo is alive: the same pixel inside it
    is not the same colour frame to frame, and the snapshot says the
    cue is breathing with an alpha inside its own range."""
    open_woven(page, woven)
    walk(page, TO_RESIDENT)
    cue = read(page)["cue"]
    assert cue["breathing"] is True
    assert 0.0 < cue["glow"] <= 0.5, cue["glow"]
    series = halo_series(page)
    assert any(series[i] != series[i + 1] for i in range(len(series) - 1)), (
        f"the halo never changed: {series}")


def test_reduced_motion_leaves_the_cue_still(browser, woven):
    """With `prefers-reduced-motion: reduce` the glow is drawn once at
    one alpha, so the halo does not change frame to frame - and the
    corner marks are still there, because the cue is never motion-only
    information."""
    ctx = browser.new_context(reduced_motion="reduce")
    page = ctx.new_page()
    try:
        open_woven(page, woven)
        walk(page, TO_RESIDENT)
        assert page.evaluate(
            "window.matchMedia('(prefers-reduced-motion: reduce)').matches")
        got = read(page)
        assert got is not None, "no cue at all under reduced motion"
        assert got["cue"]["breathing"] is False
        assert got["cue"]["at"] == [4, 3]
        assert got["cue"]["label"] == "Talk to the porter"
        # The one alpha, and the marks that carry the cue without it.
        assert 0.0 < got["cue"]["glow"] <= 0.5
        assert got["gold"] > 20
        assert all(n > 4 for n in got["corners"]), got["corners"]
        assert got["outside"] <= got["gold"] * 0.2, got
        # The alpha the pure helper reports is one number at every
        # moment, and the drawn halo is that one number repainted.
        at = page.evaluate(
            "() => [0, 600, 1200, 1800].map(window.VEFR_TARGET_GLOW)")
        assert len(set(at)) == 1, f"the glow still breathes: {at}"
        series = halo_series(page, count=3, gap=250)
        assert all(series[i] == series[i + 1] for i in range(len(series) - 1)), (
            f"the halo moved under reduced motion: {series}")
    finally:
        ctx.close()


def test_the_glow_alpha_is_a_pure_function_of_the_clock(page, woven):
    """The alphas the snapshot can report come from one pure helper, so
    a test can read the breath without a canvas: a cosine between the
    two ends of the glow's own range while motion is allowed."""
    open_woven(page, woven)
    walk(page, TO_RESIDENT)
    seen = page.evaluate(
        "() => { const out = []; for (let t = 0; t < 2400; t += 200) "
        "out.push(window.VEFR_TARGET_GLOW(t)); return out; }")
    assert min(seen) < max(seen), f"the glow never breathes: {seen}"
    # The player's own range is 0.08..0.30 (TARGET_GLOW_MIN/MAX in part 480): a soft glow, never a flash.
    assert min(seen) >= 0.08 - 1e-6 and max(seen) <= 0.30 + 1e-6, (
        f"the glow left its soft range: {min(seen)}..{max(seen)}")
