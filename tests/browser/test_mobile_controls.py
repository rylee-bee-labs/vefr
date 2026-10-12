"""The mobile controls (390x844, the iPhone-class portrait window).

Three rules, Rylee 2026-10-07:
  1. The touch cluster (the smart button and the Bag button) sits in a
     stable box: its outer position does not reflow when the HUD's text
     content changes. The HUD grows downward as the world grows lines; the
     controls stay at the bottom of the stage, at the same rect, every state.
  2. Nothing covers a control; tap targets are at least 44x44 CSS px;
     safe-area-insets (the OS home indicator at the bottom, the status
     bar at the top, the rounded corners at the sides) are respected.
  3. Buggy controls, found one by one, are fixed at the root.

The device insets are real. The test drives them through Chromium's own
`Emulation.setSafeAreaInsetsOverride` (the protocol hook behind DevTools'
device mode), so `env(safe-area-inset-*)` reports what a phone with a chin
and rounded corners reports. The test never writes a --sai-* value itself:
doing that would prove the offset arithmetic and nothing about whether the
OS insets reach the page at all. Two things have to hold for that, and both
are asserted here: the page asks the OS for its whole canvas
(`viewport-fit=cover` in 010-head.html - without it env() is 0 on every
device), and the style sheet reads env() rather than a baked number.

The browser hands back three things we trust:
  - the meta viewport tag the page shipped;
  - the live `--sai-*` values the OS reports (set on :root by the browser
    from the device metrics; 0 on a desktop page);
  - the rendered rect of every named control.

Uses the interact fixture (an 11x7 map: small on purpose, so it is
letterboxed on any window). The HUD is forced to its widest state
(HP + level + gold + bag strip + light) before measuring, so the
test does not pass on a HUD that hides the bug.
"""

import json
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
MAKE = ROOT / "tests" / "fixtures" / "make_interact_pack.py"

# An iPhone-class phone, upright: a notch at the top, a home indicator at
# the bottom, nothing at the sides (the corners round into the bezel, but
# portrait keeps them clear of the content).
PHONE = {"width": 390, "height": 844}
PHONE_INSETS = {"top": 47, "bottom": 34, "left": 0, "right": 0}
# The same phone on its side: the OS-drawn corners now come in from the
# left and right edges (59 px on an iPhone-class device), and the status
# bar is gone.
LANDSCAPE = {"width": 844, "height": 390}
LANDSCAPE_INSETS = {"top": 0, "bottom": 21, "left": 59, "right": 59}


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    d = tmp_path_factory.mktemp("mobile-ctl")
    out = subprocess.run([sys.executable, str(MAKE), str(d)],
                        capture_output=True, text=True, check=True).stdout.strip()
    pack = Path(out.splitlines()[-1])
    # A full HUD: levels (the level chip) and gold (the gold chip), as a real game shows them.
    wj = pack / "world.json"
    cfg = json.loads(wj.read_text(encoding="utf-8"))
    cfg["growth"] = {"mode": "levels", "levels": {"xp": [0, 3, 6], "gain": {"hp": 2, "atk": 1}}}
    cfg["player"]["gold"] = 128
    wj.write_text(json.dumps(cfg), encoding="utf-8")
    html = d / "x.html"
    html.write_text(cli.weave_html(pack), encoding="utf-8")
    return html


@contextmanager
def device(browser, woven, size, insets=None):
    """A phone context with the player on the game screen.

    `insets` are the safe-area insets the OS reports, in CSS px. They go
    in through the browser's own device emulation - the same channel a
    real notch and home indicator come through - and never through a
    `--sai-*` value written from the test.
    """
    ctx = browser.new_context(viewport=size, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    if insets:
        cdp = ctx.new_cdp_session(page)
        try:
            cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": insets})
        except Exception as exc:  # noqa: BLE001 - an older Chromium has no such hook
            ctx.close()
            pytest.skip(f"this Chromium cannot emulate safe-area insets "
                        f"({exc.__class__.__name__}: {exc})")
    try:
        page.goto(woven.as_uri())
        page.click("#ts-enter")
        page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
        page.wait_for_timeout(300)
        page.evaluate(SHOW_FULL_HUD)
        page.wait_for_timeout(150)
        yield page
    finally:
        ctx.close()


@pytest.fixture(scope="module")
def page_at(browser, woven):
    """A 390x844 touch context with the player on the start screen, full HUD on."""
    with device(browser, woven, PHONE) as page:
        yield page


# The controls whose outer rect we are checking on a touch screen (joystick
# mode, the default). Each must satisfy both rules at 390x844. The names
# match the DOM ids of the buttons.
CONTROLS = ["touch-smart", "touch-bag", "menu-open"]

# Show the HUD in its widest state so a layout-shift bug that hides
# under an empty cap will surface.
SHOW_FULL_HUD = """() => {
  const show = id => { const el = document.getElementById(id);
                       if (el) { el.hidden = false; } };
  show('hud-level'); show('bag-strip'); show('light-live');
  const lvl = document.getElementById('hud-level');
  if (lvl) lvl.textContent = 'lvl 3';
  const bag = document.getElementById('bag-strip');
  if (bag) bag.textContent = 'rusty key / band / lamp / rope';
  const light = document.getElementById('light-live');
  if (light) light.textContent = 'Bright';
}"""

# The live safe-area variables, read back off :root. These are the numbers
# the OS gave us through env(); if the page reads anything else - a baked
# value, or a --sai-* the test wrote - this says so.
READ_INSETS = """() => {
  const cs = getComputedStyle(document.documentElement);
  const px = name => parseFloat(cs.getPropertyValue(name)) || 0;
  return {top: px('--sai-top'), bottom: px('--sai-bottom'),
          left: px('--sai-left'), right: px('--sai-right')};
}"""

RECTS = """() => {
  const ids = ['touch-cluster', 'touch-smart', 'touch-bag', 'touch-b',
               'menu-open', 'hud-hp', 'hud-level', 'hud-gold', 'bag-strip',
               'light-live', 'toasts-toggle', 'toasts', 'verb-row'];
  const out = {};
  for (const id of ids) {
    const el = document.getElementById(id);
    if (!el || el.hidden) { out[id] = null; continue; }
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) { out[id] = null; continue; }
    out[id] = {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height};
  }
  return out;
}"""


def test_the_page_asks_the_os_for_its_whole_canvas(page_at):
    """The first half of "the insets are real". `env(safe-area-inset-*)`
    is 0 on every device unless the viewport meta asks for the whole
    canvas; without `viewport-fit=cover` the home indicator, the notch and
    the rounded corners are the browser's to keep, and every offset below
    would be measuring 0 while the control sits under the OS's own
    chrome."""
    meta = page_at.evaluate(
        "(document.querySelector('meta[name=viewport]') || {}).content || ''")
    assert "viewport-fit=cover" in meta, (
        f"the viewport meta has no viewport-fit=cover: {meta!r}")


def test_os_insets_reach_the_page_through_env(browser, woven):
    """The second half: the values the style sheet reads are the ones the
    OS reports. The test emulates a chin and a notch and reads back
    `env()` through the --sai-* variables on :root, without ever writing
    one. A sheet that hard-codes an offset, or reads a variable the page
    sets itself, fails here."""
    with device(browser, woven, PHONE, PHONE_INSETS) as page:
        live = page.evaluate(READ_INSETS)
    assert live == {k: float(v) for k, v in PHONE_INSETS.items()}, (
        f"the page reports insets {live}, the device reports "
        f"{PHONE_INSETS}: the --sai-* variables are not env(safe-area-inset-*)")


def test_safe_area_inset_bottom_respected_at_390x844(browser, woven):
    """Rylee 2026-10-07: "respect safe-area insets". The OS hands a 34 px home
    indicator at the bottom of the window on a phone with a chin. Every
    bottom-anchored control (the touch cluster, the verb row) must sit ABOVE
    that line - the gap between the control's bottom edge and the
    viewport bottom is at least the inset."""
    with device(browser, woven, PHONE, PHONE_INSETS) as page:
        inset = PHONE_INSETS["bottom"]
        rects = page.evaluate(RECTS)
        for name in ("touch-cluster", "verb-row"):
            r = rects.get(name)
            assert r, f"missing control {name}"
            gap = page.evaluate("innerHeight") - r["b"]
            assert gap >= inset - 1, (
                f"{name} sits {gap:.0f} px from the viewport bottom, "
                f"the OS home indicator is {inset} px")


def test_safe_area_inset_top_respected_at_390x844(browser, woven):
    """The HUD row sits below the OS status bar / notch. The HUD's top
    edge is at least the top inset."""
    with device(browser, woven, PHONE, PHONE_INSETS) as page:
        inset = PHONE_INSETS["top"]
        rects = page.evaluate(RECTS)
        r = rects["hud-hp"]
        assert r["t"] >= inset - 1, (
            f"hud-hp top {r['t']:.0f} px, top inset {inset} px")


def test_side_insets_keep_the_controls_clear_of_the_rounded_corners(
        browser, woven):
    """The phone on its side. `env(safe-area-inset-left/right)` is the
    corner the OS cuts out of its own screen; a control anchored to a
    side has to stand clear of it or it sits on the rounding, where it
    reads as cut off. Every visible piece of the interface stays inside
    the OS's own box."""
    with device(browser, woven, LANDSCAPE, LANDSCAPE_INSETS) as page:
        left, right = LANDSCAPE_INSETS["left"], LANDSCAPE_INSETS["right"]
        width = page.evaluate("innerWidth")
        rects = page.evaluate(RECTS)
        checked = 0
        for name, r in rects.items():
            if not r:
                continue
            checked += 1
            assert r["l"] >= left - 1, (
                f"{name} starts {r['l']:.0f} px from the left edge, the OS "
                f"keeps {left} px there for its rounded corner")
            assert r["r"] <= width - right + 1, (
                f"{name} ends {r['r']:.0f} px from a {width} px window, the OS "
                f"keeps {right} px there for its rounded corner")
        assert checked >= len(CONTROLS), (
            f"only {checked} pieces were on screen; the test would pass "
            f"without measuring anything")


def test_dock_mode_holds_the_controls_in_the_room_below_the_map(browser, woven):
    """The stable-control layout is the dock's, so the test has to be on
    it. At 390x844 the camera sets `.stage--dock` on #stage: the stage is
    the whole window, the map is letterboxed with spare room above and
    below, and the touch cluster sits in the room below while the messages
    grow up out of the map. This asserts we are measuring that layout, and
    that it is laid out."""
    with device(browser, woven, PHONE, PHONE_INSETS) as page:
        assert "stage--dock" in page.evaluate(
            "document.getElementById('stage').className"), (
            "the 390x844 window is not in dock mode; the rest of this file "
            "would be measuring the desktop layout")
        rects = page.evaluate(RECTS)
        m = page.evaluate("window.VEFR_STAGE.map")
        # The cluster stays in the room below the drawn map, never on it.
        assert rects["touch-cluster"]["t"] >= m["y"] + m["h"] - 1, (
            f"the touch cluster starts {rects['touch-cluster']['t']:.0f} px, "
            f"the map ends {m['y'] + m['h']:.0f} px: it sits on the map")
        # The joystick zone is the left side, the cluster the right.
        zone = page.evaluate(
            "(() => { const r = document.getElementById('touch-zone').getBoundingClientRect();"
            " return {l: r.left, r: r.right}; })()")
        assert zone["r"] <= rects["touch-smart"]["l"] + 1, (
            f"the joystick zone ({zone['r']:.0f} px) reaches the smart button "
            f"({rects['touch-smart']['l']:.0f} px)")
        # The messages grow up into the room above the map, never down
        # over it.
        assert rects["toasts"]["b"] <= m["y"] + 1, (
            f"the messages end {rects['toasts']['b']:.0f} px, the map starts "
            f"{m['y']:.0f} px: they are drawn over the map")


def test_control_bar_is_stable_when_hud_changes(browser, woven):
    """Rylee 2026-10-07: "controls shift and get buggy with the ui". The
    control bar (d-pad + action row) is a stable, reserved box at the
    bottom of the stage. HUD text growing shows the items move; the
    control bar's outer rect does NOT."""
    with device(browser, woven, PHONE) as page:
        assert "stage--dock" in page.evaluate(
            "document.getElementById('stage').className"), (
            "the stable box is the dock's; this measured another layout")
        # Start from the sparsest HUD: hide the level chip, bag strip and light.
        # The interact fixture already enables growth + gold so the HUD grows
        # when we flip them back on.
        page.evaluate("""() => {
          const hide = id => { const el = document.getElementById(id);
                               if (el) { el.hidden = true; } };
          hide('hud-level'); hide('bag-strip'); hide('light-live');
        }""")
        page.wait_for_timeout(150)
        sparse = page.evaluate(RECTS)
        # Now flip the HUD to its widest state (level + bag strip + light).
        page.evaluate(SHOW_FULL_HUD)
        page.wait_for_timeout(150)
        full = page.evaluate(RECTS)
        # The HUD moved (proves the test isn't a no-op) and the controls did not.
        assert sparse["hud-level"] is None, \
            "the HUD did not start sparse: hud-level was already showing"
        assert full["hud-level"] is not None, \
            "the HUD width-state toggle did not flip"
        for name in CONTROLS:
            a = sparse.get(name)
            b = full.get(name)
            assert a and b, f"missing control {name} in one of the states"
            # Less than 1.5 CSS px of drift - far below the tap-target floor.
            drift = max(abs(a["l"] - b["l"]), abs(a["t"] - b["t"]),
                        abs(a["r"] - b["r"]), abs(a["b"] - b["b"]))
            assert drift < 1.5, (
                f"{name} shifted by {drift:.1f} px when the HUD grew: "
                f"sparse={a} full={b}")


def test_tap_targets_meet_the_44px_floor(browser, woven):
    """Rylee 2026-10-07: "tap targets at least 44x44 CSS px". Every
    visible control is at least 44 px wide and 44 px tall in CSS px.
    The Bag button and the smart button are the touch controls; the B
    button only shows while a panel is open and is measured in
    test_touch_controls.py."""
    with device(browser, woven, PHONE) as page:
        info = page.evaluate("""() => {
          const names = ['touch-smart', 'touch-bag', 'menu-open', 'toasts-toggle'];
          const out = {};
          for (const name of names) {
            const el = document.getElementById(name);
            if (!el || el.hidden) continue;
            const r = el.getBoundingClientRect();
            out[name] = {w: r.width, h: r.height};
          }
          return out;
        }""")
        for name, size in info.items():
            assert size["w"] >= 44 and size["h"] >= 44, (
                f"{name} is {size['w']:.0f}x{size['h']:.0f}, below the 44px floor")


def test_page_does_not_sideways_scroll(browser, woven):
    """Rylee 2026-10-07: "no horizontal scroll". The page's scrollWidth
    equals the inner width even with the full HUD on."""
    with device(browser, woven, PHONE) as page:
        info = page.evaluate("""() => ({
          sw: document.documentElement.scrollWidth,
          iw: innerWidth,
        })""")
        assert info["sw"] <= info["iw"], \
            f"the page sideways-scrolls: scrollWidth={info['sw']}, innerWidth={info['iw']}"