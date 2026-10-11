"""Scenarios in Chromium (ADR 0016, slice P2): `vefr look --scenario` opens the woven game there.

The unit half (tests/test_scenarios.py) pins the shape, the pack checks and the save
keys. This half weaves the neutral descent fixture, plants a scenario's keys before
the page loads, walks the hero in through the player's own arrival paths, and reads
the harness's window onto play back: the hero is in the scenario's region or at its
depth, holding its gold, and the game did not take the planted state for a Release 1
save.

Each case runs the real command in its own process. The dev tools start their own
Playwright, and this suite's session-wide `browser` fixture keeps another one running
in this process, which the sync API refuses to share. It skips without Chromium, like
the rest of tests/browser, and fails instead when VEFR_BROWSER_REQUIRED=1 (CI).
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fixtures"))
import make_descent_pack  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _pack(tmp_path):
    pack = make_descent_pack.build(tmp_path)
    folder = pack / "scenarios"
    folder.mkdir()
    (folder / "town-rich.json").write_text(json.dumps(
        {"start": {"region": "town", "at": [5, 4]}, "gold": 120, "bag": ["pebble"]}), encoding="utf-8")
    (folder / "floor-two.json").write_text(json.dumps(
        {"start": {"depth": 2}, "gold": 9}), encoding="utf-8")
    return pack


def _python(code: str, *args) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True,
                       cwd=ROOT, timeout=240)
    if r.returncode == 2 and "Chromium not available" in r.stderr:
        if os.environ.get("VEFR_BROWSER_REQUIRED") == "1":
            pytest.fail(r.stderr)
        pytest.skip("Chromium isn't installed; run: uv run playwright install chromium")
    return r


def _look(pack, name, tmp_path):
    r = _python("import sys; from vefr.cli import vefr_main; sys.argv = ['vefr', *sys.argv[1:]]; sys.exit(vefr_main())",
                "look", "--pack", str(pack), "--scenario", name, "--json",
                "--out", str(tmp_path / f"{name}.png"))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_a_region_scenario_opens_in_its_region_on_its_tile_with_its_gold(tmp_path):
    report = _look(_pack(tmp_path), "town-rich", tmp_path)
    seen = report["scenario"]
    assert (seen["region"], seen["at"], seen["gold"], seen["card"]) == ("town", [5, 4], 120, False)
    assert Path(report["screenshot"]).is_file()


def test_a_depth_scenario_opens_on_that_generated_floor(tmp_path):
    report = _look(_pack(tmp_path), "floor-two", tmp_path)
    seen = report["scenario"]
    assert (seen["depth"], seen["gold"], seen["card"]) == (2, 9, False)
    assert seen["region"] and seen["region"] != "town"


# Why a scenario writes a current descent document: the same gold planted alone reads
# as a Release 1 save, and the game opens its one-time generation card.
_BARE = """
import json, sys
from pathlib import Path
from vefr import devtools, maplab, scenarios
pack = Path(sys.argv[1])
w = maplab.load_pack(pack)
keys = scenarios.storage(w, {"start": {"depth": 2}, "gold": 9})
keys.pop(scenarios.DESCENT_KEY + scenarios.world_name(w))
boot = {"name": "bare", "storage": keys, "start": {"depth": 2},
        "world": scenarios.world_name(w), "gold": 9}
with devtools._player_file(None, pack) as player, \
        devtools._session(player, 800, plant=keys) as page:
    if page is None:
        sys.exit(2)
    report, problem = devtools._arrive(page, boot)
print(json.dumps({"card": report["card"], "problem": problem}))
"""


def test_without_the_descent_document_the_planted_save_opens_the_old_save_card(tmp_path):
    r = _python(_BARE, str(_pack(tmp_path)))
    assert r.returncode == 0, r.stderr
    seen = json.loads(r.stdout.strip().splitlines()[-1])
    assert seen["card"] is True
    assert "generation card" in seen["problem"]
