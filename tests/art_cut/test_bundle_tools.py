"""The bundle tools from the Cottage art pass (2026-10-12): slice a #00FF00 grid, make a seamless tile, cut a
feathered way tile. Small synthetic pictures, so each tool's one promise is checked without any real art."""
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools" / "art"


def run(tool, *args):
    out = subprocess.run([sys.executable, str(TOOLS / tool), *map(str, args)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_slice_bundle_keys_every_backdrop_pixel_even_inside_the_subject(tmp_path):
    # a 2x1 sheet on #00FF00: a brown ring with green INSIDE it (the case corner flood-fill misses)
    sheet = Image.new("RGB", (400, 200), (0, 255, 0))
    d = ImageDraw.Draw(sheet)
    d.ellipse((40, 40, 160, 160), fill=(120, 80, 40))
    d.ellipse((80, 80, 120, 120), fill=(0, 255, 0))
    d.rectangle((250, 60, 350, 140), fill=(200, 160, 90))
    src = tmp_path / "sheet.png"
    sheet.save(src)
    run("slice_bundle.py", src, "--grid", "2x1", "--names=ring,box", "--out", tmp_path / "cut")
    ring = Image.open(tmp_path / "cut" / "ring.png").convert("RGBA")
    assert ring.size == (128, 128)
    cx, cy = 64, ring.getchannel("A").getbbox()[1] + (ring.getchannel("A").getbbox()[3] - ring.getchannel("A").getbbox()[1]) // 2
    assert ring.getpixel((cx, cy))[3] == 0, "the green inside the ring was not keyed"
    rgba = ring.tobytes()
    assert any(rgba[i + 3] == 255 and rgba[i + 1] < 200 for i in range(0, len(rgba), 4)), "the ring itself was lost"
    assert (tmp_path / "cut" / "box.png").exists()


def test_seamless_tile_wraps_without_a_seam(tmp_path):
    # a left-to-right gradient: as a raw tile its left and right edges are far apart
    g = Image.new("RGB", (256, 256))
    g.putdata([(x, 100, 255 - x) for y in range(256) for x in range(256)])
    src = tmp_path / "g.png"
    g.save(src)
    out = tmp_path / "t.png"
    run("seamless_tile.py", src, "--grid", "1x1", "--cell", "0", "--out", out, "--size", "96", "--inset", "0")
    t = Image.open(out).convert("RGB")
    left = [t.getpixel((0, y))[0] for y in range(96)]
    right = [t.getpixel((95, y))[0] for y in range(96)]
    wrap = sum(abs(a - b) for a, b in zip(left, right)) / 96
    step = sum(abs(t.getpixel((47, y))[0] - t.getpixel((48, y))[0]) for y in range(96)) / 96
    assert wrap <= step + 12, f"the wrap seam ({wrap:.1f}) is far larger than an interior step ({step:.1f})"


def test_way_tile_fades_its_edges_and_keeps_its_middle(tmp_path):
    src = tmp_path / "w.png"
    Image.new("RGB", (300, 300), (90, 70, 50)).save(src)
    out = tmp_path / "way.png"
    run("way_tile.py", src, "--grid", "1x1", "--cell", "0", "--out", out)
    w = Image.open(out).convert("RGBA")
    assert w.size == (96, 96)
    assert w.getpixel((0, 0))[3] < 40, "the corner should be nearly transparent"
    assert w.getpixel((48, 48))[3] == 255, "the middle should be opaque"
