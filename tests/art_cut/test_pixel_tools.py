"""The pixel-art tools (vefr#426): pixelize, make_sheet, animate, process_kit.

Every picture is drawn here, small and synthetic, so each tool's promise is checked without real art:
painted blocks become the exact native pixels, frames are cut by shape and stand on one baseline, an
animation changes only its role colours, and a kit comes out at its planned sizes on one palette.
"""
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "art"
sys.path.insert(0, str(TOOLS))
import animate  # noqa: E402
import make_sheet  # noqa: E402
import pixel_common as pc  # noqa: E402
import pixelize  # noqa: E402
import process_kit  # noqa: E402

GREEN = (0, 255, 0)
PAL = [(40, 30, 60), (200, 80, 60), (240, 200, 120), (60, 140, 90), (90, 110, 200)]


def run(tool, *args):
    out = subprocess.run([sys.executable, str(TOOLS / tool), *map(str, args)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def colours(img):
    return {p[:3] for p in pc.pixels(img.convert("RGBA")) if p[3]}


def alpha_mask(img):
    return [p[3] for p in pc.pixels(img)]


# --- pixelize ---------------------------------------------------------------------------------------------

def native_picture(w=20, h=14, seed=4):
    rnd = random.Random(seed)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(2, h - 1):
        for x in range(3, w - 2):
            img.putpixel((x, y), PAL[rnd.randrange(len(PAL))] + (255,))
    return img


def paint_wandering(native, base, seed=1, offset=3, noise=6):
    """What an image model hands back: blocks of about `base` px, each a pixel wider or narrower now and
    then, with grain inside every block, on flat #00FF00."""
    rnd = random.Random(seed)
    ws = [base + rnd.choice((-1, 0, 0, 0, 1)) for _ in range(native.width)]
    hs = [base + rnd.choice((-1, 0, 0, 0, 1)) for _ in range(native.height)]
    big = Image.new("RGB", (offset + sum(ws) + 5, offset + sum(hs) + 5), GREEN)
    px = big.load()
    y0 = offset
    for j, h in enumerate(hs):
        x0 = offset
        for i, w in enumerate(ws):
            p = native.getpixel((i, j))
            c = p[:3] if p[3] else GREEN
            for y in range(y0, y0 + h):
                for x in range(x0, x0 + w):
                    px[x, y] = tuple(min(255, max(0, v + rnd.randint(-noise, noise))) for v in c)
            x0 += w
        y0 += h
    return big


def trimmed(img):
    return img.crop(pc.opaque_bbox(img))


@pytest.mark.parametrize("base", [6, 9, 12])
def test_pixelize_recovers_the_native_pixels_from_wandering_blocks(base):
    native = native_picture()
    out, grid = pixelize.pixelize(paint_wandering(native, base), palette=PAL)
    assert abs(grid["x"][0] - base) < 0.5 and abs(grid["y"][0] - base) < 0.5
    assert pc.pixels(trimmed(out)) == pc.pixels(trimmed(native)), "a block came out wrong"


def test_pixelize_keys_the_backdrop_and_locks_the_palette():
    out, _ = pixelize.pixelize(paint_wandering(native_picture(), 8, noise=20), palette=PAL)
    assert out.getpixel((0, 0))[3] == 0, "the #00FF00 backdrop was not keyed"
    assert colours(out) <= set(PAL)
    assert set(alpha_mask(out)) <= {0, 255}, "alpha must be hard"


def test_pixelize_with_a_known_block_skips_the_search():
    native = native_picture(seed=9)
    big = native.resize((native.width * 7, native.height * 7), Image.NEAREST)
    out, grid = pixelize.pixelize(big, block=7, offset=(0, 0), key="none")
    assert grid["x"] == (7, 0)
    assert pc.pixels(out) == pc.pixels(pc.hard_alpha(native))


def test_despeckle_removes_strays_and_keeps_real_details():
    skin, eye, near = (230, 180, 150), (30, 20, 20), (236, 186, 156)
    img = Image.new("RGBA", (12, 7), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((1, 1, 7, 5), fill=skin + (255,))
    img.putpixel((3, 3), eye + (255,))        # an eye: far from skin, stays
    img.putpixel((5, 3), near + (255,))       # a stray shade of skin, goes
    img.putpixel((2, 4), (0, 0, 0, 0))        # a pinhole, filled
    img.putpixel((10, 3), skin + (255,))      # a lone speck in the backdrop, cleared
    out = pc.despeckle(img)
    assert out.getpixel((3, 3))[:3] == eye
    assert out.getpixel((5, 3))[:3] == skin
    assert out.getpixel((2, 4)) == skin + (255,)
    assert out.getpixel((10, 3))[3] == 0


def test_build_palette_keeps_only_real_colours():
    small = Image.new("RGBA", (4, 1))
    for i, c in enumerate(PAL[:4]):
        small.putpixel((i, 0), c + (255,))
    assert set(pixelize.build_palette([small], 32)) == set(PAL[:4])
    rnd = random.Random(2)
    many = Image.new("RGBA", (40, 40))
    many.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255) for _ in range(1600)])
    pal = pixelize.build_palette([many, small], 16)
    assert 1 < len(pal) <= 16
    assert set(pal) <= colours(many) | colours(small), "the master palette invented a colour"


def test_pixelize_cli_image_and_palette(tmp_path):
    src = tmp_path / "painted.png"
    paint_wandering(native_picture(), 8).save(src)
    approved = tmp_path / "approved.png"
    native_picture(seed=5).save(approved)
    assert "usage" in run("pixelize.py", "--help")
    run("pixelize.py", "palette", tmp_path / "pal.json", approved, "--colors", "8")
    assert len(json.loads((tmp_path / "pal.json").read_text())["colors"]) == len(PAL)
    out = run("pixelize.py", "image", src, tmp_path / "out.png", "--palette", tmp_path / "pal.json", "--trim")
    assert "15x11 px (block 7" in out or "15x11 px (block 8" in out
    assert Image.open(tmp_path / "out.png").size == (15, 11)


# --- make_sheet -------------------------------------------------------------------------------------------

BODY, STICK = (90, 60, 140), (150, 110, 60)


def figure(d, x, ground, h=20, stick=0):
    """A little person at slot x: a body standing on `ground`, and a stick held out `stick` px to the right."""
    d.rectangle((x, ground - h, x + 7, ground - 1), fill=BODY)
    if stick:
        d.rectangle((x + 8, ground - 14, x + 7 + stick, ground - 13), fill=STICK)


def strip(n, slot=24, ground=26, sticks=(), heights=None, backdrop=GREEN):
    img = Image.new("RGB", (n * slot, 30), backdrop)
    d = ImageDraw.Draw(img)
    for i in range(n):
        figure(d, i * slot + 4, ground - (i % 2), (heights or {}).get(i, 20), dict(sticks).get(i, 0))
    return img


def test_make_sheet_cuts_by_shape_and_writes_the_engine_shape(tmp_path):
    from vefr.maplab import sprite_sheet_errors

    idle, walk = tmp_path / "idle.png", tmp_path / "walk.png"
    strip(2).save(idle)
    strip(4).save(walk)
    # figure 2's stick reaches 14 px right, across the slot edge into figure 3's slot: an even cut would slice it
    act = tmp_path / "act.png"
    strip(6, sticks=[(2, 14)]).save(act)
    out = tmp_path / "pack" / "sprites" / "hero"
    run("make_sheet.py", "--out", out, f"{idle}=idle", f"{walk}=walk", f"{act}=act,attack:3,up/idle,hurt")
    data = json.loads((out.parent / "hero.sheet.json").read_text())
    assert data["image"] == "hero-sheet.png" and data["fps"] == 8
    assert data["directions"] == {
        "down": {"idle": [0, 1], "walk": [6, 7, 8, 9], "act": [12], "attack": [13, 14, 15], "hurt": [17]},
        "up": {"idle": [16]},
    }
    assert sprite_sheet_errors(tmp_path / "pack") == []
    sheet = Image.open(out.parent / "hero-sheet.png").convert("RGBA")
    fw, fh = data["frame"]
    assert sheet.size == (6 * fw, 3 * fh)
    stick_px = sum(1 for p in pc.pixels(sheet) if p[3] and p[:3] == STICK)
    assert stick_px == 14 * 2, "the swung stick was cut away from its figure"
    for i in range(6 * 3):          # every frame stands on the frame's bottom row: one baseline
        f = sheet.crop(((i % 6) * fw, (i // 6) * fh, (i % 6 + 1) * fw, (i // 6 + 1) * fh))
        bb = pc.opaque_bbox(f)
        if bb:
            assert bb[3] == fh
    assert (out.parent / "hero.png").exists()


def test_make_sheet_scales_every_figure_by_one_factor():
    tall = strip(2, heights={0: 20, 1: 20}).convert("RGBA")
    short = strip(2, heights={0: 10, 1: 10}).convert("RGBA")
    sheet, data, _ = make_sheet.make_sheet([("i", tall, "idle"), ("w", short, "walk")], height=40)
    fw, fh = data["frame"]
    assert fh == 40
    walk = sheet.crop((0, fh, fw, 2 * fh))
    bb = pc.opaque_bbox(walk)
    assert bb[3] - bb[1] == 20, "a short figure must stay half as tall, not be stretched"


def test_make_sheet_refuses_a_spec_that_does_not_match_the_figures(tmp_path):
    src = tmp_path / "walk.png"
    strip(4).save(src)
    bad = subprocess.run([sys.executable, str(TOOLS / "make_sheet.py"), "--out", tmp_path / "x",
                          f"{src}=idle,walk:4"], capture_output=True, text=True)
    assert bad.returncode == 2 and "found 4 figures" in bad.stderr


# --- animate ----------------------------------------------------------------------------------------------

WALL, ROOF = (120, 100, 90), (150, 70, 50)
LAMP = [(255, 220, 130), (230, 170, 80), (170, 110, 60)]
WATER = [(70, 130, 200), (100, 160, 230), (150, 200, 250)]


def house():
    img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((2, 10, 21, 23), fill=WALL + (255,))
    d.rectangle((2, 6, 21, 9), fill=ROOF + (255,))
    d.rectangle((15, 3, 17, 5), fill=WALL + (255,))   # chimney
    d.rectangle((5, 13, 8, 16), fill=LAMP[0] + (255,))
    d.point((6, 14), fill=LAMP[1] + (255,))
    for x in range(2, 22):
        d.point((x, 22), fill=WATER[x % 3] + (255,))
    return img


def test_animate_changes_only_the_role_colours():
    img = house()
    roles = [("flicker", LAMP), ("cycle", WATER)]
    frames = animate.animate(img, roles, frames=6, seed=3)
    assert len(frames) == 6
    assert pc.pixels(frames[0]) == pc.pixels(img), "frame 0 is the picture as drawn"
    moving = set(LAMP) | set(WATER)
    still = [i for i, p in enumerate(pc.pixels(img)) if not (p[3] and p[:3] in moving)]
    for f in frames:
        assert alpha_mask(f) == alpha_mask(img), "the shape moved"
        fp = pc.pixels(f)
        assert all(fp[i] == pc.pixels(img)[i] for i in still), "a pixel outside the roles changed"
        assert colours(f) <= colours(img) | moving, "a frame made a new colour"
    assert len({tuple(pc.pixels(f)) for f in frames}) > 1, "nothing moved"
    assert pc.pixels(frames[3]) != pc.pixels(frames[0]), "the water cycle should have moved by frame 3"


def test_cycle_loops_and_glow_breathes():
    img = house()
    frames = animate.animate(img, [("cycle", WATER)], frames=6)
    assert pc.pixels(frames[3]) == pc.pixels(frames[0])
    glow = animate.animate(img, [("glow", LAMP)], frames=4)
    assert glow[2].getpixel((5, 13))[:3] == LAMP[2] and glow[0].getpixel((5, 13))[:3] == LAMP[0]


def test_smoke_rises_only_in_clear_sky_above_the_chimney():
    img = house()
    frames = animate.animate(img, [], frames=4, smoke=(16, 3))
    src = img.load()
    for f in frames:
        px = f.load()
        for y in range(img.height):
            for x in range(img.width):
                if px[x, y] != src[x, y]:
                    assert src[x, y][3] == 0 and y < 3 and 15 <= x <= 18


def test_animate_cli_writes_one_row_of_frames(tmp_path):
    src = tmp_path / "house.png"
    house().save(src)
    run("animate.py", src, tmp_path / "anim.png", "--frames", "6", "--role",
        "flicker:" + ",".join(pc.hex_colour(c) for c in LAMP), "--split")
    assert Image.open(tmp_path / "anim.png").size == (24 * 6, 24)
    assert (tmp_path / "anim-5.png").exists()


# --- process_kit ------------------------------------------------------------------------------------------

def test_process_kit_cuts_by_cell_at_planned_sizes_on_one_palette(tmp_path):
    cols, rows, side = 4, 3, 80
    sheet = Image.new("RGB", (cols * side, rows * side), GREEN)
    d = ImageDraw.Draw(sheet)
    for i in range(cols * rows):
        x, y = (i % cols) * side, (i // cols) * side
        d.rectangle((x + 10, y + 8, x + side - 1, y + side - 9), fill=PAL[i % len(PAL)])
        if i % cols < cols - 1:      # each prop touches its right-hand neighbour: found by shape they merge
            d.rectangle((x + side - 1, y + 40, x + side + 10, y + 42), fill=PAL[i % len(PAL)])
    ground = Image.new("RGB", (200, 200))
    ground.putdata([(60 + x // 4, 120, 60 + y // 4) for y in range(200) for x in range(200)])
    sheet.save(tmp_path / "props.png")
    ground.save(tmp_path / "ground.png")
    pc.save_palette(tmp_path / "pal.json", PAL + [(100, 120, 100), (90, 120, 80), (80, 120, 100)])
    props = [{"name": f"p{i}", "size": [16, 24]} if i % 2 else {"name": f"p{i}", "height": 12}
             for i in range(cols * rows)]
    plan = {"palette": "pal.json", "tile": 16, "sheets": [
        {"image": "props.png", "grid": "4x3", "props": props},
        {"image": "ground.png", "grid": "1x1", "ground": ["grass"]},
    ]}
    (tmp_path / "plan.json").write_text(json.dumps(plan))
    run("process_kit.py", tmp_path / "plan.json", "--out", tmp_path / "out")
    pal = set(PAL) | {(100, 120, 100), (90, 120, 80), (80, 120, 100)}
    for i in range(cols * rows):
        pic = Image.open(tmp_path / "out" / "sprites" / f"p{i}.png").convert("RGBA")
        if i % 2:
            assert pic.size == (16, 24)
            assert pc.opaque_bbox(pic)[3] == 24, "a sized prop stands on its bottom edge"
        else:
            assert pic.height == 12
        assert colours(pic) <= pal
    tile = Image.open(tmp_path / "out" / "tiles" / "grass.grid3x3.png").convert("RGBA")
    assert tile.size == (48, 48)
    assert colours(tile) <= pal and min(alpha_mask(tile)) == 255
    px = tile.load()

    def step(a, b):
        return sum(abs(u - v) for u, v in zip(a[:3], b[:3]))
    wrap = sum(step(px[0, y], px[47, y]) for y in range(48)) / 48
    worst_inner = max(sum(step(px[x, y], px[x + 1, y]) for y in range(48)) / 48 for x in range(47))
    assert wrap <= worst_inner, f"the ground does not wrap: the seam ({wrap:.1f}) is the worst edge"


def test_a_prop_fits_inside_its_planned_size_keeping_its_shape():
    cell = Image.new("RGB", (100, 100), GREEN)
    ImageDraw.Draw(cell).rectangle((20, 10, 59, 89), fill=PAL[1])     # 40 x 80: twice as tall as wide
    pic = process_kit.make_prop(cell.convert("RGBA"), GREEN, size=[32, 32], palette=PAL)
    assert pic.size == (32, 32)
    assert pc.opaque_bbox(pic) == (8, 0, 24, 32), "fitted by height, centred, standing on the bottom"


def test_kit_tools_answer_help():
    for tool in ("make_sheet.py", "animate.py", "process_kit.py"):
        assert "usage" in run(tool, "--help")
