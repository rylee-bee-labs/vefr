"""Issue #502, first step: the optional ambient music block.

The recorded owner decision (option A) is that VEFR may offer a
reusable, opt-in ambient music capability in the always-layer, that each
pack owns its own musical identity, and that the defaults stay quiet
with usable mute and volume controls. This slice is the smallest
demonstration of that: one pack-declared block, one synthesized bed,
off until the player asks for it.

Sound is untouched - a pack with no `music` weaves and sounds exactly as
it did, which is what the half of this file about a pack that did not
opt in checks.

The browser half (the switch, the bed, no autoplay) is in
tests/browser/test_music.py; that one needs Chromium, not node.
"""

import sys
from pathlib import Path

import pytest

from vefr import maplab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import play_kit  # noqa: E402

TRACK = {"track": "shore"}


def extra_errors(tmp_path, music):
    bpack = play_kit.pack(tmp_path, "lock")
    base = maplab.validate(maplab.load_pack(bpack), pack_dir=bpack)
    pack = play_kit.pack(tmp_path, "lock",
                         {"world.json": {"music": music}} if music is not None else None)
    return [e for e in maplab.validate(maplab.load_pack(pack), pack_dir=pack)
            if e not in base]


def test_the_demonstration_track_validates(tmp_path):
    assert extra_errors(tmp_path, TRACK) == []


def test_a_pack_without_music_is_unchanged(tmp_path):
    assert extra_errors(tmp_path, None) == []


@pytest.mark.parametrize("bad", [{"track": "loud"}, {"track": "shore", "volume": 3},
                                 {"theme": "soft"}, {}, "shore", 3, ["shore"]])
def test_a_bad_music_block_is_named(tmp_path, bad):
    errs = extra_errors(tmp_path, bad)
    assert any("music" in e for e in errs), errs


def test_the_block_is_carried_into_the_loaded_pack(tmp_path):
    pack = play_kit.pack(tmp_path, "lock", {"world.json": {"music": TRACK}})
    assert maplab.load_pack(pack)["music"] == TRACK
    bare = play_kit.pack(tmp_path, "lock")
    assert "music" not in maplab.load_pack(bare)


def test_a_pack_with_no_music_bakes_the_literal_null(tmp_path):
    """The block is additive: the woven file says `null` and the player
    grows no music row, so an existing pack's file carries one extra
    data line and nothing else."""
    html = play_kit.weave(play_kit.pack(tmp_path, "lock"), tmp_path).read_text(encoding="utf-8")
    line = [ln for ln in html.splitlines() if "window.VEFR_MUSIC_DEF =" in ln]
    assert len(line) == 1, line
    assert line[0].strip() == "window.VEFR_MUSIC_DEF = null;", line


def test_a_pack_that_opts_in_bakes_its_own_track(tmp_path):
    pack = play_kit.pack(tmp_path, "lock", {"world.json": {"music": TRACK}})
    html = play_kit.weave(pack, tmp_path).read_text(encoding="utf-8")
    assert '"track": "shore"' in html