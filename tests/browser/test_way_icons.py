"""A way out is drawn as what it is, in a real browser (Chromium).

The interact fixture pack has one transition, a door on the town's [9, 3]. Two woven files are
served: one where that transition is named a down stair and the pack brings `way-stairs-down`, and
one plain door with no pack picture. Every drawImage call is recorded by source, so the test reads
which picture reached the canvas rather than sampling pixels.

Without `uv run playwright install chromium` these skip, as the other browser tests do.
"""

import argparse
import base64
import json
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

# A 1x1 PNG: enough for the bake to inline a picture the browser decodes.
PICTURE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

# Records each drawImage source before the real call, so the test can read what was drawn.
SPY = """
window.__drawn = [];
const realDraw = CanvasRenderingContext2D.prototype.drawImage;
CanvasRenderingContext2D.prototype.drawImage = function (img, ...rest) {
  if (img && img.src) window.__drawn.push(img.src);
  return realDraw.apply(this, arguments);
};
"""


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve_woven(tmp_path_factory, name: str, *, stair: bool, picture: bool):
    home = tmp_path_factory.mktemp(f"way-icons-{name}")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    if stair:
        contract_path = pack / "acts" / "act-1" / "town" / "contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["pois"] = {"9,3": "the stair down"}
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
    if picture:
        (pack / "tiles").mkdir(exist_ok=True)
        (pack / "tiles" / "way-stairs-down.png").write_bytes(PICTURE)
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / f"{name}.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/{name}.html"
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


@pytest.fixture(scope="module")
def stair_woven(tmp_path_factory):
    yield from _serve_woven(tmp_path_factory, "stair", stair=True, picture=True)


@pytest.fixture(scope="module")
def door_woven(tmp_path_factory):
    yield from _serve_woven(tmp_path_factory, "door", stair=False, picture=False)


def _drawn_after_play(page, url):
    page.add_init_script(SPY)
    page.goto(url)
    page.evaluate("localStorage.setItem('vefr-save-seed', '42')")
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    page.wait_for_timeout(600)  # the pictures decode, then the map redraws
    return page.evaluate("window.__drawn")


def test_a_down_stair_draws_the_stairs_down_picture(page, stair_woven):
    drawn = _drawn_after_play(page, stair_woven)
    picture = page.evaluate("window.VEFR_WAY_ICONS['stairs-down']")
    assert picture.startswith("data:image/png;base64,")
    assert picture in drawn, "the down stair never drew its own picture"
    assert page.evaluate("window.VEFR_DOOR") not in drawn, (
        "the down stair fell back to the door picture")


def test_a_door_without_a_pack_picture_still_draws_the_door(page, door_woven):
    drawn = _drawn_after_play(page, door_woven)
    assert page.evaluate("window.VEFR_WAY_ICONS") == {}
    door = page.evaluate("window.VEFR_DOOR")
    assert door.startswith("data:image/webp;base64,")
    assert door in drawn, "a door with no pack picture no longer draws the door art"
