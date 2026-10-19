"""Talking to someone fires `comes-near`, in a real browser.

The page-level half of the fix: the Interact verb - what the F key and
the button that reads `Talk to <name>` reach - named the resident it
picked and spoke to them with no rules event at all, so a pack's
`comes-near` rule over a person never heard the one press most players
make. Here the woven mending pack is played as a player plays it: Begin,
two steps right until the keeper is in reach, then F.

The Talk button's own nearest-speaker search already fired the event
(tests/browser/test_time_rest.py covers that road); what is checked here
is the other one, and that both reach the same event.

Skips without chromium, like the rest of tests/browser.
"""

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
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_mending_pack  # noqa: E402

# One rule over the sample's own keeper (at [7, 4]) at the reach the
# verb has: `once: False`, so a second talk is a second firing.
RULES = [
    {"id": "keeper-hears-you",
     "when": {"comes-near": {"who": "keeper", "distance": 2}},
     "then": [{"say": "The Keeper looks up."}],
     "once": False},
]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(home: Path, name: str):
    """Serve `home` over http; return the URL of `name` inside it and the
    http process, so the caller can stop it when the module is done."""
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/{name}"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    return url, proc


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    """The mending pack plus the watcher's rule, woven and served."""
    home = tmp_path_factory.mktemp("talk-near")
    built = make_mending_pack.build(home)
    world = json.loads((built / "world.json").read_text(encoding="utf-8"))
    world["rules"] = RULES
    (built / "world.json").write_text(json.dumps(world), encoding="utf-8")
    (home / "talk-near.html").write_text(cli.weave_html(built), encoding="utf-8")
    url, proc = _serve(home, "talk-near.html")
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def enter(page, url):
    """Enter the woven game the way a player enters it."""
    page.goto(url)
    page.get_by_role("button", name="Begin").click()
    if page.is_visible("#config"):     # first run asks before it plays
        page.click("#cfg-offline")
    page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region")


def walk_to_the_keeper(page):
    """Two steps right: the hero stands at [5, 4], two tiles from the
    keeper at [7, 4] - the reach the rule declares."""
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(200)
    page.keyboard.press("ArrowRight")
    page.wait_for_timeout(200)


def why_ids(page) -> list:
    return page.evaluate("() => (window.VEFR_WHY || []).map(function (e) { return e.id; })")


def close_the_speech_box(page):
    """The box a talk opens, closed the way a player closes it."""
    if page.locator("#npc-box").is_visible():
        page.locator("#npc-close").click()
        page.wait_for_timeout(150)


def test_a_talk_with_the_f_key_fires_the_comes_near_rule(page, served):
    """One F press at a resident's tile fires the rule that watches for
    that resident, and says its line."""
    enter(page, served)
    walk_to_the_keeper(page)
    # The button's CSS uppercases its words, and inner_text() hands back the
    # text as the page shows it, so the case is not ours to assert on.
    assert page.locator("#interact-label").inner_text().strip().lower() == "talk to the keeper"
    assert "keeper-hears-you" not in why_ids(page), \
        "the walk fired a rule only a talk should"
    page.keyboard.press("f")
    page.wait_for_timeout(400)
    assert "keeper-hears-you" in why_ids(page), \
        "the talk did not fire the rule that watches for the keeper"
    assert "the keeper looks up." in page.locator("#combat-live").inner_text().lower()


def test_the_interact_button_says_the_same_thing_the_f_key_does(page, served):
    """The `Talk to <name>` button is the same verb, so it fires the same
    event - and the Talk button's own nearest-speaker search agrees."""
    enter(page, served)
    walk_to_the_keeper(page)
    page.locator("#interact").click()
    page.wait_for_timeout(400)
    close_the_speech_box(page)
    page.locator("#talk").click()
    page.wait_for_timeout(400)
    close_the_speech_box(page)
    assert why_ids(page).count("keeper-hears-you") == 2, why_ids(page)