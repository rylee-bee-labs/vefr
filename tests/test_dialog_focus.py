"""Tab stays inside an open dialog, and closing it gives the focus back (#462).

With a dialog open - a book, a character's line, a trade, the pause menu, the
floors-changed card - Tab walked out of the box and into the page behind it:
Menu, Messages, Talk, Whisper, Bag, Explore. run-004 called it out ("keyboard
focus during dialogs often drifted to underlying page buttons"), and run-002 and
run-003 found Close and Read on several Tabs away.

The REAL woven player is driven in jsdom (tests/fixtures/dialog_focus_harness.mjs),
which is the only place a Tab can be asked at all: the player traps Tab itself, so
the harness presses Tab and reads back where the focus is. Two fixtures, because
the two halves of the issue live in different places - the events pack for the
dialogs a player meets in play, the descent pack for the one box whose close path
never moved the focus anywhere, which is where "back to the opener" is a fix and
not a restatement of what closeReader already did.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import make_descent_pack  # noqa: E402
import make_events_pack  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "dialog_focus_harness.mjs"


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    home = tmp_path_factory.mktemp("dialog-focus")
    events = home / "events.html"
    events.write_text(cli.weave_html(make_events_pack.build(home)), encoding="utf-8")
    descent = home / "descent.html"
    descent.write_text(cli.weave_html(make_descent_pack.build(home)), encoding="utf-8")
    return events, descent


def test_tab_stays_inside_a_dialog_and_comes_back_to_the_opener(woven):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    run = subprocess.run(["node", str(HARNESS), str(woven[0]), str(woven[1])],
                         capture_output=True, text=True, timeout=240)
    assert run.returncode == 0, run.stderr + run.stdout
    result = json.loads(run.stdout)
    failed = [s["what"] for s in result["steps"] if not s["ok"]]
    assert result["allOk"] and len(result["steps"]) >= 23, failed