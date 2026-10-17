"""Stakes, the bake side (vefr#504): one opt-in pack field, checked here.

A stake is a risk/reward a pack puts to the player:

    "stakes": [{"id", "when": <a rule's when>, "risk", "reward", "say"}]

The player is asked only when the pack wrote the offer, only where its
`when` says, and only while they really hold the `risk`. A pack that
writes no `stakes` bakes the literal `null` and is asked nothing - so
this file also proves the default: the sample pack weaves exactly the
offer-free file.

What this file holds: the shape of the bake (`_player_stakes`), that a
malformed offer is dropped whole, that the woven line is the literal
`null` for a pack without the key, and that the sample world's own bake
is unchanged. The browser proof that a player really is asked - and can
walk away with nothing lost - is tests/browser/test_stakes.py.
"""

import json
import re
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_stakes_pack  # noqa: E402

SAMPLE = ROOT / "worlds" / "sample-world"


def _baked(pack: Path) -> str:
    """The one `window.VEFR_STAKES = ...;` line out of a woven pack."""
    html = cli.weave_html(pack)
    line = re.search(r"window\.VEFR_STAKES = .*", html)
    assert line, "the woven player carries no window.VEFR_STAKES line"
    return line.group(0)


def _baked_stakes(pack: Path):
    """The baked value, JSON as written into the file (None -> None)."""
    value = _baked(pack).split("=", 1)[1].strip().rstrip(";")
    return json.loads(value)


def test_the_fixture_stakes_bake_as_the_pack_wrote_them(tmp_path):
    pack = make_stakes_pack.build(tmp_path)
    baked = _baked_stakes(pack)
    assert baked == make_stakes_pack.STAKES, (
        "a well-formed stake must bake exactly as written: "
        f"wrote {make_stakes_pack.STAKES}, baked {baked}")


def test_a_pack_that_declares_no_stakes_bakes_null(tmp_path):
    """The default. The sample pack declares no stakes, so the woven line
    is the literal `null` and the player has nothing to be asked."""
    assert _baked_stakes(SAMPLE) is None
    assert _baked(SAMPLE) == "window.VEFR_STAKES = null;"


def test_a_pack_that_declares_no_stakes_key_at_all_bakes_null(tmp_path):
    pack = make_stakes_pack.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    del world["stakes"]
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert _baked_stakes(pack) is None


def test_an_empty_stakes_list_bakes_an_empty_list(tmp_path):
    """Opt-in is the key itself: a pack that writes `[]` has opted in and
    asked for nothing, which is the same play with the key spelled out."""
    pack = make_stakes_pack.build(tmp_path, stakes=[])
    assert _baked_stakes(pack) == []


@pytest.mark.parametrize("stake", make_stakes_pack.BROKEN, ids=lambda s: str(s)[:28])
def test_an_offer_the_player_could_not_act_on_is_dropped_whole(tmp_path, stake):
    pack = make_stakes_pack.build(tmp_path, stakes=[stake])
    assert _baked_stakes(pack) == [], (
        f"{stake!r} could not be offered, so it must not be baked half-broken")


def test_a_good_offer_stands_beside_a_broken_one(tmp_path):
    pack = make_stakes_pack.build(
        tmp_path, stakes=list(make_stakes_pack.BROKEN) + make_stakes_pack.STAKES)
    assert _baked_stakes(pack) == make_stakes_pack.STAKES


def test_the_bake_keeps_the_risky_shape_out_of_a_pack_that_declares_nothing(tmp_path):
    """`stakes` is a list or nothing: a dict where a list belongs is not a
    block of offers, so nothing bakes rather than something half-read."""
    pack = make_stakes_pack.build(tmp_path)
    world_json = pack / "world.json"
    world = json.loads(world_json.read_text(encoding="utf-8"))
    world["stakes"] = {"id": "the-tolls-price"}
    world_json.write_text(json.dumps(world), encoding="utf-8")
    assert _baked_stakes(pack) is None


def test_the_stake_when_is_the_rule_when(tmp_path):
    """One shape, one check: a stake's `when` is held to the same bake a
    rule's `when` is, so the same offer in a rule fires where it says."""
    good = make_stakes_pack.STAKES[0]["when"]
    rule = {"id": "the-toll-is-near", "when": json.loads(json.dumps(good)),
            "then": [{"say": "The toll-keeper waits."}]}
    assert cli._when_bakes(good)
    assert cli._rule_bakes(rule)
    for broken in ({"comes-near": {"who": "the toll"}},
                   {"not-an-event": {}},
                   {"comes-near": {"who": "", "distance": 1}},
                   {"comes-near": {"who": "the toll", "distance": 42}}):
        assert not cli._when_bakes(broken)
        assert not cli._rule_bakes({"id": "x", "when": broken, "then": [{"say": "."}]})
        assert not cli._stake_bakes(
            {"id": "x", "when": broken, "risk": "torch",
             "reward": "chalked-map", "say": "."})