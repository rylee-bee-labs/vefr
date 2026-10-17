"""Mending, in a real browser: two carried things become one (E2).

The mending fixture pack (sample-world + recipes, built by
`tests/fixtures/make_mending_pack.py`) carries two things that mend
into one and one thing that fits no recipe, so the whole flow plays
with no story text from any pitch:

  - a valid pair previews, then mends: both inputs are spent, the
    output is carried, the recipe's own line is said, the pack's rule
    hears the `mends` event, and the last mend is published on
    `window.VEFR_LAST_MEND`;
  - either order mends - mending the peg with the net is the same mend;
  - Cancel leaves the bag untouched;
  - an unmatched pair changes nothing and says plainly that nothing fits;
  - a pack without recipes shows no Mend control at all.

Run with: uv run pytest tests/browser/test_mending.py
"""

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
import play_kit  # noqa: E402

# The carried names, as the bag panel says them.
TORN_NET = "a torn net"
LOOSE_PEG = "a loose peg"
WHOLE_NET = "a whole net"
DRIFTWOOD = "a piece of dry driftwood"

RECIPE_LINE = "The net is whole again."
REACTION_LINE = "The yard trusts you a little more."


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """Both fixture packs, woven into one folder and served over http, so
    localStorage behaves the way it does for a player."""
    d = tmp_path_factory.mktemp("mending")
    play_kit.weave(play_kit.pack(d, "mending"), d).rename(d / "mending.html")
    play_kit.weave(play_kit.pack(d, "combat"), d).rename(d / "plain.html")
    port = _free_port()
    log = open(d / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(d)],
        stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    # The readiness probe talks to the server directly: a sandbox with
    # an HTTP proxy set would otherwise route 127.0.0.1 through it.
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for _ in range(120):
        try:
            direct.open(base + "/mending.html", timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven files never came up; see {d / 'server.log'}")
    yield base + "/mending.html", base + "/plain.html"
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="module")
def woven(served):
    return served[0]


@pytest.fixture(scope="module")
def plain(served):
    return served[1]


def enter(page, url, bag=None, bag_key="vefr-bag-mending-test"):
    """Open the woven game, plant the bag it starts from, and Begin.

    The bag is planted after the page is up and before Begin, the
    moment a saved game's bag is the one the player walks in with.
    """
    page.goto(url)
    if bag is not None:
        page.evaluate(
            "(pair) => localStorage.setItem(pair[0], JSON.stringify(pair[1]))",
            [bag_key, bag])
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(300)


def open_bag(page):
    page.click("#bagbtn")
    page.locator('[data-panel-body="bag"]').wait_for(state="visible")


def carried(page):
    """The bag panel's rows: one name per thing carried, in order."""
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('#bag-list .bag-row-name'))
                   .map(el => el.textContent.trim())""")


def mend_button(page, item):
    """One row's Mend button, by the item it mends with."""
    return page.locator(
        f'#bag-list [data-action="mend"][data-item="{item}"]')


def bag_saved(page):
    """The saved bag list, straight out of the one storage key it lives in."""
    return json.loads(page.evaluate(
        "() => localStorage.getItem('vefr-bag-mending-test')"))


def last_mend(page):
    return page.evaluate("() => window.VEFR_LAST_MEND")


def live_line(page):
    return page.text_content("#bag-live").strip()


def test_a_valid_pair_previews_then_mends(page, woven):
    enter(page, woven, ["torn-net", "loose-peg", "dry-driftwood"])
    open_bag(page)
    assert carried(page) == [TORN_NET, LOOSE_PEG, DRIFTWOOD]

    # Pick one thing, then the second: the preview names what the pair
    # makes before anything is spent.
    mend_button(page, "torn-net").click()
    mend_button(page, "loose-peg").click()
    assert page.locator("#mend-preview").is_visible()
    assert page.text_content("#mend-preview").strip().startswith(
        f"Mending {TORN_NET} and {LOOSE_PEG} makes {WHOLE_NET}.")
    # What the result will let the hero do, by the label the verb row will show (E1's grants shape).
    assert "It grants: Cast the net." in page.text_content("#mend-preview")
    # Nothing is spent yet: the preview is a look, not a change.
    assert bag_saved(page) == ["torn-net", "loose-peg", "dry-driftwood"]

    page.click("#mend-confirm")
    # Both inputs are gone and the output is carried.
    assert carried(page) == [DRIFTWOOD, WHOLE_NET], carried(page)
    assert bag_saved(page) == ["dry-driftwood", "whole-net"]
    # The recipe's own line is the one the panel says.
    assert live_line(page) == RECIPE_LINE
    # The pack's rule heard the mends event and said its piece.
    assert page.text_content("#combat-live").strip() == REACTION_LINE
    # The last mend is published for the harness snapshots to read.
    assert last_mend(page) == {
        "recipe": "mend-the-net",
        "inputs": ["torn-net", "loose-peg"],
        "output": "whole-net"}
    # The preview closed behind the mend.
    assert page.locator("#mend-preview").is_hidden()


def test_either_order_mends_the_same_pair(page, woven):
    enter(page, woven, ["loose-peg", "torn-net"])
    open_bag(page)
    mend_button(page, "loose-peg").click()
    mend_button(page, "torn-net").click()
    assert page.locator("#mend-preview").is_visible()
    assert page.text_content("#mend-preview").strip().startswith(
        f"Mending {LOOSE_PEG} and {TORN_NET} makes {WHOLE_NET}.")
    page.click("#mend-confirm")
    assert carried(page) == [WHOLE_NET]
    assert last_mend(page)["output"] == "whole-net"


def test_cancel_leaves_the_bag_unchanged(page, woven):
    enter(page, woven, ["torn-net", "loose-peg"])
    open_bag(page)
    before = bag_saved(page)
    mend_button(page, "torn-net").click()
    mend_button(page, "loose-peg").click()
    assert page.locator("#mend-preview").is_visible()
    page.click("#mend-cancel")
    assert bag_saved(page) == before
    assert carried(page) == [TORN_NET, LOOSE_PEG]
    assert page.locator("#mend-preview").is_hidden()
    assert last_mend(page) is None


def test_an_unmatched_pair_changes_nothing_and_says_so(page, woven):
    enter(page, woven, ["torn-net", "dry-driftwood"])
    open_bag(page)
    before = bag_saved(page)
    mend_button(page, "torn-net").click()
    mend_button(page, "dry-driftwood").click()
    # No preview for a pair no recipe names, and the bag keeps everything.
    assert page.locator("#mend-preview").is_hidden()
    assert bag_saved(page) == before
    assert carried(page) == [TORN_NET, DRIFTWOOD]
    assert live_line(page) == (
        f"Nothing you carry mends {TORN_NET} with {DRIFTWOOD}.")
    assert last_mend(page) is None


def test_a_pack_without_recipes_shows_no_mend_control(page, plain):
    enter(page, plain, ["cloudy-potion"], bag_key="vefr-bag-combat-test")
    open_bag(page)
    assert carried(page) == ["a cloudy potion"]
    # No Mend button on any row, and the preview never opened.
    assert page.locator('#bag-list [data-action="mend"]').count() == 0
    assert not page.evaluate(
        "() => Array.from(document.querySelectorAll('#bag-list button'))"
            ".some(b => /mend/i.test(b.textContent))")
    assert page.locator("#mend-preview").is_hidden()
    assert last_mend(page) is None