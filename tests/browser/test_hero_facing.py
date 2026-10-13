"""A mirrored side of a walk sheet is DRAWN mirrored, not just flagged so.

A sheet with no `left` row faces left by drawing its `right` frames
flipped. The player once flipped them with a negative drawImage width,
which a real canvas normalises away: VEFR_HERO_FRAME said `mirrored: true`
while the picture on screen still faced right, so the hero never looked
left. This reads the canvas pixels instead of the flag.

Every frame of the fixture sheet is red on its left half and blue on its
right, so the hero's red pixels sit left of her blue ones unless the
frame is flipped.
"""

import json
import struct
import zlib

import play_kit

RED = (255, 0, 0)
BLUE = (0, 0, 255)


def png(w, h, pixel):
    rows = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(w)) for y in range(h))
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


SHEET = {"image": "hero-sheet.png", "frame": [32, 32], "fps": 8,
         "directions": {"down": {"idle": [0], "walk": [1, 2, 3, 4]},
                        "right": {"idle": [10], "walk": [11, 12, 13, 14]},
                        "up": {"idle": [15], "walk": [16, 17, 18, 19]}}}   # left is the mirror of right


def woven(tmp_path):
    pack_dir = play_kit.pack(
        tmp_path, "lock", {"world.json": {"player": {"sprites": {"hero": "sprites/hero.png"}}}})
    sp = pack_dir / "sprites"
    sp.mkdir(exist_ok=True)
    (sp / "hero.png").write_bytes(png(1, 1, lambda x, y: RED))
    (sp / "hero.sheet.json").write_text(json.dumps(SHEET), encoding="utf-8")
    (sp / "hero-sheet.png").write_bytes(png(160, 128, lambda x, y: RED if x % 32 < 16 else BLUE))
    return play_kit.weave(pack_dir, tmp_path)


# Mean x of the exact red and exact blue pixels on the world canvas.
SIDES = """() => {
  const c = document.getElementById('town-canvas');
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let rx = 0, rn = 0, bx = 0, bn = 0;
  for (let i = 0; i < d.length; i += 4) {
    const x = (i / 4) % c.width;
    if (d[i] === 255 && d[i + 1] === 0 && d[i + 2] === 0) { rx += x; rn++; }
    else if (d[i] === 0 && d[i + 1] === 0 && d[i + 2] === 255) { bx += x; bn++; }
  }
  return { red: rn ? rx / rn : null, blue: bn ? bx / bn : null, rn, bn, frame: window.VEFR_HERO_FRAME };
}"""


def face(page, key):
    page.keyboard.press(key)
    page.wait_for_timeout(450)   # the step settles back to idle
    return page.evaluate(SIDES)


def test_facing_left_draws_the_right_frames_flipped(browser, tmp_path):
    html = woven(tmp_path)
    ctx = browser.new_context(viewport={"width": 1100, "height": 900}, reduced_motion="reduce")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(html.as_uri())
        page.click("#ts-enter")
        page.wait_for_function("window.VEFR_HERO_FRAME", timeout=15000)
        right = face(page, "ArrowRight")
        left = face(page, "ArrowLeft")
        assert right["rn"] and right["bn"] and left["rn"] and left["bn"], (right, left)
        assert right["frame"]["mirrored"] is False and left["frame"]["mirrored"] is True, (right, left)
        assert right["red"] < right["blue"], f"facing right should draw red left of blue: {right}"
        assert left["red"] > left["blue"], f"facing left should draw the frame flipped: {left}"
        assert not errors, errors
    finally:
        ctx.close()
