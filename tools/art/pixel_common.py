"""Shared pieces of the pixel-art tools (pixelize, make_sheet, animate, process_kit).

Pixel art here means hard pixels: alpha is 0 or 255, and every colour comes from one palette. These helpers
read and write palettes, key a flat backdrop, sample block centres, remove lone specks and lock colours.
Needs Pillow only (`uv run --with pillow ...`).
"""
import json
import sys
from collections import Counter

from PIL import Image

OPAQUE = 128  # alpha at or above this is a pixel; below is backdrop


def fail(message):
    """A plain one-line problem, exit 2, with no traceback."""
    print(message, file=sys.stderr)
    raise SystemExit(2)


def open_rgba(path):
    try:
        return Image.open(path).convert("RGBA")
    except (OSError, ValueError) as exc:
        fail(f"cannot read {path}: {exc}")


def pixels(img):
    """Every pixel value, row by row (Pillow 12 renamed getdata)."""
    return list(getattr(img, "get_flattened_data", img.getdata)())


def parse_colour(text):
    """'#rrggbb' (or 'rrggbb') to (r, g, b)."""
    t = text.strip().lstrip("#")
    if len(t) != 6:
        raise ValueError(f"not a #rrggbb colour: {text!r}")
    return tuple(int(t[i:i + 2], 16) for i in (0, 2, 4))


def hex_colour(rgb):
    return "#%02x%02x%02x" % tuple(rgb[:3])


def load_palette(path):
    """A palette file: JSON `{"colors": ["#rrggbb", ...]}` or a JSON list, or one #rrggbb per line."""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as exc:
        fail(f"cannot read palette {path}: {exc}")
    try:
        if text.lstrip()[:1] in "[{":
            data = json.loads(text)
            entries = data.get("colors", data.get("colours", [])) if isinstance(data, dict) else data
        else:
            entries = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("//")]
        colours = list(dict.fromkeys(parse_colour(e) for e in entries))
    except ValueError as exc:
        fail(f"palette {path}: {exc}")
    if not colours:
        fail(f"palette {path} has no colours")
    return colours


def save_palette(path, colours):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"colors": [hex_colour(c) for c in colours]}, fh, indent=1)
        fh.write("\n")


def nearest(rgb, palette):
    r, g, b = rgb[:3]
    return min(palette, key=lambda c: (r - c[0]) ** 2 + (g - c[1]) ** 2 + (b - c[2]) ** 2)


def lock_palette(img, palette):
    """Snap every opaque pixel to its nearest palette colour; alpha becomes 0 or 255."""
    img = img.convert("RGBA")
    px = img.load()
    cache = {}
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            if a < OPAQUE:
                px[x, y] = (0, 0, 0, 0)
                continue
            if (r, g, b) not in cache:
                cache[(r, g, b)] = nearest((r, g, b), palette)
            px[x, y] = cache[(r, g, b)] + (255,)
    return img


def hard_alpha(img):
    """Alpha to 0 or 255, and a cleared pixel's colour to 0 so equal pictures compare equal."""
    img = img.convert("RGBA")
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 255) if a >= OPAQUE else (0, 0, 0, 0)
    return img


def close(c1, c2, tol):
    return max(abs(c1[0] - c2[0]), abs(c1[1] - c2[1]), abs(c1[2] - c2[2])) <= tol


def backdrop_colour(img, tol=24):
    """The flat backdrop's colour when the four corners agree and the picture has no alpha of its own."""
    w, h = img.size
    if img.getchannel("A").getextrema()[0] < OPAQUE:
        return None                      # already transparent somewhere: keep its own alpha
    corners = [img.getpixel(p)[:3] for p in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    if all(close(c, corners[0], tol) for c in corners):
        return Counter(corners).most_common(1)[0][0]
    return None


def key_out(img, colour, tol=48):
    """Every pixel within tol of the backdrop colour becomes transparent (inside the subject too)."""
    img = img.convert("RGBA")
    if colour is None:
        return img
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            if close(px[x, y], colour, tol):
                px[x, y] = (0, 0, 0, 0)
    return img


def parse_key(spec, img, tol=24):
    """--key: 'auto' (the corners' flat colour, if any), 'none', or a #rrggbb."""
    if spec == "none":
        return None
    if spec == "auto":
        return backdrop_colour(img, tol)
    return parse_colour(spec)


def sample(img, xs, ys):
    """A new picture whose pixel (i, j) is the source pixel (xs[i], ys[j]): no blending, no new colours."""
    src = img.load()
    out = Image.new("RGBA", (len(xs), len(ys)))
    dst = out.load()
    for j, sy in enumerate(ys):
        for i, sx in enumerate(xs):
            dst[i, j] = src[sx, sy]
    return out


def centres(src_len, out_len):
    """The source index at the middle of each of out_len equal blocks."""
    return [min(int((i + 0.5) * src_len / out_len), src_len - 1) for i in range(out_len)]


def shrink(img, w, h):
    """Downscale to exactly w x h by taking the middle pixel of each block."""
    return sample(img, centres(img.width, w), centres(img.height, h))


def opaque_bbox(img):
    return img.getchannel("A").point(lambda v: 255 if v >= OPAQUE else 0).getbbox()


N4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
N8 = N4 + ((1, 1), (1, -1), (-1, 1), (-1, -1))


def despeckle(img, shade_tol=40):
    """Remove isolated stray pixels, in one pass over a copy so the result does not depend on scan order.

    - a lone opaque pixel with no opaque neighbour (of 8) is cleared;
    - a pinhole, a clear pixel whose 4 neighbours are opaque, is filled with their commonest colour;
    - a stray shade, a pixel whose 8 neighbours are one colour within shade_tol of its own, takes that colour.
      A real detail such as a dark eye on skin is far from its neighbours and stays.
    """
    img = hard_alpha(img)
    src = img.copy().load()
    px = img.load()
    w, h = img.size

    def at(x, y):
        return src[x, y] if 0 <= x < w and 0 <= y < h else (0, 0, 0, 0)

    for y in range(h):
        for x in range(w):
            p = src[x, y]
            ring = [at(x + dx, y + dy) for dx, dy in N8]
            if p[3]:
                if not any(q[3] for q in ring):
                    px[x, y] = (0, 0, 0, 0)
                elif all(q == ring[0] for q in ring) and ring[0] != p and close(p, ring[0], shade_tol):
                    px[x, y] = ring[0]
            else:
                four = ring[:4]
                if all(q[3] for q in four):
                    px[x, y] = Counter(four).most_common(1)[0][0]
    return img


def components(img, min_alpha=OPAQUE):
    """Connected opaque regions (8-connected): a list of (pixel count, bbox, [(x, y), ...]), left to right."""
    w, h = img.size
    alpha = img.getchannel("A").load()
    seen = bytearray(w * h)
    found = []
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0 * w + x0] or alpha[x0, y0] < min_alpha:
                continue
            seen[y0 * w + x0] = 1
            stack, pts = [(x0, y0)], []
            while stack:
                x, y = stack.pop()
                pts.append((x, y))
                for dx, dy in N8:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx] and alpha[nx, ny] >= min_alpha:
                        seen[ny * w + nx] = 1
                        stack.append((nx, ny))
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            found.append((len(pts), (min(xs), min(ys), max(xs) + 1, max(ys) + 1), pts))
    found.sort(key=lambda c: c[1][0])
    return found


def parse_grid(spec):
    try:
        cols, rows = (int(v) for v in spec.lower().split("x"))
    except ValueError:
        fail(f"a grid is COLSxROWS like 4x3, got {spec!r}")
    if cols < 1 or rows < 1:
        fail(f"a grid needs at least one column and row, got {spec!r}")
    return cols, rows


def cell(sheet, cols, rows, index, inset=0.0):
    """Cell `index` (row by row) of a COLSxROWS sheet, cut on rounded edges, trimmed by `inset` of its size."""
    W, H = sheet.size
    c, r = index % cols, index // cols
    box = [c * W // cols, r * H // rows, (c + 1) * W // cols, (r + 1) * H // rows]
    dx, dy = round((box[2] - box[0]) * inset), round((box[3] - box[1]) * inset)
    return sheet.crop((box[0] + dx, box[1] + dy, box[2] - dx, box[3] - dy))
