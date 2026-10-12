"""A dark floor's tile fills its lit circle in a real browser (fitZoom in 440-the-camera.js).

Two maps, both fogged at sight 8. The sample town (12x10) reads whole at 32 px on a desktop, so it keeps the
old fit into the HUD's band and no HUD piece covers a tile (tests/browser/test_stage_containment.py). The same
town tiled 6 across and 4 down scrolls, and there the tile fills the lit circle: 1280x720 gives 42 px. A phone
(390x844) keeps 32 px either way. The tile is read from `VEFR_STAGE.tile`.
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

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "worlds" / "sample-world"
SIGHT = 8
COLS = len([row for row in (SAMPLE / "acts" / "act-1" / "town" / "map.md").read_text(encoding="utf-8").splitlines()
            if row.strip()][0])


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def dark(tmp_path_factory):
    home = tmp_path_factory.mktemp("camzoom-home")
    pack = home / "pack"
    shutil.copytree(SAMPLE, pack)
    contract = pack / "acts" / "act-1" / "town" / "contract.json"
    cfg = json.loads(contract.read_text(encoding="utf-8"))
    cfg["fog"] = {"radius": SIGHT}
    contract.write_text(json.dumps(cfg), encoding="utf-8")
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "dark.html"), pool=0, with_bundle=False, from_live=None))
    assert rc == 0
    # the big one: the same town, its map tiled 6 across and 4 down, so it cannot read whole
    big = home / "bigpack"
    shutil.copytree(pack, big)
    town_map = big / "acts" / "act-1" / "town" / "map.md"
    rows = [row for row in town_map.read_text(encoding="utf-8").splitlines() if row.strip()]
    town_map.write_text("\n".join([row * 6 for row in rows] * 4) + "\n", encoding="utf-8")
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(big), out=str(home / "big.html"), pool=0, with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/dark.html"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    yield url, url.replace("dark.html", "big.html")
    proc.terminate()
    proc.wait(timeout=10)


def drawn_tile(browser, url, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    try:
        page = ctx.new_page()
        page.goto(url)
        page.get_by_role("button", name="Begin").click()
        page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
        return page.evaluate("window.VEFR_STAGE.tile")
    finally:
        ctx.close()


def test_a_dark_map_that_reads_whole_keeps_its_fit_on_a_desktop(browser, dark):
    tile = drawn_tile(browser, dark[0], 1280, 720)
    assert tile <= 32, f"a whole dark map keeps the old fit, so no HUD piece covers it; got {tile} px"


def test_a_scrolling_dark_floor_tile_fills_the_lit_circle_on_a_desktop(browser, dark):
    tile = drawn_tile(browser, dark[1], 1280, 720)
    assert 32 < tile <= 48, f"a scrolling dark floor's tile should fill the lit circle, got {tile} px"
    assert tile == 720 // (2 * SIGHT + 1), f"sight {SIGHT} at 720 px is {720 // (2 * SIGHT + 1)} px, got {tile}"


def test_a_dark_floor_tile_stays_at_32_px_on_a_phone(browser, dark):
    for url in dark:
        tile = drawn_tile(browser, url, 390, 844)
        assert tile <= 32, f"a phone's dark floor tile must not grow past 32 px, got {tile} px at {url}"
