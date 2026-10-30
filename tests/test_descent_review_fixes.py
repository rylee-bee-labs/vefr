"""The three findings of the vefr#308 second-family review, one test each.

Not a frozen contract: this file is the review pass. Each test here is
one finding, written to fail on the head it reviews:

1. the save was trimmed by the documented order but the trim could stop
   before the byte budget, so `store.setJSON` wrote over `SAVE_BYTES`;
2. returning to town cleared kills and chests but left the floor drops,
   so one Section reset in two halves;
3. Start over cleared the storage, swallowed a refusal and reloaded, so
   the player was told a fresh start over a save that was still there.

The first and the third need a storage of their own, so they run
through `descent_review_harness.mjs` against the REAL woven player: the
byte budget is proved on what the player's own `saveDoc` leaves in
storage, and Start over is proved against a storage that refuses one
remove the way a full or private-mode browser does. The second is a
walk, so it is played through the shared play kit the way the frozen
lifecycle tests are.

A second round of the same review (vefr#314) added two more, at the end
of this file and proved the same way: Start over erased the save when
the browser would not store the new one, and the budgets counted UTF-16
code units rather than the UTF-8 bytes the save is actually written as.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import play_kit
from vefr import delve

from test_descent_deltas import _descend, _doc, _json_store, _off_and_back, _play
from test_descent_floors import DESCENT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "descent_review_harness.mjs"
WORLD = "descent-test"
DOC_KEY = "vefr-descent-" + WORLD

# One of the keys a Release 1 save wrote and a save from this generation
# never does: its presence is what makes the descent offer the card.
OLD_SAVE_KEY = "vefr-bag-" + WORLD


def _record(i, drops=0, fog=""):
    name = "cellar-0-1-%d" % i
    return name, {
        "g": delve.GEN_VERSION,
        "h": delve.section_hash(DESCENT["sections"][0]),
        "k": "%s/cellar/0/%d" % (DESCENT["run_seed"], i + 1),
        "n": i + 1, "s": "cellar", "kills": [], "chests": [], "secrets": [],
        "drops": [{"at": [10, 10], "item": "pebble"} for _ in range(drops)],
        "fog": fog,
    }


def _doc_of(records, flags=None):
    doc = {"v": 1, "gen": delve.GEN_VERSION, "run": 0, "seed": DESCENT["run_seed"],
           "order": [], "floors": {}, "flags": flags or {}, "card": delve.GEN_VERSION}
    for name, record in records:
        doc["floors"][name] = record
        doc["order"].append(name)
    return doc


def _bytes(value):
    """The count `saveDoc` itself made: `JSON.stringify(value).length`.

    `ensure_ascii=False` because `JSON.stringify` does not escape a
    character outside ASCII either - Python's default would count six
    units where JavaScript counts one, and the two counts have to be the
    same number for the same string for this helper to stand for it.
    """
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def _utf8(value):
    """The same document as the browser will hold it: UTF-8 bytes.

    `_bytes` counts the way the code under review counted, so the two
    together are the finding: on an ASCII save they are the same number,
    and on a save carrying anything else they are not.
    """
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _run(tmp_path, cases):
    html = play_kit.weave(play_kit.pack(tmp_path, "descent"), tmp_path)
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    run = subprocess.run(["node", str(HARNESS), str(html), str(path)],
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr + run.stdout
    out = json.loads(run.stdout)
    assert out["hasApi"] is True
    return out


# ---- finding 1: the trim must not stop before the budget -----------------

# Two documents over the byte budget, because they are over it for two
# different reasons and each answers one of the budgets.
#
# FAT: forty floors, each 250 dropped items and a small bitset. Over the
# byte budget, under the 40-floor count cap, so the count cap is not what
# the byte budget can lean on - the whole-save trim has to give floors up
# to make this fit.
FAT = _doc_of([_record(i, drops=250, fog="f" * 700) for i in range(40)])

# MANY: two hundred and fifty floors, each nothing but an explored bitset
# and its identity - inside FLOOR_BYTES, every one of them - and 290 KB
# together, so both budgets are over at once and what lands can be asked
# both questions at once.
MANY = _doc_of([_record(i, fog="f" * 1000) for i in range(250)])


def test_a_save_over_the_byte_budget_is_never_stored_over_it(tmp_path):
    # The contract of PLAN §3, for a save that does not fit, is three
    # things and this test states all three:
    #
    #   * what lands in storage is inside SAVE_BYTES;
    #   * every floor record in what lands is inside FLOOR_BYTES;
    #   * nothing was refused - a save that can be made to fit is stored,
    #     not turned away.
    #
    # How many floors are left is deliberately NOT claimed here. Forty
    # records of the per-floor budget is 60 KB inside a 250 KB save, but a
    # floor's record grows with what the hero did on it, so the trim gives
    # up as many whole floors as it has to and stops - 31 of FAT today,
    # which is a number this file does not assert and must not: pinning it
    # would pin the fixtures rather than the design. The order a save
    # gives things up in, and the count, are pinned by the FROZEN
    # tests/test_descent_deltas.py, which drives `trimDoc` directly and
    # asserts it floor by floor - that is where the eviction order belongs.
    assert _bytes(FAT) > delve.SAVE_BYTES
    assert _bytes(MANY) > delve.SAVE_BYTES
    got = _run(tmp_path, {"mode": "budget", "seedDoc": _doc_of([_record(0)]),
                          "docs": [FAT, MANY]})["results"]
    fat, many = got

    # FAT: the count cap cannot help, so this is the byte budget's own work.
    assert fat["storedBytes"] <= delve.SAVE_BYTES, fat["storedBytes"]
    assert fat["storedBytes"] < fat["given"], "the save was stored whole, over budget"
    assert fat["refusal"] in (None, ""), "it fit, so nothing was refused"

    # MANY: what lands is inside the whole-save budget, and every floor in
    # it is inside the per-floor budget.
    assert many["storedBytes"] <= delve.SAVE_BYTES, many["storedBytes"]
    assert many["storedFloorBytes"], "a save that fits was stored empty"
    worst = max(many["storedFloorBytes"])
    assert worst <= delve.FLOOR_BYTES, \
        f"a stored floor record is {worst} bytes, over the {delve.FLOOR_BYTES} budget"
    assert many["refusal"] in (None, ""), "it fit, so nothing was refused"


def test_a_save_that_nothing_can_shrink_is_refused_and_says_so(tmp_path):
    # The only thing left to give up is the world's own story memory,
    # which is never given up - so this write is refused, and said.
    huge = _doc_of([_record(0)], flags={"a-flag-nobody-reads": "x" * 300000})
    seed = _doc_of([_record(0)], flags={"marker": "the old save"})
    got = _run(tmp_path, {"mode": "budget", "seedDoc": seed,
                          "docs": [huge]})["results"][0]
    assert got["given"] > delve.SAVE_BYTES
    assert got["storedFloors"] == 1, "nothing was written"
    assert got["storedFlags"] == {"marker": "the old save"}, \
        "the save that was already there is still whole, and is not over budget"
    assert got["returnedBytes"] == -1, "saveDoc refused, it did not write"
    refusal = got["refusal"] or ""
    assert len(refusal) > 20 and "save" in refusal.lower(), \
        "a save that cannot be stored says so in plain words"


# ---- finding 2: the reset is one contract --------------------------------

def test_returning_to_town_clears_the_drops_with_the_kills_and_the_chests(tmp_path):
    # A CONTRACT test, not a regression test, and the coordinator says so in the
    # PR body: this also passes against the pre-fix head 2aba3c4. The pre-fix
    # `returnToTown` really did clear kills and chests and leave `drops` alone -
    # but a floor record's drops do not survive a save round trip at all, for a
    # floor the hero entered and for one they did not, so the observable end
    # state is the same either way and nothing here can distinguish them.
    #
    # What the fix buys is that the reset is one contract in one place rather than
    # three arrays that happen to be cleared today. Keep the assertion - it pins
    # the state we want to hold - but do not read it as proof the finding was real.
    # Whether floor drops should survive a save round trip is a separate question,
    # and this slice does not answer it.
    # Two sessions, because that is what they are: the save remembers the
    # floor, not where the hero stood.
    first = _play(tmp_path, _descend(1))
    assert first["errors"] == [], first["errors"]
    doc = _doc(first)
    doc["floors"]["cellar-0-1"]["drops"] = [{"at": [10, 10], "item": "pebble"}]

    home = _play(tmp_path, _descend(1) + _off_and_back(delve.floor_plan(DESCENT, 1)) +
                 ["click:#interact", "wait:200"],
                 store=_json_store(doc))
    assert home["reads"]["VEFR_COMBAT.region"] == "town"
    record = _doc(home)["floors"]["cellar-0-1"]
    assert record["kills"] == [] and record["chests"] == []
    assert record["drops"] == [], \
        "returning to town resets the Section; what was dropped on it goes too"
    assert record["fog"], "the explored bitset is kept"


# ---- finding 3: Start over must not lie about a cleared save -------------

def _release_one_store():
    """A Release 1 save: an old bag, and a descent doc that never carried
    the card, so the player is offered the choice."""
    old = _doc_of([_record(0)])
    old["card"] = 1
    return {DOC_KEY: json.dumps(old), OLD_SAVE_KEY: "[]"}


def test_start_over_says_so_when_the_browser_will_not_clear_the_save(tmp_path):
    # The descent's own save is the key the storage refuses to remove, so
    # this is the finding exactly: the old game survives the reload.
    got = _run(tmp_path, {"mode": "startover", "store": _release_one_store(),
                          "blockKey": DOC_KEY})
    assert got["offered"]["cardHidden"] is False, "the card was offered"
    assert got["returned"] is False, "start over did not go through"
    after = got["after"]
    assert after["cardHidden"] is False, \
        "the card stays up: the player has lost nothing yet"
    assert DOC_KEY in after["left"], "the save the browser refused is still there"
    assert OLD_SAVE_KEY not in after["left"], "the keys it would remove, it did"
    said = after["line"] or ""
    assert "clear" in said.lower() and "save" in said.lower(), \
        f"a clear that failed is named in plain words, not swallowed: {said!r}"


def test_start_over_still_reloads_when_the_storage_lets_it(tmp_path):
    got = _run(tmp_path, {"mode": "startover", "store": _release_one_store(),
                          "blockKey": None})
    assert got["returned"] is True
    assert got["after"]["left"] == [], "every vefr- key was removed"


# ---- round 2: a Start over that cannot write does not erase ---------------

def test_start_over_keeps_the_old_save_when_this_browser_cannot_store_a_new_one(tmp_path):
    # `store.setJSON` gives up quietly when storage is full or blocked, so
    # a browser like this one is not an error the player sees: it is a
    # write that returns and leaves nothing behind. A Start over that
    # clears on top of such a write destroys the only copy of the game
    # and writes nothing in its place - a save gone, silently.
    #
    # So the old save must be here afterwards, whole, and the refusal
    # must be said out loud rather than swallowed.
    got = _run(tmp_path, {"mode": "startover", "store": _release_one_store(),
                          "blockKey": None, "failWrite": True})
    assert got["returned"] is False, \
        "start over went through over a save this browser would not store"
    after = got["after"]
    assert after["cardHidden"] is False, "the card stays up: nothing was done"
    assert DOC_KEY in after["left"], "the old save was cleared anyway"
    assert OLD_SAVE_KEY in after["left"], "the old bag was cleared anyway"
    # And the save itself, not only its key: the floors it remembers.
    assert json.loads(after["doc"]) == json.loads(got["before"]["doc"]), \
        "the old save was rewritten by a Start over that could not store one"
    said = after["line"] or ""
    assert "save" in said.lower() and "clear" in said.lower(), \
        f"a Start over that stored nothing says so in plain words: {said!r}"


# ---- round 2: the budgets are bytes, not UTF-16 code units ----------------

# A floor whose deltas carry a character outside ASCII. U+2620 is one
# UTF-16 code unit and three UTF-8 bytes, so this record is under
# FLOOR_BYTES by the old count and over it by the real one - the whole
# finding in a single fixture.
WIDE_ID = "☠"
WIDE = _record(0)
# 270 at the old 1_500 budget: the count is held to the budget, so the
# fixture keeps sitting between the two counts when the budget moves.
WIDE[1]["kills"] = [WIDE_ID + "x"] * (delve.FLOOR_BYTES * 9 // 50)


def test_a_floor_over_the_byte_budget_is_saved_inside_it(tmp_path):
    given = _doc_of([WIDE])
    # The fixture is only a finding if the two counts disagree about it.
    assert _bytes(WIDE[1]) <= delve.FLOOR_BYTES, \
        "the fixture is over budget by string length too, so it proves nothing"
    assert _utf8(WIDE[1]) > delve.FLOOR_BYTES, \
        "the fixture is inside the budget by bytes too, so it proves nothing"

    got = _run(tmp_path, {"mode": "budget", "seedDoc": _doc_of([_record(0)]),
                          "docs": [given]})
    floors = got["results"][0]["floors"]
    assert floors, "the save was stored empty, so nothing is proved"
    for name, record in floors.items():
        assert _utf8(record) <= delve.FLOOR_BYTES, \
            (f"floor {name} was stored at {_utf8(record)} bytes, over the "
             f"{delve.FLOOR_BYTES} byte budget")
        assert len(record["kills"]) < len(WIDE[1]["kills"]), \
            "the record was stored whole: nothing was given up to the budget"


def test_the_budgets_count_utf8_bytes(tmp_path):
    # The counter itself, read off the running player. A hundred U+2620
    # is 100 UTF-16 code units and 300 UTF-8 bytes; what the save stores
    # is the JSON, so the quotes are counted too - 302 as a bare string,
    # 308 inside a one-field record.
    got = _run(tmp_path, {"mode": "budget", "seedDoc": _doc_of([_record(0)]),
                          "docs": [_doc_of([_record(0)])]})
    assert got["bytes"]["doc"] == 302, \
        f"a hundred U+2620 weighs {got['bytes']['doc']}, not 302 bytes"
    assert got["bytes"]["floor"] == 308, \
        f"a record holding one weighs {got['bytes']['floor']}, not 308 bytes"
