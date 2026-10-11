"""The woven player's one-button interact logic, executed for real.

`design/one-button-interact.md` folds the three old use paths into one
verb. Task 1 is the pure half: a self-contained block in
web/packaged.html between its own marker comments exposes
interactTargets, pickTarget and labelFor over a plain state object -
no DOM, no storage, no clock, no randomness, no reads of the file's
other variables.

This closes the gap the way tests/test_web_pack_tiles.py does: it
extracts the REAL block from web/packaged.html between its marker
comments and runs it in a node vm sandbox that needs no npm packages,
then checks every value the harness pins. The marker and purity rules
are asserted from the shipped source text.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PACKAGED = ROOT / "web" / "packaged.html"
HARNESS = Path(__file__).resolve().parent / "fixtures" / "interact_harness.mjs"
START = "// -- interact start --"
END = "// -- interact end --"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not installed - this repo's engine tests never require it",
)


def _block() -> str:
    """The shipped block, sliced between its own marker comments."""
    src = PACKAGED.read_text(encoding="utf-8")
    start = src.find(START)
    end = src.find(END)
    assert start != -1, f"missing {START!r} in web/packaged.html"
    assert end != -1, f"missing {END!r} in web/packaged.html"
    assert start < end, "interact markers are out of order"
    return src[start:end]


def test_markers_appear_exactly_once():
    """The two marker comments exist, once each, so the harness's
    slice is unambiguous."""
    src = PACKAGED.read_text(encoding="utf-8")
    assert src.count(START) == 1, f"{START!r} appears {src.count(START)} times"
    assert src.count(END) == 1, f"{END!r} appears {src.count(END)} times"


def test_block_is_pure():
    """The purity rule, enforced: the block touches no DOM, no
    storage, no window, no randomness and no clock."""
    block = _block()
    for token in ("document", "localStorage", "window.", "Math.random", "Date"):
        assert token not in block, f"the interact block must not contain {token!r}"
    # It also reads none of the file's other variables: it only
    # defines its own three globals.
    for fn in ("interactTargets", "pickTarget", "labelFor"):
        assert f"globalThis.{fn} = function" in block, (
            f"the block must define window.{fn}")


@pytest.fixture(scope="module")
def report() -> dict:
    """The pinned report the shipped block's harness prints."""
    result = subprocess.run(
        ["node", str(HARNESS), str(PACKAGED)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"interact harness failed:\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def test_harness_reports_ok(report):
    """Every pinned expectation inside the harness matched, and no
    call mutated the state it was handed."""
    assert report["ok"] is True


def test_facing_tile_wins(report):
    """A chest on the facing tile beats a nearer chest on the hero's
    own tile and beats a resident beside the hero."""
    assert report["facingFirstTargets"] == [
        {"kind": "chest", "id": "bk-face", "name": "the oak chest",
         "at": [5, 4], "dist": 1, "label": "Open the chest"},
        {"kind": "chest", "id": "bk-here", "name": "the brass chest",
         "at": [5, 5], "dist": 0, "label": "Open the chest"},
        {"kind": "resident", "id": "sp-ada", "name": "Ada",
         "at": [4, 5], "dist": 1, "label": "Talk to Ada"},
    ]
    assert report["facingFirstPick"] == {
        "kind": "chest", "id": "bk-face", "name": "the oak chest",
        "at": [5, 4], "dist": 1, "label": "Open the chest"}


def test_own_tile_wins_over_nearest(report):
    """Nothing on the facing tile: the chest under the hero beats the
    resident one tile away."""
    assert report["ownTileTargets"] == [
        {"kind": "resident", "id": "sp-ada", "name": "Ada",
         "at": [6, 5], "dist": 1, "label": "Talk to Ada"},
        {"kind": "chest", "id": "bk-here", "name": "the brass chest",
         "at": [5, 5], "dist": 0, "label": "Open the chest"},
    ]
    assert report["ownTilePick"] == {
        "kind": "chest", "id": "bk-here", "name": "the brass chest",
        "at": [5, 5], "dist": 0, "label": "Open the chest"}


def test_nearest_fallback(report):
    """Both special tiles empty: the enemy one tile away beats the
    trader two tiles away, list order be damned."""
    assert report["nearestTargets"] == [
        {"kind": "trader", "id": "tr-bram", "name": "Bram",
         "at": [5, 7], "dist": 2, "label": "Trade with Bram"},
        {"kind": "enemy", "id": "e-rat", "name": "the cellar rat",
         "at": [5, 6], "dist": 1, "label": "Fight the cellar rat"},
    ]
    assert report["nearestPick"] == {
        "kind": "enemy", "id": "e-rat", "name": "the cellar rat",
        "at": [5, 6], "dist": 1, "label": "Fight the cellar rat"}


# Every adjacent pair of the tie list, run in both caller orders.
# door and stairs share a rank (the candidate list decides); every
# other pair is decided by the kind rank either way.
TIE_PAIRS = {
    # door / stairs: equal rank, first in the candidate list wins
    "tieDoorFirst": {"kind": "door", "id": "t-cellar", "name": "the cellar door",
                     "at": [4, 5], "dist": 1, "label": "Go through the door"},
    "tieStairsFirst": {"kind": "stairs", "id": "t-down", "name": "the way down",
                       "at": [4, 5], "dist": 1, "label": "Go down the stairs"},
    # stairs vs chest
    "tieStairsThenChest": {"kind": "stairs", "id": "t-down", "name": "the way down",
                           "at": [4, 5], "dist": 1, "label": "Go down the stairs"},
    "tieChestThenStairs": {"kind": "stairs", "id": "t-down", "name": "the way down",
                           "at": [6, 5], "dist": 1, "label": "Go down the stairs"},
    # chest vs trader
    "tieChestThenTrader": {"kind": "chest", "id": "bk-oak", "name": "the oak chest",
                           "at": [4, 5], "dist": 1, "label": "Open the chest"},
    "tieTraderThenChest": {"kind": "chest", "id": "bk-oak", "name": "the oak chest",
                           "at": [6, 5], "dist": 1, "label": "Open the chest"},
    # trader vs resident
    "tieTraderThenResident": {"kind": "trader", "id": "tr-bram", "name": "Bram",
                              "at": [4, 5], "dist": 1, "label": "Trade with Bram"},
    "tieResidentThenTrader": {"kind": "trader", "id": "tr-bram", "name": "Bram",
                              "at": [6, 5], "dist": 1, "label": "Trade with Bram"},
    # resident vs place
    "tieResidentThenPlace": {"kind": "resident", "id": "sp-ada", "name": "Ada",
                             "at": [4, 5], "dist": 1, "label": "Talk to Ada"},
    "tiePlaceThenResident": {"kind": "resident", "id": "sp-ada", "name": "Ada",
                             "at": [6, 5], "dist": 1, "label": "Talk to Ada"},
    # place vs enemy
    "tiePlaceThenEnemy": {"kind": "place", "id": "poi-well", "name": "the old well",
                          "at": [4, 5], "dist": 1, "label": "Look at the old well"},
    "tieEnemyThenPlace": {"kind": "place", "id": "poi-well", "name": "the old well",
                          "at": [6, 5], "dist": 1, "label": "Look at the old well"},
    # the two town services, and a reader against a talk (ADR 0017, T3 slice 2)
    "tieTraderThenIdentifier": {"kind": "trader", "id": "tr-bram", "name": "Bram",
                                "at": [4, 5], "dist": 1, "label": "Trade with Bram"},
    "tieIdentifierThenTrader": {"kind": "trader", "id": "tr-bram", "name": "Bram",
                                "at": [6, 5], "dist": 1, "label": "Trade with Bram"},
    "tieIdentifierThenResident": {"kind": "identifier", "id": "id-wren", "name": "Wren",
                                  "at": [4, 5], "dist": 1,
                                  "label": "Ask Wren to read things"},
    "tieResidentThenIdentifier": {"kind": "identifier", "id": "id-wren", "name": "Wren",
                                  "at": [6, 5], "dist": 1,
                                  "label": "Ask Wren to read things"},
}


def test_tie_order_by_kind(report):
    for name, expected in TIE_PAIRS.items():
        assert report[name] == expected, name


def test_reach_rules(report):
    """Things you touch reach 1; people reach 2."""
    assert report["reachChestTargets"] == []
    assert report["reachChestPick"] is None
    assert report["reachResident2Targets"] == [
        {"kind": "resident", "id": "sp-two", "name": "Toki",
         "at": [7, 5], "dist": 2, "label": "Talk to Toki"}]
    assert report["reachResident2Pick"] == {
        "kind": "resident", "id": "sp-two", "name": "Toki",
        "at": [7, 5], "dist": 2, "label": "Talk to Toki"}
    assert report["reachResident3Targets"] == []
    assert report["reachResident3Pick"] is None
    # A reader is a person: the same two tiles a resident reaches.
    assert report["reachIdentifier2Targets"] == [
        {"kind": "identifier", "id": "id-two", "name": "Wren",
         "at": [7, 5], "dist": 2, "label": "Ask Wren to read things"}]
    assert report["reachIdentifier2Pick"] == {
        "kind": "identifier", "id": "id-two", "name": "Wren",
        "at": [7, 5], "dist": 2, "label": "Ask Wren to read things"}
    assert report["reachIdentifier3Targets"] == []
    assert report["reachIdentifier3Pick"] is None


def test_nothing_in_reach_is_null_everywhere(report):
    assert report["nothingTargets"] == []
    assert report["nothingPick"] is None
    assert report["nothingLabel"] is None


def test_all_eight_labels(report):
    assert report["labelChest"] == "Open the chest"
    assert report["labelResident"] == "Talk to Ada"
    assert report["labelTrader"] == "Trade with Bram"
    assert report["labelIdentifier"] == "Ask Wren to read things"
    assert report["labelDoor"] == "Go through the door"
    assert report["labelStairs"] == "Go down the stairs"
    assert report["labelStairsUp"] == "Go up the stairs"      # a stair named "... up" climbs
    assert report["labelStairsDown"] == "Go down the stairs"
    assert report["labelPlace"] == "Look at the old well"
    assert report["labelEnemy"] == "Fight the cellar rat"
    assert report["labelNull"] is None
    assert report["labelAbsent"] is None


def test_malformed_candidates_are_skipped(report):
    """Missing kind, unknown kind, missing/short/non-array/non-numeric
    at, a null and a number in the list: skipped, never thrown - and
    the one good candidate still comes through."""
    good = {"kind": "chest", "id": "bk-good", "name": "the good chest",
            "at": [5, 5], "dist": 0, "label": "Open the chest"}
    assert report["malformedTargets"] == [good]
    assert report["malformedPick"] == good


def test_no_mutation_and_fresh_objects(report):
    """Every call was JSON-snapshot before and after (the harness
    throws on any mutation), returned targets survive being clobbered
    by the caller, and two pickTarget calls never share an object."""
    assert report["targetsStayFresh"] == [
        {"kind": "chest", "id": "bk-pure", "name": "the chest",
         "at": [5, 4], "dist": 1, "label": "Open the chest"},
        {"kind": "resident", "id": "sp-ada", "name": "Ada",
         "at": [4, 5], "dist": 1, "label": "Talk to Ada"},
    ]
    assert report["stateUntouched"] == {
        "hero": [5, 5], "facing": "up",
        "candidates": [
            {"kind": "chest", "id": "bk-pure", "name": "the chest",
             "at": [5, 4]},
            {"kind": "resident", "id": "sp-ada", "name": "Ada",
             "at": [4, 5]},
        ]}
    assert report["picksStayFresh"] == report["targetsStayFresh"][0]
