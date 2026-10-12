"""The messages panel folds itself on the phone camera (issue #430).

The panel's own rule is "a small corner panel (top left, under the health bar),
never over the map". Under the phone camera (#418, `display.phone_tile`) the map
fills the window, so there is no room outside it: the camera keeps the hero in
the middle and the panel, growing down from the top left, reaches her. There the
panel folds itself a few seconds after its newest line - the lines stay in the
page for a screen reader, exactly as a fold by hand does - and the Messages
button opens it again.

The same pack at a desk window has the old camera and the old panel: nothing
folds itself. A fold by hand is remembered, and a new line never opens it.

The pack is the sample town with `display.phone_tile` added, served over http so
localStorage is the real thing (a file:// page has none). The phone camera is
asked for by name (`?camera=phone`, as tests/browser/test_phone_camera.py does),
so the camera under test never depends on how a headless Chromium answers
`(pointer: coarse)`. The wait is shortened through `window.VEFR_MESSAGES_FOLD_MS`,
the test-only hook the player reads at each fold; without it the panel waits 6 s.

Run with: uv run pytest tests/browser/test_message_panel_fold.py
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
PHONE_W, PHONE_H = 390, 844
DESK_W, DESK_H = 1280, 720
TILE = 52
# Short enough that the whole file is seconds rather than a minute. The player
# waits FOLD_MS (6 s) without it. It is long enough that a line, and the
# round trip that reads the panel back, land well inside one wait.
FOLD_WAIT_MS = 800


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen(1)
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """The sample town with `display.phone_tile`, woven and served over http."""
    home = tmp_path_factory.mktemp("message-fold")
    pack = home / "pack"
    shutil.copytree(SAMPLE, pack)
    world = pack / "world.json"
    wj = json.loads(world.read_text(encoding="utf-8"))
    wj["display"] = {"phone_tile": TILE}
    world.write_text(json.dumps(wj), encoding="utf-8")
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "phone.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/phone.html"
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


def open_game(browser, url, w, h, touch, fold_ms=FOLD_WAIT_MS, query=""):
    """The player on the map, with the test-only fold wait already in place."""
    ctx = browser.new_context(viewport={"width": w, "height": h},
                              has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    # Set before the player runs, so even the first line folds on this wait.
    page.add_init_script(f"window.VEFR_MESSAGES_FOLD_MS = {fold_ms}")
    page.goto(url + query)
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(300)
    return ctx, page


def say_a_line(page, control):
    """A message line the way a player makes one: with nothing in reach on
    the sample town's starting tile, the Talk control writes one gentle line
    into #near and the Interact control another, so two calls are two lines
    and not a repeat of one."""
    page.click(f"#{control}")
    page.wait_for_function("() => document.getElementById('near').textContent.length > 0")


def panel(page):
    """[folded, aria-expanded] of the messages panel, read off the DOM."""
    return page.evaluate("""() => {
      const panel = document.getElementById('toasts');
      const toggle = document.getElementById('toasts-toggle');
      return [panel.classList.contains('is-collapsed'), toggle.getAttribute('aria-expanded')];
    }""")


def remembered(page):
    """What the panel stored for this world: '1' folded by hand, else nothing."""
    return page.evaluate(
        "() => localStorage.getItem('vefr-ui-messages-' + (window.VEFR_WORLD.name || 'world'))")


def wait_folded(page):
    page.wait_for_function(
        "() => document.getElementById('toasts').classList.contains('is-collapsed')",
        timeout=FOLD_WAIT_MS * 15)


def wait_shown(page):
    page.wait_for_function(
        "() => !document.getElementById('toasts').classList.contains('is-collapsed')",
        timeout=FOLD_WAIT_MS * 15)


def test_the_panel_folds_itself_on_a_phone_and_the_button_opens_it_again(browser, served):
    ctx, page = open_game(browser, served, PHONE_W, PHONE_H, touch=True, query="?camera=phone")
    try:
        assert page.evaluate("window.VEFR_STAGE.phone") is True, \
            "this pack on a touch phone is not on the phone camera"
        say_a_line(page, "talk")
        wait_shown(page)
        assert panel(page) == [False, "true"], f"the panel is not open for a new line: {panel(page)}"
        wait_folded(page)
        assert panel(page) == [True, "false"], "the panel folded without saying so to a screen reader"
        assert remembered(page) in (None, "0"), \
            f"the camera's own fold was remembered: {remembered(page)!r}"
        # A new line reads again, and folds itself after its own wait.
        say_a_line(page, "interact")
        wait_shown(page)
        wait_folded(page)
        # Tapping Messages opens it, and the wait starts again from the tap.
        page.click("#toasts-toggle")
        assert panel(page) == [False, "true"], "Messages did not open the folded panel"
        wait_folded(page)
        assert panel(page)[0] is True, "the panel did not fold again after it was opened"
    finally:
        ctx.close()


def test_a_fold_by_hand_is_remembered_and_a_new_line_does_not_open_it(browser, served):
    # The engine's own fold is pushed out of the way here, so the tap below is
    # the player's own fold and never a race with one.
    ctx, page = open_game(browser, served, PHONE_W, PHONE_H, touch=True, fold_ms=30000,
               query="?camera=phone")
    try:
        say_a_line(page, "talk")
        wait_shown(page)
        page.click("#toasts-toggle")          # the panel is open: this folds it by hand
        assert panel(page) == [True, "false"], "the tap did not fold the panel"
        assert remembered(page) == "1", f"a fold by hand is not remembered: {remembered(page)!r}"
        say_a_line(page, "interact")
        page.wait_for_timeout(FOLD_WAIT_MS * 4)
        assert panel(page) == [True, "false"], \
            "a new line opened a panel the player had folded by hand"
    finally:
        ctx.close()


def test_at_a_desk_window_the_panel_never_folds_itself(browser, served):
    ctx, page = open_game(browser, served, DESK_W, DESK_H, touch=False)
    try:
        assert page.evaluate("window.VEFR_STAGE.phone") is False, \
            "the same pack at a desk window is on the phone camera"
        say_a_line(page, "talk")
        assert panel(page) == [False, "true"], f"the panel is not open for a new line: {panel(page)}"
        page.wait_for_timeout(FOLD_WAIT_MS * 6)
        assert panel(page) == [False, "true"], "the panel folded itself with the phone camera off"
    finally:
        ctx.close()