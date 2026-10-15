"""The monsters' walking, in a real browser.

The rest of this suite drives the studio - the builder, not a woven
player. This one opens a woven file itself (a fixture floor with a wall
in it) over a plain local server, which is how a player meets the game:
one file, opened and played. Chromium draws it for real; the numbers
come from the file's own VEFR_COMBAT snapshot, the same one the jsdom
harness in tests/fixtures reads.

Three things are proved here, and all three are about the floor rather
than about a straight line:

  - a monster walks the long way round a wall to reach the hero, and
    hits them;
  - a monster hurt to a third of what it walked in with runs instead of
    closing;
  - two monsters who cannot see the hero drift toward each other.

Deterministic: the fixture is fixed and nothing in the movement path
rolls dice, so every position below is pinned.
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
MAKE = ROOT / "tests" / "fixtures" / "make_wall_pack.py"

# The fixture floor: the rat is under the wall, and the only way across
# is the doorway at [7, 2].
DOOR_TILE = [7, 2]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """A woven single-file player for the wall fixture, served over http.

    Served rather than opened as a file:// page so localStorage and the
    file's own fetches behave the way they do for a player.
    """
    home = tmp_path_factory.mktemp("wall-home")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    rc = cli.cmd_build_web(argparse.Namespace(
        pack=str(pack), out=str(home / "wall.html"), pool=0,
        with_bundle=False, from_live=None))
    assert rc == 0
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/wall.html"
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


# ---- playing it, in the words a person would use ----

def open_woven(page, url):
    """Open the woven file and step through its title screen."""
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def step(page, key):
    """One turn: a keypress, then a frame to let the turn finish."""
    page.keyboard.press(key)
    page.evaluate(
        "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def state(page):
    return page.evaluate("window.VEFR_COMBAT")


def said(page):
    return page.locator("#combat-live").inner_text()


def monster(snap, monster_id):
    return next(e for e in snap["enemies"] if e["id"] == monster_id)


def walk_distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def key_toward(frm, to):
    if to[0] != frm[0]:
        return "ArrowRight" if to[0] > frm[0] else "ArrowLeft"
    return "ArrowDown" if to[1] > frm[1] else "ArrowUp"


def key_away(frm, to):
    return {"ArrowRight": "ArrowLeft", "ArrowLeft": "ArrowRight",
            "ArrowUp": "ArrowDown", "ArrowDown": "ArrowUp"}[key_toward(frm, to)]


def the_rat_reaches_the_hero(page, limit=30):
    """Pace the hero up and down its corridor until the rat is on it.

    The hero cannot wait - every turn is a step - so it walks back and
    forth between the two tiles either side of its start while the rat
    comes round. Returns the tiles the rat stood on, in order.
    """
    walked = [[1, 3]]
    keys = ["ArrowRight", "ArrowLeft"]
    for turn in range(limit):
        step(page, keys[turn % 2])
        snap = state(page)
        here = monster(snap, "far-rat")["at"]
        if here != walked[-1]:
            walked.append(here)
        if "hits you" in said(page) and walk_distance(here, snap["hero"]["at"]) == 1:
            return walked, snap
    pytest.fail(f"the rat never reached the hero; it walked {walked}")


def test_a_monster_walks_the_long_way_round_a_wall(page, woven):
    open_woven(page, woven)
    start = state(page)
    assert start["region"] == "town"
    assert start["hero"] == {"hp": 12, "max": 12, "atk": 2, "at": [2, 1]}
    # The rat is under the wall and the hero is straight above it: every
    # straight line out of that tile is wall.
    assert monster(start, "far-rat")["at"] == [1, 3]

    walked, snap = the_rat_reaches_the_hero(page)

    # It went the long way, through the one doorway, not through a wall:
    # [1, 3] east along the bottom corridor, up at [7, 2], then west.
    assert walked[0] == [1, 3]
    assert walked[1] == [2, 3]
    assert DOOR_TILE in walked
    assert walked.index(DOOR_TILE) < walked.index([7, 1])
    # And it is next to the hero, having hit them.
    assert walk_distance(monster(snap, "far-rat")["at"], snap["hero"]["at"]) == 1
    assert snap["hero"]["hp"] == 11
    # The first landed blow of a game also teaches bump-to-strike (#464),
    # on the same line, after the fight's own words.
    assert said(page).startswith("a far rat hits you for 1."), said(page)


def test_a_hurt_monster_runs_instead_of_closing(page, woven):
    open_woven(page, woven)
    _walked, snap = the_rat_reaches_the_hero(page)
    rat = monster(snap, "far-rat")
    # The last turn's bump - the hero cannot help but walk into the rat
    # that has just arrived - left it at one of the three health it
    # walked into the region with. That is a third: badly hurt.
    assert rat["hp"] == 1
    assert walk_distance(rat["at"], snap["hero"]["at"]) == 1

    # Badly hurt, it puts the floor between itself and the hero rather
    # than closing the last tile: the hero steps west to [1, 1] and the
    # rat goes the other way, away from the hero, never back at it.
    # [3, 2] is wall, so east along the corridor is the only way off.
    step(page, key_away(snap["hero"]["at"], rat["at"]))
    after = state(page)
    rat_after = monster(after, "far-rat")
    assert after["hero"]["at"] == [1, 1]
    assert rat_after["at"] == [4, 1]
    assert walk_distance(rat_after["at"], after["hero"]["at"]) == 3
    assert after["hero"]["hp"] == snap["hero"]["hp"]   # no second bite


def test_two_monsters_out_of_sight_find_each_other(page, woven):
    open_woven(page, woven)
    # Leave by the door in the corner the hero started beside.
    for _ in range(4):
        step(page, "ArrowLeft")
    assert state(page)["hero"]["at"] == [1, 1]
    step(page, "f")
    cellar = state(page)
    assert cellar["region"] == "cellar"
    hound = monster(cellar, "gutter-hound")["at"]
    crow = monster(cellar, "cold-crow")["at"]
    assert walk_distance(hound, crow) == 3
    # Neither can see the hero from that far off, so neither comes.
    assert walk_distance(hound, cellar["hero"]["at"]) > 2
    assert walk_distance(crow, cellar["hero"]["at"]) > 2

    # The hero paces in its own corner. The two monsters close on each
    # other: one step each puts them nose to nose, and then they hold.
    for turn in range(4):
        step(page, "ArrowDown" if turn % 2 == 0 else "ArrowUp")
        snap = state(page)
        hound = monster(snap, "gutter-hound")["at"]
        crow = monster(snap, "cold-crow")["at"]
        assert walk_distance(hound, crow) == 1
        assert walk_distance(hound, snap["hero"]["at"]) > 2
        assert walk_distance(crow, snap["hero"]["at"]) > 2
    # Nothing was fought for: the hero is as whole as they were.
    assert snap["hero"]["hp"] == 12
    assert [hound, crow] == [[7, 1], [8, 1]]
