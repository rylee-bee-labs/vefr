"""The ending room's own tile, drawn in a real browser (`display.ending_tile`, parts 110 and 440).

Cottage-of-the-breeze#166, option B: the ending room under a `complete-act` end card is drawn at the
pack's own `ending_tile` - here 64 CSS px, a whole multiple of the sample's 32 px art - and at no
other time. The sample town (12 x 10, fogged) reads whole at 32 px, so the card doubling it is plain
to read at 1280x720. On a 390x844 phone 64 px a tile does not fit (12 x 64 = 768 > 390), so the room
steps down to the largest whole multiple that does: 32 px, the room still whole (never cropped, never
scrolled). Closing the card returns the room to the tile it always drew, and a pack that names no
`ending_tile` keeps that tile with the card up, exactly as before.
"""

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

def _ns(value):
    """window.VEFR_STAGE comes back as plain dicts; read it with attributes, as the assertions do."""
    if isinstance(value, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in value.items()})
    return value


import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"
NATIVE = 32
ENDING = 64
COLS, ROWS = 12, 10          # the sample town's own map
END_RULE = [{"id": "the-end", "when": {"starts": {}}, "once": True,
             "then": [{"complete-act": "act-1"}]}]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _pack(dest: Path, ending: bool) -> Path:
    """The shipped sample, with pixel art and a `complete-act` rule that opens
    the end card the moment the game begins; `ending_tile` only when asked."""
    shutil.copytree(SAMPLE, dest)
    cfg = json.loads((dest / "world.json").read_text(encoding="utf-8"))
    display = {"pixel_art": {"native_tile": NATIVE}}
    if ending:
        display["ending_tile"] = ENDING
    cfg["display"] = display
    cfg["flags"], cfg["claims"], cfg["people"] = {}, {}, {}
    cfg["rules"] = END_RULE
    (dest / "world.json").write_text(json.dumps(cfg), encoding="utf-8")
    return dest


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("endingtile-home")
    for name, ending in (("end", True), ("plain", False)):
        rc = cli.cmd_build_web(argparse.Namespace(
            pack=str(_pack(home / f"{name}-pack", ending)), out=str(home / f"{name}.html"),
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
            urllib.request.urlopen(f"{base}/end.html", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        log.close()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    yield {"end": f"{base}/end.html", "plain": f"{base}/plain.html"}
    proc.terminate()
    proc.wait(timeout=10)
    log.close()


def _open(browser, url, width, height):
    """A context at the given size with the end card already up."""
    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_ACT_COMPLETE && window.VEFR_ACT_COMPLETE.shown")
    return ctx, page


def test_the_ending_room_reads_at_its_own_tile_on_a_desktop(browser, woven):
    ctx, page = _open(browser, woven["end"], 1280, 720)
    try:
        stage = _ns(page.evaluate("window.VEFR_STAGE"))
        assert stage.tile == ENDING, f"the card's room reads at ending_tile, got {stage.tile} px"
        assert stage.pixel.k * NATIVE == ENDING   # crisp: two screen pixels per art pixel
        assert stage.map.w == COLS * ENDING and stage.map.h == ROWS * ENDING
        assert stage.map.w <= 1280 and stage.map.h <= 720   # whole, never cropped or scrolled
    finally:
        ctx.close()


def test_the_ending_room_steps_down_to_the_largest_multiple_that_fits_a_phone(browser, woven):
    ctx, page = _open(browser, woven["end"], 390, 844)
    try:
        stage = _ns(page.evaluate("window.VEFR_STAGE"))
        asked = COLS * ENDING
        assert asked > 390, "the fixture must ask for a room too wide for the phone"
        assert stage.tile == NATIVE, f"64 px does not fit, so the room steps down to 32, got {stage.tile} px"
        assert stage.map.w == COLS * NATIVE <= 390 and stage.map.h == ROWS * NATIVE <= 844
    finally:
        ctx.close()


def test_closing_the_card_returns_the_room_to_its_ordinary_tile(browser, woven):
    ctx, page = _open(browser, woven["end"], 1280, 720)
    try:
        assert page.evaluate("window.VEFR_STAGE.tile") == ENDING
        page.keyboard.press("e")   # Interact continues the game (510-rules-closure-surfaces.js)
        page.wait_for_function("document.getElementById('act-end').hidden")   # the card closed
        assert page.evaluate("window.VEFR_STAGE.tile") == NATIVE
        assert page.evaluate("window.VEFR_STAGE.map.w") == COLS * NATIVE
    finally:
        ctx.close()


def test_a_pack_without_ending_tile_keeps_its_ordinary_tile_with_the_card_up(browser, woven):
    ctx, page = _open(browser, woven["plain"], 1280, 720)
    try:
        stage = _ns(page.evaluate("window.VEFR_STAGE"))
        assert stage.tile == NATIVE   # the room's ordinary whole fit, card or no card
        assert stage.map.w == COLS * NATIVE
    finally:
        ctx.close()