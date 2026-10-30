"""Show it (ADR 0023), played in the real woven file in jsdom.

Four `display` keys, each off unless a pack says true, and one fix:

  * `spell_card`  - a card says what a spell just learned does, what it
    costs and how to cast it, on a level and from a book, one card per
    spell, and a walking key does not wave it away;
  * `wear_prompt` - gear picked up that would raise a number asks "Wear
    it?" with the change, Y wears it and N keeps it, and an unread trait is
    in no number;
  * `hit_numbers` - each blow's number over the one it struck, the hero's
    hurt over the hero, and still under reduced motion;
  * `hotbar`      - the things used in one tap and the spells known, keys
    5 to 8, with the fight row's digits stopping at 4;
  * the fall card's note no longer says the bag is as it was when the fall
    left it on the floor.

And the pack that names none of it plays as it did. Every read is what a
player and a screen reader get, or the harness view the player publishes.
Needs node and jsdom; skips without them.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli, maplab

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "rpg_play_harness.mjs"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_rpg_pack as mk  # noqa: E402

import test_rpg_core_play as rpg  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

ALL = {"spell_card": True, "wear_prompt": True, "hit_numbers": True, "hotbar": True}
# Two spells learned on the same level, the second level, which one kill of
# the hound (5 xp) reaches.
SPELLS = {"schools": ["ember"], "spells": [
    {"id": "bolt", "name": "an ember bolt", "school": "ember", "level": 2, "mana": 2, "harm": 3},
    {"id": "ward", "name": "a warding word", "school": "ember", "level": 2, "mana": 1,
     "ward": {"guard": 2, "turns": 2}},
    {"id": "mend", "name": "a mending word", "school": "ember", "heal": 3},
]}
GROWTH = {"mode": "levels", "levels": {"xp": [0, 3, 50], "gain": {"hp": 1, "atk": 1}}}
ITEMS = dict(mk.ITEMS, **{
    "mend-book": {"name": "a mending primer", "spell": "mend", "use": "read"},
    "sly-ring": {"name": "a sly ring", "slot": "charm", "traits": ["keen"]},
})
LEFT = {"do": "press", "dir": "left"}
KILL = [LEFT, LEFT, LEFT]                      # 5 hp, 2 a blow


def play(tmp_path, steps, display=ALL, media=True, pack=None, **build):
    """Weave the RPG fixture with the show-it keys and play `steps`.

    `media` is what every media query answers: True is the harness's own
    default (a touch screen, motion reduced by the OS), False a desk with
    motion on.
    """
    opts = {"items": ITEMS, "spells": SPELLS, "player": {"mana": 4}, "growth": GROWTH,
            "traits": mk.TRAITS, "hound": {"xp": 5}, "display": display}
    opts.update(build)
    pack = pack or mk.build(tmp_path, **opts)
    out = tmp_path / "show-it.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    spec = {"steps": steps, "matchMedia": media}
    run = subprocess.run(["node", str(HARNESS), str(out), json.dumps(spec)],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr + run.stdout
    result = json.loads(run.stdout)
    assert result["errors"] == [], result["errors"]
    return result


def ev(js, tag):
    return {"do": "eval", "js": js, "tag": tag}


CARD = ev("({open: !document.getElementById('learn').hidden,"
          " line: document.getElementById('learn-line').textContent,"
          " notes: Array.from(document.querySelectorAll('#learn-notes li')).map(l => l.textContent),"
          " focus: document.activeElement && document.activeElement.id})", "card")
ASK = ev("({open: !document.getElementById('wear-ask').hidden,"
         " line: (document.getElementById('wear-line') || {}).textContent || '',"
         " change: Array.from(document.querySelectorAll('#wear-ask .wear-change')).map(p => p.textContent),"
         " focus: document.activeElement && document.activeElement.id,"
         " hand: EQUIP_STATE.hand || null, charm: EQUIP_STATE.charm || null,"
         " bag: bagItems(), live: document.getElementById('combat-live').textContent})", "ask")
# Every number drawn, in order, kept by an observer started before the fight.
WATCH = ev("window.__hits = []; new MutationObserver(function (m) { m.forEach(function (r) {"
           " r.addedNodes.forEach(function (n) { __hits.push([n.dataset.kind, n.textContent]); }); }); })"
           ".observe(document.getElementById('hits'), {childList: true}); true", "watch")
HITS = ev("({seen: __hits, now: Array.from(document.querySelectorAll('#hits .hit')).map(e => e.textContent)})",
          "hits")
BAR = ev("({hidden: document.getElementById('touch-quick').hidden,"
         " bar: document.getElementById('touch-quick').classList.contains('hotbar'),"
         " names: Array.from(document.querySelectorAll('#touch-quick button')).map(b => b.getAttribute('aria-label')),"
         " keys: Array.from(document.querySelectorAll('#touch-quick kbd')).map(k => k.textContent)})", "bar")


def key(k):
    return {"do": "key", "key": k}


# ------------------------------------------------------------------ opt-out


def test_a_pack_that_names_none_of_it_shows_none_of_it(tmp_path):
    out = play(tmp_path, [WATCH, *KILL, LEFT, CARD, ASK, BAR, HITS,
                          ev("spellsKnown().map(s => s.id)", "known")],
               display=None, hound={"xp": 5, "drops": ["keen-blade"]})
    evals = out["evals"]
    assert evals["hits"]["seen"] == []             # a fight, and no number drawn
    assert evals["known"] == ["bolt", "ward"]
    assert evals["card"]["open"] is False          # the spells were learned, with no card
    assert evals["ask"]["open"] is False and evals["ask"]["hand"] is None
    assert "keen-blade" in evals["ask"]["bag"]
    assert evals["bar"]["bar"] is False            # the quickslots stay the quickslots
    assert not [k for k in out["final"]["saved"] if "hotbar" in k or "learn" in k]


def test_the_four_keys_validate_and_refuse_anything_but_true_or_false(tmp_path):
    pack = mk.build(tmp_path, display=ALL)
    assert maplab.display_errors(maplab.load_pack(pack)) == []
    for name in ALL:
        bad = mk.build(tmp_path / name, display={name: "yes"})
        errs = maplab.display_errors(maplab.load_pack(bad))
        assert len(errs) == 1 and f"display.{name} must be true or false" in errs[0], errs


# --------------------------------------------------------------- spell card


def test_a_level_teaches_two_spells_and_each_gets_its_card(tmp_path):
    out = play(tmp_path, [*KILL, CARD, key("Escape"), {**CARD, "tag": "second"},
                          key("Escape"), {**CARD, "tag": "after"}])["evals"]
    first = out["card"]
    assert first["open"] and first["line"] == "You learn an ember bolt."
    assert first["notes"] == [
        "It strikes the nearest foe within 6 tiles for 3. Guard does not stop it.",
        "It costs 2 mana.",
        "Press 5 or tap it on the quick bar. It is in the Bag too.",
    ]
    assert first["focus"] == "learn-ok"
    second = out["second"]
    assert second["line"] == "You learn a warding word."
    assert second["notes"][0] == "It raises your guard by 2 for 2 turns."
    assert second["notes"][-1].startswith("Press 6 ")
    assert out["after"]["open"] is False


def test_a_walking_key_does_not_wave_the_card_away(tmp_path):
    out = play(tmp_path, [*KILL, key("ArrowLeft"), key("a"), CARD,
                          ev("VEFR_COMBAT.hero.at", "at"), key("f"), {**CARD, "tag": "after"}])
    assert out["evals"]["card"]["open"] is True
    assert out["evals"]["at"] == [3, 4]            # the hero did not walk under it
    assert out["evals"]["after"]["line"] == "You learn a warding word."   # Interact went on


def test_without_the_bar_the_card_names_the_fight_row_and_the_bag(tmp_path):
    out = play(tmp_path, [*KILL, CARD, key("Escape"), {**CARD, "tag": "ward"}],
               display={"spell_card": True})["evals"]
    assert out["card"]["notes"][-1] == "In a fight, Cast on the fight row casts it. It is in the Bag too."
    assert out["ward"]["notes"][-1] == "Cast it from the Bag."


def test_a_book_read_gets_a_card_and_a_second_reading_does_not(tmp_path):
    out = play(tmp_path, [ev("bagAdd('mend-book'); bagAdd('mend-book'); useItem('mend-book'); true", "read"),
                          CARD, key("Escape"),
                          ev("useItem('mend-book'); !document.getElementById('learn').hidden", "again")])
    card = out["evals"]["card"]
    assert card["line"] == "You learn a mending word."
    assert card["notes"][0] == "It heals you by 3."
    assert len(card["notes"]) == 2                 # no mana cost on this one
    assert out["evals"]["again"] is False


def test_the_card_is_kept_on_the_quiet_page(tmp_path):
    out = play(tmp_path, [*KILL, ev("store.getJSON(pageKey(), [])", "page")])
    assert {"line": "You learn an ember bolt.", "who": ""} in out["evals"]["page"]


# ---------------------------------------------------------------- Wear it?


def test_better_gear_picked_up_asks_and_y_wears_it(tmp_path):
    out = play(tmp_path, [*KILL, key("Escape"), key("Escape"), LEFT, ASK, key("y"),
                          {**ASK, "tag": "worn"}], hound={"xp": 5, "drops": ["keen-blade"]})
    ask = out["evals"]["ask"]
    assert ask["open"] and ask["line"] == "Wear a keen blade?"
    # Level 2 made the hero's attack 3; the blade's own +1 is all that is
    # known - its traits are unread, so they are in no number.
    assert ask["change"] == ["Attack from 3 → to 4"]
    assert ask["focus"] == "wear-no"               # the answer that changes nothing
    worn = out["evals"]["worn"]
    assert worn["open"] is False and worn["hand"] == "keen-blade"
    assert "keen-blade" not in worn["bag"]
    assert worn["live"] == "You put on a keen blade. Attack up by 1."


def test_n_keeps_it_in_the_bag(tmp_path):
    out = play(tmp_path, [*KILL, key("Escape"), key("Escape"), LEFT, {**ASK, "tag": "asked"}, key("n"), ASK],
               hound={"xp": 5, "drops": ["keen-blade"]})["evals"]
    assert out["asked"]["open"] is True
    assert out["ask"]["open"] is False and out["ask"]["hand"] is None
    assert "keen-blade" in out["ask"]["bag"]


def test_gear_that_raises_nothing_known_does_not_ask(tmp_path):
    """A plain ring raises nothing; a ring whose only good is an unread
    trait raises nothing the player can know, so neither asks - and the
    blade picked up with them, which does, is the one asked about."""
    out = play(tmp_path, [*KILL, key("Escape"), key("Escape"), LEFT, ASK],
               hound={"xp": 5, "drops": ["plain-ring", "sly-ring", "keen-blade"]})["evals"]["ask"]
    assert out["open"] is True and out["line"] == "Wear a keen blade?"
    assert out["bag"].count("plain-ring") == 1 and out["bag"].count("sly-ring") == 1


def test_the_question_names_what_comes_off(tmp_path):
    out = play(tmp_path, [ev("bagAdd('warded-coat'); equipItem('warded-coat'); true", "wear"),
                          ev("offerToWear({id: 'warded-coat', rarity: '', traits: [], identified: false})", "same"),
                          ev("VEFR_ITEMS['thick-coat'] = {name: 'a thick coat', slot: 'body',"
                             " mods: {guard: 2, hp: 1}}; bagAdd('thick-coat');"
                             " offerToWear({id: 'thick-coat', rarity: '', traits: [], identified: false})", "better"),
                          ASK])["evals"]
    assert out["same"] is False                    # the same coat again raises nothing
    assert out["better"] is True
    assert out["ask"]["change"] == ["Health from 8 → to 9", "Guard from 1 → to 2",
                                    "a warded coat comes off."]


# ------------------------------------------------------------- hit numbers


def test_each_blow_draws_its_number_over_the_one_it_struck(tmp_path):
    out = play(tmp_path, [WATCH, LEFT, HITS])["evals"]
    assert out["hits"]["seen"] == [["hit", "2"], ["hurt", "-3"]]
    assert out["hits"]["now"] == ["2", "-3"]


def test_misses_and_critical_blows_say_so(tmp_path):
    out = play(tmp_path, [WATCH, *([LEFT] * 6), HITS], fight={"miss": 40, "crit": 40},
               player={"hp": 40, "mana": 4}, hound={"hp": 40})
    seen = out["evals"]["hits"]["seen"]
    said = out["final"]["said"]
    kinds = {k for k, _ in seen}
    assert "miss" in kinds and "crit" in kinds, seen
    # Every number drawn is one the fight's own line said, in words.
    for kind, text in seen:
        if kind == "hit":
            assert any(f"for {text}." in line for line in said), (text, said)
        if kind == "crit" and not text.startswith("CRIT -"):
            assert any(f"for {text.split()[-1]}." in line for line in said), (text, said)


def test_a_number_holds_still_and_stays_a_beat_longer_with_motion_off(tmp_path):
    """Either blanket: the OS's own setting, or the player's switch."""
    steps = [LEFT, {"do": "wait", "ms": 1100},
             ev("({now: Array.from(document.querySelectorAll('#hits .hit')).map(e => e.textContent)})", "hits")]
    moving = play(tmp_path / "a", steps, media=False)["evals"]["hits"]["now"]
    by_os = play(tmp_path / "b", steps, media=True)["evals"]["hits"]["now"]
    switch = [ev("store.set(reducedMotionKey(), '1'); applyPlayerSettings();"
                 " document.body.classList.contains('reduced-motion')", "rm")]
    by_switch = play(tmp_path / "c", switch + steps, media=False)["evals"]
    assert moving == []                            # risen and gone
    assert by_os == ["2", "-3"]                    # still there to be read
    assert by_switch["rm"] is True and by_switch["hits"]["now"] == ["2", "-3"]


def test_a_drink_and_a_healing_spell_show_what_they_mended(tmp_path):
    out = play(tmp_path, [WATCH, LEFT, ev("bagAdd('potion'); useItem('potion'); true", "drink"), HITS])
    assert out["evals"]["hits"]["seen"][-1] == ["heal", "+2"]


# ------------------------------------------------------------------ the bar


def test_the_bar_holds_the_quick_things_then_the_spells_known(tmp_path):
    out = play(tmp_path, [ev("bagAdd('potion'); bagAdd('potion'); bagAdd('gem'); true", "bag"),
                          BAR, *KILL, key("Escape"), key("Escape"), {**BAR, "tag": "later"}])["evals"]
    assert out["bar"]["hidden"] is False and out["bar"]["bar"] is True
    assert out["bar"]["names"] == ["drink a cloudy potion, 2 carried (key 5)"]
    assert out["later"]["names"] == ["drink a cloudy potion, 2 carried (key 5)",
                                     "Cast an ember bolt, 2 mana (key 6)",
                                     "Cast a warding word, 1 mana (key 7)"]
    assert out["later"]["keys"] == ["5", "6", "7"]


def test_a_key_on_the_bar_drinks_and_says_so_where_the_player_looks(tmp_path):
    out = play(tmp_path, [LEFT, ev("bagAdd('potion'); true", "bag"), key("5"),
                          ev("({hp: HERO_HP, bag: bagItems(), live: document.getElementById('combat-live').textContent})",
                             "drunk")])["evals"]["drunk"]
    assert out["hp"] == 7                          # 8 - 3 + 2
    assert out["bag"] == []
    assert out["live"] == "You drink a cloudy potion. You recover 2 health."


def test_a_spell_on_the_bar_casts_at_the_foe_beside_the_hero(tmp_path):
    # Two blows leave the hound 3 of its 7; level 2 (two cards, closed)
    # puts the bolt in the bar's first slot, with no potion carried.
    out = play(tmp_path, [LEFT, LEFT, ev("growAward(3); true", "lvl"), key("Escape"), key("Escape"),
                          key("5"),
                          ev("({foes: VEFR_COMBAT.enemies.map(e => [e.hp, e.alive]),"
                             " mana: HERO_MP, live: document.getElementById('combat-live').textContent})",
                             "cast")], hound={"xp": 5, "hp": 7})["evals"]["cast"]
    assert out["foes"] == [[0, False]]
    assert out["mana"] == 2
    assert out["live"].startswith("You cast an ember bolt. It strikes an ember hound for 3.")


def test_with_the_bar_on_the_fight_row_stops_its_digits_at_four(tmp_path):
    verbs = ["attack", "shove", "taunt", "feint", "parry", "dodge"]
    row = ("renderVerbRow(); Array.from(document.querySelectorAll('#verb-row button[data-verb]'))"
           ".map(b => (b.querySelector('kbd') || {}).textContent || '')")
    on = play(tmp_path / "on", [ev(row, "row")], verbs=verbs)["evals"]["row"]
    off = play(tmp_path / "off", [ev(row, "row")], verbs=verbs, display=None)["evals"]["row"]
    assert on == ["1", "2", "3", "4", "", ""]
    assert off == ["1", "2", "3", "4", "5", "6"]


def test_the_bar_keys_are_the_players_to_change(tmp_path):
    out = play(tmp_path, [ev("[keybindRefused('quick1', '9'), keybindRefused('quick1', 'z'),"
                             " keybindRefused('interact', '5'), keybindRefused('quick2', '5'),"
                             " KEYBIND_ACTIONS.filter(keybindListed).map(a => a.id).filter(i => /^quick/.test(i))]",
                             "refused")])["evals"]["refused"]
    assert out[0] is None and out[1] is None
    assert out[2].startswith("The number keys stay on the fight verbs")
    assert out[3] == "5 already answers for Quick use, first button. Choose a different key."
    assert out[4] == ["quick1", "quick2", "quick3", "quick4"]
    off = play(tmp_path / "off", [ev("KEYBIND_ACTIONS.filter(keybindListed).map(a => a.id)"
                                     ".filter(i => /^quick/.test(i))", "rows")], display=None)
    assert off["evals"]["rows"] == []


# -------------------------------------------------------------- the fall note


def test_a_fall_that_leaves_the_bag_on_the_floor_says_so_in_its_note(tmp_path):
    pack = rpg._trip_pack(tmp_path, fall="home")
    world = json.loads((pack / "world.json").read_text())
    world["fight"] = {"turns": True}
    (pack / "world.json").write_text(json.dumps(world))
    note = ev("document.getElementById('fall-note').textContent", "note")
    out = play(tmp_path, [{"do": "eval", "js": rpg.FALL, "tag": "fell"}, note], pack=pack)["evals"]
    assert out["fell"]["satchel"] == ["pebble", "pebble"]
    assert out["note"] == ("Your health is whole again. What you wear, your gold "
                           "and the ground you have walked are as you left them.")


def test_any_other_fall_keeps_the_cards_own_note(tmp_path):
    out = play(tmp_path, [ev("HERO_HP = 1; saveHeroHp(); true", "low"), LEFT,
                          ev("[!document.getElementById('fall').hidden,"
                             " document.getElementById('fall-note').textContent]", "note")])["evals"]["note"]
    assert out[0] is True
    assert out[1] == ("Your health is whole again. Your bag, your gold and the ground "
                      "you have walked are as you left them.")
