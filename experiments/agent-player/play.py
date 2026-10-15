#!/usr/bin/env python3
"""Run one Agent Player Lab session.  See README.md.

    uv run --group test python experiments/agent-player/play.py \
        --pack ../<pack repo>/worlds/<pack> \
        --policy random --seed apl-1 --out /tmp/apl/dry
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import apl  # noqa: E402

VEFR_ROOT = HERE.parents[1]


# ---- provider: one OpenAI-compatible call --------------------------------
# The same shape as bench/design/run.py's `_chat`, plus image parts and usage.
def opencode_provider(name: str) -> dict:
    """baseURL/apiKey from the existing opencode config (bench/design/run.py reads it the same way)."""
    path = Path.home() / ".config/opencode/opencode.json"
    cfg = json.loads(re.sub(r"^\s*//.*$", "", path.read_text(), flags=re.M))
    return cfg["provider"][name]["options"]


def make_chat(base_url: str, model: str, api_key: str | None, max_tokens: int = 1200,
              timeout: int = 180):
    def chat(messages) -> dict:
        req_body = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if "anthropic.com" not in base_url:  # newer Claude models refuse `temperature`
            req_body["temperature"] = 0.7
        body = json.dumps(req_body).encode()
        h = {"Content-Type": "application/json"}
        if api_key:
            h["Authorization"] = "Bearer " + api_key
            h["x-api-key"] = api_key  # Anthropic's native header; same key, same host
        req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body, headers=h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.loads(r.read())
        msg = out["choices"][0]["message"]
        usage = out.get("usage") or {}
        return {"text": msg.get("content") or "", "tokens_in": usage.get("prompt_tokens"),
                "tokens_out": usage.get("completion_tokens")}
    return chat


def text_renders(browser) -> bool:
    """A browser with no usable fonts draws pages with no words at all, and every
    screenshot (and the vision check) is quietly blank.  Catch that first."""
    page = browser.new_page(viewport={"width": 320, "height": 120})
    shots = []
    for text in ("OTTER 47", ""):
        page.set_content('<body style="background:#111;color:#eee;font:48px sans-serif;margin:0">'
                         f"{text}</body>")
        shots.append(page.screenshot())
    page.close()
    return shots[0] != shots[1]


def vision_check(chat, browser) -> dict:
    """Prove the model reads images: show it a word and a number only the picture carries."""
    page = browser.new_page(viewport={"width": 640, "height": 360})
    page.set_content('<body style="background:#111;color:#eee;font:64px sans-serif;'
                     'display:grid;place-items:center;height:100vh;margin:0">OTTER 47</body>')
    img = page.screenshot(type="jpeg", quality=80)
    page.close()
    policy = apl.ModelPolicy(chat, "You describe images exactly.")
    r = policy.decide("What word and what number are written in the image? Answer in a few words.", img)
    text = apl.strip_thinking(r.get("text")).upper()
    return {"ok": "OTTER" in text and "47" in text, "reply": text[:200],
            "tokens_in": r.get("tokens_in"), "tokens_out": r.get("tokens_out")}


# ---- build identity ------------------------------------------------------
def git_id(path: Path) -> dict:
    def g(*a):
        try:
            return subprocess.run(["git", "-C", str(path), *a], capture_output=True, text=True,
                                  check=True).stdout.strip()
        except Exception:  # noqa: BLE001
            return None
    dirty = g("status", "--porcelain", "--untracked-files=no")
    return {"sha": g("rev-parse", "HEAD"), "dirty_files": None if dirty is None else len(dirty.splitlines())}


def weave(pack: Path, out: Path) -> tuple[Path, str]:
    from vefr.cli import weave_html
    html = weave_html(pack)
    path = out / "game.html"
    path.write_text(html, encoding="utf-8")
    return path, hashlib.sha256(html.encode()).hexdigest()


def launch(pw):
    exe = os.environ.get("APL_CHROMIUM")
    return pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()


# ---- the final report ----------------------------------------------------
REPORT_ASK = """You have finished playing. Write your playtest report as ONE JSON object:
{"observed": [{"claim": "...", "steps": [n, ...]}],
 "inferred": ["what you believe happened or how things work, but did not confirm"],
 "interesting": ["..."], "confusing": ["..."],
 "unknown": ["what you could not establish"],
 "next": ["what you would explore next"],
 "summary": "three or four sentences, plain words"}
Only put something under "observed" if you can cite the decision numbers where you saw it.
Do not claim anything you did not do. Here is your full action log and journal:
"""


def final_report(chat, system: str, trace: list[dict], journal: list[str]) -> dict:
    lines = []
    for r in trace:
        a = json.dumps(r.get("action")) if r.get("action") else f"REFUSED ({r.get('refused')})"
        new = " | ".join(r.get("new_text") or [])[:400]
        lines.append(f"{r['step']}. {a} -> {r.get('result', '')}"
                     + (f"\n   new text: {new}" if new else "")
                     + (f"\n   thought: {r.get('thought')}" if r.get("thought") else ""))
    prompt = REPORT_ASK + "\n".join(lines) + "\n\nJournal:\n" + "\n".join(journal or ["(empty)"])
    r = chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}])
    m = re.search(r"\{.*\}", apl.strip_thinking(r.get("text")), re.S)
    try:
        body = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        body = {}
    return {"body": body, "raw": (r.get("text") or "")[:6000],
            "tokens_in": r.get("tokens_in"), "tokens_out": r.get("tokens_out")}


def render_report(run: dict, trace: list[dict], fr: dict | None, audit: dict) -> str:
    steps = {r["step"] for r in trace}
    u = run["usage"]
    L = [f"# Agent Player Lab run: {run['profile']} on {run['pack_name']}", "",
         f"- **Mode:** {run['mode']}  ·  **Policy:** {run['policy']}  ·  **Model:** {run.get('model') or 'none'}"
         f" ({run.get('provider') or 'no provider'})",
         f"- **Seed / viewport:** `{run['seed']}` / {run['viewport'][0]}x{run['viewport'][1]}",
         f"- **Build:** vefr `{(run['vefr']['sha'] or '?')[:7]}` (dirty files: {run['vefr']['dirty_files']}),"
         f" pack repo `{(run['pack_repo']['sha'] or '?')[:7]}` (dirty files: {run['pack_repo']['dirty_files']}),"
         f" woven sha256 `{run['weave_sha256'][:16]}`",
         f"- **Stopped because:** {run['stop']}",
         f"- **Decisions / key inputs:** {run['decisions']} / {run['inputs']}  ·  "
         f"**Refused replies:** {sum(1 for r in trace if r.get('refused'))}",
         f"- **Tokens (measured):** {u['tokens_in']} in / {u['tokens_out']} out "
         f"(play {u['play_in']}/{u['play_out']}, report {u['report_in']}/{u['report_out']}); "
         f"median decision latency {u['median_latency_ms']} ms; wall clock {run['wall_seconds']} s",
         f"- **Leak audit:** {'PASS' if audit['ok'] else 'FAIL ' + json.dumps(audit['leaks'])} "
         f"(canaries planted: {audit['canary_planted']}, hidden facts checked: {audit['hidden_facts_checked']})",
         "", "> An AI's impressions are not a human playtest. Treat this as evidence of what it tried,"
         " noticed and misunderstood.", ""]
    L += ["## Observed (from the trace, written by the harness)", ""]
    for r in trace:
        a = r.get("action") or {"refused": r.get("refused")}
        line = f"{r['step']}. `{json.dumps(a)}` keys `{' '.join(r.get('keys') or []) or '-'}` → {r.get('result', '')}"
        if r.get("new_text"):
            line += "  \n   new: " + " / ".join(t.strip(" -") for t in r["new_text"][:4])[:300]
        if r.get("shot"):
            line += f"  \n   ![step {r['step']}]({r['shot']})"
        L.append(line)
    if fr and fr["body"]:
        b = fr["body"]

        def cite(o):
            bad = [s for s in o.get("steps", []) if s not in steps]
            ref = ", ".join(str(s) for s in o.get("steps", [])) or "no steps cited"
            return f"- {o.get('claim')} _(steps {ref}{'; UNVERIFIED step refs ' + str(bad) if bad else ''})_"
        L += ["", "## The agent's report", "", b.get("summary", ""), "",
              "### Observed (agent, with step references)", ""]
        L += [cite(o) for o in b.get("observed", []) if isinstance(o, dict)] or ["- (none)"]
        for title, key in (("Inferred", "inferred"), ("Subjective: interesting", "interesting"),
                           ("Subjective: confusing", "confusing"), ("Unknown", "unknown"),
                           ("What it would explore next", "next")):
            items = [f"- {x}" for x in b.get(key, [])] or ["- (none)"]
            L += ["", f"### {title}", ""] + items
    elif fr:
        L += ["", "## The agent's report", "", "The final report was not valid JSON; raw text:", "",
              "```", fr["raw"], "```"]
    else:
        L += ["", "## The agent's report", "", "No model in this run, so no report."]
    L += ["", "## Comparison with the scripted 40/40 playthrough", "",
          "_Written by hand after the run._", "",
          "## Reproduce", "", "```bash", run["reproduce"], "```", ""]
    return "\n".join(L)


# ---- main ----------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--policy", choices=["random", "model"], default="random")
    ap.add_argument("--profile", default="curious-explorer")
    ap.add_argument("--mode", choices=["player"], default="player",
                    help="player only for now; QA evidence is always recorded separately")
    ap.add_argument("--seed", default="apl-1")
    ap.add_argument("--viewport", default="1280x720")
    ap.add_argument("--max-actions", type=int, default=50)
    ap.add_argument("--max-inputs", type=int, default=150)
    ap.add_argument("--max-seconds", type=float, default=1200)
    ap.add_argument("--max-input-tokens", type=int, default=400_000)
    ap.add_argument("--settle-ms", type=int, default=250)
    ap.add_argument("--canary", action="store_true", help="plant hidden canaries and audit prompts")
    ap.add_argument("--provider", help="opencode:<name> (reads ~/.config/opencode/opencode.json) or a base URL")
    ap.add_argument("--model")
    ap.add_argument("--api-key-env", help="env var holding the key when --provider is a URL")
    ap.add_argument("--text-only", action="store_true", help="send no screenshot (ARIA text only)")
    ap.add_argument("--max-reply-tokens", type=int, default=4000,
                    help="per reply; models that think inline need room for it")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    from playwright.sync_api import sync_playwright

    args = parse_args(argv)
    pack = Path(args.pack).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    vw = tuple(int(x) for x in args.viewport.lower().split("x"))
    limits = apl.Limits(decisions=args.max_actions, inputs=args.max_inputs,
                        wall_seconds=args.max_seconds, input_tokens=args.max_input_tokens)
    profile = (HERE / "profiles" / f"{args.profile}.md").read_text(encoding="utf-8")
    # The game's title is what its title screen shows a player; nothing else is read.
    title = json.loads((pack / "world.json").read_text()).get("title") or "this game"
    sight = ("You can't see the screen: you get the text a screen reader would read out, and nothing else."
             if args.text_only else
             "You see the screen as a picture, plus the text a screen reader would read out.")
    system = (profile.strip().replace("{game}", title).replace("{sight}", sight)
              + "\n\n" + apl.ACTION_HELP)

    chat = None
    provider = model = None
    if args.policy == "model":
        if not (args.provider and args.model):
            print("--policy model needs --provider and --model", file=sys.stderr)
            return 2
        if args.provider.startswith("opencode:"):
            opts = opencode_provider(args.provider.split(":", 1)[1])
            base, key = opts["baseURL"], opts.get("apiKey")
        else:
            base, key = args.provider, os.environ.get(args.api_key_env or "", None)
        provider, model = args.provider, args.model
        chat = make_chat(base, model, key, max_tokens=args.max_reply_tokens)

    html, sha = weave(pack, out)
    run = {"profile": args.profile, "pack": str(pack), "pack_name": pack.name,
           "mode": "player (text-only ARIA)" if args.text_only else "player",
           "policy": args.policy, "provider": provider, "model": model,
           "seed": args.seed, "viewport": list(vw), "settle_ms": args.settle_ms,
           "max_reply_tokens": args.max_reply_tokens, "canary": args.canary, "limits": limits.__dict__,
           "vefr": git_id(VEFR_ROOT), "pack_repo": git_id(pack), "weave_sha256": sha}
    t_start = time.monotonic()
    with sync_playwright() as pw:
        browser = launch(pw)
        run["chromium"] = browser.version
        if not text_renders(browser):
            print("this Chromium draws no text (missing fonts?): screenshots would be blank. "
                  "Install fonts or use a browser that has them.", file=sys.stderr)
            return 4
        if chat is not None and not args.text_only:
            vc = vision_check(chat, browser)
            run["vision_check"] = vc
            if not vc["ok"]:
                print(f"vision check failed: {vc['reply']!r}; rerun with --text-only "
                      "(and label the run so) or pick another model", file=sys.stderr)
                (out / "run.json").write_text(json.dumps(run, indent=2))
                return 3
        game = apl.BrowserGame(browser, html, seed=args.seed, viewport=vw, canary=args.canary,
                               settle_ms=args.settle_ms)
        policy = apl.ModelPolicy(chat, system) if chat else apl.RandomPolicy(args.seed)
        st = apl.run_loop(game, policy, out, limits, system_prompt=system, text_only=args.text_only)
        # QA side, after play: which of the game's own books sit in places the hero never went.
        visited = {json.loads(ln).get("region") for ln in (out / "qa.jsonl").read_text().splitlines()}
        try:
            lib = game.page.evaluate("() => window.VEFR_LIBRARY || []") or []
        except Exception:  # noqa: BLE001
            lib = []
        hidden = [p for b in lib if b.get("region") not in visited for p in b.get("pages", [])
                  if isinstance(p, str)]
        game.close()
        browser.close()
    run["wall_seconds"] = round(time.monotonic() - t_start, 1)
    audit = apl.leak_audit(out, hidden, args.canary)
    trace = [json.loads(ln) for ln in (out / "trace.jsonl").read_text().splitlines() if ln.strip()]
    fr = final_report(chat, system, trace, st.journal) if chat else None
    lat = sorted(r["latency_ms"] for r in trace if r.get("latency_ms") is not None)
    run.update({"stop": st.stop, "decisions": st.step, "inputs": st.inputs, "journal": st.journal,
                "leak_audit": audit, "final_report": fr,
                "usage": {"play_in": st.tokens_in, "play_out": st.tokens_out,
                          "report_in": (fr or {}).get("tokens_in") or 0,
                          "report_out": (fr or {}).get("tokens_out") or 0,
                          "median_latency_ms": lat[len(lat) // 2] if lat else None}})
    run["usage"]["tokens_in"] = run["usage"]["play_in"] + run["usage"]["report_in"]
    run["usage"]["tokens_out"] = run["usage"]["play_out"] + run["usage"]["report_out"]
    argv_s = " ".join(a if " " not in a else repr(a) for a in (argv or sys.argv[1:]))
    run["reproduce"] = (f"git -C <vefr> checkout {run['vefr']['sha']}\n"
                        f"git -C <pack repo> checkout {run['pack_repo']['sha']}\n"
                        f"uv run --group test python experiments/agent-player/play.py {argv_s}\n"
                        f"# keys only, no model:\n"
                        f"uv run --group test python experiments/agent-player/replay.py {out}")
    (out / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    (out / "report.md").write_text(render_report(run, trace, fr, audit), encoding="utf-8")
    (out / "game.html").unlink(missing_ok=True)
    print(f"{run['decisions']} decisions, {run['inputs']} inputs, stop: {run['stop']}; "
          f"leak audit {'PASS' if audit['ok'] else 'FAIL'}; report: {out / 'report.md'}")
    return 0 if audit["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
