"""The shared play kit's Python side: build a fixture pack, weave it, then
run play.mjs and hand back its parsed JSON. Used by the play tests so they
do not each re-implement jsdom boot, packing and weaving.
"""

import itertools
import json
import subprocess
import sys
from pathlib import Path

from vefr import cli

PLAY_MJS = Path(__file__).parent / "fixtures" / "play.mjs"

# The fixture pack builders live beside play.mjs as importable modules.
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import make_blueprint_pack  # noqa: E402
import make_combat_pack  # noqa: E402
import make_descent_pack  # noqa: E402
import make_desk_pack  # noqa: E402
import make_equip_pack  # noqa: E402
import make_events_pack  # noqa: E402
import make_growth_pack  # noqa: E402
import make_interact_pack  # noqa: E402
import make_kitchen_pack  # noqa: E402
import make_library_pack  # noqa: E402
import make_lock_pack  # noqa: E402
import make_mending_pack  # noqa: E402
import make_motion_pack  # noqa: E402
import make_rules_pack  # noqa: E402
import make_skin_pack  # noqa: E402
import make_two_act_pack  # noqa: E402
import make_wall_pack  # noqa: E402

# Every fixture builder, keyed by the short base name specs use.
BASES = {
    "interact": make_interact_pack,
    "lock": make_lock_pack,
    "mending": make_mending_pack,
    "events": make_events_pack,
    "combat": make_combat_pack,
    "growth": make_growth_pack,
    "equip": make_equip_pack,
    "library": make_library_pack,
    "kitchen": make_kitchen_pack,
    "desk": make_desk_pack,
    "skin": make_skin_pack,
    "wall": make_wall_pack,
    "blueprint": make_blueprint_pack,
    "motion": make_motion_pack,
    "two_act": make_two_act_pack,
    "rules": make_rules_pack,
    "descent": make_descent_pack,
}

_counter = itertools.count(1)


def _apply_merge(target, patch):
    """Merge-patch `patch` into dict `target`: null deletes the key, a
    nested dict merges key by key, anything else replaces."""
    for key, value in patch.items():
        if value is None:
            target.pop(key, None)
        elif isinstance(value, dict):
            if not isinstance(target.get(key), dict):
                target[key] = {}
            _apply_merge(target[key], value)
        else:
            target[key] = value


def pack(tmp_path, base, patch=None, **kwargs):
    """Build a named fixture pack into a fresh sub-folder of `tmp_path`,
    apply the optional JSON merge `patch`, and return the pack path.

    `patch` maps a file name to a merge; a named file that does not exist
    is created, and a null value deletes that key.
    """
    if base not in BASES:
        raise KeyError(f"unknown base {base!r}: not in play_kit.BASES")
    sub = Path(tmp_path) / f"p{next(_counter)}"
    sub.mkdir(parents=True, exist_ok=True)
    built = BASES[base].build(sub, **kwargs)
    for name, merge in (patch or {}).items():
        path = built / name
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        _apply_merge(data, merge)
        path.write_text(json.dumps(data), encoding="utf-8")
    return built


def weave(pack_dir, tmp_path):
    """Weave a pack to `tmp_path/woven.html` and return that Path."""
    out = Path(tmp_path) / "woven.html"
    out.write_text(cli.weave_html(Path(pack_dir)), encoding="utf-8")
    return out


def play(html, spec):
    """Run play.mjs against `html` with `spec`, returning its parsed JSON.

    A non-zero exit raises RuntimeError carrying play.mjs's stderr.
    """
    run = subprocess.run(
        ["node", str(PLAY_MJS), str(html), json.dumps(spec)],
        capture_output=True, text=True, timeout=300,
    )
    if run.returncode != 0:
        raise RuntimeError(run.stderr)
    return json.loads(run.stdout)
