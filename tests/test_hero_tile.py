"""`window.VEFR_HERO_AT`: where the hero stands, published every turn.

The playthrough driver walks by this and re-reads it after every press,
so a refused step has to be a refusal something can see. Played through
the REAL woven file in jsdom (tests/fixtures/play.mjs), the same door the
other play tests use: the pack's own hero start, then a walk, then a walk
into a wall - and the published tile follows each one, or refuses to.

Skips when node is not installed, like the other node-vm tests. The
browser half of this coverage lives in tests/browser/test_playthrough.py.
"""

import shutil

import pytest

import play_kit

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node not installed")

# The interact fixture's own start tile (make_interact_pack.py).
START = [1, 1]


def _play(tmp_path, steps):
    html = play_kit.weave(play_kit.pack(tmp_path, "interact"), tmp_path)
    reads = ["VEFR_HERO_AT"]
    out = play_kit.play(html, {"steps": ["begin"] + steps, "read": reads})
    assert out["errors"] == [], out["errors"]
    return out["reads"]["VEFR_HERO_AT"]


def test_the_hero_tile_is_published_where_the_pack_put_the_hero(tmp_path):
    """At the start it is the pack's own hero start, and it names the
    region it is in - the two facts a driver needs before its first key."""
    at = _play(tmp_path, [])
    assert at == {"x": START[0], "y": START[1], "region": "town"}


def test_the_hero_tile_follows_every_step(tmp_path):
    """One step is one tile, and the published tile is the step - not the
    tile before it, and not the tile after the turn has run on."""
    # (The storeroom rat stands at [2, 1], right of the start, so a first step right is a fight,
    # not a step: the walk goes down first.)
    assert _play(tmp_path, ["dir:down", "wait:400"]) == {"x": START[0], "y": START[1] + 1,
                                                        "region": "town"}
    assert _play(tmp_path, ["dir:down", "wait:400", "dir:right", "wait:400"]) == \
        {"x": START[0] + 1, "y": START[1] + 1, "region": "town"}


def test_a_refused_step_leaves_the_published_tile_where_it_was(tmp_path):
    """A wall is a refusal the driver can see, not a silent one: up out
    of the hero's own row is off the map, and the tile says so."""
    before = _play(tmp_path, [])
    after = _play(tmp_path, ["dir:up", "wait:400"])
    assert after == before


def test_the_hero_tile_follows_the_hero_through_a_door(tmp_path):
    """Through the fixture's own door the tile names the cellar - the
    same fact the canvas and the combat snapshot read, from one place."""
    to_door = ["down", "down", "right", "right", "up", "right", "right",
               "right", "right", "down", "down", "right", "right"]
    at = _play(tmp_path, ["walk:" + ",".join(to_door), "key:e"])
    assert at["region"] == "cellar", at


def test_the_pack_file_is_where_it_was(tmp_path):
    """The global is a read-only publication: playing the pack writes no
    byte of it."""
    pack = play_kit.pack(tmp_path, "interact")
    before = {p: p.read_bytes() for p in sorted(pack.rglob("*")) if p.is_file()}
    play_kit.play(play_kit.weave(pack, tmp_path),
                  {"steps": ["begin", "dir:right"], "read": ["VEFR_HERO_AT"]})
    after = {p: p.read_bytes() for p in sorted(pack.rglob("*")) if p.is_file()}
    assert after == before