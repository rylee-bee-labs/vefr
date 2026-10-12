"""A pack's pixel art is drawn crisply in a real browser (`display.pixel_art`, parts 440, 460, 480).

Two woven copies of the shipped sample, each with a 48 px tall hero: one declares `display.pixel_art` with a native
tile of 32, the other declares nothing. In the pixel pack the drawn tile is a whole number of device pixels that is a
multiple of 32, the world canvas does not smooth (also after a resize), and the hero is drawn 48 * k / dpr CSS px tall.
The plain pack keeps its old tile and its smoothing, and its hero is drawn at sprite_scale as before.
"""

import argparse
import json
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import zlib
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"
NATIVE = 32
HERO_H = 48

# Records every draw of the hero (the only picture 48 px tall), so a test reads the size it was drawn at.
SPY = """
window.__heroDraws = [];
const drawImage = CanvasRenderingContext2D.prototype.drawImage;
CanvasRenderingContext2D.prototype.drawImage = function (img) {
  if (img && img.naturalHeight === %d) {
    window.__heroDraws.push(arguments[arguments.length - 1]);
  }
  return drawImage.apply(this, arguments);
};
""" % HERO_H


def _png(width: int, height: int) -> bytes:
    raw = (b"\x00" + bytes([200, 60, 60, 255]) * width) * height

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pack(dest: Path, pixel: bool) -> Path:
    shutil.copytree(SAMPLE, dest)
    cfg = json.loads((dest / "world.json").read_text(encoding="utf-8"))
    cfg["player"] = {"sprites": {"hero": "sprites/hero.png"}}
    if pixel:
        cfg["display"] = {"pixel_art": {"native_tile": NATIVE}}
    (dest / "world.json").write_text(json.dumps(cfg), encoding="utf-8")
    (dest / "sprites").mkdir(exist_ok=True)
    (dest / "sprites" / "hero.png").write_bytes(_png(24, HERO_H))
    return dest


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("pixelart-home")
    for name, pixel in (("pixel", True), ("plain", False)):
        rc = cli.cmd_build_web(argparse.Namespace(
            pack=str(_pack(home / f"{name}-pack", pixel)), out=str(home / f"{name}.html"),
            pool=0, with_bundle=False, from_live=None))
        assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            urllib.request.urlopen(f"{base}/pixel.html", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    yield {"pixel": f"{base}/pixel.html", "plain": f"{base}/plain.html"}
    proc.terminate()
    proc.wait(timeout=10)


def _open(browser, url, width, height, dpr):
    ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=dpr)
    ctx.add_init_script(SPY)
    page = ctx.new_page()
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    page.wait_for_function("window.__heroDraws && window.__heroDraws.length > 0")
    return ctx, page


def _device_px(css: float, dpr: float) -> float:
    return css * dpr


def test_the_tile_is_a_whole_multiple_of_the_art_on_a_phone(browser, woven):
    ctx, page = _open(browser, woven["pixel"], 390, 844, 3)
    try:
        tile = page.evaluate("window.VEFR_STAGE.tile")
        k = page.evaluate("window.VEFR_STAGE.pixel.k")
        assert k >= 1
        assert _device_px(tile, 3) == pytest.approx(k * NATIVE, abs=1e-6)
        assert round(_device_px(tile, 3)) % NATIVE == 0
    finally:
        ctx.close()


def test_the_tile_is_a_whole_multiple_of_the_art_on_a_desktop(browser, woven):
    ctx, page = _open(browser, woven["pixel"], 1280, 720, 1)
    try:
        tile = page.evaluate("window.VEFR_STAGE.tile")
        k = page.evaluate("window.VEFR_STAGE.pixel.k")
        assert _device_px(tile, 1) == pytest.approx(k * NATIVE, abs=1e-6)
        assert round(_device_px(tile, 1)) % NATIVE == 0
    finally:
        ctx.close()


def test_the_world_canvas_does_not_smooth_before_or_after_a_resize(browser, woven):
    ctx, page = _open(browser, woven["pixel"], 1280, 720, 1)
    try:
        smoothing = "document.getElementById('town-canvas').getContext('2d').imageSmoothingEnabled"
        assert page.evaluate(smoothing) is False
        page.set_viewport_size({"width": 1000, "height": 700})
        page.wait_for_timeout(200)
        assert page.evaluate(smoothing) is False
    finally:
        ctx.close()


def test_the_hero_is_drawn_at_its_own_art_size(browser, woven):
    ctx, page = _open(browser, woven["pixel"], 390, 844, 3)
    try:
        k = page.evaluate("window.VEFR_STAGE.pixel.k")
        drawn = page.evaluate("window.__heroDraws[window.__heroDraws.length - 1]")
        assert drawn == pytest.approx(HERO_H * k / 3, abs=1e-6)
    finally:
        ctx.close()


def test_a_pack_without_pixel_art_keeps_its_tile_smoothing_and_sprite_scale(browser, woven):
    ctx, page = _open(browser, woven["plain"], 1280, 720, 1)
    try:
        assert page.evaluate("window.VEFR_STAGE.pixel") is None
        tile = page.evaluate("window.VEFR_STAGE.tile")
        assert tile == pytest.approx(72.0, abs=1e-6)
        smoothing = "document.getElementById('town-canvas').getContext('2d').imageSmoothingEnabled"
        assert page.evaluate(smoothing) is True
        drawn = page.evaluate("window.__heroDraws[window.__heroDraws.length - 1]")
        assert drawn == pytest.approx(1.5 * tile, abs=1e-6)
    finally:
        ctx.close()
