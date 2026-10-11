"""vefr #364: what a Section's fog is DRAWN as. `shape` is circle or square.

Rylee, 2026-10-09: "Add square as an option (Recommended). Packs can pick
circle or square via `{\"fog\":{\"radius\":N,\"shape\":\"square\"}}`; circle
stays the default." The option she turned down - sight that grows with
what the hero has explored - is not here: this touches no explored-bitset
semantics and no save format.

The change is one key on `shapes.FOG` beside `radius`, and one branch
where the lit area is computed. Everything else about it is proof:

- the key is optional and its default is the circle that was always
  drawn, so a pack that names nothing validates and plays as it did;
- a pack that names `"circle"` produces the very same floor records as a
  pack that names nothing - the digest below is pinned to the bytes nine
  floors had before this key existed, and `circle` reads the same;
- a pack that names `"square"` gets a square, and gets it on every floor
  of its Section;
- anything else is refused by name: the sentence quotes the key, the
  refused value and both legal shapes;
- the player reads the shape in exactly one place (`litNow`, in
  `450-fog-of-war.js`), and its two branches are the whole of the
  geometry - the circle branch is the expression that was there.

The lit-set tests below run a PYTHON MIRROR of the two branches, because
the player part is JavaScript and this estate has no JS runtime to run it
in (`node`, `deno` and a Python JS engine are all absent - the browser
and jsdom suites skip for the same reason). The mirror is held to the
part's own text by `test_the_two_branches_are_the_geometry`, which reads
the woven player: if the JavaScript stops saying what the mirror says,
that test fails.

Run with:

    bash tests/run.sh tests/test_fog_shape.py
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from blueprint_helpers import normalized_pack
from vefr import delve, maplab, shapes

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "sections"
PARTS = ROOT / "web" / "player" / "parts"
WOVEN = ROOT / "web" / "packaged.html"

SHAPE = next(k for k in shapes.FOG.keys if k.name == "shape")
RADIUS = next(k for k in shapes.FOG.keys if k.name == "radius")


def fixture_section(name: str = "cellar") -> dict:
    """One committed fixture pack's Section, read off disk (not written out
    here, so the tests hold against the bytes a pack author ships)."""
    return json.loads((FIXTURES / name / "sections" / f"{name}.json").read_text(
        encoding="utf-8"))


def only(problems) -> tuple[str, str]:
    assert len(problems) == 1, [p.sentence for p in problems]
    return problems[0].pointer, problems[0].sentence


def descent_with(section: dict) -> dict:
    """A one-Section descent, the shape `delve.floor_plan` reads."""
    return {"run_seed": "fog-shape", "entry": {"region": "town", "at": [4, 5]},
            "sections": [copy.deepcopy(section)]}


def pack_with_fog(tmp_path, name: str, fog: dict) -> Path:
    """A real pack carrying a fixture Section with this fog block.

    Built the shipped way - `make_blueprint_pack` plus a real `vefr
    normalize` - over the fixture's own Blueprint, so the Section's
    families resolve, and then the one value under test is written into
    the pack's `sections/<id>.json`. The acceptance is about `vefr check
    --pack`, not about a dict handed to a function.
    """
    built = normalized_pack(
        tmp_path,
        blueprint=json.loads((FIXTURES / name / "blueprint.json").read_text(
            encoding="utf-8")))
    (built / "sections").mkdir(exist_ok=True)
    (built / "affixes.json").write_text(
        (FIXTURES / name / "affixes.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    section = fixture_section(name)
    section["fog"] = fog
    (built / "sections" / f"{name}.json").write_text(
        json.dumps(section, indent=1), encoding="utf-8")
    return built


# --------------------------------------------------- the key on the table

def test_the_table_offers_two_shapes_with_the_circle_first():
    """`circle` is first because it is the default and because a refusal
    reads its choices in table order: "circle" or "square"."""
    assert shapes.FOG_SHAPES == ("circle", "square")
    assert SHAPE.choices == ("circle", "square")
    assert SHAPE.kind == "enum"
    assert SHAPE.required is False, "shape is a choice, not a demand"


def test_the_shape_key_sits_beside_the_radius_and_the_radius_is_untouched():
    """The two keys are siblings on one block, and this slice moved neither
    the radius's bounds nor its place in the table."""
    assert [k.name for k in shapes.FOG.keys] == ["radius", "shape"]
    assert RADIUS.required is True
    assert (RADIUS.lo, RADIUS.hi) == (2, 32)
    assert shapes.FOG.example == '{"radius": 4}'


def test_the_block_still_writes_the_radius_example_it_always_did():
    """The `example` is quoted by `missing-key` and `not-object`, so it
    stays the radius alone: a Section whose fog has no radius is refused
    with the words it was refused with before this key existed."""
    assert only(shapes.check(shapes.FOG, {})) == (
        "/fog/radius",
        'fog must hold its radius, such as {"radius": 4}')


# --------------------------------------------------------- what is refused

def test_a_shape_that_is_not_one_of_the_two_is_refused_by_name():
    section = dict(fixture_section(), fog={"radius": 4, "shape": "triangle"})
    assert only(shapes.check(shapes.SECTION, section)) == (
        "/section/fog/shape",
        'section.fog.shape must be "circle" or "square", not \'triangle\'')


def test_a_shape_that_is_not_a_string_is_refused_the_same_way():
    """A closed set refuses a value of the wrong type the same way it
    refuses a value of the right type and the wrong name - by naming it."""
    for bad in (3, 4.0, True, None, ["square"], {"shape": "square"}):
        section = dict(fixture_section(), fog={"radius": 4, "shape": bad})
        pointer, sentence = only(shapes.check(shapes.SECTION, section))
        assert pointer == "/section/fog/shape", (bad, pointer)
        assert sentence == ('section.fog.shape must be "circle" or "square", '
                            f"not {bad!r}"), (bad, sentence)


def test_a_shape_spelled_the_right_way_is_accepted():
    for good in ("circle", "square"):
        section = dict(fixture_section(), fog={"radius": 4, "shape": good})
        assert shapes.check(shapes.SECTION, section) == [], good


def test_a_fog_with_no_shape_is_still_a_whole_fog_block():
    """The key is optional, and the pack that ships names no shape: the
    fixture Section validates exactly as it did before the key existed."""
    section = fixture_section()
    assert section["fog"] == {"radius": 4}
    assert shapes.check(shapes.SECTION, section) == []


def test_the_refusals_reach_an_author_through_vefr_check(tmp_path, capsys):
    """Acceptance 4, through the door an author walks through: `vefr check
    --pack P` is `maplab.cmd_validate`, and it reads every pack's
    `sections/`."""
    for good in ({"radius": 4}, {"radius": 4, "shape": "circle"},
                 {"radius": 4, "shape": "square"}):
        pack = pack_with_fog(tmp_path / f"good{good.get('shape', 'none')}",
                             "cellar", good)
        assert maplab.cmd_validate(argparse.Namespace(pack=str(pack))) == 0, good
        assert capsys.readouterr().out.startswith("ok:")

    for bad in ({"radius": 4, "shape": "triangle"}, {"radius": 4, "shape": 3}):
        pack = pack_with_fog(tmp_path / f"bad{bad['shape']}", "cellar", bad)
        assert maplab.cmd_validate(argparse.Namespace(pack=str(pack))) == 1, bad
        out = capsys.readouterr().out
        assert "sections/cellar.json: /section/fog/shape" in out, out
        assert 'must be "circle" or "square", not ' in out, out


# ------------------------------- the default is the circle that was there

# The fog block of all nine floors of the fixture descent, one canonical
# JSON line each, digested. This is the value BEFORE the shape key
# existed (vefr #364, 2026-10-09) and it must not move: a pack that names
# no shape weaves to the same bytes it wove to before this slice. To
# refresh it, and to say in the commit message why it moved, run this
# module's own `floor_fog_digest(fixture_section())` with this constant
# replaced by a placeholder and print it:
#   PYTHONPATH=src python3 -c "import sys; sys.path.insert(0, 'tests'); \
#     import test_fog_shape as t; print(t.floor_fog_digest(t.fixture_section()))"
FLOOR_FOG_DIGEST = "cd155d1247bb6ff12ca89da27c748954404da8906ee97c0da4689e13963cbff0"


def floor_fog_digest(section: dict) -> str:
    descent = descent_with(section)
    body = "".join(
        json.dumps({"depth": d, "fog": delve.floor_plan(descent, d)["fog"]},
                   sort_keys=True, separators=(",", ":")) + "\n"
        for d in range(1, 10))
    return hashlib.sha256(body.encode()).hexdigest()


def test_a_pack_that_names_no_shape_still_weaves_the_bytes_it_wove_before():
    """Acceptance 1, pinned. The fixture Section is the shipped shape of a
    pack's fog block (`{"radius": 4}`) and this digest is what those nine
    floors wove to before `shape` existed."""
    assert floor_fog_digest(fixture_section()) == FLOOR_FOG_DIGEST


def test_a_pack_that_names_circle_explicitly_is_that_same_pack():
    """Acceptance 2: naming the default is not a second spelling of it. The
    floor record carries `shape` only when it is not the default circle, so
    the two packs produce the same records, the same digest and the same
    save bytes - there is no "circle" state to tell apart at runtime."""
    named = dict(fixture_section(), fog={"radius": 4, "shape": "circle"})
    assert delve.floor_plan(descent_with(named), 5)["fog"] == {"radius": 4}
    assert floor_fog_digest(named) == FLOOR_FOG_DIGEST


def test_a_section_that_names_no_fog_at_all_still_gets_the_engine_default():
    """The bound on what a pack may ASK for moved with the radius ceiling
    and no default moved with the shape key: no `fog` key, no `fog.shape`
    key, the same radius on every floor."""
    section = fixture_section()
    del section["fog"]
    descent = descent_with(section)
    assert [delve.floor_plan(descent, d)["fog"] for d in (1, 3, 9)] == \
        [{"radius": delve.DEFAULT_FOG_RADIUS}] * 3
    assert delve.DEFAULT_FOG_RADIUS == 5


# --------------------------------------------------- a square gets drawn

def test_a_pack_that_names_square_gets_a_square_on_every_floor():
    """Acceptance 3, in the record the player draws from: the shape rides
    along on every floor of the Section, unclamped, and the radius is the
    radius the pack asked for."""
    section = dict(fixture_section(), fog={"radius": 4, "shape": "square"})
    descent = descent_with(section)
    assert {delve.floor_plan(descent, d)["fog"]["shape"]
            for d in range(1, 10)} == {"square"}
    assert {delve.floor_plan(descent, d)["fog"]["radius"]
            for d in range(1, 10)} == {4}


def test_the_ceiling_radius_draws_a_square_that_still_fits_the_floor():
    """The reason #375 gave for the ceiling holds for a square too: at the
    ceiling both shapes fit inside the largest floor the schema allows on
    both axes (the square is 65 tiles across, the same as the disc's
    bounding box)."""
    section = dict(fixture_section(), fog={"radius": 32, "shape": "square"})
    assert shapes.check(shapes.SECTION, section) == []
    assert delve.floor_plan(descent_with(section), 1)["fog"] == \
        {"radius": 32, "shape": "square"}


# ------------------------------------------------------ the geometry itself

def lit(radius: int, shape: str = "circle", at=(0, 0), size: int = 81):
    """A PYTHON MIRROR of `litNow` in `450-fog-of-war.js`.

    The JavaScript is the thing that runs; this is the two branches of it,
    written out again so the sets they produce can be compared without a JS
    runtime. `test_the_two_branches_are_the_geometry` below holds the part's
    own text to what is mirrored here.
    """
    hx, hy = at
    half = size // 2
    out = set()
    for y in range(hy - radius, hy + radius + 1):
        for x in range(hx - radius, hx + radius + 1):
            if not (0 <= x < size and 0 <= y < size):
                continue
            dx, dy = x - hx, y - hy
            lit_ = (max(abs(dx), abs(dy)) <= radius if shape == "square"
                    else dx * dx + dy * dy <= radius * radius)
            if lit_:
                out.add((x, y))
    assert half * 2 + 1 == size
    return out


def test_the_circle_is_the_circle_that_was_there():
    """The default branch is unchanged arithmetic: tiles within `radius`
    steps by straight line of the hero. Frozen as sets, because a lit set
    is what the player remembers as explored."""
    assert lit(1, at=(40, 40)) == {(40, 40), (39, 40), (41, 40),
                                   (40, 39), (40, 41)}
    assert lit(2, at=(40, 40)) == {
        (40 + dx, 40 + dy)
        for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)
        if dx * dx + dy * dy <= 4}
    assert len(lit(4, at=(40, 40))) == 49      # radius 4, the shipped pack
    assert len(lit(5, at=(40, 40))) == 81      # radius 5, the engine default


def test_a_square_is_a_square_and_holds_every_tile_the_circle_holds():
    """Chebyshev, so the lit area is (2r+1) tiles on a side: at radius 4,
    81 tiles against the circle's 49. A pack that asks for a square sees
    more, never less - and the extra is on the corners, which is what a
    floor of rooms wants and what the disc left dark."""
    for radius in (2, 4, 5, 8, 32):
        circle, square = lit(radius, "circle", (40, 40)), \
            lit(radius, "square", (40, 40))
        assert circle < square, radius
        assert len(square) == (2 * radius + 1) ** 2, radius
        assert len(circle) == sum(
            1 for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)
            if dx * dx + dy * dy <= radius * radius), radius


def test_neither_shape_lights_a_tile_beyond_the_radius_on_either_axis():
    """The loop over `fogRadius` steps out on each axis is the bounding box
    of BOTH shapes, so no test is left out by the loop and none is lit
    twice."""
    for radius in (3, 7):
        for shape in ("circle", "square"):
            for tile in lit(radius, shape, (40, 40)):
                dx, dy = tile[0] - 40, tile[1] - 40
                assert max(abs(dx), abs(dy)) <= radius, (shape, tile)


def test_a_floor_edge_does_not_light_a_tile_that_is_not_there():
    """The bounds check is unchanged: a lit tile is a tile on the map.

    A hero standing in the corner of an 11x11 floor at radius 3 lights the
    4x4 the map has of the 7x7 a radius-3 shape would cover, as a square,
    and the eleven tiles of that 4x4 within three steps by straight line, as
    a circle - the same corner cut both shapes have always made.
    """
    square_corner = lit(3, "square", at=(0, 0), size=11)
    assert square_corner == {(x, y) for x in range(4) for y in range(4)}
    circle_corner = lit(3, "circle", at=(0, 0), size=11)
    assert circle_corner == {(x, y) for x in range(4) for y in range(4)
                             if x * x + y * y <= 9}
    assert circle_corner < square_corner
    assert len(circle_corner) == 11


# ------------------------------------------- the player part, in the woven file

FOG_PART = (PARTS / "450-fog-of-war.js").read_text(encoding="utf-8")


def test_the_two_branches_are_the_geometry():
    """The mirror above is held to the part's own text.

    The player reads the shape in one function and one function only: the
    circle keeps the expression it had, and the square is the Chebyshev
    test. A radius a torch adds (`fogRadius = lightBase() + lightBonus`)
    needs no shape branch, because `lightBase()` only reads the radius and
    `litNow()` is the only reader of the shape.
    """
    assert FOG_PART.count("function fogShape()") == 1
    assert ("town.fog && town.fog.shape === 'square'") in FOG_PART
    assert "dx * dx + dy * dy <= fogRadius * fogRadius" in FOG_PART
    assert "Math.max(Math.abs(dx), Math.abs(dy)) <= fogRadius" in FOG_PART
    assert "var square = fogShape() === 'square';" in FOG_PART


def test_the_woven_player_carries_both_shapes_and_the_default():
    """`web/packaged.html` is the file that ships; the parts are woven into
    it byte for byte, so what a player runs is what is pinned above."""
    html = WOVEN.read_text(encoding="utf-8")
    assert "var DEFAULT_FOG_SHAPE = 'circle';" in html
    assert html.count("var DEFAULT_FOG_SHAPE = 'circle';") == 1
    assert "town.fog && town.fog.shape === 'square'" in html
    assert "Math.max(Math.abs(dx), Math.abs(dy)) <= fogRadius" in html
    assert "dx * dx + dy * dy <= fogRadius * fogRadius" in html


def test_the_descent_twin_and_the_python_agree_on_the_record():
    """Two languages draw the same floor, so the fog block they both write
    has to be the same block: a square rides along, a circle and a missing
    key do not. This reads the twin's own source for the rule, since there
    is no JS runtime here to run it in (`tests/fixtures/descent_parity_harness.mjs`
    runs it in CI under node)."""
    part = (PARTS / "397-the-descent.js").read_text(encoding="utf-8")
    assert "var blockFog = { radius: Math.max(1, radius) };" in part
    assert "if (fog && fog.shape === 'square') blockFog.shape = 'square';" in part
    assert "fog: blockFog" in part