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
# Re-cut 2026-10-11, the vefr#359 monster-reward piece onto current `main`: part
# 397 reads a family's `xp` in `mobsAt` and `withWarden` and exports `xpFor`, so
# every pack's woven player moves. Measured twice with the documented command
# above (as `PYTHONPATH=src python3 -c ...`, no uv in the sandbox), readings equal:
#   ebff7450540b050ca83d6796c6184264314040eeb4ac90c3e5dc7a7ef9770348
#   ebff7450540b050ca83d6796c6184264314040eeb4ac90c3e5dc7a7ef9770348
# Re-cut 2026-10-11, the vefr#350 death-resume stack onto current `main`:
# a death on a floor of the descent wakes the hero on that floor instead of
# at the pack's baked wake point. That is `deathResume` beside `cozyDeath` in
# the player template, and `cozyDeath` reads it, so every pack's weave moves,
# skinned or not; this pack's own bytes do not (no skin, no `VEFR_ITEMS`
# change). Measured twice with the documented command above (as
# `PYTHONPATH=src python3 -c ...`, no uv in the sandbox), readings equal:
#   4927bff9b106baf362e253589a9e01f6a1e2e41c70e3af8ea2339fc4ca66cfc5
#   4927bff9b106baf362e253589a9e01f6a1e2e41c70e3af8ea2339fc4ca66cfc5
# Last moved 2026-10-10, on the E8d tree. E8d changed the player: it adds
# ADR 0015 Amendment 1's warden's `challenge`, `yields` and `fightable`
# (the key a rule challenge delivers, a beaten warden that stays, and a
# warden a blow cannot land on). The player template is woven into every
# pack, so the digest had to be recomputed rather than carried over.
# Last moved 2026-10-11, repairing the E8d union. E8d changed the player:
# it adds ADR 0015 Amendment 1's warden's `challenge`, `yields` and
# `fightable` (the key a rule challenge delivers, a beaten warden that
# stays, and a warden a blow cannot land on). The repair keeps a `yields`
# warden hostile until it is actually beaten - on the live entry `yields`
# is a state, not the pack's key - so `enemyEntry` no longer copies it and
# the player template moved again. The template is woven into every pack,
# so the digest had to be recomputed rather than carried over.
# Nothing about this pack's own bytes moved - `worlds/sample-world`
# declares no skin and no descent, so `window.VEFR_TOWN_STATES` and
# `window.VEFR_DESCENT_DEF` bake the literal null here exactly as
# `window.VEFR_SKIN` does, and E8d did not touch the pack at all.
# `tests/test_warden_challenge.py` holds the pin that says so for a pack
# that DOES name a descent: the bytes the pack itself contributes.
# Re-cut 2026-10-11, the E8d warden stack onto current `main` (after #402): the
# woven player moved on the union, so every pack's weave moves. Measured twice
# with the documented command above (as `PYTHONPATH=src python3 -c ...`, no uv
# in the sandbox), readings equal:
#   5fe9f907e61cf39c96f6d442605bce131fc15786d2491ddb61bc0824e82ff580
#   5fe9f907e61cf39c96f6d442605bce131fc15786d2491ddb61bc0824e82ff580
# Re-cut 2026-10-11, the V352S stack (vefr #352 descent entry tile, #346 stamp
# sweep) onto current `main`: the descent part's `claimTile` moves the woven
# player, so every pack's weave moves. Measured twice with the documented
# command above (as `PYTHONPATH=src python3 -c ...`, no uv in the sandbox),
# readings equal:
#   5c281472acffbba023480b7fc0fc4cf43d21cb2d67e093ab07fdfac5401703c0
#   5c281472acffbba023480b7fc0fc4cf43d21cb2d67e093ab07fdfac5401703c0
# V352fix 2026-10-11, repairing that same re-cut: the union of the descent
# part's `wireEntry` had kept main's gate on a `stair` variable and called
# `claimTile(list, stair)`, which is the #352 precedence fix in behaviour but
# not in the shape the acceptance test pins - the authored-door precedence
# call is restored as the original inline `claimTile(list, { from: entry.region
# ... })`, with main's gate folded into the literal, so the player template
# moved again. Measured twice with the documented command above (as
# `PYTHONPATH=src python3 -c ...`, no uv in the sandbox), readings equal, and
# all 41 `window.VEFR_*` data lines of this pack are byte-identical before and
# after - only the player around them changed:
#   4f88895a4fe23ea81dda35e30c887d09540a29fac4ded1821ee29a5975a550c7
#   4f88895a4fe23ea81dda35e30c887d09540a29fac4ded1821ee29a5975a550c7
# ELSLICEFIX 2026-10-11, the endless gate (the stair past the last Section waits
# for `story_end`) cherry-picked onto post-#405 main: its hunk in the descent
# part moves the woven player, so this weave moves. Measured twice in separate
# processes, readings equal; the pack's data lines are unchanged:
#   bd38a6085259b6ec3fc987037c78d1d35fcecddb6105f69c99070c4cc6eaa8ff
#   bd38a6085259b6ec3fc987037c78d1d35fcecddb6105f69c99070c4cc6eaa8ff
# Descent polish 2026-10-12 (vefr#412): generated monsters carry their family's sprite, the bag strip
# stacks by kind, a scrolling dark floor sizes its tile to the lit circle; all three move the woven
# player. Measured twice in separate processes, readings equal; the pack's data lines are unchanged:
#   258470fd8a0d9c8925f39b9d1dff597ab443bc6807f24fd34e47f9119cdede20
#   258470fd8a0d9c8925f39b9d1dff597ab443bc6807f24fd34e47f9119cdede20
# ELDECFIX4 2026-10-12, PR 410 edits web/player/parts/397-the-descent.js, which
# is woven into every pack, so this weave moved from the ELSLICEFIX digest
# (bd38a6085259b6ec3fc987037c78d1d35fcecddb6105f69c99070c4cc6eaa8ff) to:
#   f02974fad1de235eb0a6b0123cc692c0362c6405a45470315d995b57249f9eb6
# Merged with #412 on 2026-10-12: both moved the woven player; measured twice in separate processes:
#   c9ec6b7110edeb6fb3d3d3d8d0eba4d3a3475888339280a88042e866ab4b162e
#   c9ec6b7110edeb6fb3d3d3d8d0eba4d3a3475888339280a88042e866ab4b162e
# WAYART 2026-10-12: the woven player gains VEFR_WAY_ICONS and VEFR_REGION_WAY_ICONS (both `{}` here)
# and picks a transition's picture by kind; measured twice in separate processes, readings equal:
#   07f66d54ca31e402935a9a0d285bf1703d8fa283a6e7f7dfa1d319c807a4d116
#   07f66d54ca31e402935a9a0d285bf1703d8fa283a6e7f7dfa1d319c807a4d116
# #417 2026-10-12: Talk with no brain says the seeded line (480-town-input-and-turns.js), on top of #416; measured twice in separate processes, readings equal:
#   aab9d5457b034d7b900bc2ed34ccb99645514acf744739ec559e173b7f9c8d7f
#   aab9d5457b034d7b900bc2ed34ccb99645514acf744739ec559e173b7f9c8d7f
# #418 phone camera merged with #419 (Talk) on 2026-10-12; measured twice in separate processes, readings equal:
#   3efab5dcd619fc4e4510f3297cf3e6ea5dcb1a059341f4fcad5c5476b014113d
#   3efab5dcd619fc4e4510f3297cf3e6ea5dcb1a059341f4fcad5c5476b014113d
# #420 object layer merged with #418 phone camera, 2026-10-12; measured twice in separate processes, readings equal:
#   578de6ada011a5a407a4a9d6cd1e53a10c44a6c2e417dfbfe37549f8b4abb509
#   578de6ada011a5a407a4a9d6cd1e53a10c44a6c2e417dfbfe37549f8b4abb509
# Monster parts run without the props part (#420), 2026-10-12; measured twice in separate processes, readings equal:
#   0a80b00def25f0cfaecd56841753a2285a84daea0a8c74a04dd13833e51a3aca
#   0a80b00def25f0cfaecd56841753a2285a84daea0a8c74a04dd13833e51a3aca
# Pixel art (#427) merged with the object layer (#420), 2026-10-12; measured twice in separate processes, readings equal:
#   b260300bef12bb4c6f0dc52cbcea83e078522609cdf3cd87d5005d48960ecbc9
#   b260300bef12bb4c6f0dc52cbcea83e078522609cdf3cd87d5005d48960ecbc9
# Pixel art keeps main's sprite height name (#427), 2026-10-12; measured twice in separate processes, readings equal:
#   8bb8656ba52c90b03d24ce2a3d40f70606decb09aa16d91415fcd40babf869c4
#   8bb8656ba52c90b03d24ce2a3d40f70606decb09aa16d91415fcd40babf869c4
# Touch controls (#428) merged with pixel art (#427); measured twice in separate processes, readings equal:
#   e857bc9ef7ae6cbaafc57ab3e2995a2c0d833dc7fc11a0c791d7b5d9a9db31cf
#   e857bc9ef7ae6cbaafc57ab3e2995a2c0d833dc7fc11a0c791d7b5d9a9db31cf
# The sweep fixes on top of touch controls (#428); measured twice in separate processes, readings equal:
#   36865f9d011c3b59cb11d9cb235a9a02d92e1691ec233bff8375474eaaa8b1cd
#   36865f9d011c3b59cb11d9cb235a9a02d92e1691ec233bff8375474eaaa8b1cd
# Bag capacity (#434) merged with the sweep fixes, 2026-10-12; measured twice in separate processes, readings equal:
#   031824c0d4c54435c88f0de5b4d4678ca3d448d9fad9a6c1c1dc5979bb4bcfa9
#   031824c0d4c54435c88f0de5b4d4678ca3d448d9fad9a6c1c1dc5979bb4bcfa9
# The vault chest's own permanent flag (ADR 0015), 2026-10-12; measured twice in separate processes, readings equal:
#   07177f55a79e308bb2894b0858e3ead070dea3d74ff940d599f1ec36871c4455
#   07177f55a79e308bb2894b0858e3ead070dea3d74ff940d599f1ec36871c4455
# The town gate on a Section's last stair only (the stair that leaves the Section), 2026-10-12; measured twice in separate processes, readings equal:
#   7c1c8e962977b479584fc48b1bb106265bb9ae5f34cb7fbcee333c9fd9521b00
#   7c1c8e962977b479584fc48b1bb106265bb9ae5f34cb7fbcee333c9fd9521b00
# A full bag refuses a shop purchase in words (#343), 2026-10-12; measured twice in separate processes, readings equal:
#   4d79733b09c9dec30d9c2421d34199f7b456b4f226cba5693dc2a0fa666b583c
#   4d79733b09c9dec30d9c2421d34199f7b456b4f226cba5693dc2a0fa666b583c
# A cast writes the why-log (#345), 2026-10-12; measured twice in separate processes, readings equal:
#   bad7095e61c85cd26166562090bf77e0e3b2cacdf9b6288b8bf6d4d1d5abcc32
#   bad7095e61c85cd26166562090bf77e0e3b2cacdf9b6288b8bf6d4d1d5abcc32
# A deep landing's up-stair climbs to the entry (vefr#366), 2026-10-12; measured twice in separate processes, readings equal:
#   6c5b2fd0008ad2ed6c6dd262b414c444f3a879f58c881e6cc638268ebda01218
#   6c5b2fd0008ad2ed6c6dd262b414c444f3a879f58c881e6cc638268ebda01218
# A Section's label in the player's hints (#363), 2026-10-12; measured twice in separate processes, readings equal:
#   7289fe208fe7f306d626b1e154171f3a1848e4e1ad777471dc3a6491f1596442
#   7289fe208fe7f306d626b1e154171f3a1848e4e1ad777471dc3a6491f1596442
# A generated floor announced by its Section's label on arrival (#362), 2026-10-12; measured twice in separate processes, readings equal:
#   0538c9bd605fa1debc42c2ede3176dda7bc2c17cbfa89ac9c20417967e9cf41b
#   0538c9bd605fa1debc42c2ede3176dda7bc2c17cbfa89ac9c20417967e9cf41b
# A family's `sight: 0` kept on a generated floor (#437, 397-the-descent.js), 2026-10-12; measured twice in separate processes, readings equal:
#   e8cf6223969fede34b9133ae5afc07ef6b010f79e2ecce01a18f9367a816dbc4
#   e8cf6223969fede34b9133ae5afc07ef6b010f79e2ecce01a18f9367a816dbc4
# Whisper and Explore on the touch controls (#431), 2026-10-12; measured twice in separate processes, readings equal:
#   253b11028d3f6657906310f375cf8cfe9151d681609720078163e76d4d7e89b0
#   253b11028d3f6657906310f375cf8cfe9151d681609720078163e76d4d7e89b0
# A whole lit map leaves the HUD bands clear (#424), 2026-10-12; measured twice in separate processes, readings equal:
#   ec3f6c7a8ca6cb4c6e9185ec76030f14655a293d690f6b77af5c8095cc365811
#   ec3f6c7a8ca6cb4c6e9185ec76030f14655a293d690f6b77af5c8095cc365811
# All of the 2026-10-12 issue sweep merged together (#362 #363 #366 #422 #424 #425 #431 #437, #343/#345 parts); measured twice in separate processes, readings equal:
#   68ced1bfc4e74836419c4adc4d54cb4928c375b31318c12cdb12b4969657d09a
#   68ced1bfc4e74836419c4adc4d54cb4928c375b31318c12cdb12b4969657d09a
# A Section's decor drawn on its generated floors (#442), 2026-10-13; measured twice in separate processes, readings equal:
#   b6f4ea4afb04ec07c027c21fa06bd8b1d9129728a58a12ca2bc56ad8df037f79
#   b6f4ea4afb04ec07c027c21fa06bd8b1d9129728a58a12ca2bc56ad8df037f79
# A mirrored side drawn flipped and a phone drag held in play, 2026-10-13; measured twice in separate processes, readings equal:
#   9b3e7c3d5aee077ee84f0ddd1259d10fc9e8277ca9340049bf483d559f2f6849
#   9b3e7c3d5aee077ee84f0ddd1259d10fc9e8277ca9340049bf483d559f2f6849
# The storybook phone layout: a look setting, a slim top bar and a one-line message, 2026-10-13; measured twice in separate processes, readings equal:
#   fa13a8b845fb10320940f4b8e9326f4f5800cd78a0a8c3ba12111a834e42aab6
#   fa13a8b845fb10320940f4b8e9326f4f5800cd78a0a8c3ba12111a834e42aab6
# Two buttons on a phone, the Dark look dark on a light-mode phone, a calmer walk, 2026-10-13; measured twice in separate processes, readings equal:
#   82ae0a667b9c144c7abe8f2d06369ed173159303b92bbcbf6db2ec09a2f13915
#   82ae0a667b9c144c7abe8f2d06369ed173159303b92bbcbf6db2ec09a2f13915
# A desk's follow camera (display.desk_tile) and its one fading message line, 2026-10-13; measured twice in separate processes, readings equal:
#   d8aa37fc38bdc1d17160232896b30791d9be64b68b49fc7c5ed29d0174597e56
#   d8aa37fc38bdc1d17160232896b30791d9be64b68b49fc7c5ed29d0174597e56
# A stair's landing waits for the first step (#465), 2026-10-14; measured twice in separate processes, readings equal:
#   7456ac3ef602fb755e85d9b7a03d9ff6e4bfd9a5a5ddc7ebc4900dd66d3c1ec5
#   7456ac3ef602fb755e85d9b7a03d9ff6e4bfd9a5a5ddc7ebc4900dd66d3c1ec5
NO_SKIN_WEAVE_SHA256 = "7456ac3ef602fb755e85d9b7a03d9ff6e4bfd9a5a5ddc7ebc4900dd66d3c1ec5"


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
