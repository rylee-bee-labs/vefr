"""The Desk's "Play it here" pane, in a real browser.

Press the button; the studio weaves the current world through
POST /api/builder/weave and shows the woven file in an iframe served by
GET /api/builder/weave/play/{name}. The iframe is the STRICT sandbox
(`allow-scripts` alone): measured in chromium, the woven player still
starts and walks inside it (its localStorage calls are wrapped and
no-op), so every world gets the strict pane - the pane can never reach
the studio page or its origin.

axe-core gates the pane exactly the way scripts/a11y_check.py gates the
woven file: inject the vendored axe and fail on serious/critical
violations.
"""
import os
import re
import tempfile
from pathlib import Path

# The shared studio fixture (fixtures.py) starts once per session; point
# its weaves at a temp dir before it is created so the test never leaves
# files in the checkout. Set at import time, during collection.
os.environ.setdefault("VEFR_WEAVE_DIR", tempfile.mkdtemp(prefix="vefr-play-weave-"))

from .steps import open_studio  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
AXE = ROOT / "scripts" / "vendor" / "axe.min.js"


def play_pane(page, studio):
    """Open the Desk, press Play it here, wait for the woven title card."""
    open_studio(page, studio, "workshop")
    page.locator("#screen-workshop").wait_for()
    page.get_by_role("button", name="Play it here").click()
    frame = page.frame_locator("#ws-play-frame")
    frame.locator("#title-screen").wait_for(state="visible", timeout=15000)
    return frame


def _compat(frame, expr):
    """Evaluate inside the sandboxed frame through its own <body>."""
    return frame.locator("body").evaluate(expr)


def test_play_it_here_shows_the_woven_player_in_a_strict_sandbox(page, studio):
    frame = play_pane(page, studio)

    # The pane exists, is titled, and is strict: allow-scripts only.
    assert page.get_attribute("#ws-play-frame", "sandbox") == "allow-scripts"
    assert page.get_attribute("#ws-play-frame", "title")

    # The title card rendered with the world's own title.
    assert "Emberfield" in frame.locator("#title-screen").inner_text()

    # The visible Open in a new tab link points at the play route.
    link = page.get_by_role("link", name="Open in a new tab")
    assert link.is_visible()
    assert "/api/builder/weave/play/" in link.get_attribute("href")

    # The player starts: step through the title card, the hero exists.
    # Press rather than click: the pane sits low on the page, so Playwright
    # refuses the click as outside the parent viewport; Begin enters on
    # Enter either way.
    frame.get_by_role("button", name="Begin").press("Enter")
    frame.locator("#play").wait_for(state="visible")
    hero = _compat(frame, "() => window.VEFR_COMBAT && window.VEFR_COMBAT.hero")
    assert hero and hero["at"], hero

    # ...and it walks one tile on an arrow key, read off its own snapshot.
    before = _compat(frame, "() => window.VEFR_COMBAT.hero.at")
    frame.locator("body").press("ArrowRight")
    _compat(frame, "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    after = _compat(frame, "() => window.VEFR_COMBAT.hero.at")
    assert [after[0] - before[0], after[1] - before[1]] == [1, 0], (before, after)


def test_the_play_pane_announces_through_the_status_line(page, studio):
    play_pane(page, studio)
    status = page.locator("#ws-weave-status")
    # The existing polite status span carries the state, not a silent pane.
    assert status.get_attribute("role") == "status"
    assert status.get_attribute("aria-live") == "polite"
    assert status.inner_text().startswith("Playing")


def test_the_play_pane_passes_axe(page, studio):
    play_pane(page, studio)
    page.add_script_tag(path=str(AXE))
    violations = page.evaluate(
        "() => axe.run(document, { resultTypes: ['violations'] })"
        ".then(r => r.violations.map(v => ({ id: v.id, impact: v.impact,"
        " nodes: v.nodes.length })))"
    )
    serious = [v for v in violations if v["impact"] in ("serious", "critical")]
    assert serious == [], serious


def test_the_pane_link_is_a_real_target(page, studio):
    """The link targets the inline play route, not the download attachment."""
    play_pane(page, studio)
    href = page.get_by_role("link", name="Open in a new tab").get_attribute("href")
    assert re.search(r"/api/builder/weave/play/[A-Za-z0-9._-]+\.html$", href), href
    assert "/file/" not in href
