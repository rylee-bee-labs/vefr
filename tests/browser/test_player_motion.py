"""The hero's step motion, in a real browser.

The node-vm half (tests/test_player_motion.py) reads the pure maths and
the combat snapshot; this half proves the DRAWN position in a real
browser: after a step the hero settles onto the new tile, and with
`prefers-reduced-motion: reduce` it is on the new tile at once with no
hop at all.

It opens a woven sample-world file itself over a plain local server, the
way test_monster_walking.py and test_one_step.py do - one file, opened
and played - and reads the player's own window.VEFR_MOTION snapshot.
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
    home = tmp_path_factory.mktemp("hero-motion-home")
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
    """The hero's game tile, from the snapshot the browser suite reads."""
    return page.evaluate("window.VEFR_COMBAT.hero.at")


def motion(page):
    """The player's own read-only view of the hero's drawing."""
    return page.evaluate("window.VEFR_MOTION()")


def test_the_drawn_hero_settles_on_the_new_tile(page, woven):
    open_woven(page, woven)
    # The shared fixture's context does not ask for reduced motion.
    assert page.evaluate(
        "window.matchMedia('(prefers-reduced-motion: reduce)').matches") is False

    before = hero_at(page)
    assert before == [3, 4]      # the sample town's wake tile
    page.keyboard.press("ArrowRight")
    new_tile = [before[0] + 1, before[1]]
    assert hero_at(page) == new_tile

    # Poll until the hop is over, then the drawn tile is the game's tile.
    page.wait_for_function(
        "() => window.VEFR_MOTION && !window.VEFR_MOTION().animating")
    drawn = motion(page)
    assert drawn["animating"] is False
    assert drawn["drawn"] == new_tile
    assert hero_at(page) == new_tile     # the hop never moved the game


def test_reduced_motion_draws_the_new_tile_at_once(browser, woven):
    # The shared `page` fixture builds its own context, so this one is
    # written here with reduced motion asked for, in the shape of fixtures.py's.
    ctx = browser.new_context(
        viewport={"width": 1100, "height": 1400}, reduced_motion="reduce")
    page = ctx.new_page()
    try:
        open_woven(page, woven)
        assert page.evaluate(
            "window.matchMedia('(prefers-reduced-motion: reduce)').matches") is True

        before = hero_at(page)
        assert before == [3, 4]
        page.keyboard.press("ArrowRight")
        new_tile = [before[0] + 1, before[1]]

        # No hop is started, so the drawn tile is the new tile at once -
        # read straight after the press, with no poll.
        drawn = motion(page)
        assert drawn["animating"] is False
        assert drawn["drawn"] == new_tile
        assert hero_at(page) == new_tile
    finally:
        ctx.close()
