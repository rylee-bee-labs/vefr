"""Acceptance 1, in Chromium: the same seed gives the same floor after a reload.

A floor is generated at the stair, so the only thing that can keep it the
same is the run seed and the rule that nothing else may be consulted.
This walks out of the town of the woven fixture pack and down onto a
generated floor in a real browser, records the floor and what was
remembered about it, reloads the page, walks the same way, and demands
the same floor and the same memory. The browser is what the plan names
(PLAN §5, row E1); it skips without chromium, like the rest of
tests/browser.
"""

import copy
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli, delve

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixtures"))
import make_descent_pack  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _quiet(descent):
    """The fixture's descent with nothing living on the floors.

    The walks below are planned against the floor the generator drew, and
    a monster that wakes and walks is a step the plan cannot promise. The
    fight on a generated floor is proved in tests/test_descent_deltas.py.
    """
    out = copy.deepcopy(descent)
    for section in out["sections"]:
        # No family, no monster: the count is generator policy, so `mobs` is
        # never read; this walk passed on v2 only because no monster stood on
        # it (E8-0, 2026-10-09).
        section["families"] = []
    return out


DESCENT = _quiet({
    "run_seed": "run-a",
    "entry": {"region": "town", "at": list(make_descent_pack.ENTRY_AT)},
    "sections": make_descent_pack.SECTIONS,
})

KEYS = {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight"}
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
TOWN_HERO = [3, 4]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("descent-home")
    pack = make_descent_pack.build(home, descent=DESCENT)
    out = home / "descent.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/descent.html"
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


def _walk(page, path):
    for name in path:
        page.keyboard.press(KEYS[name])
        page.wait_for_timeout(12)


def _path(plan, start, goal, avoid=()):
    from collections import deque
    blocked = {tuple(a) for a in avoid}
    seen = {tuple(start)}
    queue = deque([(tuple(start), [])])
    while queue:
        (x, y), steps = queue.popleft()
        if (x, y) == tuple(goal):
            return steps
        for name, (dx, dy) in DIRS.items():
            nxt = (x + dx, y + dy)
            if nxt in seen or nxt in blocked:
                continue
            if not (0 <= nxt[1] < plan["h"] and 0 <= nxt[0] < plan["w"]):
                continue
            if plan["rows"][nxt[1]][nxt[0]] == "#":
                continue
            seen.add(nxt)
            queue.append((nxt, steps + [name]))
    return []


def descend_to(page, depth, descent=DESCENT):
    """Walk out of the town and down to `depth`, one stair at a time."""
    plan = delve.floor_plan(descent, 1)
    _walk(page, _path(TOWN, TOWN_HERO, descent["entry"]["at"]))
    page.locator("#interact").click()
    page.wait_for_function(
        "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'" % plan["name"])
    for d in range(1, depth):
        here = delve.floor_plan(descent, d)
        _walk(page, _path(here, here["anchors"]["up"], here["anchors"]["down"]))
        page.locator("#interact").click()
        page.wait_for_function(
            "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'"
            % delve.floor_plan(descent, d + 1)["name"])
    last = delve.floor_plan(descent, depth)
    _walk(page, _path(last, last["anchors"]["up"], last["anchors"]["down"]))
    return last


TOWN = {"rows": (ROOT / "worlds" / "sample-world" / "acts" / "act-1" / "town"
                 / "map.md").read_text(encoding="utf-8").splitlines(),
        "w": 12, "h": 10}


def read_floor(page):
    return page.evaluate(
        "() => ({name: window.VEFR_DESCENT.floor.name,"
        " key: window.VEFR_DESCENT.floor.key,"
        " rows: window.VEFR_DESCENT.floor.rows,"
        " mobs: window.VEFR_DESCENT.floor.mobs,"
        " doc: window.VEFR_DESCENT.doc})")


def open_woven(page, url):
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def test_the_same_seed_draws_the_same_floor_after_a_reload(page, woven):
    open_woven(page, woven)
    first = descend_to(page, 1)
    a = read_floor(page)
    assert a["name"] == first["name"]
    assert a["doc"]["floors"][first["name"]]["fog"], "the walk was remembered"

    page.reload()
    open_woven(page, woven)
    descend_to(page, 1)
    b = read_floor(page)

    assert b["rows"] == a["rows"], "the same seed must draw the same floor"
    assert b["mobs"] == a["mobs"], "the same mobs on the same tiles"
    assert b["key"] == a["key"]
    assert b["doc"]["floors"][first["name"]]["fog"] == a["doc"]["floors"][first["name"]]["fog"]


def test_a_third_floor_generates_on_its_own_seed(page, woven):
    open_woven(page, woven)
    descend_to(page, 1)
    page.reload()
    open_woven(page, woven)
    descend_to(page, 3)
    got = read_floor(page)
    three = delve.floor_plan(DESCENT, 3)
    # The floor the run key names, not merely a floor that differs from
    # another one: a grid that merely differs from floor one's would pass
    # even if every depth drew the same wrong floor.
    assert got["name"] == three["name"], \
        f"depth 3 is {got['name']}, not the floor depth 3 names"
    assert got["key"] == three["key"], \
        f"depth 3 is keyed {got['key']!r}, not {three['key']!r}"
    assert got["rows"] == three["rows"], \
        "the floor the key names is not the grid the key draws"
    assert got["doc"]["floors"][three["name"]]["k"] == three["key"], \
        "the save does not remember depth 3 as the floor that key names"
    assert got["rows"] != delve.floor_plan(DESCENT, 1)["rows"], \
        "a third floor is a different floor"