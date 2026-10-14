#!/usr/bin/env python3
"""The Cottage town walk, recorded on video at three sizes (UATWALK, 2026-10-12-vefr-mobile-ui).

One scripted first-time walk through the town, driven the way a player drives it, at the three
sizes the 2026-10-12 vefr-mobile-ui brief asks every phase to be recorded at. Each size is one
browser context opened with `record_video_dir`, so the run leaves a `.webm` of the whole walk,
plus a still PNG at every milestone. Nothing here asserts anything: this is the evidence the
coordinator watches and judges in motion, not a verdict.

    390x844   phone portrait, touch    ->  ~/missions/2026-10-12-vefr-mobile-ui/uat/390x844/
    844x390   phone landscape, touch  ->  ~/missions/2026-10-12-vefr-mobile-ui/uat/844x390/
    1280x720  desktop, mouse + keys   ->  ~/missions/2026-10-12-vefr-mobile-ui/uat/1280x720/

Each of those three directories holds `walk.webm`, one `<milestone>.png` per stop, two
`<milestone>.cluster.png` close-ups of the touch button's caption, and `notes.md` - what was
driven at each stop and what the page read back there (hero tile, drawn tile, camera, pixel
scale, captions, page errors). `--out` moves the whole tree somewhere else.

The milestones, the same thirteen names at every size so the three runs sit side by side:

    01-title              the title screen, before Begin
    02-arrival            in the town: the follow camera, the dark, the art
    03-move-hold          finger down on the floating zone (a key down on a desk), mid-walk
    04-move-release       let go: the ring is gone and the walk has stopped
    05-smart-caption      the smart button with nothing in reach
    06-smart-press        one press, one action, and what it said
    07-bag-open           the Bag, on a phone and on a desk
    08-bag-closed         closed again (the B button closes it on a phone)
    09-settings-open      the menu, on the Display panel
    10-setting-changed    control size at 130% (phone) / darkness off (desk), back in play
    11-approach           walked to the first person; the caption now says Talk
    12-first-interaction  the smart button pressed: the speech box
    13-back-out           out of the speech box, and a step back

The pack is the shipped sample town (Emberfield) unless `VEFR_UAT_PACK` names another one - the
Cottage town itself is built in its own repo, and this recorder takes whatever town it is given.
The recorder copies that pack into a scratch folder and adds, in the copy only:

  - `display.phone_tile` / `display.desk_tile`, so the follow camera has a tile to follow at
    P2CAM and its three-tile margin at the map's edge has somewhere to show;
  - `display.pixel_art.native_tile`, so every picture is drawn at a whole number of its own art
    pixels with no smoothing (P9PIXEL);
  - a hero sprite, and `player.people_block`, so the hero stops beside the Keeper instead of on
    her tile;
  - when the town declares no props of its own, three pictures on the ground - one of them a
    three-frame strip played at 4 fps - so the object layer and its animation (P8WORLD) are on
    the video rather than only in the source.

The pack in the repository is never written to. The player, the browser tests and the docs are
not touched either.

Run it on the host (Chromium first: `uv run playwright install chromium`):

    uv run python tests/uat/record_walk.py                            # all three sizes
    uv run python tests/uat/record_walk.py --list                     # the plan, no browser
    uv run python tests/uat/record_walk.py --sizes 390x844 --headed   # watch one size happen
    VEFR_UAT_PACK=/path/to/cottage uv run python tests/uat/record_walk.py
"""

import argparse
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:  # `python tests/uat/record_walk.py` without uv
    sys.path.insert(0, str(ROOT / "src"))

from vefr import cli  # noqa: E402 - the path above has to come first

MISSION = "2026-10-12-vefr-mobile-ui"
OUT_ROOT = Path(os.environ.get("VEFR_UAT_OUT") or (Path.home() / "missions" / MISSION / "uat"))
PACK = Path(os.environ.get("VEFR_UAT_PACK") or (ROOT / "worlds" / "sample-world"))

PHONE_TILE = 52   # display.phone_tile: the follow camera's tile on a phone, in CSS px
DESK_TILE = 48    # display.desk_tile: the same follow camera on a screen with a mouse
NATIVE = 32       # display.pixel_art.native_tile: the art's own tile, the pixel pack's whole unit
VIDEO = "walk.webm"
WOVEN = "walk.html"

# The thirteen milestones, in the order the walk reaches them.
MILESTONES = (
    "01-title",
    "02-arrival",
    "03-move-hold",
    "04-move-release",
    "05-smart-caption",
    "06-smart-press",
    "07-bag-open",
    "08-bag-closed",
    "09-settings-open",
    "10-setting-changed",
    "11-approach",
    "12-first-interaction",
    "13-back-out",
)
# Two stops turn on what the smart button says; a close-up of the cluster is taken there too.
CLOSE_UPS = ("05-smart-caption", "11-approach")

# The joystick's own reach: a drag past the 14 px dead zone, under the 60 px ring.
JOY = {"up": (0, -56), "down": (0, 56), "left": (-56, 0), "right": (56, 0)}
KEYS = {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight"}
# The sample town: the walk demo leaves the hero on the north wall, and the approach walks back
# down the lane to the Keeper at [7, 4]. A pack that answers some other way is walked on to.
ROUTE = (("down", 3), ("right", 3))
HOLD_MS = 900          # how long the walk demo holds: five steps at the touch layer's 200 ms
CONTROL_SIZE = "130"   # what milestone 10 sets, in place of the phone's own 100%
STEP_GAP_MS = 300      # longer than the step tween (110 ms), so a held key never queues


class Size:
    """One size of the walk: the viewport, and how a person drives it."""

    def __init__(self, name, width, height, touch, dpr):
        self.name = name
        self.width = width
        self.height = height
        self.touch = touch
        self.dpr = dpr

    @property
    def viewport(self):
        return {"width": self.width, "height": self.height}

    @property
    def kind(self):
        return "touch" if self.touch else "mouse and keys"

    def __str__(self):
        return f"{self.name} ({self.kind})"


SIZES = (
    Size("390x844", 390, 844, True, 3),    # a phone held upright
    Size("844x390", 844, 390, True, 3),    # the same phone on its side
    Size("1280x720", 1280, 720, False, 1),  # a desk: the Acts row, a mouse and a keyboard
)


# ---- the little pictures, drawn here so the pack carries no art of its own ------------

def _png(width, height, pixels):
    """An RGBA PNG from a grid of (r, g, b, a) rows.

    The same shape tests/browser/test_pixel_art_draw.py writes its hero with, so the pack this
    recorder dresses carries art that was made the way the engine already reads art.
    """
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in pixels)

    def chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


class _Art:
    """A tiny pixel canvas: fill rectangles, then hand back a PNG."""

    def __init__(self, width, height, clear=(0, 0, 0, 0)):
        self.width = width
        self.height = height
        self.px = [[clear] * width for _ in range(height)]

    def fill(self, x0, y0, x1, y1, colour):
        for y in range(max(0, y0), min(self.height, y1)):
            for x in range(max(0, x0), min(self.width, x1)):
                self.px[y][x] = colour
        return self

    def png(self):
        return _png(self.width, self.height, self.px)


SKIN = (226, 196, 160, 255)
HAT = (58, 48, 44, 255)
TUNIC = (150, 64, 58, 255)
BELT = (88, 64, 44, 255)
LEG = (74, 66, 60, 255)
BOOT = (40, 36, 34, 255)
POST = (96, 72, 52, 255)
IRON = (70, 74, 80, 255)
GLASS = (58, 70, 88, 170)
FLAME = (232, 176, 64, 255)
FLAME_HOT = (244, 214, 120, 255)
WOOD = (122, 92, 58, 255)
WOOD_EDGE = (84, 62, 38, 255)


def hero_png():
    """A 24 x 48 figure, drawn at its own art size because the pack declares pixel art."""
    art = _Art(24, 48)
    art.fill(6, 0, 18, 3, HAT)          # the hat
    art.fill(8, 3, 16, 5, HAT)          # its brim
    art.fill(8, 5, 16, 13, SKIN)         # the head
    art.fill(6, 14, 18, 30, TUNIC)       # the coat
    art.fill(6, 30, 18, 32, BELT)
    art.fill(7, 33, 11, 45, LEG)         # two legs, so a step reads
    art.fill(13, 33, 17, 45, LEG)
    art.fill(7, 45, 11, 48, BOOT)
    art.fill(13, 45, 17, 48, BOOT)
    return art.png()


def lantern_png(frames=3, frame_w=16, frame_h=32):
    """A post and a flame, as a horizontal strip: one frame per flick of the light."""
    art = _Art(frame_w * frames, frame_h)
    for f in range(frames):
        x0 = f * frame_w
        sway = f - (frames - 1) // 2  # -1, 0, 1 for three frames
        art.fill(x0 + 7, 20, x0 + 9, frame_h, POST)
        art.fill(x0 + 6, 18, x0 + 10, 21, IRON)
        art.fill(x0 + 4, 5, x0 + 12, 7, IRON)
        art.fill(x0 + 4, 5, x0 + 6, 19, IRON)
        art.fill(x0 + 10, 5, x0 + 12, 19, IRON)
        art.fill(x0 + 4, 17, x0 + 12, 19, IRON)
        art.fill(x0 + 6, 7, x0 + 10, 17, GLASS)
        art.fill(x0 + 6 + sway, 9, x0 + 10 + sway, 16, FLAME)
        art.fill(x0 + 7 + sway, 11, x0 + 9 + sway, 15, FLAME_HOT)
    return art.png()


def crate_png():
    """A still picture on the ground, so the object layer has something that does not move."""
    art = _Art(32, 32)
    art.fill(2, 6, 30, 28, WOOD)
    art.fill(2, 6, 30, 9, WOOD_EDGE)
    art.fill(2, 25, 30, 28, WOOD_EDGE)
    art.fill(2, 6, 5, 28, WOOD_EDGE)
    art.fill(27, 6, 30, 28, WOOD_EDGE)
    art.fill(15, 6, 17, 28, WOOD_EDGE)
    return art.png()


PROPS = [
    {"pic": "lantern", "at": [2, 3], "size": [1, 1], "frames": 3, "fps": 4},
    {"pic": "crate", "at": [5, 6], "size": [1, 1]},
    {"pic": "lantern", "at": [8, 5], "size": [1, 1], "frames": 3, "fps": 4},
]


# ---- the pack the recorder walks ---------------------------------------------------


def _town_dir(pack):
    """The one region with a map of its own, which is where the town's own files live."""
    towns = sorted(p for p in pack.glob("acts/*/*/map.md"))
    if not towns:
        raise SystemExit(f"{pack} has no acts/<act>/<region>/map.md to walk")
    return towns[0].parent


def build_pack(dest):
    """A copy of the pack, dressed for the walk. The pack itself is only ever read."""
    shutil.copytree(PACK, dest)
    world_path = dest / "world.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    player = world.setdefault("player", {})
    player["people_block"] = True
    player["sprites"] = {"hero": "sprites/hero.png"}
    world["display"] = {"phone_tile": PHONE_TILE, "desk_tile": DESK_TILE,
                        "pixel_art": {"native_tile": NATIVE}}
    world_path.write_text(json.dumps(world, indent=2), encoding="utf-8")

    (dest / "sprites").mkdir(exist_ok=True)
    (dest / "sprites" / "hero.png").write_bytes(hero_png())

    town = _town_dir(dest)
    (town / "props").mkdir(exist_ok=True)
    (town / "props" / "lantern.png").write_bytes(lantern_png())
    (town / "props" / "crate.png").write_bytes(crate_png())
    contract_path = town / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if not contract.get("props"):  # a pack that brings its own object layer keeps it
        contract["props"] = PROPS
        contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return dest


# ---- a page, served ------------------------------------------------------------------


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Served:
    """The woven file over http, so localStorage and the file's own fetches behave."""

    def __init__(self, directory, filename):
        self.port = _free_port()
        self.log = open(directory / "server.log", "w")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(self.port), "--bind", "127.0.0.1",
             "--directory", str(directory)], stdout=self.log, stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{self.port}"
        # The file itself is the probe, not the directory listing: a listing can be refused
        # where the page is served fine (tests/browser/test_one_step.py probes the same way).
        for _ in range(120):
            try:
                urllib.request.urlopen(f"{self.base}/{filename}", timeout=2)
                return
            except Exception:  # noqa: BLE001 - not up yet
                time.sleep(0.25)
        self.stop()
        raise SystemExit(f"the woven file never came up; see {directory / 'server.log'}")

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)
        self.log.close()


# ---- the walk ------------------------------------------------------------------------

READ = """() => {
  const el = (id) => document.getElementById(id);
  const txt = (id) => {
    const e = el(id);
    return e ? (e.textContent || '').replace(/\\s+/g, ' ').trim() : '';
  };
  const shown = (id) => { const e = el(id); return !!e && e.getClientRects().length > 0; };
  const smart = el('touch-smart');
  const part = (name) => {
    const e = smart && smart.querySelector(name);
    return e ? e.textContent.trim() : '';
  };
  const canvas = el('town-canvas');
  const stage = window.VEFR_STAGE || {};
  const box = el('npc-box');
  return {
    hero: (window.VEFR_COMBAT && window.VEFR_COMBAT.hero.at) || null,
    tile: stage.tile === undefined ? null : stage.tile,
    follow: !!stage.phone,
    pixel: stage.pixel || null,
    camera: window.VEFR_CAMERA ? window.VEFR_CAMERA() : null,
    facing: window.VEFR_MOTION ? window.VEFR_MOTION().facing : null,
    animating: window.VEFR_MOTION ? window.VEFR_MOTION().animating : null,
    props: window.VEFR_PROPS ? window.VEFR_PROPS().props.length : null,
    smoothing: canvas ? canvas.getContext('2d').imageSmoothingEnabled : null,
    interact: txt('interact-label'),
    verb: part('.verb'),
    cap: part('.cap'),
    dim: smart ? smart.classList.contains('gbtn--dim') : null,
    status: txt('status'),
    near: txt('near'),
    poi: txt('poi'),
    menuOpen: el('menu') ? !el('menu').hidden : null,
    bagCount: txt('bag-count'),
    speech: box ? {open: !box.hidden, who: txt('npc-name'), line: txt('npc-line')} : null,
    controlSize: txt('touch-size-out'),
    fog: txt('fog-toggle'),
    shown: {zone: shown('touch-zone'), cluster: shown('touch-cluster'),
             acts: shown('acts'), dpad: shown('dpad')},
  };
}"""

RECT = """id => { const r = document.getElementById(id).getBoundingClientRect();
           return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; }"""


class Walk:
    """One size's walk: drive the page, stop at each milestone, leave a still and a note."""

    def __init__(self, page, size, out):
        self.page = page
        self.size = size
        self.out = out
        self.errors = []
        self.stops = []
        self._cdp = None

    # -- the small helpers ---------------------------------------------------------------

    @property
    def touch(self):
        return self.size.touch

    def hit(self, selector):
        """Press a button the way a person at this size would: a tap, or a click."""
        (self.page.tap if self.touch else self.page.click)(selector)

    def settle(self):
        """Two frames, so a still never catches the page between its own updates."""
        self.page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    def blur(self):
        self.page.evaluate("() => { const a = document.activeElement; if (a && a.blur) a.blur(); }")

    def read(self):
        try:
            return self.page.evaluate(READ)
        except Exception as exc:  # noqa: BLE001 - a broken page is a note, not a crash
            self.errors.append(f"read: {exc}")
            return {}

    def still(self, milestone, what):
        """The frame the coordinator looks at, with what the page read back beside it."""
        path = self.out / f"{milestone}.png"
        self.page.screenshot(path=str(path))
        files = [path.name]
        if milestone in CLOSE_UPS and self.page.locator("#touch-cluster").is_visible():
            crop = self.out / f"{milestone}.cluster.png"
            self.page.locator("#touch-cluster").screenshot(path=str(crop))
            files.append(crop.name)
        reading = self.read()
        self.stops.append({"milestone": milestone, "what": what, "files": files,
                           "reading": reading})
        print(f"    {milestone:<20} {what}", flush=True)
        return reading

    def touch_actions(self, key):
        return self.page.evaluate(
            "k => window.__vefrTouch.log.filter(e => e.kind === 'action' && e.key === k).length",
            key)

    # -- moving --------------------------------------------------------------------------

    def drag(self, dx, dy, hold_ms=60, on_hold=None):
        """A real touch: down on the floating zone, out to a direction, hold, let go.

        Sent over CDP so the page sees the touch a phone sends (the same road
        tests/browser/test_touch_controls.py's drag test takes).
        """
        if self._cdp is None:
            self._cdp = self.page.context.new_cdp_session(self.page)
        zone = self.page.evaluate(RECT, "touch-zone")
        x = int(zone["l"] + zone["w"] * 0.5)
        y = int(zone["t"] + zone["h"] * 0.5)
        self._cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        self._cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchMove", "touchPoints": [{"x": x + dx, "y": y + dy}]})
        self.page.wait_for_timeout(max(150, hold_ms))
        if on_hold:
            on_hold()
        self._cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})

    def step(self, direction):
        """One tile, walked the way this size walks."""
        if self.touch:
            self.drag(*JOY[direction], hold_ms=60)
            self.page.wait_for_timeout(STEP_GAP_MS)
        else:
            self.blur()
            self.page.keyboard.press(KEYS[direction])
            self.page.wait_for_timeout(STEP_GAP_MS)

    def says_talk(self):
        return self.read().get("interact", "").startswith("Talk")

    # -- the milestones ------------------------------------------------------------------

    def enter(self):
        self.page.click("#ts-enter")
        if self.page.is_visible("#config"):
            self.page.click("#cfg-save")
        self.page.wait_for_function("window.VEFR_COMBAT && window.VEFR_COMBAT.region",
                                    timeout=30000)
        self.page.wait_for_timeout(600)
        self.settle()

    def walk_demo(self):
        """03 and 04: hold the joystick north into the town wall, then let go."""
        if self.touch:
            self.drag(*JOY["up"], hold_ms=HOLD_MS, on_hold=lambda: self.still(
                "03-move-hold",
                f"finger down on the floating zone, dragged up and held {HOLD_MS} ms"))
        else:
            self.blur()
            self.page.keyboard.press(KEYS["up"])
            self.page.wait_for_timeout(40)
            self.still("03-move-hold", "ArrowUp one step in: the hero drawn between two tiles")
            for _ in range(3):
                self.page.keyboard.press(KEYS["up"])
                self.page.wait_for_timeout(STEP_GAP_MS)
        self.page.wait_for_timeout(500)
        self.settle()
        self.still("04-move-release",
                   "finger (or key) up: the ring is gone and the walk has stopped")

    def smart_button(self):
        """05 and 06: read the caption with nothing in reach, then press once."""
        self.page.wait_for_timeout(400)
        self.still("05-smart-caption", "the smart button with nothing in reach, and its caption")
        before = self.touch_actions("interact") if self.touch else 0
        self.hit("#touch-smart" if self.touch else "#interact")
        self.page.wait_for_timeout(700)  # one press; the touch layer's lockout is 300 ms
        after = self.touch_actions("interact") if self.touch else 0
        self.still("06-smart-press",
                   f"one press -> {after - before} action(s) in the touch log; what it said")

    def bag(self):
        """07 and 08: open the Bag and close it - on a phone, with the B button."""
        self.hit("#touch-bag" if self.touch else "#bagbtn")
        self.page.wait_for_timeout(600)
        self.still("07-bag-open", "the Bag, open")
        self.hit("#touch-b" if self.touch else "#menu-close")
        self.page.wait_for_timeout(600)
        what = "the Bag closed again"
        if self.touch:
            what += " (the B button, which only shows while a panel is open)"
        self.still("08-bag-closed", what)

    def settings(self):
        """09 and 10: open Display, change a setting, and look at it back in play."""
        self.hit("#menu-open")
        self.page.wait_for_timeout(300)
        self.hit('[data-panel="display"]')
        self.page.wait_for_timeout(400)
        self.still("09-settings-open", "the menu, on the Display panel")
        if self.touch:
            self.page.fill("#touch-size", CONTROL_SIZE)
            self.hit("#menu-close")
            self.page.wait_for_timeout(500)
            self.still("10-setting-changed",
                       f"back in play with the control size at {CONTROL_SIZE}%")
            self.hit("#menu-open")  # put it back the way a walk leaves it
            self.page.wait_for_timeout(300)
            self.hit('[data-panel="display"]')
            self.page.wait_for_timeout(300)
            self.page.fill("#touch-size", "100")
            self.hit("#menu-close")
        else:
            self.hit("#fog-toggle")  # the desk's own setting: the dark off, the whole town
            self.hit("#menu-close")
            self.page.wait_for_timeout(500)
            self.still("10-setting-changed", "back in play with the darkness off, the whole town")
            self.hit("#menu-open")
            self.page.wait_for_timeout(300)
            self.hit('[data-panel="display"]')
            self.page.wait_for_timeout(300)
            self.hit("#fog-toggle")
            self.hit("#menu-close")
        self.page.wait_for_timeout(500)
        self.settle()

    def approach(self):
        """11: walk on until the caption names the first person in reach."""
        for direction, times in ROUTE:
            for _ in range(times):
                self.step(direction)
        tries = 0
        while not self.says_talk() and tries < 8:
            self.step("right" if tries % 2 else "down")
            tries += 1
        self.page.wait_for_timeout(400)
        self.settle()
        self.still("11-approach", "walked on to the first person; the caption now names them")

    def first_interaction(self):
        """12: press the smart button where it says who it will talk to."""
        self.hit("#touch-smart" if self.touch else "#interact")
        try:
            self.page.wait_for_function("!document.getElementById('npc-box').hidden", timeout=8000)
        except Exception as exc:  # noqa: BLE001 - nothing to talk to is a finding, not a crash
            self.errors.append(f"first interaction: {exc}")
        self.page.wait_for_timeout(500)
        self.still("12-first-interaction", "the smart button pressed: the speech box is up")

    def back_out(self):
        """13: close the speech box and step back off it."""
        self.hit("#npc-close" if not self.touch else "#touch-b")
        self.page.wait_for_timeout(600)
        self.step("left")
        self.page.wait_for_timeout(400)
        self.settle()
        self.still("13-back-out", "out of the speech box, and a step back")

    def run(self, url):
        self.page.goto(url)
        self.still("01-title", "the title screen, before Begin")
        self.enter()
        self.still("02-arrival", "in the town: the follow camera, the dark, the art")
        self.walk_demo()
        self.smart_button()
        self.bag()
        self.settings()
        self.approach()
        self.first_interaction()
        self.back_out()

    # -- the notes ------------------------------------------------------------------------

    def notes_md(self):
        head = [
            f"# UAT walk - {self.size.name} ({self.size.kind})",
            "",
            f"Recorded {datetime.now():%Y-%m-%d %H:%M} by `tests/uat/record_walk.py`.",
            f"Viewport {self.size.width}x{self.size.height} at {self.size.dpr}x.",
            f"Video: `{VIDEO}`. One still per milestone, and what the page read back at it:",
            "",
            "| milestone | still | hero | tile | caption | interact |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for stop in self.stops:
            r = stop["reading"]
            caption = f"{r.get('verb', '')} {r.get('cap', '')}".strip()
            if r.get("dim"):
                caption += " (dim)"
            head.append("| {} | {} | {} | {} | {} | {} |".format(
                stop["milestone"], stop["files"][0], r.get("hero") or "-", _tile(r),
                caption or "-", r.get("interact") or "-"))
        head += ["", "## Stops", ""]
        for stop in self.stops:
            head += [f"### {stop['milestone']} - {stop['what']}", ""]
            head += [f"- still: {', '.join('`' + f + '`' for f in stop['files'])}",
                     f"- read: {_reading(stop['reading'])}", ""]
        head += ["## Page errors", ""]
        head += [f"- {e}" for e in self.errors] or ["- none"]
        return "\n".join(head) + "\n"


def _tile(reading):
    tile = reading.get("tile")
    if tile is None:
        return "-"
    pixel = reading.get("pixel")
    out = f"{tile:.2f}px"
    if pixel:
        out += f" (pixel k={pixel.get('k')}, native {pixel.get('native')})"
    if reading.get("follow"):
        out += " follow"
    return out


def _reading(r):
    bits = []
    if r.get("hero"):
        bits.append(f"hero {r['hero']}, facing {r.get('facing')}, animating {r.get('animating')}")
    if r.get("tile") is not None:
        bits.append(f"tile {_tile(r)}")
    if r.get("camera"):
        bits.append(f"camera {r['camera']}")
    if r.get("smoothing") is not None:
        bits.append(f"canvas smoothing {r['smoothing']}")
    if r.get("props") is not None:
        bits.append(f"{r['props']} object(s) on the map")
    caption = f"{r.get('verb', '')} {r.get('cap', '')}".strip()
    bits.append(f"smart button says '{caption}'" + (" (dimmed)" if r.get("dim") else ""))
    if r.get("interact"):
        bits.append(f"interact reads '{r['interact']}'")
    for name in ("status", "near", "poi", "bagCount", "controlSize", "fog"):
        if r.get(name):
            bits.append(f"{name}: '{r[name]}'")
    if r.get("menuOpen"):
        bits.append("the menu is open")
    speech = r.get("speech") or {}
    if speech.get("open"):
        bits.append(f"speech box: {speech.get('who')} says '{speech.get('line')}'")
    shown = r.get("shown") or {}
    bits.append("on screen: " + ", ".join(k for k, v in shown.items() if v))
    return "; ".join(bits)


# ---- the run --------------------------------------------------------------------------


def record_size(browser, size, url, out):
    out.mkdir(parents=True, exist_ok=True)
    video_dir = out / ".video"
    video_dir.mkdir(exist_ok=True)
    ctx = browser.new_context(
        viewport=size.viewport, device_scale_factor=size.dpr,
        has_touch=size.touch, is_mobile=size.touch, record_video_dir=str(video_dir))
    # A first-time walk: this size's own storage, empty however the last size left it.
    ctx.add_init_script("try { localStorage.clear(); } catch (err) {}")
    page = ctx.new_page()
    walk = Walk(page, size, out)
    page.on("pageerror", lambda exc: walk.errors.append(str(exc)))
    try:
        walk.run(url)
    finally:
        video = page.video
        if video:
            video.save_as(str(out / VIDEO))
        ctx.close()
        shutil.rmtree(video_dir, ignore_errors=True)
    (out / "notes.md").write_text(walk.notes_md(), encoding="utf-8")
    return walk


def plan(sizes, out, pack):
    print(f"pack:   {pack}")
    print(f"out:    {out}")
    print("milestones:")
    for name in MILESTONES:
        print(f"  {name}")
    for size in sizes:
        print(f"{size}:")
        print(f"  {out / size.name}/{VIDEO} and {out / size.name}/<milestone>.png")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record the Cottage town walk on video.")
    parser.add_argument("--sizes", nargs="*", choices=[s.name for s in SIZES],
                        help="which sizes to record (default: all three)")
    parser.add_argument("--out", type=Path, default=OUT_ROOT, help="where the runs are written")
    parser.add_argument("--pack", type=Path, default=PACK, help="the pack to walk")
    parser.add_argument("--headed", action="store_true", help="watch it happen")
    parser.add_argument("--list", dest="listing", action="store_true",
                        help="print the plan and exit, without a browser")
    args = parser.parse_args(argv)
    sizes = [s for s in SIZES if not args.sizes or s.name in args.sizes]
    if args.listing:
        return plan(sizes, args.out, args.pack)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed: uv run --with playwright python "
              "tests/uat/record_walk.py  (and: playwright install chromium)", file=sys.stderr)
        return 2

    scratch = Path(tempfile.mkdtemp(prefix="vefr-uat-walk-"))
    try:
        home = scratch / "home"
        home.mkdir()
        print(f"weaving {args.pack} ...", flush=True)
        home.joinpath(WOVEN).write_text(cli.weave_html(build_pack(scratch / "pack")),
                                        encoding="utf-8")
        server = Served(home, WOVEN)
        url = f"{server.base}/{WOVEN}"
        runs = {}
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=not args.headed)
                try:
                    for size in sizes:
                        print(f"{size.name} - {size.kind}", flush=True)
                        out = args.out / size.name
                        try:
                            runs[size.name] = record_size(browser, size, url, out)
                            print(f"  -> {out}", flush=True)
                        except Exception as exc:  # noqa: BLE001 - one size must not sink the rest
                            runs[size.name] = {"failed": str(exc)}
                            print(f"  FAILED: {exc}", file=sys.stderr, flush=True)
                finally:
                    browser.close()
        finally:
            server.stop()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    args.out.mkdir(parents=True, exist_ok=True)
    report = {"mission": MISSION, "pack": str(args.pack), "milestones": list(MILESTONES),
              "recorded": datetime.now().isoformat(timespec="seconds"), "sizes": {}}
    for size in sizes:
        walk = runs.get(size.name) or {}
        report["sizes"][size.name] = {
            "out": str(args.out / size.name),
            "video": str(args.out / size.name / VIDEO) if not walk.get("failed") else None,
            "stills": [s["milestone"] for s in walk.get("stops", [])],
            "page_errors": walk.get("errors", []),
            "failed": walk.get("failed"),
        }
    (args.out / "run.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nreport: {args.out / 'run.json'}")
    return 1 if any(r.get("failed") for r in runs.values() if isinstance(r, dict)) else 0


if __name__ == "__main__":
    sys.exit(main())