"""The optional `time` block and the standing-phase rule condition (vefr E3).

Time that costs something is opt-in and game-neutral: a pack that
declares no `time` block loads with no `time` key at all, validates
exactly as before and bakes exactly the rules it always baked, while a
pack that declares one gets its three answers - Rest, the rail lock and
the phase save - each checked with a plain sentence.

The second half is the `{"phase": "<id>"}` condition: the validator
resolves the name against the pack's `phases`, and the baker keeps a
rule the engine can actually evaluate (and drops one it could not).
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from vefr import cli, maplab, shapes

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_time_pack  # noqa: E402

GOOD = {"rest": True, "rail": "locked", "persist": True}


def _pack(tmp_path: Path, **world_keys) -> Path:
    """The sample pack with `world_keys` merged into its world.json."""
    pack = tmp_path / "sample-world"
    if pack.exists():
        shutil.rmtree(pack)
    shutil.copytree(SAMPLE, pack)
    cfg = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    cfg.update(world_keys)
    (pack / "world.json").write_text(json.dumps(cfg), encoding="utf-8")
    return pack


def _errors(tmp_path: Path, **world_keys) -> list[str]:
    pack = _pack(tmp_path, **world_keys)
    return maplab.validate(maplab.load_pack(pack), pack_dir=pack)


def _has(errors: list[str], *needles: str) -> bool:
    return any(all(n.lower() in e.lower() for n in needles) for e in errors)


# --- the shape table ---


def test_the_good_block_is_accepted_and_every_field_is_optional():
    assert shapes.check(shapes.BLOCKS["time"], GOOD) == []
    assert shapes.check(shapes.BLOCKS["time"], {}) == []


def test_every_wrong_shape_is_one_plain_sentence_naming_time():
    bad = [
        ({"rest": "yes"}, ("time", "rest", "yes or a no")),
        ({"persist": 1}, ("time", "persist", "yes or a no")),
        ({"rail": "shut"}, ("time", "rail", '"open" or "locked"')),
        ({"nap": True}, ("time", "nap")),
    ]
    for value, needles in bad:
        problems = shapes.check(shapes.BLOCKS["time"], value)
        assert len(problems) == 1, (value, problems)
        assert all(n in problems[0].sentence for n in needles), \
            (value, problems[0].sentence)


# --- the validator ---


def test_a_pack_with_no_time_block_is_unchanged(tmp_path):
    """The whole point of the slice: a pack that never opted in has no
    `time` key, no errors, and no rule that mentions a phase condition."""
    pack = _pack(tmp_path)
    loaded = maplab.load_pack(pack)
    assert "time" not in loaded
    assert maplab.time_errors(loaded) == []
    assert maplab.validate(loaded, pack_dir=pack) == []


def test_a_good_time_block_validates_and_loads(tmp_path):
    pack = _pack(tmp_path, time=GOOD)
    loaded = maplab.load_pack(pack)
    assert loaded["time"] == GOOD
    assert maplab.validate(loaded, pack_dir=pack) == []


def test_a_bad_time_block_is_refused_with_a_plain_sentence(tmp_path):
    for bad, needles in [(dict(GOOD, rest="yes"), ("time", "rest")),
                         (dict(GOOD, rail="shut"), ("time", "rail")),
                         (dict(GOOD, nap=True), ("time", "nap"))]:
        errors = _errors(tmp_path, time=bad)
        assert _has(errors, *needles), (bad, errors)


def test_explain_knows_the_block(tmp_path, capsys):
    """`vefr explain time` resolves the block and speaks for a bad one."""
    from types import SimpleNamespace

    good = _pack(tmp_path, time=GOOD)
    assert cli.cmd_explain(SimpleNamespace(block="time", pack=str(good))) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "ok"
    bad = _pack(tmp_path, time=dict(GOOD, rail="shut"))
    assert cli.cmd_explain(SimpleNamespace(block="time", pack=str(bad))) == 0
    assert capsys.readouterr().out.splitlines()[-1] == \
        'time rail must be the string "open" or "locked"'


# --- the standing-phase condition ---


PHASE_RULE = {
    "id": "boats-may-come-in",
    "when": {"comes-near": {"who": "keeper", "distance": 2}},
    "if": [{"phase": "dusk"}],
    "then": [{"say": "The boats can come in now."}],
}


def _phase_errors(tmp_path: Path, cond) -> list[str]:
    pack = _pack(tmp_path, rules=[{**PHASE_RULE, "if": [cond]}])
    return maplab.rules_errors(maplab.load_pack(pack), pack_dir=pack)


def test_a_condition_on_a_declared_phase_is_accepted(tmp_path):
    assert _phase_errors(tmp_path, {"phase": "dusk"}) == []


def test_a_condition_on_a_phase_the_pack_does_not_declare_is_refused(tmp_path):
    errors = _phase_errors(tmp_path, {"phase": "highwater"})
    assert _has(errors, "boats-may-come-in", "phase", "highwater"), errors


def test_a_condition_on_something_that_is_not_a_phase_name_is_refused(tmp_path):
    errors = _phase_errors(tmp_path, {"phase": ["dusk"]})
    assert _has(errors, "boats-may-come-in", "phase", "phase name"), errors


def test_the_baker_keeps_a_rule_the_engine_can_read_and_drops_one_it_cannot(tmp_path):
    """`vefr weave` bakes only rules the engine can actually run, so the
    phase condition is read at bake time like every other one."""
    good = [dict(PHASE_RULE)]
    bad = [{**PHASE_RULE, "if": [{"phase": ["dusk"]}]}]
    assert cli._conditions_bake([{"phase": "dusk"}]) is True
    assert cli._conditions_bake([{"phase": ""}]) is False
    assert cli._conditions_bake([{"phase": 5}]) is False
    assert cli._conditions_bake([{"phase": ["dusk"]}]) is False
    assert cli._player_rules({"rules": good})["rules"] == good
    assert cli._player_rules({"rules": bad})["rules"] == []


# --- the fixture the browser tests play ---


def test_the_time_fixture_pack_validates_both_ways(tmp_path):
    opted_in = make_time_pack.build(tmp_path / "in")
    plain = make_time_pack.build(tmp_path / "out", name="no-time-test",
                                 time_block=None)
    for pack, has_time in ((opted_in, True), (plain, False)):
        loaded = maplab.load_pack(pack)
        assert maplab.validate(loaded, pack_dir=pack) == [], pack.name
        assert ("time" in loaded) is has_time, pack.name
    # And the woven world carries the block for the pack that declared it,
    # and no such key for the pack that did not.
    def _baked_world(pack: Path) -> str:
        line = next(ln for ln in cli.weave_html(pack).splitlines()
                    if ln.startswith("window.VEFR_WORLD = "))
        return line
    assert '"time"' in _baked_world(opted_in)
    assert '"time"' not in _baked_world(plain)