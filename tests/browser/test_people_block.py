"""player.people_block: a pack's people stand in the way when it asks, and only then.

The sample world's hero starts at [3, 4] in the town and the keeper stands at [7, 4]. Four steps right: with
`people_block` she stops beside the keeper, facing her; without it she walks onto the keeper's tile as before.
"""

import argparse
import json
import shutil
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
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("people-block")
    for name, block in (("solid", True), ("plain", None)):
        pack = home / f"{name}-pack"
        shutil.copytree(SAMPLE, pack)
        cfg = json.loads((pack / "world.json").read_text(encoding="utf-8"))
        if block is not None:
            cfg.setdefault("player", {})["people_block"] = block
        (pack / "world.json").write_text(json.dumps(cfg), encoding="utf-8")
        assert cli.cmd_build_web(argparse.Namespace(pack=str(pack), out=str(home / f"{name}.html"), pool=0,
                                                    with_bundle=False, from_live=None)) == 0
    port = _free_port()
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                             "--directory", str(home)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    for _ in range(120):
        try:
            urllib.request.urlopen(f"{base}/solid.html", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    yield {"solid": f"{base}/solid.html", "plain": f"{base}/plain.html"}
    proc.terminate()
    proc.wait(timeout=10)


def walk_right(page, url, n):
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")
    assert page.evaluate("window.VEFR_COMBAT.hero.at") == [3, 4]
    for _ in range(n):
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(200)
    return page.evaluate("window.VEFR_COMBAT.hero.at")


def test_a_solid_person_stops_the_hero_beside_them(page, woven):
    assert walk_right(page, woven["solid"], 4) == [6, 4]


def test_without_people_block_the_hero_walks_through_as_before(page, woven):
    assert walk_right(page, woven["plain"], 4) == [7, 4]
