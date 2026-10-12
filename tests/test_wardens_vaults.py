"""E8c2: `vefr check` rule 2 (ADR 0015) - the vault's note, chest and home are reached from its door - and
the permanent `vault-chest:<vault id>:c<c>` flag that keeps a taken vault chest taken across a town return.
"""
import json
import shutil

import pytest

import play_kit
from vefr import delve, stamp_check
from test_descent_deltas import TOWN, TOWN_HERO, _go, _go_fight, _path
from test_vault_contents import _pack
from test_vault_door import RECORDS, _descent



def _warden_floor(depth=3):
    descent = {**_descent(), "stamps": RECORDS}
    cycle, section, k = delve.locate(depth, descent)
    run_seed = delve._run_seed_of(descent, 0)
    key = delve.floor_key(run_seed, section["id"], cycle, k)
    plan = delve._v3_floor(run_seed, section, cycle, k, key, delve.stamps_of(descent))
    return section["id"], plan


def test_a_note_behind_a_secret_socket_fails_with_one_sentence_naming_the_section():
    rows = ["###########", "#.........#", "###########"]
    plan = {
        "rows": rows,
        "secrets": [[5, 1]],
        "stamps": [{"id": "vault-cellar", "role": "vault", "socket": [2, 1],
                    "anchors": {"chest": [1, 1], "home": [3, 1], "note": [7, 1]}}],
    }
    assert stamp_check.vault_reach_findings(plan, "cellar") == [
        "section cellar: its note at 7,1 can only be reached from the vault door "
        "by opening a secret /stamps/0/anchors/note"]
    plan["secrets"] = []
    assert stamp_check.vault_reach_findings(plan, "cellar") == []


def test_the_vault_fixture_from_the_door_test_passes_check_two():
    section_id, plan = _warden_floor(3)
    assert any(placement.get("role") == "vault" for placement in plan["stamps"])
    assert stamp_check.vault_reach_findings(plan, section_id) == []


# ---- a taken vault chest stays taken across a return to town (ADR 0015) ---------------------------------

def _named_vault_pack(tmp_path):
    """The warden floor of `test_vault_contents._pack`, with the vault named.

    A vault that carries its own `id` is what ADR 0015's permanent chest flag
    `vault-chest:<vault id>:c<c>` is keyed by; the record must still name its
    `sets` flag, which every vault record does.
    """
    descent, pack = _pack(tmp_path)
    vault = {"stamp": "vault-cellar", "sets": "vault-1-read", "id": "cellar-vault"}
    descent["sections"][0]["vault"] = vault
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["descent"]["sections"][0]["vault"] = vault
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    return descent, pack


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_a_taken_vault_chest_stays_taken_after_a_return_to_town(tmp_path):
    descent, pack = _named_vault_pack(tmp_path)
    html = play_kit.weave(pack, tmp_path)
    woven = {**descent, "stamps": RECORDS}
    plan = delve.floor_plan(woven, 3)
    vault = plan["vault"]
    assert vault["id"] == "cellar-vault"
    flag = delve.vault_chest_flag("cellar-vault", 0)
    assert flag == "vault-chest:cellar-vault:c0"
    (warden,) = [m for m in plan["mobs"] if m.get("warden")]

    down = ["begin", _go(TOWN, TOWN_HERO, descent["entry"]["at"]), "click:#interact", "wait:150"]
    for d in (1, 2):
        p = delve.floor_plan(woven, d)
        down += [_go(p, p["anchors"]["up"], p["anchors"]["down"]), "click:#interact", "wait:150"]
    fought = play_kit.play(html, {"steps": down + [_go_fight(plan, warden)] + ["wait:100"] * 6,
                                  "read": ["store"]})
    assert fought["errors"] == [], fought["errors"]

    # From that save: in to the note, beside the chest, open it, then home.
    chest, home = vault["chest"], vault["home"]
    beside = next(t for t in ([chest[0] + 1, chest[1]], [chest[0] - 1, chest[1]],
                              [chest[0], chest[1] + 1], [chest[0], chest[1] - 1])
                  if plan["rows"][t[1]][t[0]] != "#" and abs(t[0] - home[0]) + abs(t[1] - home[1]) > 1
                  and t != vault["note"])
    to_note = _path(plan, plan["anchors"]["up"], vault["note"], [chest])
    to_chest = _path(plan, vault["note"], beside, [chest])
    to_home = _path(plan, beside, home, [chest])
    walked = down + ["walk:" + ",".join(to_note), "wait:300", "walk:" + ",".join(to_chest),
                     "click:#interact", "wait:300"]
    taken = play_kit.play(html, {"steps": walked + ["walk:" + ",".join(to_home), "click:#interact",
                                                   "wait:300"],
                                 "store": fought["store"],
                                 "read": ["store", "VEFR_COMBAT.region"]})
    assert taken["errors"] == [], taken["errors"]
    assert taken["reads"]["VEFR_COMBAT.region"] == "town", "the stair home did not lead home"
    doc = json.loads(taken["store"]["vefr-descent-descent-test"])
    assert doc["flags"][flag] is True, doc["flags"]
    assert "a-chest" in json.loads(taken["store"]["vefr-library-descent-test"])
    assert json.loads(taken["store"]["vefr-bag-descent-test"]).count("cellar-gem") == 1

    # Back down, with the library's found-list gone: the flag alone must keep
    # the chest taken, so opening it again gives nothing.
    store = dict(taken["store"])
    store["vefr-library-descent-test"] = json.dumps(
        [b for b in json.loads(store["vefr-library-descent-test"]) if b != "a-chest"])
    again = play_kit.play(html, {"steps": walked, "store": store, "read": ["store"]})
    assert again["errors"] == [], again["errors"]
    assert json.loads(again["store"]["vefr-bag-descent-test"]).count("cellar-gem") == 1, \
        "the vault chest gave its loot a second time"
    assert "a-chest" not in json.loads(again["store"]["vefr-library-descent-test"] or "[]"), \
        "the empty chest was reported as newly found"
