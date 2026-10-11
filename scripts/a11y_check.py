"""Accessibility gate: run axe-core (vendored at scripts/vendor/axe.min.js,
MPL-2.0, see scripts/vendor/axe.min.js.LICENSE) over the woven single-file
player in real chromium. Fails on serious/critical violations; moderate and
below are printed for the record but do not fail the gate (the a11y matrix
in docs/guides/accessibility-contract.md remains the design authority).

It also runs the two layout rules that axe cannot see (issue #353), because
this is already the script that opens a woven player in a real browser and
measures it: `#interact` must keep its whole label at every width, and every
fight verb must stand inside the painted play panel and clear of the d-pad,
the action row and the messages. A missing label and a control that has
fallen out of the frame are the same class of fault as an unlabelled control,
so they belong in the same gate. The per-size detail of both is `vefr look
--sizes`, which repeats its containment report at every size it photographs.

usage: uv run python scripts/a11y_check.py <woven.html> [more.html ...]
"""

import sys
import pathlib

from playwright.sync_api import sync_playwright

AXE = pathlib.Path(__file__).resolve().parent / "vendor" / "axe.min.js"

# Every piece of graphics is looked at "at phone and desktop size" before
# it ships (Rylee, 2026-10-08), so both are measured here and not one. The
# desktop pair and the phone widths are the ones issue #353 names; 1440x900
# and 390x844 are the sizes the committed screenshot gallery is taken at.
SIZES = [(1440, 900), (1280, 720), (900, 600),
         (390, 844), (360, 640), (320, 568), (414, 896)]
# `#interact`'s own list: the widths its label has to survive.
LABEL_WIDTHS = [320, 360, 390, 414]

# The measurements, read back in one pass: is anything on screen, where the
# painted play panel is (the game's own `window.VEFR_STAGE`, never the
# viewport - a piece on the page around the panel is inside one and not the
# other), and does `#interact` have room for its own words.
LAYOUT_JS = """() => {
  const box = el => { const r = el.getBoundingClientRect();
    return {l: r.left, t: r.top, r: r.right, b: r.bottom}; };
  const play = document.getElementById('play');
  const canvas = document.getElementById('town-canvas');
  const stage = window.VEFR_STAGE || null;
  const shown = id => { const el = document.getElementById(id);
    if (!el || el.hidden || el.closest('[hidden]')) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && getComputedStyle(el).display !== 'none'; };
  const btn = document.getElementById('interact');
  const label = document.getElementById('interact-label');
  const kids = btn ? Array.from(btn.querySelectorAll('*')).map(el => ({
    sw: el.scrollWidth, cw: el.clientWidth,
    tag: el.tagName.toLowerCase(),
  })) : [];
  const frame = document.getElementById('hud-frame');
  return {
    playing: !!(play && !play.hidden && canvas && canvas.getBoundingClientRect().width > 1),
    stage: stage,
    frame: frame ? box(frame) : null,
    canvas: canvas ? box(canvas) : null,
    verbButtons: Array.from(document.querySelectorAll('.verb-row button')).map(box),
    neighbours: ['dpad', 'acts', 'toasts'].filter(shown).map(id => box(document.getElementById(id))),
    interact: btn ? {
      sw: btn.scrollWidth, cw: btn.clientWidth,
      w: btn.getBoundingClientRect().width,
      h: btn.getBoundingClientRect().height,
      label: label ? label.textContent.trim() : '',
      name: (btn.getAttribute('aria-label') || btn.innerText.replace(/\\s+/g, ' ')).trim(),
      kids: kids,
    } : null,
  };
}"""


def _inside(box, frame, slack=1):
    return (box["l"] >= frame["l"] - slack and box["t"] >= frame["t"] - slack
            and box["r"] <= frame["r"] + slack and box["b"] <= frame["b"] + slack)


def _covers(a, b, slack=4):
    return (min(a["r"], b["r"]) - max(a["l"], b["l"]) > slack
            and min(a["b"], b["b"]) - max(a["t"], b["t"]) > slack)


def layout_findings(info, width):
    """Every layout fault in one measurement, as readable sentences."""
    if not info["playing"]:
        return []
    out = []
    stage = info["stage"]
    dock = bool(stage and stage["w"] >= width - 2)
    # Where a piece must sit: the painted play panel when the stage is a
    # real rectangle inside the window, and the canvas when it is not.
    frame = info["frame"] if not dock else info["canvas"]
    if frame is None:
        return ["the game published no frame and no canvas to measure against"]
    for box in info["verbButtons"]:
        where = f"at {width}px"
        if not _inside(box, frame):
            out.append(f"a fight verb is outside the play panel {where}: {box} vs {frame}")
        for other in info["neighbours"]:
            if _covers(box, other):
                out.append(f"a fight verb covers another control {where}: {box} vs {other}")
    btn = info["interact"]
    if btn is not None and width in LABEL_WIDTHS:
        if btn["sw"] > btn["cw"]:
            out.append(f"#interact is clipped at {width}px: {btn['cw']}px wide, "
                       f"its label needs {btn['sw']}px")
        for kid in btn["kids"]:
            if kid["sw"] > kid["cw"]:
                out.append(f"a descendant of #interact is clipped at {width}px: {kid}")
        # innerText reflects text-transform, the accessible name does not, so
        # the comparison must fold case; the message prints the real strings.
        if btn["label"] and btn["label"].casefold() not in btn["name"].casefold():
            out.append(f"#interact's accessible name at {width}px is {btn['name']!r}, "
                       f"without its label {btn['label']!r}")
        if btn["w"] < 44 or btn["h"] < 44:
            out.append(f"#interact is {btn['w']:.0f}x{btn['h']:.0f} at {width}px, "
                       "below the 44px tap floor")
    return out


def audit(page_path: str) -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(pathlib.Path(page_path).resolve().as_uri())
        # enter past the title screen; blank setup = the remembered
        # offline choice, so the gate audits the real play surface.
        page.click("#ts-enter")
        page.wait_for_timeout(1000)
        if page.is_visible("#config"):
            page.click("#cfg-save")
            page.wait_for_timeout(400)
        page.add_script_tag(path=str(AXE))
        violations = page.evaluate(
            "() => axe.run(document, { resultTypes: ['violations'] })"
            ".then(r => r.violations.map(v => ({ id: v.id, impact: v.impact,"
            " nodes: v.nodes.length })))"
        )
        browser.close()
        return violations


def audit_layout(page_path: str) -> list[str]:
    """The layout rules, at every size this gate photographs."""
    out: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width, height in SIZES:
            page = browser.new_page(viewport={"width": width, "height": height})
            try:
                page.goto(pathlib.Path(page_path).resolve().as_uri())
                page.click("#ts-enter")
                page.wait_for_timeout(900)
                if page.is_visible("#config"):
                    page.click("#cfg-save")
                    page.wait_for_timeout(400)
                out.extend(layout_findings(page.evaluate(LAYOUT_JS), width))
            finally:
                page.close()
        browser.close()
    return out


def main(argv: list[str]) -> int:
    bad: list[tuple[str, dict]] = []
    for path in argv[1:]:
        for v in audit(path):
            print(f"{path}: {v['id']} [{v['impact']}] x{v['nodes']}")
            if v["impact"] in ("serious", "critical"):
                bad.append((path, v))
        print(f"{path}: audit complete")
        for sentence in audit_layout(path):
            print(f"{path}: layout {sentence}")
            bad.append((path, {"id": "layout", "impact": "serious",
                               "sentence": sentence}))
        print(f"{path}: layout complete at "
              f"{', '.join(f'{w}x{h}' for w, h in SIZES)}")
    if bad:
        print(f"A11Y GATE FAILED: {len(bad)} serious/critical violation(s)")
        return 1
    print("a11y gate: no serious/critical violations")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))