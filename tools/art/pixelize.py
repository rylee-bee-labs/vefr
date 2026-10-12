#!/usr/bin/env python3
"""Turn an image model's painted "pixel art" into real pixels, and build a master palette.

An image model paints pixel art as blocks of about the same size that wander off a true grid: the block is
8.3 px here, 7.6 px there, and the edges blur. This finds the block size and offset on each axis, takes the
middle pixel of each block (never an average, so no new colours), keys the flat backdrop to transparent,
removes lone specks and locks every colour to a palette.

    pixelize.py image IN.png OUT.png [--palette PAL.json] [--key auto|none|#rrggbb] [--block S] [--offset X,Y]
    pixelize.py palette OUT.json APPROVED.png ... [--colors 32]

`image`: the grid is found from the picture's edges, one axis at a time. Each block size from 4 to 64 px is
scored by the share of edge strength within a pixel of its lines, less the share a grid that size would catch
by chance; the best is then fitted to the edges by least squares. Walking the grid, each line moves to the
strongest edge within a quarter block of where it should be, so a grid that wanders is followed. `--block`
(and `--offset`) skip the search when you know the answer.
`--key auto` keys the corners' colour when all four corners share it (a #00FF00 sheet, a flat grey) and keeps
a picture's own alpha when it has one. `--trim` crops to the subject.

`palette`: the colours of a set of approved pictures (opaque pixels only) become one master palette. When
they hold more than `--colors`, they are grouped (median cut) and each group keeps its commonest REAL colour,
so the palette holds only colours an approved picture already uses. Written as {"colors": ["#rrggbb", ...]},
darkest first. Every pixel-art tool here reads that file with --palette.

Needs Pillow:  uv run --with pillow tools/art/pixelize.py --help
"""
import argparse
from collections import Counter

from PIL import Image, ImageChops

import pixel_common as pc


def edge_profile(img, axis):
    """For each position, the share of lines that change colour there: prof[x] is the edge between x-1 and x."""
    img = img.convert("RGBA")
    shifted = ImageChops.offset(img, 1, 0) if axis == "x" else ImageChops.offset(img, 0, 1)
    bands = ImageChops.difference(img, shifted).split()
    diff = bands[0]
    for b in bands[1:]:
        diff = ImageChops.lighter(diff, b)
    mask = diff.point(lambda v: 255 if v > 24 else 0)
    n = img.width if axis == "x" else img.height
    line = mask.resize((n, 1) if axis == "x" else (1, n), Image.BOX)
    prof = [v / 255 for v in pc.pixels(line)]
    prof[0] = 0.0                       # the wrap-around comparison, not an edge
    return prof


def _score(prof, total, s, o):
    """Edge share near the lines of the grid (s, o), less the share a grid that size catches by chance."""
    n = len(prof)
    hit, k = 0.0, 0
    while True:
        p = round(o + k * s)
        if p > n - 1:
            break
        hit += sum(prof[max(0, p - 1):p + 2])   # a wandering line may sit one pixel off
        k += 1
    return hit / total - 3 / s


def find_grid(prof, lo=4.0, hi=64.0):
    """(block size, offset) on one axis, or None when the axis has no edges."""
    total = sum(prof)
    if total == 0:
        return None
    hi = min(hi, len(prof) / 3)

    def best(sizes, offsets_for):
        return max(((_score(prof, total, s, o), s, o) for s in sizes for o in offsets_for(s)))

    whole = lambda s: range(int(s) + 1)  # noqa: E731 - integer offsets are close enough before refining
    coarse = best([lo + i * 0.25 for i in range(int((hi - lo) / 0.25) + 1)], whole)
    fine = best([coarse[1] + i * 0.05 for i in range(-6, 7) if coarse[1] + i * 0.05 >= lo],
                lambda s: [i * 0.5 for i in range(int(2 * s) + 1)])
    return fit_lines(prof, fine[1], fine[2])


def fit_lines(prof, s, o, rounds=3):
    """Refine (s, o) by a weighted straight-line fit of the edges to their nearest grid line numbers.

    The search scores whole grids, so it can settle a little off when the blocks wander; the fit moves the
    grid to run through the edges it should, an edge far from every line (texture) left out."""
    for _ in range(rounds):
        pts = []
        for x, w in enumerate(prof):
            k = round((x - o) / s)
            if w > 0 and abs(x - (o + k * s)) <= s / 3:
                pts.append((k, x, w))
        total = sum(w for _, _, w in pts)
        if len(pts) < 3 or total == 0:
            break
        mk = sum(k * w for k, _, w in pts) / total
        mx = sum(x * w for _, x, w in pts) / total
        var = sum(w * (k - mk) ** 2 for k, _, w in pts)
        if var == 0:
            break
        s = sum(w * (k - mk) * (x - mx) for k, x, w in pts) / var
        o = mx - s * mk
    return s, o % s


def block_centres(prof, s, o):
    """The middle of each block. The grid is walked line by line from the offset, both ways; each line moves
    to the strongest edge within a quarter block of where it should be, and the next line is measured from
    there, so a grid that wanders is followed instead of slowly lost."""
    n = len(prof)
    r = max(1, int(s / 4))

    def snap(pos):
        p = min(max(round(pos), 0), n - 1)
        q = max(range(max(0, p - r), min(n, p + r + 1)), key=lambda i: (prof[i], -abs(i - p)))
        return q if prof[q] > prof[p] else pos

    lines = []
    for step in (s, -s):
        pos = o if step > 0 else o - s
        while 0 <= pos <= n:
            pos = snap(pos)
            lines.append(round(pos))
            pos += step
    lines = sorted(set(lines))
    if not lines or lines[0] >= s / 2:
        lines.insert(0, 0)              # a part block at the start, if it is at least half a block
    if n - lines[-1] >= s / 2:
        lines.append(n)
    return [(a + b) // 2 for a, b in zip(lines, lines[1:]) if b > a]


def pixelize(img, palette=None, key="auto", block=None, offset=None, specks=True, trim=False):
    """The whole pass on one RGBA picture. Returns (native picture, {axis: (block, offset)})."""
    img = img.convert("RGBA")
    backdrop = pc.parse_key(key, img)
    found, profs = {}, {}
    for i, axis in enumerate("xy"):
        prof = edge_profile(img, axis)
        if block:
            s = block
            total = sum(prof) or 1
            o = offset[i] if offset else max(
                (_score(prof, total, s, j * 0.5), j * 0.5) for j in range(int(2 * s) + 1))[1]
            grid = (s, o)
        else:
            grid = find_grid(prof)      # None when flat along this axis: the other axis's block is used
        found[axis] = grid
        profs[axis] = prof
    if found["x"] is None and found["y"] is None:
        pc.fail("no blocks found: the picture is one flat colour")
    found["x"] = found["x"] or found["y"]
    found["y"] = found["y"] or found["x"]
    xs = block_centres(profs["x"], *found["x"])
    ys = block_centres(profs["y"], *found["y"])
    out = pc.sample(img, xs, ys)
    out = pc.hard_alpha(pc.key_out(out, backdrop))
    if specks:
        out = pc.despeckle(out)
    if palette:
        out = pc.lock_palette(out, palette)
    if trim:
        bb = pc.opaque_bbox(out)
        if bb:
            out = out.crop(bb)
    return out, found


def build_palette(images, colours=32):
    """One palette from the opaque pixels of approved pictures, holding only colours they already use."""
    counts = Counter()
    for img in images:
        counts.update(p[:3] for p in pc.pixels(img.convert("RGBA")) if p[3] >= pc.OPAQUE)
    if not counts:
        pc.fail("the approved pictures have no opaque pixels")
    if len(counts) <= colours:
        chosen = list(counts)
    else:
        uniq = list(counts)
        # weight by count, capped so one huge flat area does not take every group
        flat = [c for c in uniq for _ in range(min(counts[c], 64))]
        strip = Image.new("RGB", (len(flat), 1))
        strip.putdata(flat)
        groups = pc.pixels(strip.quantize(colors=colours, method=Image.Quantize.MEDIANCUT))
        best = {}
        for c, g in zip(flat, groups):
            if g not in best or counts[c] > counts[best[g]]:
                best[g] = c
        chosen = list(best.values())
    return sorted(set(chosen), key=lambda c: (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2], c))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Painted pixel art to real pixels; or build a master palette.")
    sub = ap.add_subparsers(dest="mode", required=True)
    im = sub.add_parser("image", help="one painted picture to native pixels")
    im.add_argument("input")
    im.add_argument("output")
    im.add_argument("--palette", help="palette file to lock colours to (see the `palette` mode)")
    im.add_argument("--key", default="auto", help="backdrop: auto (default), none, or #rrggbb")
    im.add_argument("--block", type=float, help="block size in source pixels; skips the search")
    im.add_argument("--offset", help="X,Y of the first grid line, with --block")
    im.add_argument("--keep-specks", action="store_true", help="skip the despeckle step")
    im.add_argument("--trim", action="store_true", help="crop to the subject")
    pa = sub.add_parser("palette", help="a master palette from approved pictures")
    pa.add_argument("output", help="palette .json to write")
    pa.add_argument("images", nargs="+")
    pa.add_argument("--colors", type=int, default=32, help="most colours to keep (default 32)")
    a = ap.parse_args(argv)

    if a.mode == "palette":
        colours = build_palette([pc.open_rgba(p) for p in a.images], a.colors)
        pc.save_palette(a.output, colours)
        print(f"wrote {a.output}: {len(colours)} colours from {len(a.images)} pictures")
        return 0

    offset = None
    if a.offset:
        if not a.block:
            pc.fail("--offset needs --block")
        try:
            offset = tuple(float(v) for v in a.offset.split(","))
            assert len(offset) == 2
        except (ValueError, AssertionError):
            pc.fail(f"--offset is X,Y, got {a.offset!r}")
    if a.key not in ("auto", "none"):
        try:
            pc.parse_colour(a.key)
        except ValueError as exc:
            pc.fail(str(exc))
    palette = pc.load_palette(a.palette) if a.palette else None
    out, grid = pixelize(pc.open_rgba(a.input), palette, a.key, a.block, offset, not a.keep_specks, a.trim)
    out.save(a.output)
    (sx, ox), (sy, oy) = grid["x"], grid["y"]
    print(f"wrote {a.output}: {out.width}x{out.height} px (block {sx:.2f} x {sy:.2f}, offset {ox:g},{oy:g})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
