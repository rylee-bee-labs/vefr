"""The fight verbs and the Interact label, in the layout they ship in (#353).

Two layout bugs, both about the game not telling the player where it is:

  1. `.verb-row` - Strike / Console / Retreat - was absolutely positioned
     with `#stage` as its offset parent, which is the whole page. At
     1280x720 it pinned itself 16 px off the window's bottom-left corner,
     on the parchment surround rather than on the framed play panel, and
     the game's main offence controls read as having fallen out of the
     game. Every other piece of the in-world interface is placed against
     `.hud-frame`; this one was not.
  2. `#interact` is the one control that keeps its words on its face, and
     at the phone dock's 44 px square the label was cut off - the one
     labelled button losing its label on the device the owner plays on.

The sizes are the ones the issue names: 1280x720 and 900x600 on a
desktop, 390x844, 360x640 and 320x568 on a phone; and 320, 360, 390 and
414 px wide for the label. Every piece of graphics is looked at "at
phone and desktop size" before it ships, and this file is the look.

Two weaves. The desktop sizes use a town padded to 20x16 tiles, so the
painted play panel is a real sub-rectangle of the window and "inside
the panel" is a real assertion - an 11x7 map is letterboxed onto the
whole stage and every piece would pass whatever it did. The phone sizes
use the fixture as shipped, which is the layout the existing mobile
suite already pins. The hero's start and the rat one tile to its right
are the same pinned coordinates in both, so the fight verbs are up in
every run: no walk is needed.

Without `uv run playwright install chromium` these skip - conftest's
browser fixture, not a failure.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
MAKE = ROOT / "tests" / "fixtures" / "make_interact_pack.py"

# The sizes the issue names, and the woven file each is measured on.
DESKTOP = [(1280, 720), (900, 600)]
PHONES = [(390, 844), (360, 640), (320, 568)]
# `#interact`'s own list: four phone widths the label must survive.
LABEL_WIDTHS = [320, 360, 390, 414]

# The town as shipped is 11x7 tiles at 32 px, which the camera letterboxes
# onto the whole stage on any window. Padding it out with wall - to the
# right and below, so every pinned coordinate keeps its meaning - makes it
# 20x16, past the stage's 420x360 floor, so on a desktop the stage is the
# map rectangle and a control outside it is outside the stage.
PAD_TO = (20, 16)


def _pad_map(rows, size=PAD_TO):
    width, height = size
    out = []
    for row in rows:
        out.append(row + "#" * max(0, width - len(row)))
    while len(out) < height:
        out.append("#" * width)
    return out[:height]


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    """The interact fixture as shipped: an 11x7 town, phone-sized."""
    home = tmp_path_factory.mktemp("verb-row")
    out = subprocess.run([sys.executable, str(MAKE), str(home)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return _weave(Path(out.splitlines()[-1]), home / "small.html")


@pytest.fixture(scope="module")
def woven_wide(tmp_path_factory):
    """The same fixture with its town padded, for the desktop sizes."""
    home = tmp_path_factory.mktemp("verb-row-wide")
    out = subprocess.run([sys.executable, str(MAKE), str(home)],
                         capture_output=True, text=True, check=True).stdout.strip()
    pack = Path(out.splitlines()[-1])
    region = pack / "acts" / "act-1" / "town"
    rows = [line for line in
            (region / "map.md").read_text(encoding="utf-8").splitlines()
            if line.strip()]
    padded = _pad_map(rows)
    assert len(padded[0]) * 32 >= 420 and len(padded) * 32 >= 360, padded[0]
    (region / "map.md").write_text("\n".join(padded) + "\n", encoding="utf-8")
    return _weave(pack, home / "wide.html")


def _weave(pack, out):
    out.write_text(cli.weave_html(pack), encoding="utf-8")
    return out


def _open(browser, html, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    page.goto(html.as_uri())
    page.click("#ts-enter")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    # The game paints its verbs and its Interact label on its own frame loop,
    # and `textContent` is live while a box comes from the last layout pass. A
    # fixed pause therefore reads whatever pass the machine happened to be on;
    # under the whole suite at once that was the pass before the acts were
    # rendered, and a label with no box (0x0) is what the read used to see.
    # Wait, bounded, for the pieces this file measures, instead.
    page.wait_for_function(
        "() => {"
        "  const lab = document.getElementById('interact-label');"
        "  const box = lab && lab.getBoundingClientRect();"
        "  const row = document.getElementById('verb-row');"
        "  return !!box && box.width > 0 && box.height > 0"
        "    && !!row && !row.hidden"
        "    && row.querySelectorAll('button').length >= 1;"
        "}", timeout=15000)
    return ctx, page


# The fight verbs, the frame they are painted on, and the pieces they must
# not cover. `offsetParent` is the whole of bug 1: it was `#stage` - the
# page - and it is now `.hud-frame`.
VERBS = """() => {
  const box = el => { const r = el.getBoundingClientRect();
    return {l: r.left, t: r.top, r: r.right, b: r.bottom,
            w: r.width, h: r.height}; };
  const row = document.getElementById('verb-row');
  const frame = document.getElementById('hud-frame');
  const parent = row && row.offsetParent;
  const others = {};
  for (const id of ['dpad', 'acts', 'toasts']) {
    const el = document.getElementById(id);
    const shown = el && !el.hidden && !el.closest('[hidden]')
      && getComputedStyle(el).display !== 'none'
      && el.getBoundingClientRect().width > 1;
    others[id] = shown ? box(el) : null;
  }
  return {
    stage: window.VEFR_STAGE || null,
    offsetParentId: parent ? (parent.id || String(parent.className)) : null,
    frame: frame ? box(frame) : null,
    canvas: box(document.getElementById('town-canvas')),
    row: box(row),
    buttons: Array.from(document.querySelectorAll('.verb-row button')).map(box),
    others: others,
  };
}"""


def _overlaps(a, b, slack=4):
    """True when two rectangles cover each other by more than `slack` px."""
    return (min(a["r"], b["r"]) - max(a["l"], b["l"]) > slack
            and min(a["b"], b["b"]) - max(a["t"], b["t"]) > slack)


def _fight_is_on(page):
    """The rat is one tile from the hero's start, so the verbs show with
    no walk at all. Asserted, so the rest cannot pass on an empty row."""
    buttons = page.evaluate(
        "() => document.querySelectorAll('.verb-row button').length")
    assert buttons >= 1, "no fight verbs: the rat is not beside the hero"


@pytest.mark.parametrize("w,h", DESKTOP)
def test_desktop_the_fight_verbs_are_inside_the_painted_frame(browser, woven_wide, w, h):
    """The painted play panel, not the window: the row's own offset
    parent is the HUD frame, and every verb is inside that frame's box."""
    ctx, page = _open(browser, woven_wide, w, h)
    try:
        info = page.evaluate(VERBS)
        assert info["offsetParentId"] == "hud-frame", (
            f"the verb row's offset parent is {info['offsetParentId']!r}, "
            "so it is placed against the page and not the play panel")
        _fight_is_on(page)
        stage = info["stage"]
        assert stage, "window.VEFR_STAGE is not published"
        assert (stage["w"], stage["h"]) != (w, h), (
            f"the stage is the whole window at {w}x{h}; this size cannot "
            "tell a control inside the panel from one outside it")
        frame = info["frame"]
        for button in info["buttons"]:
            assert button["l"] >= frame["l"] - 1 and button["t"] >= frame["t"] - 1, \
                f"a fight verb is above the frame at {w}x{h}: {button} vs {frame}"
            assert button["r"] <= frame["r"] + 1 and button["b"] <= frame["b"] + 1, \
                f"a fight verb is past the frame at {w}x{h}: {button} vs {frame}"
            assert button["l"] >= stage["x"] - 1 and button["t"] >= stage["y"] - 1, \
                f"a fight verb is outside the stage at {w}x{h}: {button} vs {stage}"
    finally:
        ctx.close()


@pytest.mark.parametrize("w,h", PHONES)
def test_phone_the_fight_verbs_are_inside_the_canvas(browser, woven, w, h):
    ctx, page = _open(browser, woven, w, h)
    try:
        info = page.evaluate(VERBS)
        assert info["offsetParentId"] == "hud-frame", (
            f"the verb row's offset parent is {info['offsetParentId']!r}")
        _fight_is_on(page)
        canvas = info["canvas"]
        for button in info["buttons"]:
            assert button["l"] >= canvas["l"] - 1 and button["t"] >= canvas["t"] - 1, \
                f"a fight verb is off the canvas at {w}x{h}: {button} vs {canvas}"
            assert button["r"] <= canvas["r"] + 1 and button["b"] <= canvas["b"] + 1, \
                f"a fight verb is off the canvas at {w}x{h}: {button} vs {canvas}"
    finally:
        ctx.close()


@pytest.mark.parametrize("w,h", DESKTOP + PHONES)
def test_no_fight_verb_covers_the_pad_the_actions_or_the_messages(
        browser, woven, woven_wide, w, h):
    """Today it overlaps none; this keeps it that way at every size.
    The same pieces the containment contract measures: the d-pad, the
    action row and the messages strip."""
    html = woven_wide if (w, h) in DESKTOP else woven
    ctx, page = _open(browser, html, w, h)
    try:
        info = page.evaluate(VERBS)
        _fight_is_on(page)
        for name, rect in info["others"].items():
            if rect is None:
                continue
            for button in info["buttons"]:
                assert not _overlaps(button, rect), (
                    f"a fight verb covers {name} at {w}x{h}: "
                    f"{button} vs {rect}")
    finally:
        ctx.close()


# The one button with a face label, and the accessible name behind it.
INTERACT = """() => {
  const btn = document.getElementById('interact');
  const r = btn.getBoundingClientRect();
  const kids = Array.from(btn.querySelectorAll('*'))
    // A display: none descendant has no box, and the phone layouts hide
    // the kbd on purpose (020-style.css), so report only the boxes that exist.
    .filter(el => el.getClientRects().length > 0)
    .map(el => {
    const k = el.getBoundingClientRect();
    return {tag: el.tagName.toLowerCase(),
            sw: el.scrollWidth, cw: el.clientWidth,
            l: k.left, t: k.top, r: k.right, b: k.bottom};
  });
  return {
    sw: btn.scrollWidth, cw: btn.clientWidth,
    w: r.width, h: r.height,
    l: r.left, t: r.top, r: r.right, b: r.bottom,
    label: document.getElementById('interact-label').textContent.trim(),
    name: (btn.getAttribute('aria-label')
           || btn.innerText.replace(/\\s+/g, ' ')).trim(),
    kids: kids,
  };
}"""


@pytest.mark.parametrize("width", LABEL_WIDTHS)
def test_interact_keeps_its_whole_label_at_every_phone_width(browser, woven, width):
    """The label is the words; a 44 px square cut them off. It is a pill
    the label fits inside now - and the scroll width proves it: nothing
    inside the button is wider than the button."""
    height = 844 if width >= 390 else 640
    ctx, page = _open(browser, woven, width, height)
    try:
        info = page.evaluate(INTERACT)
        assert info["label"], "#interact has no label"
        assert info["sw"] <= info["cw"], (
            f"at {width}px #interact is {info['cw']}px wide and its contents "
            f"need {info['sw']}px: the label is clipped")
        for kid in info["kids"]:
            assert kid["sw"] <= kid["cw"], (
                f"a descendant of #interact is clipped at {width}px: {kid}")
            assert kid["l"] >= info["l"] - 1 and kid["t"] >= info["t"] - 1, \
                f"a descendant sits above #interact at {width}px: {kid}"
            assert kid["r"] <= info["r"] + 1 and kid["b"] <= info["b"] + 1, \
                f"a descendant sits past #interact at {width}px: {kid}"
        # The pill renders the label in caps (text-transform) and innerText
        # is rendered text, so the same words are compared in one case.
        assert info["label"].upper() in info["name"].upper(), (
            f"the accessible name at {width}px is {info['name']!r}, "
            f"without the label {info['label']!r}")
        assert info["w"] >= 44 and info["h"] >= 44, (
            f"the Interact target is {info['w']:.0f}x{info['h']:.0f} at "
            f"{width}px, below the 44px floor")
    finally:
        ctx.close()


def test_interact_keeps_its_label_when_the_target_names_something_long(
        browser, woven, tmp_path):
    """The label is the target's own words - "Go down the stairs", "Talk
    to <name>" - so it is longer than "Interact" on plenty of turns. The
    pill has to carry those too, wrapping rather than clipping."""
    pack = Path(subprocess.run([sys.executable, str(MAKE), str(tmp_path / "long")],
                               capture_output=True, text=True,
                               check=True).stdout.strip())
    html = _weave(pack, tmp_path / "long.html")
    ctx, page = _open(browser, html, 320, 568)
    try:
        page.evaluate(
            "() => { document.getElementById('interact-label').textContent ="
            " 'Go down the stairs to the cellar below'; }")
        # The same staleness as in `_open`: `innerText` is rendered text, so
        # this waits for the pass that carries the new words.
        page.wait_for_function(
            "() => document.getElementById('interact-label').innerText"
            ".toUpperCase().includes('CELLAR')", timeout=15000)
        info = page.evaluate(INTERACT)
        assert "Go down the stairs" in info["label"]
        assert info["sw"] <= info["cw"], (
            f"a long label needs {info['sw']}px in a {info['cw']}px button: "
            "it is clipped")
        for kid in info["kids"]:
            assert kid["r"] <= info["r"] + 1, kid
    finally:
        ctx.close()


def test_the_packaged_player_holds_both_fixes():
    """`web/packaged.html` is generated from the parts; this says the
    generated file has them too, so a player who never rebuilds still
    gets them."""
    html = (ROOT / "web" / "packaged.html").read_text(encoding="utf-8")
    frame = html.index('<div class="hud-frame" id="hud-frame">')
    row = html.index('id="verb-row"')
    assert frame < row < html.index("\n      </div>", frame), (
        "the packaged player puts the verb row outside the HUD frame")
    assert "var SEED_PARAM = 'vefr-seed'" in html, (
        "the packaged player does not read ?vefr-seed=")
    assert "#stage.stage--dock .gbtn--main:not(.touch-smart) { width: auto;" in html, (
        "the packaged player still draws Interact as a square")