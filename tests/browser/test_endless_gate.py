"""The stair past the last Section is shut until the pack's story ends, in a real browser.

The descent fixture's last floor of the story is the last floor of its
last Section; its down stair leads into endless cycle 1. That stair names
the pack's `story_end` flag, says so in one sentence while it is shut,
and opens when that flag is set - and no other flag opens it. The flag
here is not the default, so the test reads what the pack declares.
"""

import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli, delve, stamps

from .test_descent_reload import DESCENT as BASE
from .test_descent_reload import _free_port, descend_to, open_woven

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixtures"))
import make_descent_pack  # noqa: E402

FLAG = "the-quiet-room-is-reached"
ENDED = dict(BASE, story_end=FLAG)
LAST = sum(section["floors"] for section in make_descent_pack.SECTIONS)
SHUT = f"The stair is shut until the story ends: {FLAG} must be set."

CELLAR, HOLLOW = make_descent_pack.SECTIONS
GATE_LOCKED = ("The stair is shut. Go up to town first: town knows nothing of the way "
               "on until you have read what is kept down here.")
CELLAR_TOWN_SEEN = "town-seen:cellar:c0"


def _single_floor(section, **extra):
    kept = {key: value for key, value in section.items() if key != "pattern"}
    return {**kept, "floors": 1, **extra}


# The one-floor cellar takes the warden slot, where its vault sits; hollow has none.
# One floor each: depth 1 cellar, 2 hollow, 3 cellar in cycle 1.
STAMPS = Path(__file__).resolve().parents[1] / "fixtures" / "stamps"
RECORDS = json.loads(json.dumps(stamps.load(STAMPS)))
VAULTED = dict(BASE, story_end=FLAG, stamps=RECORDS, sections=[
    _single_floor(CELLAR, pattern=["warden"], stamps=["cellar"],
                  vault={"stamp": "vault-cellar", "sets": "cellar-read"}),
    _single_floor(HOLLOW),
])


def _serve(tmp_path_factory, name, descent):
    home = tmp_path_factory.mktemp(f"{name}-home")
    pack = make_descent_pack.build(home, descent=descent)
    if "stamps" in descent:
        shutil.copytree(STAMPS, pack / "stamps")
    out = home / f"{name}.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
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
def woven(tmp_path_factory):
    yield from _serve(tmp_path_factory, "endless", ENDED)


@pytest.fixture(scope="module")
def vaulted(tmp_path_factory):
    yield from _serve(tmp_path_factory, "vaulted", VAULTED)


def _interact(page):
    page.locator("#interact").click()
    page.wait_for_timeout(200)


def test_the_stair_past_the_last_section_says_what_it_waits_for(page, woven):
    open_woven(page, woven)
    last = descend_to(page, LAST)
    _interact(page)
    # innerText is the rendered text and reads empty on a browser that lays out no glyphs;
    # textContent is the line the element carries. The region assertion below proves the gate held.
    assert page.locator("#combat-live").text_content() == SHUT
    assert page.evaluate("() => window.VEFR_COMBAT.region") == last["name"]


def test_the_declared_story_end_opens_the_stair_into_endless(page, woven):
    open_woven(page, woven)
    descend_to(page, LAST)
    page.evaluate(f"() => window.VEFR_DESCENT.setFlag('{FLAG}', true)")
    _interact(page)
    endless = delve.floor_plan(ENDED, LAST + 1)
    page.wait_for_function(
        "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'" % endless["name"])


def test_another_flag_does_not_open_the_stair(page, woven):
    open_woven(page, woven)
    last = descend_to(page, LAST)
    page.evaluate("() => window.VEFR_DESCENT.setFlag('king-slain', true)")
    _interact(page)
    assert page.locator("#combat-live").text_content() == SHUT
    assert page.evaluate("() => window.VEFR_COMBAT.region") == last["name"]


def test_a_vaulted_section_still_shuts_its_stair_in_cycle_zero(page, vaulted):
    open_woven(page, vaulted)
    first = descend_to(page, 1, descent=VAULTED)
    _interact(page)
    assert page.locator("#combat-live").text_content() == GATE_LOCKED
    assert page.evaluate("() => window.VEFR_COMBAT.region") == first["name"]


def test_an_endless_section_with_a_vault_opens_its_stair_without_a_town_visit(page, vaulted):
    open_woven(page, vaulted)
    # The cycle-0 visit is set by its flag; no flag is set for cycle 1.
    page.evaluate(f"() => window.VEFR_DESCENT.setFlag('{CELLAR_TOWN_SEEN}', true)")
    page.evaluate(f"() => window.VEFR_DESCENT.setFlag('{FLAG}', true)")
    descend_to(page, 3, descent=VAULTED)
    _interact(page)
    there = delve.floor_plan(VAULTED, 4)
    page.wait_for_function(
        "() => window.VEFR_COMBAT && window.VEFR_COMBAT.region === '%s'" % there["name"])
