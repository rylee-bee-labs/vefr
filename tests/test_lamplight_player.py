"""Lamplight in the player, without a browser: the light rig part is the pinned copy, and `draw()` runs its
after-draw hooks. What it draws is `tests/browser/test_lamplight.py`.
"""

import hashlib
import re
from pathlib import Path

PARTS = Path(__file__).resolve().parents[1] / "web" / "player" / "parts"
RIG = PARTS / "398-lightrig.js"

# The light rig (lightrig.js 1.0.1, Rylee's own; see docs/guides/world-creation.md, "Lamplight"), as it is published:
# 14,698 bytes. The part carries it between its two marker lines with the one word `export ` taken off its one
# export, since the player is one classic script. To move to a new version: paste the new file between the markers,
# take `export ` off again, and set this to `sha256sum lightrig.js` and the markers to its version.
LIGHTRIG_VERSION = "1.0.1"
LIGHTRIG_SHA256 = "fe4aad5702a67f4d23e6b886d80e3ac25b7dca9d4218dfd17c519216d59ced57"


def _pinned() -> str:
    text = RIG.read_text(encoding="utf-8")
    start = f"// -- lightrig.js {LIGHTRIG_VERSION} start --\n"
    end = f"// -- lightrig.js {LIGHTRIG_VERSION} end --\n"
    assert text.count(start) == 1 and text.count(end) == 1
    return text.split(start, 1)[1].split(end, 1)[0]


def test_the_rig_copy_is_the_pinned_one():
    body = _pinned()
    assert body.splitlines()[0].startswith(f"// lightrig.js {LIGHTRIG_VERSION}")
    assert body.count("\nfunction createLightRig(") == 1 and "export " not in body
    published = body.replace("\nfunction createLightRig(", "\nexport function createLightRig(", 1)
    assert len(published.encode()) == 14698
    assert hashlib.sha256(published.encode()).hexdigest() == LIGHTRIG_SHA256


def test_the_rig_keeps_its_helpers_to_itself():
    """Only `createLightRig` reaches the player's scope: the rig's own helpers (`program`, `tex`, ...) stay inside."""
    text = RIG.read_text(encoding="utf-8")
    outside = text.split("// -- lightrig.js", 1)[0] + text.rsplit(" end --\n", 1)[1]
    assert re.search(r"^var createLightRig = \(function \(\) \{$", outside, re.M)
    assert re.search(r"^  return createLightRig;\n\}\)\(\);$", outside, re.M)


def test_draw_runs_its_after_draw_hooks_last():
    text = (PARTS / "480-town-input-and-turns.js").read_text(encoding="utf-8")
    body = text.split("  function draw() {", 1)[1].split("\n  }\n", 1)[0]
    assert body.rstrip().endswith("ctx.restore();\n    afterDraw.forEach(function (f) { f(); });\n"
                                  "    if (animWant) scheduleAnim();")
    assert "var afterDraw = [];" in text.split("  function draw() {", 1)[0]


def test_a_rule_flag_has_a_read_only_view():
    text = (PARTS / "320-pack-rules.js").read_text(encoding="utf-8")
    assert "function ruleFlagOn(name) {" in text
