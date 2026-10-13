"""The phone layout a skinned, levelled pack plays in (docs/design/storybook/DESIGN.md).

- Look: a pack whose world.json says `display.look: "plain"` starts on the plain dark
  look with its skin offered in Display; picking the skin paints it at once, and the
  choice is the player's and outlives a reload. A skinned pack that says nothing starts
  painted, as every skinned pack always has.
- The top bar on a touch screen keeps health (and quickslots) only: the level line and
  gold are not drawn there, and the level reads in the Bag beside the gold.
- The phone camera follows the hero at the pack's tile on a small map too, instead of
  blowing a small room up to fill the width.
"""

import json
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

import play_kit

PHONE = {"width": 390, "height": 844}
LOOK_KEY = "() => 'vefr-look-' + (window.VEFR_WORLD.name || 'world')"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def serve(tmp_path):
    """Serve one woven file over http, so localStorage is the real thing."""
    procs = []

    def _serve(html):
        port = _free_port()
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
             "--directory", str(html.parent)],
            stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        procs.append(proc)
        url = f"http://127.0.0.1:{port}/{html.name}"
        for _ in range(120):
            try:
                urllib.request.urlopen(url, timeout=2)
                return url
            except Exception:  # noqa: BLE001 - not up yet
                time.sleep(0.25)
        pytest.fail("the woven file never came up")

    yield _serve
    for proc in procs:
        proc.terminate()
        proc.wait(timeout=10)


def enter(page):
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(300)


def phone(browser):
    return browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)


LOOK = """() => ({ skin: document.body.classList.contains('has-skin'),
  sheet: !!document.getElementById('vefr-skin-css') && !document.getElementById('vefr-skin-css').disabled,
  offered: !document.getElementById('look-settings').hidden,
  checked: (document.querySelector('input[name=look]:checked') || {}).value || null })"""


def test_a_plain_look_pack_starts_dark_and_the_skin_is_one_tap_away(browser, tmp_path, serve):
    pack = play_kit.pack(tmp_path, "skin", {"world.json": {"display": {"look": "plain"}}})
    url = serve(play_kit.weave(pack, tmp_path))
    ctx = phone(browser)
    try:
        page = ctx.new_page()
        page.goto(url)
        enter(page)
        start = page.evaluate(LOOK)
        assert start == {"skin": False, "sheet": False, "offered": True, "checked": "plain"}, start
        page.click("#menu-open")
        page.click('[data-panel="display"]')
        page.check('input[name="look"][value="skin"]')
        painted = page.evaluate(LOOK)
        assert painted["skin"] and painted["sheet"], f"picking the skin did not paint it: {painted}"
        assert page.evaluate(f"localStorage.getItem(({LOOK_KEY})())") == "skin"
        page.reload()
        enter(page)
        again = page.evaluate(LOOK)
        assert again["skin"] and again["checked"] == "skin", f"the choice did not outlive a reload: {again}"
    finally:
        ctx.close()


def test_the_dark_look_stays_dark_on_a_light_mode_phone(browser, tmp_path):
    """A phone set to light mode drew every panel on cream paper over the dark
    world; the Dark look is dark whatever the device says."""
    pack = play_kit.pack(tmp_path, "skin", {"world.json": {"display": {"look": "plain"}}})
    html = play_kit.weave(pack, tmp_path)
    ctx = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True, color_scheme="light")
    try:
        page = ctx.new_page()
        page.goto(html.as_uri())
        enter(page)
        card = page.evaluate("getComputedStyle(document.body).getPropertyValue('--card').trim()")
        assert card.upper() == "#15181D", f"the Dark look drew its panels in {card} on a light-mode phone"
    finally:
        ctx.close()


def test_a_skinned_pack_that_names_no_look_starts_painted(browser, tmp_path):
    html = play_kit.weave(play_kit.pack(tmp_path, "skin"), tmp_path)
    ctx = phone(browser)
    try:
        page = ctx.new_page()
        page.goto(html.as_uri())
        enter(page)
        look = page.evaluate(LOOK)
        assert look["skin"] and look["sheet"] and look["checked"] == "skin", look
    finally:
        ctx.close()


def test_a_phone_top_bar_keeps_health_and_the_level_reads_in_the_bag(browser, tmp_path):
    pack = play_kit.pack(tmp_path, "growth", growth=play_kit.make_growth_pack.LEVELS)
    html = play_kit.weave(pack, tmp_path)
    ctx = phone(browser)
    try:
        page = ctx.new_page()
        page.goto(html.as_uri())
        enter(page)
        drawn = page.evaluate("""() => ['hud-hp', 'hud-level', 'hud-gold'].map(id =>
          document.getElementById(id).getClientRects().length > 0)""")
        assert drawn == [True, False, False], f"[health, level, gold] drawn on the top bar: {drawn}"
        level = page.evaluate("document.getElementById('bag-level').textContent")
        assert level.startswith("Level 1"), f"the Bag does not say the level: {level!r}"
    finally:
        ctx.close()


def test_a_small_map_on_a_phone_draws_at_the_pack_tile(browser, tmp_path):
    pack = play_kit.pack(tmp_path, "interact", {"world.json": {"display": {"phone_tile": 52}}})
    # The town cut down to a room five tiles across: before, a phone drew a map
    # this small whole at 78 px, wider than the pack asked for.
    act = pack / "acts" / "act-1"
    (act / "town" / "map.md").write_text("#####\n#...#\n#...#\n#####\n", encoding="utf-8")
    cfg = json.loads((act / "world.json").read_text(encoding="utf-8"))
    cfg["transitions"] = []
    (act / "world.json").write_text(json.dumps(cfg), encoding="utf-8")
    html = play_kit.weave(pack, tmp_path)
    ctx = phone(browser)
    try:
        page = ctx.new_page()
        page.goto(html.as_uri() + "?camera=phone")
        enter(page)
        stage = page.evaluate("window.VEFR_STAGE")
        assert stage["phone"] is True, stage
        assert abs(stage["tile"] - 52) < 0.5, f"a small map on a phone drew at {stage['tile']} px, not 52"
    finally:
        ctx.close()
