"""The verbs an item grants, in the game (the item-grants slice, E1).

An item may declare `"grants": [{"verb": "mend", "label": "Mend the hull"}]`.
While the hero carries that item the verb sits in the verb row beside the
act's own; when the item is spent, given away or worn it goes with it - or
stays, if it is worn, because a worn thing is still carried. Pressing it
fires `uses-verb`, the event a pack authors what the press does with.

What this file proves, and each in its own test:

  * picking an item up adds its verb button, with the words the pack wrote
    on it, and the number keys follow it to its place in the row;
  * pressing that button fires the rule the pack wrote on `uses-verb`;
  * the `changes` a carried thing declares is the damage its verb lands;
  * using the thing up takes the verb away again;
  * wearing a thing that grants a verb keeps the verb in the row;
  * a pack that grants nothing shows exactly the row it showed before -
    the same bytes, read from a weave of the sample world untouched.

Every reading is from the published `window.VEFR_*` snapshots
(`VEFR_VERBS`, `VEFR_RULES_STATE`, `VEFR_WHY`) or from the DOM the player
is looking at; nothing here reaches into a private variable.

Without `uv run playwright install chromium` these skip - fixtures.py's
browser fixture, not a failure.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
MAKE = FIXTURES / "make_grants_pack.py"
SAMPLE = ROOT / "worlds" / "sample-world"

# The verb row as the player reads it: the verb, the words on its face and
# the number that presses it. Read from the DOM, because that is the row.
ROW = """() => Array.from(
  document.querySelectorAll('#verb-row button[data-verb]')
).map(b => ({verb: b.dataset.verb,
             label: b.textContent.replace(/\\s+/g, ' ').trim(),
             key: (b.querySelector('kbd') || {}).textContent || ''}))"""

# What the hero is carrying, as the bag and the worn map read it.
CARRIED = """() => {
  const bag = ((window.VEFR_COMBAT || {}).bag) || [];
  return {bag: bag.slice(),
          verbs: (window.VEFR_VERBS || []).map(v => ({
            verb: v.verb, label: v.label, from: v.from, atk: v.atk }))};
}"""

FLAGS = """() => (((window.VEFR_RULES_STATE || {}).flags) || {})"""

WHY = """() => (window.VEFR_WHY || []).map(e => e.id)"""


def _weave(pack: Path, out: Path) -> Path:
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


def _open(browser, html: Path):
    ctx = browser.new_context(viewport={"width": 1100, "height": 900})
    page = ctx.new_page()
    page.goto(html.as_uri())
    page.click("#ts-enter")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    # The row is painted from the same list the snapshot publishes, so wait
    # for the snapshot rather than for a frame: a granted verb that has
    # arrived is on `window.VEFR_VERBS` before the next paint.
    page.wait_for_function("() => Array.isArray(window.VEFR_VERBS)",
                           timeout=15000)
    return ctx, page


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The grants pack as shipped: three items, three verbs, four rules."""
    home = tmp_path_factory.mktemp("grants")
    out = subprocess.run([sys.executable, str(MAKE), str(home)],
                         capture_output=True, text=True, check=True).stdout
    return _weave(Path(out.strip().splitlines()[-1]), home / "grants.html")


@pytest.fixture(scope="module")
def woven_none(tmp_path_factory):
    """The same pack with the grants taken out: the items, and nothing else."""
    home = tmp_path_factory.mktemp("grants-none")
    out = subprocess.run([sys.executable, str(MAKE), str(home), "none"],
                         capture_output=True, text=True, check=True).stdout
    return _weave(Path(out.strip().splitlines()[-1]), home / "none.html")


@pytest.fixture(scope="module")
def woven_sample(tmp_path_factory):
    """The sample world exactly as it ships - the row a pack with no
    `grants` anywhere must still show."""
    return _weave(SAMPLE, tmp_path_factory.mktemp("grants-sample") / "sample.html")


def _press(page, verb):
    """Press a verb the way the player does - through the row's own click -
    and return once the press has run.

    The press is dispatched from the page rather than by the mouse: the row
    is only on screen during a fight, and a verb a pack granted has to work
    on an ordinary floor too, which is where these tests stand.
    """
    assert page.evaluate(
        "(verb) => { const b = document.querySelector("
        "  '#verb-row button[data-verb=' + JSON.stringify(verb) + ']');"
        "  if (!b) return false; b.click(); return true; }", verb), (
            f"the verb row has no button for {verb!r}")
    page.wait_for_timeout(150)


def _bag_button(page, action, item):
    """The bag panel's own button for one thing - Equip or Use - pressed
    through the DOM, since the panel is closed while the test stands on a
    quiet floor and closing it changes nothing the buttons do."""
    assert page.evaluate(
        "(sel) => { const b = document.querySelector(sel);"
        "  if (!b) return false; b.click(); return true; }",
        f'#bag-list button[data-action="{action}"][data-item="{item}"]'), (
            f"the bag panel has no {action} button for {item!r}")


def test_picking_a_thing_up_adds_its_verb_to_the_row(browser, woven):
    """The mallet hands the hero `mend`, with the words the pack wrote on
    the button, and the digits are renumbered so the number keys still
    answer through the one row."""
    ctx, page = _open(browser, woven)
    try:
        verbs = page.evaluate(CARRIED)
        assert {v["verb"] for v in verbs["verbs"]} == {"mend", "reef", "chalk"}
        by_verb = {v["verb"]: v for v in verbs["verbs"]}
        assert by_verb["mend"]["label"] == "Mend the hull"
        assert by_verb["mend"]["from"] == "mallet-1"
        # `changes` is what carrying the mallet does to that verb, and it
        # rides out beside it rather than being hidden in the catalog.
        assert by_verb["mend"]["atk"] == 2
        # A verb nothing changes carries no change at all.
        assert by_verb["chalk"]["atk"] == 0

        row = page.evaluate(ROW)
        # The act's own three are still first, in the order it always had.
        assert [b["verb"] for b in row][:3] == ["attack", "console", "hurl"]
        granted = {b["verb"]: b for b in row[3:]}
        assert set(granted) == {"mend", "reef", "chalk"}
        assert granted["mend"]["label"] == "Mend the hull 4"
        assert granted["mend"]["key"] == "4"
        assert granted["chalk"]["key"] == "6"
    finally:
        ctx.close()


def test_the_change_a_thing_carries_is_the_damage_its_verb_lands(browser, woven):
    """`changes` is not decoration: while the mallet is carried, `mend` is a
    blow worth the hero's own attack plus what the mallet adds to it. The
    rat beside the hero's start is what the blow lands on."""
    ctx, page = _open(browser, woven)
    try:
        page.keyboard.press("f")     # Interact: name the rat one tile right
        page.wait_for_function(
            "() => (document.getElementById('verb-row')"
            ".getAttribute('aria-label') || '').startsWith('What to do about')",
            timeout=15000)
        hero = page.evaluate("() => window.VEFR_COMBAT.hero")
        rat_before = page.evaluate(
            "() => window.VEFR_COMBAT.enemies.filter(e => e.alive)[0].hp")
        _press(page, "mend")
        page.wait_for_function(
            "() => window.VEFR_COMBAT.enemies.filter(e => e.alive)[0].hp < "
            + str(rat_before), timeout=15000)
        rat_after = page.evaluate(
            "() => window.VEFR_COMBAT.enemies.filter(e => e.alive)[0].hp")
        assert rat_before - rat_after == hero["atk"] + 2, (
            f"the mallet grants +2 attack to `mend`, so the blow should land "
            f"for {hero['atk']} + 2, not {rat_before - rat_after}")
    finally:
        ctx.close()


def test_pressing_a_granted_verb_fires_the_rule_the_pack_wrote(browser, woven):
    """The press is a fact of the world: it fires `uses-verb`, the rule
    runs, and the flag the rule set is there to be read."""
    ctx, page = _open(browser, woven)
    try:
        assert page.evaluate(FLAGS).get("mended") is not True
        _press(page, "mend")
        page.wait_for_function(
            "() => ((window.VEFR_RULES_STATE || {}).flags || {}).mended === true",
            timeout=15000)
        assert "the-mallet-spoke" in page.evaluate(WHY)
        # A verb the hero is not carrying fires nothing: the act's own
        # `console` is pressed here, and the pack wrote no rule for it.
        before = page.evaluate(WHY)
        _press(page, "console")
        page.wait_for_timeout(300)
        assert page.evaluate(WHY) == before
    finally:
        ctx.close()


def test_using_the_thing_up_takes_its_verb_away(browser, woven):
    """The chalk is spent by the press of the verb it granted - the pack's
    own rule takes it back - so the verb leaves the row with the thing,
    because the verb was never stored anywhere else."""
    ctx, page = _open(browser, woven)
    try:
        assert "chalk" in [b["verb"] for b in page.evaluate(ROW)]
        _press(page, "chalk")
        page.wait_for_function(
            "() => !document.querySelector('#verb-row button"
            "[data-verb=\"chalk\"]')", timeout=15000)
        carried = page.evaluate(CARRIED)
        assert "chalk-1" not in carried["bag"]
        assert "chalk" not in {v["verb"] for v in carried["verbs"]}
        # The verbs of the things still carried stay exactly where they were.
        assert {v["verb"] for v in carried["verbs"]} == {"mend", "reef"}
        # And the digits close up behind it, so the number keys still
        # answer through the one row.
        row = page.evaluate(ROW)
        assert [b["key"] for b in row] == [str(i + 1) for i in range(len(row))]
    finally:
        ctx.close()


def test_wearing_a_thing_keeps_the_verb_it_grants(browser, woven):
    """A worn thing is out of the bag list, so a verb read from the bag
    alone would blink off the moment the glove was put on."""
    ctx, page = _open(browser, woven)
    try:
        _bag_button(page, "equip", "glove-1")
        page.wait_for_function(
            "() => !((window.VEFR_COMBAT || {}).bag || []).includes('glove-1')",
            timeout=15000)
        assert "glove-1" not in page.evaluate(CARRIED)["bag"]
        assert "reef" in [b["verb"] for b in page.evaluate(ROW)]
        verbs = page.evaluate(CARRIED)["verbs"]
        assert [v["verb"] for v in verbs if v["from"] == "glove-1"] == ["reef"]
    finally:
        ctx.close()


def test_a_pack_that_grants_nothing_shows_the_row_it_always_did(
        browser, woven_none, woven_sample):
    """The backward-compatibility proof, in the browser: the items are the
    same three and the row is the row the untouched sample world paints -
    same verbs, same labels, same digits - and the snapshot says there is
    nothing granted."""
    ctx, page = _open(browser, woven_none)
    try:
        none_row = page.evaluate(ROW)
        none_verbs = page.evaluate(CARRIED)
    finally:
        ctx.close()
    assert none_verbs["verbs"] == []
    assert none_verbs["bag"], "the fixture pack should still hand the items over"

    ctx, page = _open(browser, woven_sample)
    try:
        assert page.evaluate(ROW) == none_row
        assert page.evaluate(CARRIED)["verbs"] == []
    finally:
        ctx.close()


def test_the_pack_with_no_grants_still_plays_its_own_rules(browser, woven_none):
    """Nothing about a pack that declines the feature changed: the bag holds
    what it is given, the rules still fire on what the player does, and a
    plain verb press fires no rule the pack did not write."""
    ctx, page = _open(browser, woven_none)
    try:
        assert "mallet-1" in page.evaluate(CARRIED)["bag"]
        flags = page.evaluate(FLAGS)
        assert flags.get("tooled") is True      # `starts` still hands the bag over
        assert flags.get("mended") is not True  # nothing granted `mend`
        _press(page, "console")
        assert page.evaluate(WHY) == ["the-tool-bag"]
    finally:
        ctx.close()

def test_a_rule_on_the_acts_own_verb_fires_too(browser, tmp_path_factory):
    """#531 review: the validator accepts a `uses-verb` rule on a verb the act already had
    (maplab.pack_verbs), so pressing that verb must fire it, granted or not."""
    import json as _json
    home = tmp_path_factory.mktemp("plain-verb")
    out = subprocess.run([sys.executable, str(MAKE), str(home), "none"],
                         capture_output=True, text=True, check=True).stdout
    pack = Path(out.strip().splitlines()[-1])
    w = _json.loads((pack / "world.json").read_text())
    w.setdefault("rules", []).append({"id": "plain-console", "when": {"uses-verb": {"verb": "console"}},
                                     "once": True, "then": [{"set": "consoled"}]})
    (pack / "world.json").write_text(_json.dumps(w))
    ctx, page = _open(browser, _weave(pack, home / "plain.html"))
    try:
        _press(page, "console")
        assert page.evaluate(FLAGS).get("consoled") is True, "a rule on the act's own verb never fired"
    finally:
        ctx.close()
