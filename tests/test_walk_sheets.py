"""Walk sheets, phase B of design/pack-art-proposal.md (Cottage release 1, plan W1). FROZEN CONTRACT.
Played through the shared tests/play_kit.py.

A pack may put a sprite sheet next to a sprite:
  sprites/<key>.png            the single picture (still the fallback)
  sprites/<key>-sheet.png      the frames, numbered left to right, top to bottom
  sprites/<key>.sheet.json     {"image": "<key>-sheet.png", "frame": [w, h], "fps": 8,
                                "directions": {"down": {"idle": [0], "walk": [1,2,3,4]}, "left": ..., "right": ..., "up": ...}}
  - `*.sheet.json` files are never sprites themselves. A missing `left`/`right` is the other side mirrored; a
    missing `up` falls back to `down`; `down` is required.
  - validator: image must exist beside it; frame two ints 8..512; fps int 1..30; every index an int inside the
    sheet's grid (image size / frame size); idle 1..16 indexes; walk 2..16 indexes; optional act, attack, hurt and
    talk lists of 1..16 indexes each. Plain sentences naming the sheet file.
  - weave: window.VEFR_SPRITE_SHEETS = {<key>: {image: data URI, frame, fps, directions}} — `{}` for a pack with no sheets.
  - player: window.VEFR_HERO_FRAME = {dir, state: "idle"|"walk", frame: <sheet index>, mirrored: bool} exists only when the
    hero has a sheet. Facing the hero's last move (down at the start); standing shows `idle`; a step shows a `walk`
    frame of that direction; it returns to `idle` after the step settles. A missing side is drawn mirrored
    (`mirrored: true`). No sheet: Phase A hop as today, no VEFR_HERO_FRAME. `frame` is the cell drawn last, so a
    looping idle or a one-shot moves it.
  - FROZEN CONTRACT change (characters move slice): `idle` was exactly one index and is now 1..16, looping at the
    sheet's fps; a one-frame idle still stands still. The optional act, attack, hurt (one-shots, then idle) and talk
    (looped while the speech box is open) lists are new; a pack that names none plays as before.
Neutral fixtures only.
"""

import json
import shutil
import struct
import zlib

import pytest

from vefr import maplab

import play_kit

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

SHEETS = "VEFR_SPRITE_SHEETS"
FRAME = "VEFR_HERO_FRAME"


def png(w, h, rgb=(180, 60, 60)):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


SHEET = {"image": "hero-sheet.png", "frame": [32, 32], "fps": 8,
         "directions": {"down": {"idle": [0], "walk": [1, 2, 3, 4]},
                        "right": {"idle": [10], "walk": [11, 12, 13, 14]},
                        "up": {"idle": [15], "walk": [16, 17, 18, 19]}}}   # left is the mirror of right


def build(tmp_path, sheet=SHEET, image_size=(160, 128), with_image=True):
    # The kit builds the world; the sprite pictures and the sheet JSON are
    # written onto the pack path it returns, exactly as before.
    pack_dir = play_kit.pack(
        tmp_path, "lock", {"world.json": {"player": {"sprites": {"hero": "sprites/hero.png"}}}})
    sp = pack_dir / "sprites"
    (sp / "hero.png").write_bytes(png(1, 1))
    if sheet is not None:
        (sp / "hero.sheet.json").write_text(json.dumps(sheet), encoding="utf-8")
        if with_image:
            (sp / "hero-sheet.png").write_bytes(png(*image_size))
    return pack_dir


def extra_errors(tmp_path, **kw):
    bpack = build(tmp_path / "b", sheet=None)
    base = maplab.validate(maplab.load_pack(bpack), pack_dir=bpack)
    pack = build(tmp_path / "x", **kw)
    return [e for e in maplab.validate(maplab.load_pack(pack), pack_dir=pack) if e not in base]


# --- validator -------------------------------------------------------------------------------

def test_a_good_sheet_validates(tmp_path):
    assert extra_errors(tmp_path) == []


def test_no_sheet_is_unchanged(tmp_path):
    assert extra_errors(tmp_path, sheet=None) == []


def test_idle_loops_and_the_optional_states_validate(tmp_path):
    loops = {"down": {"idle": [0, 1, 2], "walk": [1, 2, 3, 4], "talk": [5, 6],
                      "attack": [7, 8, 9], "hurt": [9], "act": [0, 1]}}
    assert extra_errors(tmp_path, sheet=mod(directions=loops)) == []


def test_a_character_that_never_walks_needs_no_walk_frames(tmp_path):
    still = {"down": {"idle": [0, 1], "talk": [2, 3]}, "right": {"idle": [4]}, "up": {"idle": [5]}}
    assert extra_errors(tmp_path, sheet=mod(directions=still)) == []


def mod(**over):
    s = json.loads(json.dumps(SHEET))
    for k, v in over.items():
        s[k] = v
    return s


@pytest.mark.parametrize("sheet,needle", [
    (mod(frame=[32]), "hero.sheet.json"),
    (mod(frame=[2, 2]), "hero.sheet.json"),
    (mod(fps=0), "hero.sheet.json"),
    (mod(directions={"left": SHEET["directions"]["right"]}), "down"),                 # down required
    (mod(directions={"down": {"idle": [], "walk": [1, 2]}}), "idle"),
    (mod(directions={"down": {"idle": [0], "walk": [1, 2], "attack": []}}), "attack"),
    (mod(directions={"down": {"idle": [0], "walk": [1, 2], "talk": [1, 99]}}), "99"),
    (mod(directions={"down": {"idle": [0], "walk": [1]}}), "walk"),
    (mod(directions={"down": {"idle": [0], "walk": [1, 2, 99]}}), "99"),              # outside the grid
    (mod(image="missing.png"), "missing.png"),
])
def test_bad_sheets_are_named(tmp_path, sheet, needle):
    errs = extra_errors(tmp_path, sheet=sheet)
    assert any(needle in e for e in errs), errs


# --- loader and weave -----------------------------------------------------------------------

def test_a_sheet_json_is_not_a_sprite_and_the_sheet_is_baked(tmp_path):
    pack_dir = build(tmp_path)
    html = play_kit.weave(pack_dir, tmp_path).read_text(encoding="utf-8")
    assert '"hero.sheet"' not in html and '"hero-sheet"' not in html   # not baked as sprite keys
    assert "window.VEFR_SPRITE_SHEETS" in html
    assert "data:image/png;base64," in html.split("window.VEFR_SPRITE_SHEETS", 1)[1][:2000]


def test_a_pack_with_no_sheets_bakes_an_empty_map(tmp_path):
    html = play_kit.weave(build(tmp_path, sheet=None), tmp_path).read_text(encoding="utf-8")
    assert "window.VEFR_SPRITE_SHEETS = {}" in html


# --- player ------------------------------------------------------------------------------------

def run(html, steps, reads=(FRAME,)):
    # A read is one snapshot at the end, so standing, stepping and settling
    # are three runs over the same woven html.
    return play_kit.play(html, {"steps": steps, "read": list(reads)})


def test_standing_then_a_step_then_standing(tmp_path):
    html = play_kit.weave(build(tmp_path), tmp_path)
    start = run(html, ["begin"], [SHEETS, FRAME])
    during = run(html, ["begin", "dir:right"])
    settled = run(html, ["begin", "dir:right", "wait:1000"])
    assert start["errors"] == []
    assert list(start["reads"][SHEETS] or {}) == ["hero"]
    assert start["reads"][FRAME] == {"dir": "down", "state": "idle", "frame": 0, "mirrored": False}
    d = during["reads"][FRAME]
    assert d["dir"] == "right" and d["state"] == "walk" and d["frame"] in (11, 12, 13, 14) and d["mirrored"] is False
    assert settled["reads"][FRAME] == {"dir": "right", "state": "idle", "frame": 10, "mirrored": False}


def test_a_held_walk_never_flashes_the_standing_frame_between_steps(tmp_path):
    """A held walk steps every 200 ms and a step's tween takes 110 ms; the walk frame
    lingers past the tween, so the standing frame no longer flashes between two steps
    (that flash read as a bounce on every tile, owner, 2026-10-13)."""
    html = play_kit.weave(build(tmp_path), tmp_path)
    between = run(html, ["begin", "dir:down", "wait:180"])
    assert between["errors"] == []
    assert between["reads"][FRAME]["state"] == "walk", between["reads"][FRAME]


def test_a_missing_side_is_the_other_mirrored(tmp_path):
    html = play_kit.weave(build(tmp_path), tmp_path)
    during = run(html, ["begin", "dir:left"])
    settled = run(html, ["begin", "dir:left", "wait:1000"])
    d = during["reads"][FRAME]
    assert d["dir"] == "left" and d["state"] == "walk" and d["frame"] in (11, 12, 13, 14) and d["mirrored"] is True
    assert settled["reads"][FRAME]["frame"] == 10 and settled["reads"][FRAME]["mirrored"] is True


def test_up_uses_its_own_frames(tmp_path):
    html = play_kit.weave(build(tmp_path), tmp_path)
    during = run(html, ["begin", "dir:up"])
    d = during["reads"][FRAME]
    assert d["dir"] == "up" and d["frame"] in (16, 17, 18, 19)


def test_a_pack_without_a_sheet_has_no_frame_snapshot(tmp_path):
    html = play_kit.weave(build(tmp_path, sheet=None), tmp_path)
    start = run(html, ["begin"], [SHEETS, FRAME])
    settled = run(html, ["begin", "dir:right", "wait:1000"])
    assert list(start["reads"][SHEETS] or {}) == []
    assert start["reads"][FRAME] is None and settled["reads"][FRAME] is None
    assert start["errors"] == []
