#!/usr/bin/env python3
"""Replay a run's key tape with no model, and report the first divergence.

    uv run --group test python experiments/agent-player/replay.py [--fast] <run dir>

By default each step's keys go in at the same time offset as in the run,
because some of the player's UI runs on real time (the message panel folds
after 6 s).  `--fast` presses them back to back and will diverge there.

Re-weaves the same pack, refuses if the woven digest differs from the run's,
opens it with the same seed, viewport and harness setup, presses exactly the
keys the trace records, and compares each step's ARIA digest (the text a
player perceives) and screenshot digest.  A key tape, not #317's Action
Tape: it says "reproduce this run", not "continue this save".
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apl  # noqa: E402
from play import launch, weave  # noqa: E402


def replay(run_dir: Path, fast: bool = False) -> dict:
    from playwright.sync_api import sync_playwright

    run = json.loads((run_dir / "run.json").read_text())
    trace = [json.loads(ln) for ln in (run_dir / "trace.jsonl").read_text().splitlines() if ln.strip()]
    work = run_dir / "replay"
    work.mkdir(exist_ok=True)
    html, sha = weave(Path(run["pack"]), work)
    if sha != run["weave_sha256"]:
        return {"ok": False, "refused": f"woven build differs: {sha[:16]} != {run['weave_sha256'][:16]}"}
    qa = {}
    if (run_dir / "qa.jsonl").exists():
        for ln in (run_dir / "qa.jsonl").read_text().splitlines():
            q = json.loads(ln)
            qa[q["step"]] = (q.get("region"), q.get("at"))
    rows, first = [], None
    with sync_playwright() as pw:
        browser = launch(pw)
        game = apl.BrowserGame(browser, html, seed=run["seed"], viewport=tuple(run["viewport"]),
                               canary=run.get("canary", False), settle_ms=run["settle_ms"])
        t0 = time.monotonic()
        for r in trace:
            if not r.get("action") or r["action"]["type"] == "finish":
                continue
            if not fast and r.get("t_ms") is not None:
                ahead = r["t_ms"] / 1000 - (time.monotonic() - t0)
                if ahead > 0:
                    game.idle(int(ahead * 1000))
            for k in r["keys"]:
                game.press(k)
            if r["action"]["type"] == "wait":
                game.idle(1000)
            game.settle()
            obs = game.observe()
            q = game.qa()  # QA side: did the hero end up in the same place?
            row = {"step": r["step"], "aria": obs["aria_digest"] == r["aria_digest"],
                   "screen": obs["png_digest"] == r["png_digest"],
                   "world": qa.get(r["step"]) == (q.get("region"), q.get("at"))}
            rows.append(row)
            if not row["aria"] and first is None:
                first = {"step": r["step"], "expected_aria": r.get("aria"), "got_aria": obs["aria"]}
                game.shot(work / f"diverged-{r['step']:03d}.png")
        game.close()
        browser.close()
    (work / "game.html").unlink(missing_ok=True)
    result = {"ok": first is None, "timing": "fast" if fast else "recorded", "steps": len(rows),
              "aria_match": sum(r["aria"] for r in rows),
              "screen_match": sum(r["screen"] for r in rows),
              "world_match": sum(r["world"] for r in rows),
              "first_divergence": first, "rows": rows}
    (work / "replay.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    fast = "--fast" in argv
    if fast:
        argv.remove("--fast")
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    res = replay(Path(argv[0]).resolve(), fast=fast)
    if "refused" in res:
        print(f"refused: {res['refused']}")
        return 2
    print(f"[{res['timing']} timing] {res['aria_match']}/{res['steps']} steps match on player-visible text, "
          f"{res['screen_match']}/{res['steps']} on exact pixels, "
          f"{res['world_match']}/{res['steps']} on hero region and tile (QA)")
    if res["first_divergence"]:
        print(f"first divergence at step {res['first_divergence']['step']} (see replay/replay.json)")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
