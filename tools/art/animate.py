#!/usr/bin/env python3
"""Animate a pixel-art picture the Game Boy Advance way: by changing colours, never by repainting.

    animate.py IN.png OUT.png --frames 8 --role flicker:#ffe08a,#f0b050,#b07830 \\
        [--role cycle:#5aa0d8,#7cc0f0,#a8dcff] [--smoke X,Y] [--split]

Every frame is the same picture with a few colours swapped, so nothing drifts, wobbles or changes shape
between frames: the alpha mask and every pixel outside the roles are identical in each frame. A role is
KIND:COLOURS, the colours as they appear in the picture, in order:

  cycle    each colour steps one place along the list per frame and wraps: water shimmer, a sliding
           highlight. Use a frame count that is a multiple of the list length so the loop is seamless.
  glow     the colours breathe together: up to len-1 steps along the list and back over the loop. List them
           from the colour drawn outward (coals: hot, warm, dull).
  flicker  like glow but on an uneven pattern, mostly lit, now and then one or two steps dimmer: lamps, lit
           windows. List from the lit colour to the dim one. `--seed` picks the pattern.

Keep a role to the light itself: a rust roof close in colour to a lamp would shimmer with it, so name the
lamp's exact colours (they are exact after pixelize.py --palette). Frame 0 is always the picture as drawn.

`--smoke X,Y` adds a small chimney smoke: a few puffs rising from just above pixel (X, Y), drawn only where
the picture is clear. It is the one thing that changes shape, so leave room above the chimney.

Writes OUT.png, the frames left to right in one row (each the input's size); `--split` also writes
OUT-0.png, OUT-1.png, ...

Needs Pillow:  uv run --with pillow tools/art/animate.py --help
"""
import argparse
import random
from pathlib import Path

from PIL import Image

import pixel_common as pc

KINDS = ("cycle", "glow", "flicker")
SMOKE_HEIGHT = 8   # pixels a puff rises before it is gone


def shift(kind, n, t, frames, seed=0):
    """How many places along a role's list its colours move at frame t (cycle wraps; the others clamp)."""
    if kind == "cycle":
        return t
    if kind == "glow":
        return round((n - 1) * (1 - abs(2 * t / frames - 1)))
    rnd = random.Random(seed)
    pattern = [0] + [rnd.choice((0, 0, 0, 1, 1, 2)) for _ in range(frames - 1)]
    return min(pattern[t], n - 1)


def recolour_table(roles, t, frames, seed=0):
    """{colour as drawn: colour in frame t} for every role colour."""
    table = {}
    for kind, colours in roles:
        n = len(colours)
        k = shift(kind, n, t, frames, seed)
        for i, c in enumerate(colours):
            table[c] = colours[(i + k) % n] if kind == "cycle" else colours[min(i + k, n - 1)]
    return table


def smoke_pixels(origin, t, frames, height=SMOKE_HEIGHT, puffs=3):
    """(x, y, step) of each smoke pixel in frame t; step 0 is fresh smoke, height-1 nearly gone."""
    x0, y0 = origin
    out = []
    for k in range(puffs):
        rise = (t * height // frames + k * height // puffs) % height
        x = x0 + (1 if (rise // 3) % 2 else 0)
        y = y0 - 1 - rise
        out.append((x, y, rise))
        if rise < height // 2:           # young puffs are two pixels wide
            out.append((x + 1, y, rise))
    return out


def animate(img, roles, frames=8, smoke=None, smoke_colours=((200, 200, 200), (160, 160, 168)), seed=0):
    """A list of `frames` RGBA pictures."""
    img = pc.hard_alpha(img)
    out = []
    for t in range(frames):
        table = recolour_table(roles, t, frames, seed)
        f = img.copy()
        px = f.load()
        for y in range(f.height):
            for x in range(f.width):
                r, g, b, a = px[x, y]
                if a and (r, g, b) in table:
                    px[x, y] = table[(r, g, b)] + (255,)
        if smoke:
            src = img.load()
            for x, y, rise in smoke_pixels(smoke, t, frames):
                if 0 <= x < f.width and 0 <= y < f.height and not src[x, y][3]:
                    age = min(rise * len(smoke_colours) // SMOKE_HEIGHT, len(smoke_colours) - 1)
                    px[x, y] = smoke_colours[age] + (255,)
        out.append(f)
    return out


def parse_role(spec):
    kind, _, colours = spec.partition(":")
    if kind not in KINDS:
        pc.fail(f"{spec!r}: a role is KIND:#c1,#c2,... with KIND one of {', '.join(KINDS)}")
    try:
        cs = [pc.parse_colour(c) for c in colours.split(",")]
    except ValueError as exc:
        pc.fail(f"{spec!r}: {exc}")
    if len(cs) < 2:
        pc.fail(f"{spec!r}: a role needs at least two colours to move between")
    return kind, cs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Animate a pixel-art picture by recolouring only.")
    ap.add_argument("input")
    ap.add_argument("output", help="the frames in one row, .png")
    ap.add_argument("--frames", type=int, default=8, help="how many frames (default 8)")
    ap.add_argument("--role", action="append", default=[], metavar="KIND:#c1,#c2,...",
                    help="cycle, glow or flicker over these colours; repeat for more roles")
    ap.add_argument("--smoke", help="X,Y of the chimney top: small rising smoke above it")
    ap.add_argument("--smoke-colours", default="#c8c8c8,#a0a0a8", help="smoke colours, fresh to old")
    ap.add_argument("--seed", type=int, default=0, help="the flicker pattern (default 0)")
    ap.add_argument("--split", action="store_true", help="also write each frame as OUT-N.png")
    a = ap.parse_args(argv)
    if a.frames < 2:
        pc.fail("--frames must be 2 or more")
    if not a.role and not a.smoke:
        pc.fail("give at least one --role or --smoke; with neither, nothing would move")
    img = pc.open_rgba(a.input)
    roles = [parse_role(r) for r in a.role]
    drawn = {p[:3] for p in pc.pixels(pc.hard_alpha(img)) if p[3]}
    seen = set()
    for kind, colours in roles:
        missing = [pc.hex_colour(c) for c in colours if c not in drawn]
        if len(missing) == len(colours):
            pc.fail(f"none of the {kind} colours is in the picture: {', '.join(missing)}")
        if seen & set(colours):
            pc.fail(f"a colour is in two roles: {', '.join(pc.hex_colour(c) for c in seen & set(colours))}")
        seen |= set(colours)
    smoke = None
    if a.smoke:
        try:
            smoke = tuple(int(v) for v in a.smoke.split(","))
            assert len(smoke) == 2
        except (ValueError, AssertionError):
            pc.fail(f"--smoke is X,Y, got {a.smoke!r}")
    try:
        smoke_colours = tuple(pc.parse_colour(c) for c in a.smoke_colours.split(","))
    except ValueError as exc:
        pc.fail(str(exc))
    frames = animate(img, roles, a.frames, smoke, smoke_colours, a.seed)
    strip = Image.new("RGBA", (img.width * a.frames, img.height), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f, (i * img.width, 0))
    out = Path(a.output)
    strip.save(out)
    if a.split:
        for i, f in enumerate(frames):
            f.save(out.with_name(f"{out.stem}-{i}{out.suffix}"))
    print(f"wrote {out} ({a.frames} frames of {img.width}x{img.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
