"""The identify service in the real woven player (ADR 0017, T3 slice 2).

The engine half is pinned in `test_identify.py`: the flag, the three
refusals, the no-re-roll rule and the backward-compatibility hash. This
file pins the half a player meets - walking up to the pack's reader,
pressing Interact, and reading a thing - and it reads the page rather
than the source wherever the claim is about the page.

Three claims are checked here and nowhere else, because only a real DOM
can carry them:

  * the REVEAL IS INSTANT. The snapshot after the Read click is taken in
    the same tick as the click, with no await between them, and the
    traits are in it. Motion off changes nothing: the whole run is
    repeated with `matchMedia` reporting reduced motion and the two DOMs
    are compared word for word.
  * the REVEAL IS TEXT. The traits are in the bag rows and in the HUD
    strip's `aria-label` - what a screen reader reads - not in a
    picture, a title attribute or a class.
  * READING DOES NOT RE-ROLL. The bag carries two copies of the same
    drawn thing; reading both gives both the traits the drop drew, and
    the second read cannot move the first.

Drives the shipped player in jsdom, the way `test_rolled_loot_play.py`
does.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "identify_harness.mjs"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_identify_pack as mi  # noqa: E402

# The bag a floor drop leaves behind: a plain thing as the bare id it has
# always been, one rolled thing unread (the copy to read) and one already
# read (the copy whose traits must already be in the page).
BAG = [
    "pebble",
    {"id": "brass-ring", "rarity": "rare", "traits": ["keen", "cold"],
     "identified": False},
    {"id": "brass-ring", "rarity": "rare", "traits": ["keen", "cold"],
     "identified": True},
]

# Two tiles right of the fixture's wake point [3, 4], which is one tile
# from the reader at [6, 4] - inside the same reach a shopkeeper has.
WALK = ["right", "right"]


def weave(dest):
    pack = mi.build(dest)
    out = dest / "identify-test.html"
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


def run(html, steps, bag=BAG, motion=True):
    spec = json.dumps({"steps": steps, "bag": bag, "motion": motion})
    result = subprocess.run(["node", str(HARNESS), str(html), spec],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr + result.stdout
    out = json.loads(result.stdout)
    assert out["errors"] == [], out["errors"]
    return out


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    return weave(tmp_path_factory.mktemp("identify"))


def _to_the_reader(woven):
    return [{"do": "reload"}, {"do": "walk", "dirs": WALK},
            {"do": "words", "tag": "before"}]


# --- the place -------------------------------------------------------------

def test_the_interact_verb_offers_the_read(woven):
    """Standing beside the reader, Interact says what it will do."""
    out = run(woven, _to_the_reader(woven) + [{"do": "snap", "tag": "before"}])
    before = out["snaps"]["before"]
    assert before["hero"] == [5, 4]
    assert before["hint"] == "Ask The Reader to read things", before["hint"]
    assert before["label"] == "Ask The Reader to read things", before["label"]


def test_interact_opens_the_readers_panel(woven):
    """The same verb the trade panel uses opens this one."""
    out = run(woven, _to_the_reader(woven) + [{"do": "interact"}])
    final = out["final"]
    assert final["hidden"] is False
    assert final["title"] == "The Reader"
    assert [r["text"] for r in final["rows"]] == [
        "a brass ring (rare)"], final["rows"]
    assert [r["button"] for r in final["rows"]] == ["Read"]


def test_a_read_thing_is_not_offered_twice(woven):
    """Only what has not been read is on the list - and a plain drop,
    which hides nothing, is not on it at all."""
    out = run(woven, _to_the_reader(woven) + [{"do": "interact"}])
    rows = out["final"]["rows"]
    assert "a grey pebble" not in out["final"]["panelText"]
    assert len(rows) == 1 and rows[0]['text'].startswith("a brass ring")


def test_the_panel_says_so_when_there_is_nothing_to_read(woven):
    """An empty list is a sentence, not an empty box."""
    out = run(woven, [{"do": "reload"}, {"do": "walk", "dirs": WALK},
                      {"do": "interact"}], bag=["pebble"])
    assert out["final"]["rows"] == []
    assert "waiting to be read" in out["final"]["panelText"]


def test_the_close_button_closes_the_panel(woven):
    """Open it, then close it: the panel goes back to hidden and the
    Interact verb is still the reader's."""
    out = run(woven, _to_the_reader(woven) + [{"do": "interact"},
                                              {"do": "snap", "tag": "open"},
                                              {"do": "closeIdentify"}])
    assert out["snaps"]["open"]["hidden"] is False
    assert out["final"]["hidden"] is True
    assert out["final"]["hint"] == "Ask The Reader to read things"


# --- the reveal ------------------------------------------------------------

def test_the_traits_are_in_the_page_on_the_first_frame_after_the_click(woven):
    """The accessibility claim, checked rather than asserted.

    The snapshot is taken in the same tick as the click - the harness
    does not await between them - so this reads what a player can see on
    the first frame. With motion off (the run below) and with motion on
    (the comparison after it), the words are the same words.
    """
    steps = _to_the_reader(woven) + [{"do": "interact"}, {"do": "readOne"}]
    out = run(woven, steps, motion=True)
    final = out["final"]
    # In the HUD strip's own words, which is what a screen reader reads.
    assert "a brass ring (rare) - traits: keen, cold" in final["strip"], \
        final["strip"]
    # And in the panel's own live line.
    assert "You read a brass ring (rare) - traits: keen, cold." in \
        final["live"], final["live"]
    # And the saved bag says so too.
    assert [r["identified"] for r in final["bag"] if isinstance(r, dict)] == \
        [True, True]


def test_motion_off_is_the_same_page_as_motion_on(woven):
    """The reveal is instant either way: nothing to turn off, so the two
    runs' DOMs are the same words in the same places."""
    steps = _to_the_reader(woven) + [{"do": "interact"}, {"do": "readOne"},
                                     {"do": "closeIdentify"},
                                     {"do": "openBag"}]
    off = run(woven, steps, motion=True)["final"]
    on = run(woven, steps, motion=False)["final"]
    for key in ("strip", "bagNames", "bagPanel", "live", "bag"):
        assert off[key] == on[key], key
    assert "keen" in off["strip"] and "cold" in off["strip"]


def test_the_bag_names_the_traits_once_the_thing_has_been_read(woven):
    """Both bag surfaces, in text - and the unread copy next to the read
    one shows the difference is the flag, not a picture."""
    steps = _to_the_reader(woven) + [{"do": "interact"}, {"do": "readOne"},
                                     {"do": "closeIdentify"},
                                     {"do": "openBag"}]
    final = run(woven, steps)["final"]
    assert "a brass ring (rare) - traits: keen, cold" in final["bagNames"], \
        final["bagNames"]
    assert "a brass ring (rare)" in final["bagNames"], final["bagNames"]
    assert "keen" in final["bagPanel"] and "cold" in final["bagPanel"]
    # A plain thing is still just its own words.
    assert "a grey pebble" in final["bagNames"]


def test_the_read_survives_a_reload(woven):
    """The record is what loads next run: the flag is in the saved bag,
    so a second boot reads the same traits and never re-draws them."""
    steps = _to_the_reader(woven) + [{"do": "interact"}, {"do": "readOne"},
                                     {"do": "closeIdentify"},
                                     {"do": "snap", "tag": "read"},
                                     {"do": "reload"}, {"do": "openBag"}]
    out = run(woven, steps)
    assert out["snaps"]["read"]["bagNames"] == out["final"]["bagNames"]
    assert out["final"]["bag"] == [
        "pebble",
        {"id": "brass-ring", "rarity": "rare", "traits": ["keen", "cold"],
         "identified": True},
        {"id": "brass-ring", "rarity": "rare", "traits": ["keen", "cold"],
         "identified": True}]


# --- no re-roll ------------------------------------------------------------

def test_reading_two_copies_of_one_draw_gives_the_same_words(woven):
    """The evidence that reading is not drawing, in play.

    The bag holds two copies that were drawn once. Reading the first
    moves nothing; reading the second gives the same rarity and the same
    traits, in the same order, because the only field a read writes is
    the flag.
    """
    steps = _to_the_reader(woven) + [
        {"do": "interact"}, {"do": "readOne"},
        {"do": "snap", "tag": "one"},
        {"do": "closeIdentify"}, {"do": "interact"}, {"do": "readOne"},
        {"do": "snap", "tag": "two"},
        {"do": "closeIdentify"}, {"do": "openBag"},
    ]
    out = run(woven, steps)
    one = out["snaps"]["one"]["bag"]
    two = out["snaps"]["two"]["bag"]
    read_words = ["a brass ring (rare) - traits: keen, cold"]
    assert out["snaps"]["one"]["live"].count("keen, cold") == 1
    assert out["snaps"]["two"]["live"].count("keen, cold") == 1
    # Same rarity, same traits, same order - and the flags only went up.
    assert [r["rarity"] for r in one if isinstance(r, dict)] == ["rare", "rare"]
    assert [r["traits"] for r in two if isinstance(r, dict)] == \
        [["keen", "cold"], ["keen", "cold"]]
    assert [r["identified"] for r in two if isinstance(r, dict)] == [True, True]
    assert out["final"]["bagNames"].count(read_words[0]) == 2
