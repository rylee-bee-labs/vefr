"""The fire/burning encounter, played in the real woven file (vefr#497).

The engine half is pinned in `test_elements.py`: the resolver, the four
refusals, the bake and the byte-for-byte opt-out. This file plays the
other half - the prototype encounter a pack gets when it opts in:

  * a hazard that deals fire, and the sentence that says so;
  * the hero's own resistance turning the blow aside, and immunity
    stopping it dead;
  * burning: the HUD line, the tick after the monsters' turn, and the
    turn it ends;
  * and the pack that declares none of it, which plays the old fight
    with the old sentence and no line on the HUD at all.

Every read is what a player and a screen reader get: the health, the
live region's sentence, and the words on the state line. Nothing is a
colour, so nothing here is a colour.

Needs node and jsdom; skips without them.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "element_play_harness.mjs"
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_element_pack as mk  # noqa: E402


def play(tmp_path, steps, **build):
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    opts = {"burns": mk.BURNING}
    opts.update(build)
    out = tmp_path / "element-test.html"
    out.write_text(cli.weave_html(mk.build(tmp_path, **opts)), encoding="utf-8")
    spec = json.dumps({"steps": steps})
    run = subprocess.run(["node", str(HARNESS), str(out), spec],
                         capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stderr + run.stdout
    out_json = json.loads(run.stdout)
    assert out_json["errors"] == [], out_json["errors"]
    return out_json


def test_fire_is_dealt_and_burning_is_caught_in_words(tmp_path):
    """The whole encounter in three turns, from the hero's own side.

    The blow lands for what the hazard deals, the live region says what
    it was, and the state line beside the health carries the burn - the
    same words for the eye and for a screen reader.

    The fire ticks where the hero's own damage always resolved: after
    the monsters' turn, so the turn that lights it is the turn it takes
    from the hero, and the live region carries the whole of that turn in
    the order it happened - the blow, the lighting, the tick (vefr#497,
    review #528).
    """
    out = play(tmp_path, [
        {"do": "press", "dir": "left"},          # bump: the hero strikes, the hazard answers
        {"do": "snap", "tag": "lit"},
        {"do": "press", "dir": "right"},         # a plain step: the burn's last turn
        {"do": "snap", "tag": "one"},
        {"do": "press", "dir": "right"},         # and again: the fire is long out
        {"do": "snap", "tag": "out"},
    ])
    lit, one, out_ = out["snaps"]["lit"], out["snaps"]["one"], out["snaps"]["out"]

    assert "hits you with fire for 3" in lit["live"], lit["live"]
    assert "sets you alight" in lit["live"], lit["live"]
    assert "The fire takes 2 from you." in lit["live"], lit["live"]
    assert lit["live"].index("hits you with fire") < lit["live"].index("sets you alight") \
        < lit["live"].index("The fire takes"), lit["live"]
    assert lit["hp"] == 3, lit["hp"]            # 8, less the hazard's 3 and the fire's 2
    assert lit["foe"] == 3, lit["foe"]          # and the hero's own blow still landed
    assert lit["state"] == "Burning (fire, 1 turn left)", lit["state"]
    assert lit["stateOn"] is True

    assert "The fire takes 2 from you." in one["live"], one["live"]
    assert "The burning dies out of you." in one["live"], one["live"]
    assert one["hp"] == 1, one["hp"]
    assert one["state"] == "" and one["stateOn"] is False
    assert one["statuses"] == []

    assert out_["hp"] == 1, out_["hp"]          # and the fire takes nothing more
    assert out_["state"] == "" and out_["stateOn"] is False
    assert out_["statuses"] == []


def test_a_resistance_turns_the_blow_and_the_burn_aside(tmp_path):
    """`resist: {"fire": 2}` is a divisor: 3 becomes 1, and the burn's
    own tick of 2 becomes 1 - the resistance is read on both paths."""
    out = play(tmp_path, [
        {"do": "press", "dir": "left"},
        {"do": "snap", "tag": "lit"},
        {"do": "press", "dir": "right"},
    ], resist={"fire": 2})
    lit, one = out["snaps"]["lit"], out["final"]
    assert "hits you with fire for 1" in lit["live"], lit["live"]
    assert "your resistance turns the rest aside" in lit["live"], lit["live"]
    # The tick runs in the same turn as the blow it came from, after the
    # monsters' turn: 8, less the blow's 1 and the tick's 1.
    assert lit["hp"] == 6, lit["hp"]
    assert one["hp"] == 5, one["hp"]


def test_a_resistance_that_divides_the_blow_away_says_it_did_not_land(tmp_path):
    """The same resolver, one step further: `resist: {"fire": 9}` leaves
    nothing of a blow of 3 or of a tick of 2, so the sentence is the one
    true thing - it did not land - and there is no burn to start."""
    out = play(tmp_path, [{"do": "press", "dir": "left"}], resist={"fire": 9})
    assert "your resistance turns it aside" in out["final"]["live"], out["final"]["live"]
    assert out["final"]["hp"] == 8, out["final"]["hp"]
    assert out["final"]["statuses"] == []


def test_an_immunity_stops_the_blow_and_never_lights_the_hero(tmp_path):
    """Immunity beats a resistance, and a burn whose every tick is turned
    aside never starts: the hero is untouched and told so."""
    out = play(tmp_path, [
        {"do": "press", "dir": "left"},
        {"do": "press", "dir": "right"},
    ], immune=["fire"], resist={"fire": 2})
    assert "hits you with fire, and it cannot touch you" in out["final"]["live"], out["final"]["live"]
    assert out["final"]["hp"] == 8, out["final"]["hp"]
    assert out["final"]["state"] == "" and out["final"]["stateOn"] is False
    assert out["final"]["statuses"] == []


def test_a_pack_that_declares_none_of_it_plays_the_old_fight(tmp_path):
    """The opt-out, in play rather than in bytes.

    The hazard still stands there and still hits for its 3 - but the blow
    is untyped, the sentence is the one this always spoke, and the HUD
    keeps the line it always had.
    """
    out = play(tmp_path, [
        {"do": "press", "dir": "left"},
        {"do": "press", "dir": "right"},
    ], dmg_type=None, burns=None)
    assert "an ember hound hits you for 3." in out["final"]["live"], out["final"]["live"]
    assert out["final"]["hp"] == 5, out["final"]["hp"]
    assert out["final"]["state"] == "" and out["final"]["stateOn"] is False
    assert out["final"]["statuses"] == []


def test_a_burn_is_not_stored_so_a_reload_is_the_hero_again(tmp_path):
    """Reversible, and the reason no save changes shape.

    The burn is in memory: after the fight the player's own storage holds
    the health it always held and not one key about a status, so there is
    nothing to read wrong on the next page and no save to migrate.
    """
    out = play(tmp_path, [{"do": "press", "dir": "left"}])
    lit = out["final"]
    # Still in memory, and one turn of it already gone: the burn ticks
    # after the monsters' turn, in the very turn that lit it.
    assert lit["statuses"] == [{"effect": "burning", "type": "fire",
                                "turns": 1, "tick": 2}], lit["statuses"]
    about_a_status = [k for k in lit["saved"]
                      if "status" in k or "burn" in k or "state" in k]
    assert about_a_status == [], about_a_status
    assert "vefr-hp-element-test" in lit["saved"], lit["saved"]