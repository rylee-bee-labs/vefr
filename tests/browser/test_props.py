"""Map props, in a real browser.

A prop is a picture on the ground. A prop whose footprint blocks walking
stops the hero exactly as a wall does; a prop that blocks nothing does
not. Each test weaves the sample town with one stone beside the hero's
start and opens the file the way a player does.

The hero starts at [3, 4] and the stone sits at [4, 4], directly east.
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
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_props_pack as mk  # noqa: E402

BLOCKING = [{"pic": "stone", "at": [4, 4]}]
OPEN = [{"pic": "stone", "at": [4, 4], "block": ["."]}]
# flat, under the hero, on the tile beside her start
GROUND = [{"pic": "stone", "at": [4, 4], "block": ["."], "layer": "ground"}]
# a tall open prop one row below the hero's start: it stands in front of her
TALL = [{"pic": "stone", "at": [3, 5], "block": ["."]}]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve_woven(tmp_path_factory, name, props):
    home = tmp_path_factory.mktemp(name)
    pack = mk.build(home, props=props)
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "props.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/props.html"
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
def blocked(tmp_path_factory):
    yield from _serve_woven(tmp_path_factory, "props-blocking", BLOCKING)


@pytest.fixture(scope="module")
def open_stone(tmp_path_factory):
    yield from _serve_woven(tmp_path_factory, "props-open", OPEN)


@pytest.fixture(scope="module")
def ground_stone(tmp_path_factory):
    yield from _serve_woven(tmp_path_factory, "props-ground", GROUND)


@pytest.fixture(scope="module")
def tall_stone(tmp_path_factory):
    yield from _serve_woven(tmp_path_factory, "props-tall", TALL)


def open_woven(page, url):
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def step(page, key):
    page.keyboard.press(key)
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def hero_at(page):
    return page.evaluate("window.VEFR_COMBAT.hero.at")


def test_a_blocking_prop_stops_the_hero_like_a_wall(page, blocked):
    open_woven(page, blocked)
    assert hero_at(page) == [3, 4]
    step(page, "ArrowRight")
    assert hero_at(page) == [3, 4]


def test_a_prop_that_blocks_nothing_lets_the_hero_pass(page, open_stone):
    open_woven(page, open_stone)
    assert hero_at(page) == [3, 4]
    step(page, "ArrowRight")
    assert hero_at(page) == [4, 4]


def test_the_props_view_reports_the_stone_and_its_blocked_cell(page, blocked):
    open_woven(page, blocked)
    view = page.evaluate("window.VEFR_PROPS()")
    assert view["props"] == [{"pic": "stone", "at": [4, 4], "size": [1, 1],
                              "frames": 1, "fps": 4}]
    assert "4,4" in view["blocked"]


def test_the_draw_order_names_the_stone_and_the_hero(page, blocked):
    open_woven(page, blocked)
    order = page.evaluate("window.VEFR_DRAW_ORDER")
    assert "prop:stone" in order
    assert "hero" in order


def test_a_ground_prop_is_drawn_under_the_hero_standing_on_it(page, ground_stone):
    open_woven(page, ground_stone)
    step(page, "ArrowRight")
    assert hero_at(page) == [4, 4]
    order = page.evaluate("window.VEFR_DRAW_ORDER")
    assert order.index("ground:stone") < order.index("hero"), order
    assert "prop:stone" not in order


def test_a_standing_prop_is_in_front_of_the_hero_north_of_it_and_behind_her_south_of_it(page, tall_stone):
    open_woven(page, tall_stone)
    assert hero_at(page) == [3, 4]                      # north of the prop's row: it covers her
    order = page.evaluate("window.VEFR_DRAW_ORDER")
    assert order.index("hero") < order.index("prop:stone"), order
    step(page, "ArrowDown")
    step(page, "ArrowDown")
    assert hero_at(page) == [3, 6]                      # south of it: she is in front
    order = page.evaluate("window.VEFR_DRAW_ORDER")
    assert order.index("prop:stone") < order.index("hero"), order
