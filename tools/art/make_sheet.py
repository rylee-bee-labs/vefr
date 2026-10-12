#!/usr/bin/env python3
"""Make one walk sheet and its `.sheet.json` from one-row strips of a character.

    make_sheet.py --out sprites/hero idle.png=idle walk.png=walk \\
        action.png=act,attack:3,up/idle,hurt [--height 48] [--fps 8] [--key auto]

Each strip is one row of poses on one ground line (draw it with an image model, then run pixelize.py on it so
it is real pixels). A strip argument is PATH=SPEC. SPEC lists where the strip's figures go, left to right:
`[dir/]state[:N]`, N figures (default 1; the last item takes the rest), dir `down` when left out. `-:N`
skips N figures. So `action.png=act,attack:3,up/idle,hurt` sends figure 1 to down/act, 2-4 to down/attack,
5 to up/idle (a back view from an action strip) and 6 to down/hurt. A direction left out is filled in by the
player (left/right mirror each other, up falls back to down).

Figures are cut by SHAPE, not by even slots: each connected opaque region is a figure, so a swung stick that
crosses into the next slot stays with the figure holding it, and a small loose piece (a spark, a dropped
hat) joins the nearest figure. Every figure stands on the bottom edge of its frame (one baseline), centred on
the middle of its lower half, so a stick swung out to one side does not shove the body sideways. `--height`
scales every figure by ONE factor (nearest neighbour), chosen so the tallest idle figure is that tall.

Writes OUT-sheet.png (one row per strip, frames numbered left to right, top to bottom), OUT.sheet.json in
the engine's walk-sheet shape (docs/guides/rulesets.md, "Walk sheets") and OUT.png, the down idle frame
as the still picture.

Needs Pillow:  uv run --with pillow tools/art/make_sheet.py --help
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image

import pixel_common as pc

DIRECTIONS = ("down", "up", "left", "right")
STATES = ("idle", "walk", "act", "attack", "hurt", "talk")
LIMITS = {"idle": (1, 16), "walk": (2, 16)}   # every other state: 1 to 16


def parse_spec(spec):
    """'act,attack:3,up/idle' -> [('down', 'act', 1), ('down', 'attack', 3), ('up', 'idle', None)]."""
    items = []
    parts = spec.split(",")
    for i, part in enumerate(parts):
        name, _, count = part.strip().partition(":")
        if count:
            try:
                n = int(count)
            except ValueError:
                pc.fail(f"{part!r}: the count after ':' must be a whole number")
            if n < 1:
                pc.fail(f"{part!r}: the count must be 1 or more")
        else:
            n = None if i == len(parts) - 1 else 1
        if name == "-":
            items.append((None, None, n))
            continue
        d, _, state = name.rpartition("/")
        d = d or "down"
        if d not in DIRECTIONS:
            pc.fail(f"{part!r}: direction must be one of {', '.join(DIRECTIONS)}")
        if state not in STATES:
            pc.fail(f"{part!r}: state must be one of {', '.join(STATES)}")
        items.append((d, state, n))
    return items


def cut_figures(strip, min_share=0.2):
    """The figures of a keyed strip, left to right, each a tight RGBA picture holding only its own pixels."""
    comps = pc.components(strip)
    if not comps:
        return []
    largest = max(c[0] for c in comps)
    big = [[c] for c in comps if c[0] >= min_share * largest]
    for c in comps:
        if c[0] >= min_share * largest:
            continue
        # a loose piece joins the figure it is horizontally nearest (0 when it overlaps the figure's span)
        def gap(group):
            left = min(g[1][0] for g in group)
            right = max(g[1][2] for g in group)
            return max(left - c[1][2], c[1][0] - right, 0)
        min(big, key=gap).append(c)
    src = strip.load()
    figures = []
    for group in big:
        pts = [p for g in group for p in g[2]]
        x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
        x1, y1 = max(p[0] for p in pts) + 1, max(p[1] for p in pts) + 1
        fig = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
        dst = fig.load()
        for x, y in pts:
            dst[x - x0, y - y0] = src[x, y]
        figures.append(fig)
    return figures


def anchor_x(fig):
    """The median x of the opaque pixels in the figure's lower half: where it stands."""
    a = fig.getchannel("A").load()
    xs = sorted(x for y in range(fig.height // 2, fig.height) for x in range(fig.width) if a[x, y] >= pc.OPAQUE)
    return xs[len(xs) // 2] + 0.5 if xs else fig.width / 2


def route(figures, items, label):
    """Pair each figure with its (dir, state); None for skipped ones."""
    named = sum(n for _, _, n in items if n)
    if items[-1][2] is None:
        items[-1] = items[-1][:2] + (max(len(figures) - named, 0),)
    want = sum(n for _, _, n in items)
    if want != len(figures):
        pc.fail(f"{label}: found {len(figures)} figures, the spec names {want}; check for figures that touch "
                f"(they merge) or a loose speck")
    out = []
    for d, state, n in items:
        out += [(d, state)] * n
    return out


def make_sheet(strips, height=None, fps=8, frame=None, key="auto", margin=0):
    """strips: [(label, RGBA picture, spec)]. Returns (sheet picture, sheet dict without 'image', still)."""
    rows = []
    for label, img, spec in strips:
        keyed = pc.hard_alpha(pc.key_out(img, pc.parse_key(key, img)))
        figures = cut_figures(keyed)
        if not figures:
            pc.fail(f"{label}: no figures found (is the backdrop keyed? try --key)")
        rows.append([(f, t) for f, t in zip(figures, route(figures, parse_spec(spec), label)) if t[0]])

    if height:
        idle = [f.height for row in rows for f, t in row if t[1] == "idle"]
        ref = max(idle or [f.height for row in rows for f, _ in row])
        k = height / ref
        rows = [[(f.resize((max(1, round(f.width * k)), max(1, round(f.height * k))), Image.NEAREST), t)
                 for f, t in row] for row in rows]

    placed = [[(f, anchor_x(f), t) for f, t in row] for row in rows]
    fw = max(8, 2 * math.ceil(max(max(ax, f.width - ax) for row in placed for f, ax, _ in row)))
    fh = max(8, max(f.height for row in placed for f, _, _ in row) + margin)
    if frame:
        if frame[0] < fw or frame[1] < fh:
            pc.fail(f"--frame {frame[0]}x{frame[1]} is too small: the figures need {fw}x{fh}")
        fw, fh = frame
    cols = max(len(row) for row in placed)
    sheet = Image.new("RGBA", (cols * fw, len(placed) * fh), (0, 0, 0, 0))
    directions = {}
    for r, row in enumerate(placed):
        for c, (f, ax, (d, state)) in enumerate(row):
            sheet.alpha_composite(f, (c * fw + round(fw / 2 - ax), r * fh + fh - margin - f.height))
            directions.setdefault(d, {}).setdefault(state, []).append(r * cols + c)

    if "down" not in directions:
        pc.fail("no figure goes to the down direction; the engine needs 'down'")
    out = {}
    for d in DIRECTIONS:
        if d not in directions:
            continue
        states = directions[d]
        if "idle" not in states:
            first = next(iter(states.values()))[0]
            print(f"note: {d} has no idle; using frame {first}")
            states["idle"] = [first]
        for state, frames in states.items():
            lo, hi = LIMITS.get(state, (1, 16))
            if not lo <= len(frames) <= hi:
                pc.fail(f"{d}/{state} has {len(frames)} frames; the engine takes {lo} to {hi}")
        out[d] = {s: states[s] for s in STATES if s in states}
    first = out["down"]["idle"][0]
    still = sheet.crop(((first % cols) * fw, (first // cols) * fh, (first % cols + 1) * fw, (first // cols + 1) * fh))
    return sheet, {"frame": [fw, fh], "fps": fps, "directions": out}, still


def main(argv=None):
    ap = argparse.ArgumentParser(description="One-row character strips to a walk sheet plus .sheet.json.")
    ap.add_argument("strips", nargs="+", metavar="PATH=SPEC",
                    help="a strip and where its figures go, e.g. walk.png=walk or act.png=act,attack:3,up/idle")
    ap.add_argument("--out", required=True, help="OUT path without suffix, e.g. sprites/hero")
    ap.add_argument("--height", type=int, help="scale so the tallest idle figure is this tall (one factor for all)")
    ap.add_argument("--fps", type=int, default=8, help="frames per second, 1 to 30 (default 8)")
    ap.add_argument("--frame", help="WxH of one frame; default the smallest that holds every figure")
    ap.add_argument("--margin", type=int, default=0, help="pixels left under the feet (default 0)")
    ap.add_argument("--key", default="auto", help="backdrop: auto (default), none, or #rrggbb")
    a = ap.parse_args(argv)
    if not 1 <= a.fps <= 30:
        pc.fail("--fps must be 1 to 30")
    frame = pc.parse_grid(a.frame) if a.frame else None
    strips = []
    for arg in a.strips:
        path, sep, spec = arg.rpartition("=")
        if not sep or not path or not spec:
            pc.fail(f"{arg!r}: a strip is PATH=SPEC, e.g. walk.png=walk")
        strips.append((path, pc.open_rgba(path), spec))
    sheet, data, still = make_sheet(strips, a.height, a.fps, frame, a.key, a.margin)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    image = out.with_name(out.name + "-sheet.png")
    sheet.save(image)
    still.save(out.with_name(out.name + ".png"))
    data = {"image": image.name, **data}
    out.with_name(out.name + ".sheet.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    fw, fh = data["frame"]
    print(f"wrote {image.name} ({sheet.width}x{sheet.height}, frames {fw}x{fh}), {out.name}.sheet.json, {out.name}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
