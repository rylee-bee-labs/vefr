#!/usr/bin/env python3
"""Cut a painted 'way through' (door, stair, trapdoor) out of a bundled sheet as a 96px tile whose edges feather
into transparency, so it sits on the real floor beneath instead of stamping its own square of floor on it.

    python3 tools/art/way_tile.py SHEET.png --grid 3x4 --cell 9 --out tiles/way-stairs-down.webp [--feather 0.18]
"""
import argparse
from pathlib import Path

from PIL import Image, ImageFilter


def feathered(im, feather):
    w, h = im.size
    mask = Image.new("L", (w, h), 0)
    px = mask.load()
    f = max(1, int(min(w, h) * feather))
    for y in range(h):
        for x in range(w):
            d = min(x, y, w - 1 - x, h - 1 - y)
            px[x, y] = 255 if d >= f else int(255 * (d / f) ** 1.6)
    out = im.convert("RGBA")
    out.putalpha(mask.filter(ImageFilter.GaussianBlur(1)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--grid", required=True)
    ap.add_argument("--cell", type=int, required=True)
    ap.add_argument("--inset", type=float, default=0.03)
    ap.add_argument("--feather", type=float, default=0.18)
    ap.add_argument("--size", type=int, default=96)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cols, rows = (int(v) for v in a.grid.lower().split("x"))
    sheet = Image.open(a.sheet).convert("RGB")
    W, H = sheet.size
    c, r = a.cell % cols, a.cell // cols
    x0, y0, x1, y1 = c * W // cols, r * H // rows, (c + 1) * W // cols, (r + 1) * H // rows
    side = min(x1 - x0, y1 - y0)
    pad = round(side * a.inset)
    cell = sheet.crop((x0 + pad, y0 + pad, x0 + side - pad, y0 + side - pad)).resize((a.size, a.size), Image.LANCZOS)
    tile = feathered(cell, a.feather)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tile.save(out, quality=90, method=6) if out.suffix == ".webp" else tile.save(out)
    print(f"{out} {a.size}x{a.size}")


if __name__ == "__main__":
    main()
