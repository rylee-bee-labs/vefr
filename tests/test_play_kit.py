"""The shared test kit (docs/research/size-and-language-pass.md, pass 2 items 1 and 2). FROZEN CONTRACT.

tests/fixtures/play.mjs: one jsdom runner driven by a data spec, replacing a 35-line copy in every harness.
  node play.mjs <woven.html> '<spec json>'  ->  prints {"reads": {...}, "errors": [...], "store": {...}}
  spec = {"store": {key: value}, "steps": [...], "read": [...]}
  steps:  "begin"            click the title Begin and wait for window.VEFR_COMBAT, then settle 400 ms
          "wait:MS"          wait
          "key:e"            a keydown on the document (key name as KeyboardEvent.key)
          "dir:right"        click the on-screen pad button for that direction
          "walk:down,down"   several dir presses, 10 ms apart
          "click:#sel"       click the first element matching the selector
          "menu:PANEL"       click #menu-open, then the menu button [data-panel="PANEL"]
  reads:  "NAME" or "NAME.a.b"   a window global (JSON-cloned), optionally a dotted path into it (arrays by index)
          "text:#sel"        the element's text, or null
          "exists:#sel"      true/false
          "visible:#sel"     exists and neither it nor an ancestor is hidden
          "attr:#sel|NAME"   the element's attribute value, or null (selector and attribute split on the first '|')
          "store"            the whole localStorage as an object (also always returned as "store")
  An unknown step or read makes the process exit 2 with one plain sentence on stderr.
  That one line is written whole HOWEVER LONG it is - stdout is drained before the process exits, so a read's size
  never decides whether the harness returns it (a Section's baked base64 tile table is 64 KB of JSON on its own).
tests/play_kit.py (Python side):
  weave(pack_dir, tmp_path) -> Path of the woven html;  play(html, spec) -> the parsed output (raises RuntimeError with the
  stderr on a non-zero exit);  pack(tmp_path, base, patch=None) -> a fixture pack built from a named base
  ("interact", "lock", "events", "combat", ...) with a JSON merge patch applied: patch = {"world.json": {...}} deep-merges
  into that file; a value of null deletes the key; the base builder's own output is never mutated.
"""

import json
import shutil

import pytest

import play_kit
from play_kit import pack, play, weave

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def woven(tmp_path, patch=None):
    p = pack(tmp_path, "interact", patch)
    return weave(p, tmp_path)


def test_begin_and_read_a_global_with_a_dotted_path(tmp_path):
    out = play(woven(tmp_path), {"steps": ["begin"], "read": ["VEFR_COMBAT.region", "VEFR_COMBAT.hero.at"]})
    assert out["errors"] == []
    assert out["reads"]["VEFR_COMBAT.region"] == "town"
    assert out["reads"]["VEFR_COMBAT.hero.at"] == [1, 1]


def test_walk_and_dir_move_the_hero(tmp_path):
    out = play(woven(tmp_path), {"steps": ["begin", "walk:down,down", "dir:down"], "read": ["VEFR_COMBAT.hero.at"]})
    assert out["reads"]["VEFR_COMBAT.hero.at"] == [1, 4]


def test_menu_click_and_visibility_reads(tmp_path):
    out = play(woven(tmp_path), {"steps": ["begin", "menu:journal"],
                                 "read": ["visible:#menu", "exists:#no-such-element", "text:#menu-title"]})
    assert out["reads"]["visible:#menu"] is True
    assert out["reads"]["exists:#no-such-element"] is False


def test_the_attr_read_reads_an_attribute(tmp_path):
    """`attr:#sel|NAME` is how a test sees state that lives in an attribute
    (the combat row's own label), which no text read can reach."""
    read = "attr:#verb-row|aria-label"
    out = play(woven(tmp_path), {"steps": ["begin"], "read": [read]})
    assert out["errors"] == []
    assert out["reads"][read] == "Combat actions"
    assert out["reads"]["text:#menu-title"]


def test_store_is_injected_and_returned(tmp_path):
    out = play(woven(tmp_path), {"store": {"vefr-test-key": "kept"}, "steps": ["begin"], "read": ["store"]})
    assert out["store"]["vefr-test-key"] == "kept"
    assert out["reads"]["store"]["vefr-test-key"] == "kept"


def test_a_bad_step_is_one_plain_sentence(tmp_path):
    with pytest.raises(RuntimeError) as e:
        play(woven(tmp_path), {"steps": ["begin", "juggle:3"], "read": []})
    assert "juggle" in str(e.value)


def test_pack_deep_merges_and_does_not_mutate_the_base(tmp_path):
    p = pack(tmp_path / "a", "interact", {"world.json": {"sound": {"theme": "soft"}, "player": {"hp": 99}}})
    cfg = json.loads((p / "world.json").read_text(encoding="utf-8"))
    assert cfg["sound"] == {"theme": "soft"} and cfg["player"]["hp"] == 99
    assert "sprites" in cfg["player"], "a nested merge keeps the keys it does not mention"
    base = pack(tmp_path / "b", "interact")
    assert "sound" not in json.loads((base / "world.json").read_text(encoding="utf-8"))


def test_a_null_in_the_patch_deletes_a_key(tmp_path):
    p = pack(tmp_path, "interact", {"world.json": {"player": {"gold": None}}})
    assert "gold" not in json.loads((p / "world.json").read_text(encoding="utf-8"))["player"]


def test_an_unknown_base_is_named(tmp_path):
    with pytest.raises(KeyError) as e:
        pack(tmp_path, "no-such-base")
    assert "no-such-base" in str(e.value)


def test_the_kit_lists_its_bases():
    assert {"interact", "lock"} <= set(play_kit.BASES)
