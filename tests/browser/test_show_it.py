"""Show it (ADR 0023), in Chromium: what jsdom cannot measure.

`tests/test_show_it_play.py` plays every rule in jsdom. This file asks a real
browser what only a laid-out page can answer, on a desk and on a phone:

  - the quick bar is on screen on both, every button at least 44 px square,
    the key letters printed on the desk and not on the phone;
  - the spell card is inside the window with its button in reach, and the
    focus on it;
  - the "Wear it?" buttons are at least 44 px tall and inside the window;
  - a blow's number is drawn over the tile of the one it struck, and not
    over the hero.

The pack is the RPG fixture (the sample town and one hound beside the hero)
with all four `display` keys on.

Run with: uv run pytest tests/browser/test_show_it.py
"""

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_rpg_pack as mk  # noqa: E402

PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1280, "height": 720}
SIZES = [(DESKTOP, False), (PHONE, True)]
IDS = ["desktop", "phone"]

SPELLS = {"schools": ["ember"], "spells": [
    {"id": "bolt", "name": "an ember bolt", "school": "ember", "level": 2, "mana": 2, "harm": 3},
    {"id": "ward", "name": "a warding word", "school": "ember", "level": 2, "mana": 1,
     "ward": {"guard": 2, "turns": 2}},
]}
DISPLAY = {"spell_card": True, "wear_prompt": True, "hit_numbers": True, "hotbar": True}

BOX = """sel => Array.from(document.querySelectorAll(sel)).map(el => {
  const r = el.getBoundingClientRect();
  return {x: r.left, y: r.top, w: r.width, h: r.height,
          shown: getComputedStyle(el).display !== 'none' && r.width > 0};
})"""


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    d = tmp_path_factory.mktemp("show-it")
    pack = mk.build(d, items=mk.ITEMS, spells=SPELLS, player={"mana": 4, "hp": 30},
                    growth={"mode": "levels", "levels": {"xp": [0, 3, 50], "gain": {"hp": 1, "atk": 1}}},
                    hound={"xp": 5, "hp": 40}, display=DISPLAY)
    out = d / "show-it.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


@contextmanager
def playing(browser, woven, size, touch):
    ctx = browser.new_context(viewport=size, has_touch=touch, is_mobile=touch)
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        if page.is_visible("#config"):
            page.click("#cfg-save")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(300)
        yield page
    finally:
        ctx.close()


def inside(box, size):
    return (box["x"] >= 0 and box["y"] >= 0 and box["x"] + box["w"] <= size["width"]
            and box["y"] + box["h"] <= size["height"])


@pytest.mark.parametrize("size,touch", SIZES, ids=IDS)
def test_the_spell_card_is_in_reach_and_the_bar_is_on_screen(browser, woven, size, touch):
    with playing(browser, woven, size, touch) as page:
        page.evaluate("() => { bagAdd('potion'); bagAdd('potion'); growAward(3); }")
        page.wait_for_function("!document.getElementById('learn').hidden", timeout=3000)
        card = page.evaluate(BOX, "#learn .fcard")[0]
        ok = page.evaluate(BOX, "#learn-ok")[0]
        assert inside(card, size), card
        assert ok["h"] >= 44 and inside(ok, size), ok
        assert page.evaluate("() => document.activeElement.id") == "learn-ok"
        page.keyboard.press("Escape")
        page.keyboard.press("Escape")
        page.wait_for_function("document.getElementById('learn').hidden", timeout=3000)

        buttons = page.evaluate(BOX, "#touch-quick .hot-btn")
        assert len(buttons) == 3, buttons             # the potion, the bolt, the ward
        for b in buttons:
            assert b["shown"] and b["w"] >= 44 and b["h"] >= 44 and inside(b, size), b
        keys = page.evaluate(BOX, "#touch-quick .hot-key")
        assert all(k["shown"] for k in keys) is (not touch), keys


@pytest.mark.parametrize("size,touch", SIZES, ids=IDS)
def test_the_wear_question_is_in_reach(browser, woven, size, touch):
    with playing(browser, woven, size, touch) as page:
        page.evaluate("() => { bagAdd('keen-blade');"
                      " offerToWear({id: 'keen-blade', rarity: '', traits: [], identified: false}); }")
        page.wait_for_function("!document.getElementById('wear-ask').hidden", timeout=3000)
        for b in page.evaluate(BOX, "#wear-ask button"):
            assert b["h"] >= 44 and inside(b, size), b
        page.keyboard.press("y")
        page.wait_for_function("EQUIP_STATE.hand === 'keen-blade'", timeout=3000)


def test_a_blow_is_numbered_over_the_one_it_struck(browser, woven):
    with playing(browser, woven, DESKTOP, False) as page:
        page.keyboard.press("ArrowLeft")
        page.wait_for_function("document.querySelectorAll('#hits .hit').length >= 1", timeout=3000)
        seen = page.evaluate("""() => {
          const T = VEFR_STAGE.tile, cam = VEFR_CAMERA();
          const canvas = document.getElementById('town-canvas').getBoundingClientRect();
          const foe = VEFR_COMBAT.enemies[0].at, hero = VEFR_COMBAT.hero.at;
          const hit = document.querySelector('#hits .hit--hit').getBoundingClientRect();
          const mid = hit.left + hit.width / 2;
          return {mid: mid, foe: canvas.left + foe[0] * T - cam.x, hero: canvas.left + hero[0] * T - cam.x, T: T};
        }""")
        assert seen["foe"] <= seen["mid"] <= seen["foe"] + seen["T"], seen
        assert not (seen["hero"] <= seen["mid"] <= seen["hero"] + seen["T"]), seen
