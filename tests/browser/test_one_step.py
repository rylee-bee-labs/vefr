"""One key press, one tile: an arrow-key step in a real browser.

NOTE - the report "one key press moves the hero about four tiles" did NOT
reproduce. A single ArrowRight keypress (page.keyboard.press: a tap, not a
held key) moves the hero exactly one tile, read through the player's own
window.VEFR_COMBAT snapshot - the same hook tests/browser/test_monster_walking.py
uses. On worlds/sample-world's town floor the hero went [3, 4] -> [4, 4]:
x +1, y +0. Nothing in the movement path chains a keypress.

What looks like a multi-tile jump is display scale, not a logic bug. The
player draws a tile at T = town.tile * fitZoom(), and fitZoom() scales a
whole map up as far as 3x (and the hero sprite is drawn 1.5 tiles tall), so
one tile of travel can LOOK like several pack tiles: measured, one step was
48px in the foggy sample town (T = 48, the largest a dark floor is drawn at) and 96px on the no-fog wall fixture
(T = 3 x town.tile = 96). In addition, a HELD arrow key chains moves because
the keydown handler has no e.repeat guard: the browser's own key auto-repeat
delivers repeated keydown events, each calling move() once (4 synthetic
repeat=true events moved the hero 4 tiles). The press made here does not hold
the key, so it moves exactly one tile. Behaviour was therefore left unchanged;
no engine test hook was needed (VEFR_COMBAT already exposes the hero tile).
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
SAMPLE = ROOT / "worlds" / "sample-world"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """A woven single-file player for the sample world, served over http.

    Served rather than opened as a file:// page so localStorage and the
    file's own fetches behave the way they do for a player.
    """
    home = tmp_path_factory.mktemp("one-step-home")
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(SAMPLE), out=str(home / "sample.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/sample.html"
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
    """Open the woven file and step through its title screen."""
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def hero_at(page):
    """The hero's tile, from the same snapshot the browser suite reads."""
    return page.evaluate("window.VEFR_COMBAT.hero.at")


def test_one_arrow_press_moves_exactly_one_tile(page, woven):
    open_woven(page, woven)
    before = hero_at(page)
    assert before == [3, 4]      # the sample town's wake tile

    # A press, not a down/up hold: no second keydown, so no auto-repeat.
    page.keyboard.press("ArrowRight")
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    after = hero_at(page)
    assert after[0] - before[0] == 1
    assert after[1] - before[1] == 0
