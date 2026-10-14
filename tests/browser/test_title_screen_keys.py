"""The title screen takes the same keys the game does (vefr#466).

Begin has the focus when the screen paints, so Enter already worked; F
and E - the game's own Interact keys - did nothing, and Tab walked the
focus off Begin onto the BODY, an invisible stop that swallowed the next
Enter. A runner pressed F first on this screen in 7 of 16 runs and lost
29 of 50 decisions to it.

Keys are sent as real browser key events (page.keyboard.press), never
synthetic DOM events. The woven file is served over http so it behaves the
way it does for a player. Skips without chromium, like the rest of
tests/browser.
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
    home = tmp_path_factory.mktemp("title-keys-home")
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


def open_title(page, url):
    page.goto(url)
    page.locator("#ts-enter").wait_for(state="visible")


def active_id(page):
    return page.evaluate(
        "() => document.activeElement && document.activeElement.id")


def assert_in_game(page):
    page.locator("#play").wait_for(state="visible", timeout=10000)
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region",
                           timeout=10000)


def test_begin_has_the_focus_when_the_screen_paints(page, woven):
    open_title(page, woven)
    assert active_id(page) == "ts-enter"


@pytest.mark.parametrize("key", ["F", "e", "Space"])
def test_f_e_and_space_start_the_game(page, woven, key):
    open_title(page, woven)
    page.keyboard.press(key)
    assert_in_game(page)


def test_space_starts_the_game_with_the_focus_nowhere(page, woven):
    """Space belongs to a focused button, so it needs the title screen's
    own handler to work once focus has wandered off Begin."""
    open_title(page, woven)
    page.evaluate("() => document.activeElement.blur()")
    page.keyboard.press("Space")
    assert_in_game(page)


def test_tab_does_not_walk_the_focus_off_begin(page, woven):
    open_title(page, woven)
    page.keyboard.press("Tab")
    assert active_id(page) == "ts-enter"
    page.keyboard.press("Shift+Tab")
    assert active_id(page) == "ts-enter"


def test_enter_after_a_tab_still_starts_the_game(page, woven):
    """The run-001 shape: a Tab, then Enter, and nothing happened."""
    open_title(page, woven)
    page.keyboard.press("Tab")
    page.keyboard.press("Enter")
    assert_in_game(page)