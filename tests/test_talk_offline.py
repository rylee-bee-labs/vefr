"""Talk with no brain: the speaker's own seeded line, or no Talk at all.

The woven player's talk path, executed in a real DOM (jsdom) by
tests/fixtures/talk_offline_harness.mjs against the interact fixture
pack. Static: no endpoint, so the cat (seeds only) says its seeded
lines in order and wraps, and the stranger (no line at all) is not
offered Talk - the Interact words say 'Look at'. Brain: an endpoint is
configured and every request fails, so the stranger keeps 'Talk to'
and its Talk says "They didn't answer.", while the cat falls back to
its seeded line.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "talk_offline_harness.mjs"
MAKE = ROOT / "tests" / "fixtures" / "make_interact_pack.py"

CAT_LINES = ["The cat looks at you, then away.",
             "The cat stretches in the first light."]
SILENT = "They didn't answer."


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("talk-offline-home")
    made = subprocess.run(
        [sys.executable, str(MAKE), str(home)],
        capture_output=True, text=True, timeout=120)
    assert made.returncode == 0, made.stderr
    pack = Path(made.stdout.strip())
    static = home / "static.html"
    assert cli.cmd_build_web(_args(pack, static)) == 0

    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["player"]["model"] = "optional"
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    brain = home / "brain.html"
    assert cli.cmd_build_web(_args(pack, brain)) == 0

    return {"static": _run(static, "static"), "brain": _run(brain, "brain")}


def _args(pack: Path, out: Path):
    return argparse.Namespace(
        pack=str(pack), out=str(out), pool=0,
        with_bundle=False, from_live=None)


def _run(html: Path, mode: str) -> dict:
    run = subprocess.run(
        ["node", str(HARNESS), str(html), mode],
        capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    return {k: v for k, v in json.loads(run.stdout)["log"]}


def test_the_harness_played_every_scenario_without_throwing(runs):
    for mode in ("static", "brain"):
        assert "HARNESS-ERROR" not in runs[mode], mode


def test_static_the_cat_says_its_seeded_lines_in_order_and_wraps(runs):
    log = runs["static"]
    assert log["cat-spot"] == [8, 2]
    assert log["cat-label"] == "Talk to the cat"
    for n, line in ((1, CAT_LINES[0]), (2, CAT_LINES[1]), (3, CAT_LINES[0])):
        assert log[f"cat-talk-{n}-box-hidden"] is False, n
        assert log[f"cat-talk-{n}-name"] == "the cat", n
        assert log[f"cat-talk-{n}-line"] == line, n
        assert log[f"cat-talk-{n}-near"] == "", n


def test_static_the_stranger_is_looked_at_not_talked_to(runs):
    log = runs["static"]
    assert log["stranger-spot"] == [8, 4]
    assert log["stranger-label"] == "Look at the stranger"
    assert log["stranger-hint"] == "Look at the stranger"


def test_static_the_stranger_shows_its_name_on_press_and_on_talk(runs):
    log = runs["static"]
    assert log["stranger-key-box-hidden"] is False
    assert log["stranger-key-name"] == "the stranger"
    assert log["stranger-key-line"] == ""
    assert log["stranger-key-near"] == ""
    assert log["stranger-talkbtn-box-hidden"] is False
    assert log["stranger-talkbtn-name"] == "the stranger"
    assert log["stranger-talkbtn-near"] == ""


def test_static_the_silent_words_never_appear(runs):
    assert SILENT not in json.dumps(runs["static"])


def test_brain_the_stranger_keeps_talk_and_a_failed_brain_is_silent(runs):
    log = runs["brain"]
    assert log["brain-stranger-label"] == "Talk to the stranger"
    assert log["brain-stranger-talkbtn-box-hidden"] is True
    assert log["brain-stranger-talkbtn-near"] == SILENT


def test_brain_the_cat_falls_back_to_its_seeded_line(runs):
    log = runs["brain"]
    assert log["brain-cat-label"] == "Talk to the cat"
    assert log["brain-cat-box-hidden"] is False
    assert log["brain-cat-name"] == "the cat"
    assert log["brain-cat-line"] == CAT_LINES[0]
    assert log["brain-cat-near"] == ""
