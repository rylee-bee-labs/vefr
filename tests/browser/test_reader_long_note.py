"""A long note keeps Read on in reach, in a real browser (Chromium).

Issue #165: on a phone the Read on control sat under the reader card's
max-height overflow fold, so the dialog looked like it had no way on.
The woven player of a pack with one LONG note is opened on the note; the
test asks the page what is at the centre of Read on (the same
document.elementFromPoint sample the cottage probe takes) and whether the
control lies inside the card's visible box, at a phone and a desktop size.

Without a browser these skip (fixtures.py's browser fixture).
"""

import argparse
import importlib.util
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
MAKE = ROOT / "tests" / "fixtures" / "make_book_label_pack.py"

LONG_NOTE = (
    "---\ntitle: A Note Left at the Door\nfound: map\nat: [3, 1]\n"
    "kind: note\n---\n"
    + "\n\n".join(
        "Somebody knocked and nobody answered, and the knocking went on "
        "through the long grey evening until the lamps were lit. " * 4
        for _ in range(6))
    + "\n\n* * *\n\nThe rest is blank.\n")

SIZES = [(390, 844), (360, 640), (1280, 800)]

PROBE = """() => {
  const b = document.getElementById('reader-next');
  const card = document.querySelector('#reader .reader-card');
  const r = b.getBoundingClientRect(), c = card.getBoundingClientRect();
  const hit = document.elementFromPoint(r.left + r.width / 2,
                                        r.top + r.height / 2);
  return {hit: !!hit && (hit === b || b.contains(hit)),
          inside: r.top >= c.top && r.bottom <= c.bottom,
          overflows: card.scrollHeight > card.clientHeight};
}"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("long-note-home")
    spec = importlib.util.spec_from_file_location("make_book_label_pack", MAKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BOOK = LONG_NOTE
    pack = mod.build(home)
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "book.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/book.html"
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


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_read_on_is_in_the_cards_visible_area(browser, woven, size):
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]})
    page = ctx.new_page()
    try:
        page.goto(woven)
        page.evaluate("localStorage.setItem('vefr-save-seed', '42')")
        page.get_by_role("button", name="Begin").click()
        page.wait_for_function(
            "window.VEFR_COMBAT && window.VEFR_COMBAT.region")
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("ArrowRight")
        page.wait_for_function(
            "() => !document.getElementById('reader').hidden")
        got = page.evaluate(PROBE)
        assert got["overflows"], "the fixture note must overflow the card"
        assert got["inside"], f"Read on is under the fold: {got}"
        assert got["hit"], f"something is drawn over Read on: {got}"
    finally:
        ctx.close()
