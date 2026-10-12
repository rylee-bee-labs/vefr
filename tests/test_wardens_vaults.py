"""E8c2: `vefr check` rule 2 (ADR 0015) - the vault's note, chest and home are reached from its door."""
from vefr import delve, stamp_check
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
