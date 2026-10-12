#!/usr/bin/env python3
"""Turn a kit's bundled sheets into game art: props at their planned native sizes, and seamless 3x3 ground
grids, every picture locked to one palette.

    process_kit.py PLAN.json --out STAGING/ [--palette PAL.json]

A kit is a place's set drawn in a few bundled image calls (a grid of subjects on flat #00FF00, see
making-art.md "Kits"). The plan names each cell and the size it is planned at in the game:

    {
      "palette": "palette.json",
      "tile": 32,
      "sheets": [
        {"image": "town-props.png", "grid": "4x3",
         "props": [{"name": "lamp", "size": [12, 32]}, {"name": "barrel", "height": 20}, null, ...]},
        {"image": "town-ground.png", "grid": "2x2", "inset": 0.04,
         "ground": ["grass", "cobbles", "dirt", null]}
      ]
    }

Paths are relative to the plan file. `props` and `ground` list the sheet's cells row by row; `null` (or
"-") skips a cell. A prop's `size` [w, h] is its picture: the subject is fitted inside it, standing on the
bottom edge, centred. A prop with only `height` gets the width its shape needs. Each ground cell becomes ONE
picture of `repeat` x `repeat` tiles (default 3, set per sheet), `tile` px each, made to wrap without a seam,
written as NAME.grid3x3.png: the player draws one cell of it per tile, so the floor repeats only every three tiles.
`key` (default "auto": the sheet's corner colour) and `inset` (the share of each cell trimmed off its
edges, default 0 for props and 0.04 for ground, which drops the lines a grid prompt draws) may be set per
sheet. A `--palette` on the command line wins over the plan's.

Cells are cut BY CELL, never by shape: twelve props in a 4x3 grid merge into nine when found by shape,
because a lamp's glow or a fence's end touches its neighbour.

Shrinking takes the middle pixel of each block, so it makes no new colours; the palette lock and despeckle
from pixelize.py finish each picture. Writes OUT/sprites/NAME.png and OUT/tiles/NAME.grid3x3.png, the
places a pack keeps them.

Needs Pillow:  uv run --with pillow tools/art/process_kit.py --help
"""
import argparse
import json
from pathlib import Path

from PIL import Image

import pixel_common as pc
from seamless_tile import seamless


def make_prop(cell_img, backdrop, size=None, height=None, palette=None):
    """One prop: key the cell, crop to the subject, shrink to its planned size, clean and lock."""
    keyed = pc.hard_alpha(pc.key_out(cell_img, backdrop))
    bb = pc.opaque_bbox(keyed)
    if not bb:
        return None
    subject = keyed.crop(bb)
    if size:
        k = min(size[0] / subject.width, size[1] / subject.height)
    else:
        k = height / subject.height
    w, h = max(1, round(subject.width * k)), max(1, round(subject.height * k))
    small = pc.despeckle(pc.shrink(subject, w, h))
    if palette:
        small = pc.lock_palette(small, palette)
    if not size:
        return small
    canvas = Image.new("RGBA", tuple(size), (0, 0, 0, 0))
    canvas.alpha_composite(small, ((size[0] - w) // 2, size[1] - h))
    return canvas


def make_ground(cell_img, tile=32, grid=3, palette=None):
    """One seamless ground picture of grid x grid tiles: blend to wrap, shrink by block middles, lock."""
    side = min(cell_img.size)
    square = cell_img.convert("RGB").crop((0, 0, side, side))
    wrapped = seamless(square).convert("RGBA")
    small = pc.shrink(wrapped, tile * grid, tile * grid)
    return pc.lock_palette(small, palette) if palette else small


def _size(entry, label):
    size, height = entry.get("size"), entry.get("height")
    if size is not None:
        if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and v > 0 for v in size)):
            pc.fail(f"{label}: 'size' must be [width, height] in whole pixels")
        return size, None
    if not (isinstance(height, int) and height > 0):
        pc.fail(f"{label}: give 'size' [w, h] or 'height'")
    return None, height


def process(plan_path, out_dir, palette=None):
    """Run a plan. Returns the list of files written."""
    plan_path = Path(plan_path)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        pc.fail(f"cannot read plan {plan_path}: {exc}")
    base = plan_path.parent
    if palette is None and plan.get("palette"):
        palette = pc.load_palette(base / plan["palette"])
    tile = plan.get("tile", 32)
    out_dir = Path(out_dir)
    written = []
    for s, sheet in enumerate(plan.get("sheets", [])):
        label = f"sheet {s + 1} ({sheet.get('image')})"
        img = pc.open_rgba(base / sheet["image"])
        cols, rows = pc.parse_grid(sheet.get("grid", "1x1"))
        props, ground = sheet.get("props"), sheet.get("ground")
        if (props is None) == (ground is None):
            pc.fail(f"{label}: give 'props' or 'ground' (one list per sheet)")
        entries = props if props is not None else ground
        if len(entries) != cols * rows:
            pc.fail(f"{label}: {len(entries)} entries for a {cols}x{rows} grid")
        for i, entry in enumerate(entries):
            if entry in (None, "-"):
                continue
            if props is not None:
                if not isinstance(entry, dict) or not entry.get("name"):
                    pc.fail(f"{label} cell {i}: a prop is {{\"name\": ..., \"size\": [w, h]}} or with \"height\"")
                size, height = _size(entry, f"{label} {entry['name']}")
                piece = pc.cell(img, cols, rows, i, sheet.get("inset", 0.0))
                backdrop = pc.parse_key(sheet.get("key", "auto"), piece)
                pic = make_prop(piece, backdrop, size, height, palette)
                if pic is None:
                    pc.fail(f"{label} cell {i} ({entry['name']}) is empty after keying")
                path = out_dir / "sprites" / f"{entry['name']}.png"
            else:
                grid = sheet.get("repeat", 3)
                pic = make_ground(pc.cell(img, cols, rows, i, sheet.get("inset", 0.04)), tile, grid, palette)
                path = out_dir / "tiles" / f"{entry}.grid{grid}x{grid}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            pic.save(path)
            written.append(path)
            print(f"{path}  {pic.width}x{pic.height}")
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description="A kit's bundled sheets to props and seamless ground, on one palette.")
    ap.add_argument("plan", help="the kit plan .json (see this file's top comment)")
    ap.add_argument("--out", required=True, help="folder to write sprites/ and tiles/ into")
    ap.add_argument("--palette", help="palette file; wins over the plan's")
    a = ap.parse_args(argv)
    written = process(a.plan, a.out, pc.load_palette(a.palette) if a.palette else None)
    print(f"wrote {len(written)} pictures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
