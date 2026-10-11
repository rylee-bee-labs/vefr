"""Skin loader, K1 (design/ui-skin.md rules 1, 5, 6): a pack may name a skin folder.

`"skin": "skins/<name>"` in world.json points at a folder inside the pack with a `skin.json`.
`maplab.validate` refuses a bad skin with a plain sentence; the bake carries a good one into the
woven file as data URIs (`window.VEFR_SKIN`); a pack with no skin bakes `window.VEFR_SKIN = null;`.

Interface slice 4 also lives here: the nine parts the validator already accepts and the baker
already inlines, and the one thing that is still missing - a part the validator accepts is a
part the player draws.
"""

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli, maplab

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import make_skin_pack as mk  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def errors(pack):
    return maplab.validate(maplab.load_pack(pack), pack_dir=pack)


def has(errs, *needles):
    return any(all(n.lower() in e.lower() for n in needles) for e in errs)


def test_a_good_skin_validates_and_loads(tmp_path):
    pack = mk.build(tmp_path)
    assert errors(pack) == []
    assert maplab.load_pack(pack)["skin"] == "skins/test-skin"


def test_a_pack_without_a_skin_is_unchanged():
    assert "skin" not in maplab.load_pack(ROOT / "worlds" / "sample-world")


@pytest.mark.parametrize("mutate,needles", [
    (lambda s: s.pop("name"), ("skin", "name")),
    (lambda s: s.update(credit=""), ("skin", "credit")),
    (lambda s: s["parts"].update(sparkle={"file": "panel.png"}), ("sparkle",)),
    (lambda s: s["parts"]["panel"].update(file="nope.png"), ("nope.png",)),
    (lambda s: s["parts"]["panel"].update(file="panel.gif"), (".gif",)),
    (lambda s: s["parts"]["panel"].update(slice=0), ("slice",)),
    (lambda s: s["parts"]["panel"].update(slice="wide"), ("slice",)),
    (lambda s: s["parts"]["panel"].update(slice=40), ("slice",)),     # a 64 px panel: at most 32
    (lambda s: s["ink"].update(on_panel="brown"), ("ink",)),
    (lambda s: s["parts"]["button"].update(hover="gone.png"), ("gone.png",)),
])
def test_a_bad_skin_is_named(tmp_path, mutate, needles):
    skin = copy.deepcopy(mk.SKIN)
    mutate(skin)
    files = dict(mk.FILES)
    if skin["parts"]["panel"].get("file") == "panel.gif":
        files["panel.gif"] = (64, 64)
    assert has(errors(mk.build(tmp_path, skin=skin, files=files)), *needles), needles


# ---- the backdrop (docs/plans/interface/PLAN.md, slice 2) ----
# An optional top-level `"backdrop": "<picture>"`: the seamless picture the
# ground outside the drawn map takes. A skin without one plays as before.


def test_a_good_backdrop_validates_and_bakes_as_a_data_uri(tmp_path):
    skin = copy.deepcopy(mk.SKIN)
    skin["backdrop"] = "table.png"
    files = dict(mk.FILES, **{"table.png": (128, 128)})
    pack = mk.build(tmp_path, skin=skin, files=files)
    assert errors(pack) == []
    baked = json.loads(_baked(cli.weave_html(pack)))
    assert baked["backdrop"].startswith("data:image/png;base64,")


def test_a_skin_without_a_backdrop_is_untouched(tmp_path):
    pack = mk.build(tmp_path)
    assert errors(pack) == []
    assert "backdrop" not in json.loads(_baked(cli.weave_html(pack)))


@pytest.mark.parametrize("backdrop,needles", [
    ("table.gif", ("backdrop", ".gif")),
    ("table.png", ("backdrop",)),          # named, but not in the skin folder
    ("", ("backdrop",)),
    (7, ("backdrop",)),
])
def test_a_bad_backdrop_is_named(tmp_path, backdrop, needles):
    """Every picture named is checked here, so the table the ground takes is
    checked too: it has to be a real png or webp, in the skin folder."""
    skin = copy.deepcopy(mk.SKIN)
    skin["backdrop"] = backdrop
    files = dict(mk.FILES)          # no table.png: the only pictures are the parts'
    assert has(errors(mk.build(tmp_path, skin=skin, files=files)), *needles), backdrop


def test_a_backdrop_of_the_right_suffix_but_the_wrong_size_is_named(tmp_path):
    skin = copy.deepcopy(mk.SKIN)
    skin["backdrop"] = "table.png"
    files = dict(mk.FILES, **{"table.png": (128, 128)})
    pack = mk.build(tmp_path, skin=skin, files=files)
    (pack / "skins" / "test-skin" / "table.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"0" * 400_000)
    assert has(errors(pack), "table.png", "big")


def test_a_backdrop_may_not_leave_the_skin_folder(tmp_path):
    skin = copy.deepcopy(mk.SKIN)
    skin["backdrop"] = "../outside.png"
    assert has(errors(mk.build(tmp_path, skin=skin)), "backdrop")


# The digest rule 6 of docs/plans/interface/PLAN.md is about, pinned so a
# skin change can never move a pack that names no skin. It moves when the
# engine's own player code or the bundled fonts move - the player template is
# woven into every pack, skinned or not - and never because of a skin. To
# refresh it, and to say in the commit message why it moved:
#   uv run python -c "import hashlib, vefr.cli as c; from pathlib import Path; \
#     print(hashlib.sha256(c.weave_html(Path('worlds/sample-world')).encode()).hexdigest())"
# Last moved 2026-10-10, for ADR 0017 slice 2. The identify service and its
# reveal now reach the woven player: a new part (195-the-identify-service.js)
# and the bag strip, bag panel and Interact verb beside it all sit in the
# player template, which is woven into every pack skinned or not, so every
# pack's weave moved by 13989 bytes of engine code.
#
# It last moved for vefr #364's fog `shape` key: the player part that draws
# the lit area grew one branch, and the part that writes a floor's fog
# block grew one line. Nothing a pack carries moved with it - the sample
# world's own weave of its own data is the same bytes, and the sample world
# names no shape at all.
#
# This digest is over the WHOLE weave and does not compose: it is measured,
# never derived, and it must be re-measured after every union of two stacks
# that each changed the player. The value a stack computes on its own is
# worth nothing here, and neither side's can be carried across a merge.
# This union carries both moves at once, so the value below was re-measured
# over the merged weave and is neither side's old value. The lit-area reader
# also named its local `inLight` (vefr #364), a rename in the same part, so
# the pin moved once more with the union's re-measure.
#
# What was checked before this value was written, and is the reason it is a
# pack-neutrality proof rather than a golden: the pack's OWN baked content
# did not move. All 41 `window.VEFR_*` data lines this pack weaves are
# byte-identical before and after - only the player around them grew - and
# `worlds/sample-world` declares no skin, so `window.VEFR_SKIN` lands the
# literal null exactly as it did.
# Last moved 2026-10-10, rebasing the S349 Section-tiles stack onto E8c.
# Two player changes reach the woven pack from opposite sides of that rebase:
# E8c adds the town gate, the state a region shows and the descent's
# story-end handling, and S349 adds the per-Section tiles and the descent
# lines that name them. Both land in the player template, which is woven into
# every pack skinned or not, so neither side's digest could be carried over
# and the two could not be composed: the digest is over the whole weave, not
# a sum. Both sides were self-consistent before the rebase (E8c's tree
# computed `7ef6d441...` and the S349 tip computed `86311d4c...`), so this
# value is the digest of the merged tree and nothing else. Recomputed by the
# documented command above. Nothing about this pack's own bytes moved -
# `worlds/sample-world` declares no skin, so every new bake lands the literal
# null here exactly as `window.VEFR_SKIN` does.
# Moved again 2026-10-11, rebasing the C4 player-words stack onto main. That
# stack adds the woven player's message table (`VEFR_PLAYER_WORDS`, part 340)
# and reads the where-next lines from it, so the player template - woven into
# every pack, skinned or not - changed. The stack left the constant at its own
# base's value, so it is the merged tree's digest and nothing else. Recomputed
# with the documented command above; the pack's own bytes did not move.
# Last moved 2026-10-10, on the spells tree (ADR 0018). Spells changed the
# player: a new `225-spells.js` part teaches the Bag panel the spells a
# level has earned and the ones a book has taught, and `180-gold.js` reads a
# spellbook's `spell` through the `use` verb it already had. The player
# template is woven into every pack, so the digest had to be recomputed
# rather than carried over. Nothing about this pack's own bytes moved -
# `worlds/sample-world` declares no skin and no spells, so the bake adds
# no spells data for it (the line meant to bake the literal null was later
# dropped entirely; see the last note below), and spells did not touch the
# pack at all. The
# proof that only the shared template moved: woven with `main`'s
# `web/packaged.html` in place of this one, this branch's `cli.py` produces
# `7ef6d4411e8a6f2661346fe6701d4a741173f33aaa94ec4085925c2649258dfe` for
# this pack - byte for byte what `main` produced.
# Re-cut 2026-10-11, the union of the spells stack with `main`'s identify
# service: both sides changed the player template, so the pinned value is
# this merged tree's weave and neither side's could be carried across.
# The spells refactor (one gate for what the hero knows) moved the player
# once more, and measured `d993042f...` for the source stack on its own.
# The source stack's own union repair moved the player again: `spellsKnown`
# in `225-spells.js` published the book-learned spells ahead of the ones a
# level had earned; it now walks the pack's own order and publishes each
# known spell in the order the hero learns it, which is what
# `test_spells_play.py::test_a_book_found_as_loot_teaches_its_spell_and_is_spent`
# pins.
# Re-cut again 2026-10-11, onto `main` one landing further on: the spells
# stack now meets vefr #395 (FOGSHAPE), whose lit-area reader grew a branch
# and whose floor-fog writer grew a line. That is a third move in the same
# player template as the identify service and the spells, so the union of
# all three is measured here and is again no side's value (the earlier
# union measured `d4e5136d...`, `main` alone `7b672cc2...`, and the source
# stack's last step `abeaef56...`). The sample world names no shape and no
# skin, so its own baked bytes still do not move.
# Last moved 2026-10-11: the spells slice's `window.VEFR_SPELLS` line was
# dropped for a pack that declares no `spells` block, because a new
# `VEFR_*` line for a pack that does not use the feature is exactly what
# ADR 0017 slice 2's additive rule forbids (test_identify.py's
# `test_the_reader_needs_no_new_baked_block`). The sample world names no
# spells, so its baked data went back to pristine `main`'s bytes - the
# whole-weave pin still moves because the player template keeps the
# `225-spells.js` part (and 050's now-accurate spells comment), so the
# merged weave was re-measured here.
# Re-cut 2026-10-11, onto current `main`: U353 moves the woven player (the fight verbs now stand in the HUD frame; the look slice's `--sizes`/`--at`/`--seed` reach the descent).
# Measured twice with the documented command above (as
# `PYTHONPATH=src python3 -c ...`, no uv in the sandbox):
#   7b672cc24f806fdf7f0bfd2d05b0f6318ad8d9626e6cd1e00838df6ab5d118c7
#   2260620a961dd59f91af65b88b356cfcb2412936eefb1e28e6d57fb6297caff7
#   cd70c89312c0da7a60691b0aa6b3e0ded7aa03006bb4687bef61a07389146dfa
# Re-cut 2026-10-11, the union of the D357 monster-count stack onto current
# `main`: vefr#357's player's own descent part (397) and its generator part
# (396) read the new `mobs` key, so every pack's woven player carries the new
# lines - which is the one thing this digest is allowed to move for - on top
# of every earlier move. The value below is this merged tree's weave and
# neither side's could be carried across. Re-measured twice with the
# documented command above (as `PYTHONPATH=src python3 -c ...`, no uv in the
# sandbox) and the two readings matched:
#   73fe8996400b939e781cf8eb8df13ca848d645c2858f3d187b585c6dd6dd006c
#   73fe8996400b939e781cf8eb8df13ca848d645c2858f3d187b585c6dd6dd006c
NO_SKIN_WEAVE_SHA256 = "73fe8996400b939e781cf8eb8df13ca848d645c2858f3d187b585c6dd6dd006c"


def test_a_pack_with_no_skin_bakes_null_and_its_weave_is_stable():
    """Rule 6: a pack with no skin carries no skin, backdrop or font data, and
    weaves the same bytes every time (the digest is deterministic)."""
    pack = ROOT / "worlds" / "sample-world"
    first, second = cli.weave_html(pack), cli.weave_html(pack)
    assert first == second, "the weave of a pack with no skin is not deterministic"
    assert hashlib.sha256(first.encode()).hexdigest() == NO_SKIN_WEAVE_SHA256, (
        "the weave of a pack with no skin changed; nothing in this slice may "
        "change it, and the comment above the constant says how to refresh it")
    assert _baked(first) == "null"
    # Nothing the skin contract reads is baked for a pack that names no skin.
    skin_line = re.search(r"window\.VEFR_SKIN = .*", first).group(0)
    assert len(skin_line) < 40 and "data:" not in skin_line


def test_a_missing_skin_json_or_folder(tmp_path):
    pack = mk.build(tmp_path)
    (pack / "skins" / "test-skin" / "skin.json").unlink()
    assert has(errors(pack), "skin.json")
    world = json.loads((pack / "world.json").read_text())
    world["skin"] = "skins/not-here"
    (pack / "world.json").write_text(json.dumps(world))
    assert has(errors(pack), "skin")


def test_a_skin_may_not_leave_the_pack(tmp_path):
    pack = mk.build(tmp_path)
    world = json.loads((pack / "world.json").read_text())
    for bad in ("../outside", "/etc", "skins/../../x"):
        world["skin"] = bad
        (pack / "world.json").write_text(json.dumps(world))
        assert has(errors(pack), "skin"), bad


def test_a_huge_picture_is_refused(tmp_path):
    pack = mk.build(tmp_path)
    (pack / "skins" / "test-skin" / "panel.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 400_000)
    assert has(errors(pack), "panel.png", "big")


def _baked(html):
    m = re.search(r"window\.VEFR_SKIN = (.*);\n", html)
    assert m, "no VEFR_SKIN line"
    return m.group(1)


def test_the_bake_carries_a_skin_as_data_uris(tmp_path):
    html = cli.weave_html(mk.build(tmp_path))
    skin = json.loads(_baked(html))
    assert skin["name"] == "test-skin" and skin["credit"].startswith("Rylee and Claude")
    assert skin["parts"]["panel"]["file"].startswith("data:image/png;base64,")
    assert skin["parts"]["panel"]["slice"] == 16
    assert skin["parts"]["button"]["hover"].startswith("data:image/png;base64,")
    assert skin["ink"]["on_panel"] == "#2B2118"
    assert "http://" not in _baked(html) and "https://" not in _baked(html)   # one file, offline


def test_a_pack_with_no_skin_bakes_null():
    html = cli.weave_html(ROOT / "worlds" / "sample-world")
    assert _baked(html) == "null"


# ---- the type a skin chooses (docs/plans/interface/PLAN.md, slice 3) ----
# An optional `"fonts": {"display": ..., "body": ...}`, each a family the
# engine bundles. The engine ships the woff2, so a name a player cannot
# render is a plain sentence, not a silent fallback.


def test_a_good_font_choice_validates_and_bakes(tmp_path):
    skin = copy.deepcopy(mk.SKIN)
    skin["fonts"] = {"display": "Cinzel", "body": "Crimson Pro"}
    pack = mk.build(tmp_path, skin=skin)
    assert errors(pack) == []
    woven = cli.weave_html(pack)
    assert json.loads(_baked(woven))["fonts"] == skin["fonts"]
    # The named family is inlined, so the chosen type is there offline.
    assert "font-family: 'Crimson Pro'" in woven
    # And a pack with no skin pays nothing for a font it cannot name: the
    # two the player itself uses ride along, the third does not.
    plain = cli.weave_html(ROOT / "worlds" / "sample-world")
    assert "font-family: 'Crimson Pro'" not in plain
    assert "font-family: 'Cinzel'" in plain
    assert "font-family: 'Atkinson Hyperlegible Next'" in plain


@pytest.mark.parametrize("fonts,needles", [
    ({"display": "Papyrus"}, ("fonts", "display", "Papyrus")),
    ({"body": "papyrus"}, ("fonts", "body", "papyrus")),
    ({"title": "Cinzel"}, ("fonts", "title")),
    ({"body": ""}, ("fonts", "body")),
    ({"body": 4}, ("fonts", "body")),
    ("Cinzel", ("fonts",)),
])
def test_a_bad_font_choice_is_named(tmp_path, fonts, needles):
    skin = copy.deepcopy(mk.SKIN)
    skin["fonts"] = fonts
    assert has(errors(mk.build(tmp_path, skin=skin)), *needles), fonts


def test_the_bundled_families_are_the_ones_the_player_can_draw():
    """One list, kept in step: the validator's families, the player's font
    stacks and the woff2 files the engine ships. A family in one and not the
    others would validate and then draw in a fallback."""
    from vefr import cli as _cli

    parts = ROOT / "web" / "player" / "parts" / "540-the-skin.js"
    stacks = re.search(r"var SKIN_FONT_STACKS = \{(.*?)\};", parts.read_text(encoding="utf-8"), re.S)
    assert stacks, "no SKIN_FONT_STACKS in the player"
    in_player = set(re.findall(r"^\s*'([^']+)':", stacks.group(1), re.M))
    assert in_player == set(maplab.SKIN_FONTS)
    shipped = {family for family, _name, _weight in _cli._PLAYER_FONTS}
    assert set(maplab.SKIN_FONTS) <= shipped
    for family, name, _weight in _cli._PLAYER_FONTS:
        assert (ROOT / "web" / "fonts" / name).is_file(), name


def test_the_skin_ink_still_clears_the_contrast_floor_with_a_new_type(tmp_path):
    """A typeface changes the shape of a letter, not its colour: the ink the
    skin declares still has to clear 4.5:1 on the panel it is read on
    (design/ui-skin.md rule 2), whichever families the skin chooses."""
    def _channel(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    def luminance(colour):
        h = colour.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)

    def ratio(a, b):
        hi, lo = sorted([(luminance(a) + 0.05) / 0.05, (luminance(b) + 0.05) / 0.05], reverse=True)
        return hi / lo

    panel = "#F4EEDD"          # the ground a light panel paints behind its text
    for fonts in ({}, {"display": "Cinzel", "body": "Crimson Pro"}):
        skin = copy.deepcopy(mk.SKIN)
        skin["fonts"] = fonts
        pack = mk.build(tmp_path, skin=skin)
        assert errors(pack) == [], fonts
        ink = skin["ink"]["on_panel"]
        assert ratio(ink, panel) >= 4.5, (fonts, ratio(ink, panel))

# ---- interface slice 4: the nine parts the player used to ship and ignore ----
# design/ui-skin.md draws these in Cottage's skin, maplab.SKIN_PARTS already
# accepts them and the baker already inlines their picture keys, so the fixture
# skin carries one of each. Nothing in the engine needs to change to accept a
# part; the part still has to be painted, which is the test at the end of this
# file.

SLICE_4_PARTS = ("slot", "tab", "toggle", "tooltip", "speech",
                 "divider", "banner", "corner", "gold-plate")


def test_every_part_of_interface_slice_4_is_a_part_the_validator_accepts():
    for part in SLICE_4_PARTS:
        assert part in maplab.SKIN_PARTS, part
    # and nothing new crept in: the table is exactly the thirteen parts the
    # design note names (four drawn, nine not). The backdrop is the fourteenth
    # picture the contract carries, but it is a top-level key of its own rather
    # than a part - the ground outside the map, not a thing on it.
    assert set(maplab.SKIN_PARTS) == {
        "panel", "button", "tab", "toggle", "bar", "slot", "speech", "tooltip",
        "gold-plate", "divider", "banner", "corner", "cursor"}
    assert "backdrop" not in maplab.SKIN_PARTS


def test_a_skin_carrying_every_part_validates(tmp_path):
    pack = mk.build_parts(tmp_path)
    assert errors(pack) == []


def test_the_baker_inlines_every_picture_of_every_part(tmp_path):
    """Each part's picture keys (file, hover, selected, on, off) become data
    URIs; `slice` is carried through as written."""
    baked = json.loads(_baked(cli.weave_html(mk.build_parts(tmp_path))))
    for part, spec in mk.PARTS_SKIN.items():
        assert part in baked["parts"], part
        for key, value in spec.items():
            if key == "slice":
                assert baked["parts"][part][key] == value
                continue
            assert baked["parts"][part][key].startswith("data:image/png;base64,"), (
                f"{part}.{key} is not baked")
    assert "http://" not in _baked(cli.weave_html(mk.build_parts(tmp_path / "again")))


def test_a_missing_state_picture_is_refused_by_name(tmp_path):
    """The states are pictures too: a `tab` that names a `selected` picture
    which is not there is refused the same way a part's `file` is."""
    skin = copy.deepcopy(mk.ALL_SKIN)
    skin["parts"]["tab"]["selected"] = "not-here.png"
    assert has(errors(mk.build(tmp_path, skin=skin, files=mk.ALL_FILES,
                               colours=mk.PARTS_COLOURS)),
               "tab", "not-here.png")


@pytest.fixture(scope="module")
def parts_page(tmp_path_factory):
    """The woven player with a skin carrying every part, played in jsdom."""
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    home = tmp_path_factory.mktemp("skin-parts-validate")
    page = home / "parts.html"
    page.write_text(cli.weave_html(mk.build_parts(home)), encoding="utf-8")
    run = subprocess.run(
        ["node", str(ROOT / "tests/fixtures/skin_apply_harness.mjs"),
         "parts", str(page)],
        capture_output=True, text=True, timeout=240)
    assert run.returncode == 0, run.stderr + run.stdout
    return json.loads(run.stdout)["parts"]


def test_every_part_the_validator_accepts_is_a_part_the_player_draws(parts_page):
    """A part the validator accepts but the player ignores is a picture a pack
    ships and nobody ever sees. The validator's table is the list here, so a
    part added to SKIN_PARTS has to be drawn or this test says so."""
    css = parts_page["css"]
    bodies = re.findall(r"([^{}]*)\{([^{}]*)\}", css)
    missing = []
    for part in maplab.SKIN_PARTS:
        if part == "backdrop":
            continue                     # its own page; see test_skin_apply.py
        uris = [mk.picture_uri(fname) for fname in _pictures_of(part)]
        if not any(uri in body for _sel, body in bodies for uri in uris):
            missing.append(part)
    assert not missing, (
        "these parts validate and bake, but the player writes no rule that "
        f"draws them: {', '.join(missing)}")


def _pictures_of(part):
    """The fixture picture names of a part, if it is one the fixture carries."""
    spec = mk.ALL_SKIN["parts"].get(part) or mk.PARTS_SKIN.get(part)
    if part == "panel":
        return ["panel.png"]
    if part == "button":
        return ["button.png", "button-hover.png", "button-pressed.png"]
    if part == "bar":
        return ["bar-frame.png", "bar-fill.png"]
    if part == "cursor":
        return ["cursor.png"]
    return [f for f in (spec or {}).values() if isinstance(f, str)]
