"""Lamplight in a real browser: the light rig lays per-pixel light over the drawn map.

The sample world's town with a `light` block: walls stand one tile up, both phases are dark, the hero carries a small
light, and one lamp near the hero shines while the rule flag `lamp-lit` is set. Both lights reach half a tile (gone by
two), so a tile three or more away from both shows only the darkness. WebGL2 runs on SwiftShader here, so no GPU is
needed; Chromium is launched with the flags that allow it. Without Chromium these skip, unless VEFR_BROWSER_REQUIRED=1.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli

SAMPLE = Path(__file__).resolve().parents[2] / "worlds" / "sample-world"
GL_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
HERO, LAMP, FAR = (3, 4), (6, 2), (6, 6)   # the sample town's hero start; open ground, both lit by the fog circle
DARK = "#101018"
LIGHT = {"stand": {"stone-wall": 1}, "ambient": {"dusk": DARK, "dawn": DARK},
         "hero": {"reach": 0.5, "intensity": 3},
         "lamps": {"town": [{"at": list(LAMP), "reach": 0.5, "intensity": 3, "flag": "lamp-lit"}]}}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _weave(home: Path, out: str, light=None):
    pack = home / out.replace(".html", "")
    shutil.copytree(SAMPLE, pack)
    if light is not None:
        world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
        world["light"] = light
        world["flags"] = {"lamp-lit": "The lamp by the well is lit."}
        (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    rc = cli.cmd_build_web(argparse.Namespace(pack=str(pack), out=str(home / out), pool=0, with_bundle=False,
                                              from_live=None))
    assert rc == 0


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("lamplight-home")
    _weave(home, "lit.html", LIGHT)
    _weave(home, "dusk-only.html", {**LIGHT, "ambient": {"dusk": DARK}})
    _weave(home, "plain.html")
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}/"
    for _ in range(120):
        try:
            urllib.request.urlopen(base + "lit.html", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven files never came up; see {home / 'server.log'}")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def gl_browser():
    """Chromium with software WebGL2 (the shared `browser` fixture launches it without)."""
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=GL_ARGS)
        except Exception as exc:  # noqa: BLE001 - no browser installed here
            if os.environ.get("VEFR_BROWSER_REQUIRED") == "1":
                raise
            pytest.skip(f"Chromium isn't installed ({exc.__class__.__name__}); run: uv run playwright install chromium")
        yield b
        b.close()


@pytest.fixture
def make_page(gl_browser):
    contexts = []

    def make(motion="reduce", init=None):
        ctx = gl_browser.new_context(viewport={"width": 1100, "height": 900}, reduced_motion=motion)
        if init:
            ctx.add_init_script(init)
        contexts.append(ctx)
        page = ctx.new_page()
        page.errors = []
        page.on("pageerror", lambda e: page.errors.append(str(e)))
        return page

    yield make
    for ctx in contexts:
        ctx.close()


def _open(page, url):
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    page.wait_for_timeout(300)


# Draw the map once and read both canvases at the middle of the given tiles, in the same task as the draw: a WebGL
# canvas is cleared once it has been shown.
READ = """(tiles) => {
  window.VEFR_REDRAW();
  const map = document.getElementById('town-canvas'), gl = document.getElementById('lamp-canvas');
  const copy = document.createElement('canvas');
  copy.width = map.width; copy.height = map.height;
  const x = copy.getContext('2d');
  const out = {};
  for (const [name, which] of [['map', map], ['lit', gl]]) {
    if (!which) continue;
    x.clearRect(0, 0, copy.width, copy.height);
    x.drawImage(which, 0, 0);
    out[name] = tiles.map(([tx, ty]) => {
      const [px, py] = window.VEFR_LAMPLIGHT.px(tx, ty);
      return Array.from(x.getImageData(px, py, 1, 1).data);
    });
  }
  return out;
}"""


def _read(page, *tiles):
    return page.evaluate(READ, [list(t) for t in tiles])


def lum(px) -> int:
    return sum(px[:3])


def _visible(page) -> bool:
    return page.evaluate("(() => { const c = document.getElementById('lamp-canvas');"
                         " return !!c && getComputedStyle(c).display !== 'none'; })()")


def test_lamplight_draws_over_the_map(make_page, woven):
    page = make_page()
    _open(page, woven + "lit.html")
    assert page.evaluate("window.VEFR_LAMPLIGHT.on()") is True
    assert _visible(page)
    sizes = page.evaluate("[document.getElementById('town-canvas').width, document.getElementById('town-canvas').height,"
                          " document.getElementById('lamp-canvas').width, document.getElementById('lamp-canvas').height]")
    assert sizes[:2] == sizes[2:]
    assert page.evaluate("window.VEFR_LAMPLIGHT.planes()") == 2   # the ground and the walls
    assert page.errors == []


def test_the_dark_is_darker_than_the_map_and_the_hero_is_lit(make_page, woven):
    page = make_page()
    _open(page, woven + "lit.html")
    got = _read(page, HERO, FAR)
    hero, far = got["lit"]
    assert lum(far) < lum(got["map"][1]) / 2      # darkness over the open ground
    assert lum(hero) > lum(far) + 30              # the hero's own light


def test_a_lamp_shines_only_while_its_flag_is_set(make_page, woven):
    page = make_page()
    _open(page, woven + "lit.html")
    assert page.evaluate("window.VEFR_LAMPLIGHT.lights().length") == 1   # the hero's alone
    unlit = _read(page, LAMP)["lit"][0]
    page.evaluate("window.VEFR_RULES_STATE.flags['lamp-lit'] = true")
    assert page.evaluate("window.VEFR_LAMPLIGHT.lights().length") == 2
    shining = _read(page, LAMP)["lit"][0]
    assert lum(shining) > lum(unlit) + 30


def test_the_switch_turns_it_off_and_is_remembered(make_page, woven):
    page = make_page()
    _open(page, woven + "lit.html")
    box = page.locator("#lamplight-toggle")
    page.click("#menu-open")
    page.click('[data-panel="display"]')
    assert box.evaluate("(b) => b.closest('p').getBoundingClientRect().height") >= 44
    assert box.is_checked()
    box.uncheck()
    assert not _visible(page) and page.evaluate("window.VEFR_LAMPLIGHT.on()") is False
    page.reload()
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    assert page.evaluate("document.getElementById('lamplight-toggle').checked") is False
    assert not _visible(page)


def test_a_phase_without_darkness_is_unlit(make_page, woven):
    page = make_page()
    _open(page, woven + "dusk-only.html")
    assert _visible(page)
    page.evaluate("gotoPhase('dawn'); window.VEFR_REDRAW()")
    assert not _visible(page)
    page.evaluate("gotoPhase('dusk'); window.VEFR_REDRAW()")
    assert _visible(page)


def test_motion_flickers_and_reduced_motion_holds_still(make_page, woven):
    moving = make_page(motion="no-preference")
    _open(moving, woven + "lit.html")
    assert moving.evaluate("window.VEFR_LAMPLIGHT.looping()") is True
    still = make_page()
    _open(still, woven + "lit.html")
    assert still.evaluate("window.VEFR_LAMPLIGHT.looping()") is False


NO_WEBGL2 = """(() => { const get = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (k, o) { return k === 'webgl2' ? null : get.call(this, k, o); };
})();"""


def test_no_webgl2_plays_as_before(make_page, woven):
    page = make_page(init=NO_WEBGL2)
    _open(page, woven + "lit.html")
    assert page.locator("#lamp-canvas").count() == 0
    assert page.locator("#lamplight-toggle").count() == 0
    assert page.errors == []


def test_a_lost_context_leaves_the_map(make_page, woven):
    page = make_page()
    _open(page, woven + "lit.html")
    page.evaluate("document.getElementById('lamp-canvas').getContext('webgl2')"
                  ".getExtension('WEBGL_lose_context').loseContext()")
    page.wait_for_timeout(300)
    page.evaluate("window.VEFR_REDRAW()")
    assert page.locator("#lamp-canvas").count() == 0
    assert page.evaluate("window.VEFR_LAMPLIGHT.lost()") is True
    assert page.errors == []


def test_a_pack_without_light_has_no_switch(make_page, woven):
    page = make_page()
    _open(page, woven + "plain.html")
    assert page.locator("#lamp-canvas").count() == 0
    assert page.locator("#lamplight-toggle").count() == 0
    assert page.evaluate("typeof window.VEFR_LAMPLIGHT") == "undefined"
    assert page.errors == []
