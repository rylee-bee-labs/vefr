"""Agent Player Lab: the P4 spike of #317 (ADR 0016, docs/plans/player-driver/PLAN.md).

A model plays a woven VEFR game through the controls a person has: it sees a
screenshot and the page's accessibility (ARIA) snapshot, and it answers with one
action from a closed list, which is pressed as real keys.  Nothing here is the
Player Driver: when #317's P1 lands, `observe_player` becomes its observation
facade and `keys_for` becomes its `act()`.

Two kinds of evidence are kept apart on purpose:
  player  - what the agent saw and did (`trace.jsonl`, `prompts.jsonl`, `shots/`)
  qa      - what the engine knew (`qa.jsonl`), read with page.evaluate, NEVER
            put into a prompt.  `observe_player` must not call page.evaluate;
            test_agent_player.py checks that.
"""

from __future__ import annotations

import base64
import hashlib
import json
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# ---- the closed action vocabulary --------------------------------------
# Only what the player's own UI advertises (030-shell.html: "Interact F",
# "Talk E", "Whisper Q", "Bag B", "Explore O"), plus the keys any dialog or
# menu answers to.  Anything else is refused.
DIRS = {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight"}
SINGLE = {
    "interact": "f",
    "talk": "e",
    "whisper": "q",
    "bag": "b",
    "explore": "o",
    "confirm": "Enter",
    "back": "Escape",
    "next_control": "Tab",
}
MAX_STEPS_PER_MOVE = 5
OPTIONAL = {"thought", "note"}
ACTION_HELP = """\
Reply with ONE JSON object and nothing else:
  {"thought": "<why, one or two sentences>", "action": {...}, "note": "<optional journal line>"}
"action" is exactly one of:
  {"type": "move", "dir": "up|down|left|right", "steps": 1-5}   arrow keys
  {"type": "interact"}      F  - does whatever the big on-screen button says
  {"type": "talk"}          E
  {"type": "whisper"}       Q
  {"type": "bag"}           B  - open your bag
  {"type": "explore"}       O
  {"type": "confirm"}       Enter - continue a dialog, press the focused button
  {"type": "back"}          Escape - close a dialog or menu
  {"type": "next_control"}  Tab - move keyboard focus to the next button
  {"type": "wait"}          press nothing this turn
  {"type": "finish", "reason": "<why you are stopping>"}"""


class ActionError(ValueError):
    """A decision that is not in the closed vocabulary."""


def validate_action(action) -> dict:
    """Return a clean copy of `action` or raise ActionError.  Strict: no extra keys."""
    if not isinstance(action, dict):
        raise ActionError("action must be an object")
    kind = action.get("type")
    allowed = {"type"}
    if kind == "move":
        allowed |= {"dir", "steps"}
        if action.get("dir") not in DIRS:
            raise ActionError(f"move needs dir in {sorted(DIRS)}")
        steps = action.get("steps", 1)
        if not isinstance(steps, int) or isinstance(steps, bool) or not 1 <= steps <= MAX_STEPS_PER_MOVE:
            raise ActionError(f"move steps must be an integer 1-{MAX_STEPS_PER_MOVE}")
        clean = {"type": "move", "dir": action["dir"], "steps": steps}
    elif kind in SINGLE or kind == "wait":
        clean = {"type": kind}
    elif kind == "finish":
        allowed |= {"reason"}
        reason = action.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ActionError("finish needs a reason")
        clean = {"type": "finish", "reason": reason.strip()[:500]}
    else:
        raise ActionError(f"unknown action type {kind!r}")
    extra = set(action) - allowed
    if extra:
        raise ActionError(f"unexpected fields {sorted(extra)}")
    return clean


def keys_for(action: dict) -> list[str]:
    """The physical keys one validated action presses, in order."""
    if action["type"] == "move":
        return [DIRS[action["dir"]]] * action["steps"]
    if action["type"] in SINGLE:
        return [SINGLE[action["type"]]]
    return []


def strip_thinking(text: str | None) -> str:
    """Drop `<think>` blocks (some models reason inline), closed or cut off."""
    return re.sub(r"<think>.*?(</think>|\Z)", "", text or "", flags=re.S)


def first_json_object(text: str) -> dict | None:
    """The first complete JSON object in `text`; prose or a second object after it is ignored."""
    dec = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch == "{":
            try:
                obj, _ = dec.raw_decode(text, i)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
    return None


def parse_decision(text: str) -> dict:
    """The model's reply -> {thought, action, note}.  Raises ActionError."""
    obj = first_json_object(strip_thinking(text))
    if obj is None:
        raise ActionError("no JSON object in reply")
    if "action" not in obj:
        raise ActionError("reply has no action")
    extra = set(obj) - OPTIONAL - {"action"}
    if extra:
        raise ActionError(f"unexpected fields {sorted(extra)}")
    return {
        "thought": str(obj.get("thought") or "")[:600],
        "action": validate_action(obj["action"]),
        "note": str(obj.get("note") or "")[:300],
    }


# ---- the browser side ----------------------------------------------------
# Harness-only page setup, identical for play and replay.  `Math.random` is
# seeded so line picks (270-the-woven-pool.js, 280-the-local-composer.js)
# repeat; floors are already seeded through `?vefr-seed=`.
SEED_RANDOM_JS = """(() => {
  let h = 1779033703 ^ %(n)d;
  const s = %(seed)s;
  for (let i = 0; i < s.length; i++) { h = Math.imul(h ^ s.charCodeAt(i), 3432918353); h = h << 13 | h >>> 19; }
  let a = h >>> 0;
  Math.random = function () {
    a |= 0; a = a + 0x6D2B79F5 | 0;
    let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
})();"""

# Planted only with --canary: three things a player cannot perceive.  If any
# of these strings reaches a prompt, the run fails.
CANARIES = {
    "window": "APL-CANARY-WINDOW-7f3a",
    "hidden": "APL-CANARY-HIDDEN-91c2",
    "display_none": "APL-CANARY-DISPLAYNONE-5be8",
}
CANARY_JS = """(() => {
  window.VEFR_APL_CANARY = %(window)s;
  document.addEventListener('DOMContentLoaded', () => {
    const a = document.createElement('div'); a.hidden = true; a.textContent = %(hidden)s;
    const b = document.createElement('div'); b.style.display = 'none'; b.textContent = %(display_none)s;
    document.body.append(a, b);
  });
})();"""


def init_scripts(seed: str, canary: bool) -> list[str]:
    out = [SEED_RANDOM_JS % {"seed": json.dumps(seed), "n": len(seed)}]
    if canary:
        out.append(CANARY_JS % {k: json.dumps(v) for k, v in CANARIES.items()})
    return out


def digest(data) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()[:16]


def observe_player(page, scaler=None) -> dict:
    """What a person could perceive: the rendered screen and the ARIA tree.

    NO page.evaluate here, and nothing read from window globals.  The ARIA
    snapshot leaves out `hidden`/`display:none` content and keeps screen-
    reader-only text, which a person using a screen reader does perceive.
    """
    png = page.screenshot()
    aria = page.locator("body").aria_snapshot()
    # A sighted player sees the focus ring; the ARIA snapshot doesn't say where it is.
    focused = page.locator("*:focus")
    focus = focused.first.aria_snapshot().strip() if focused.count() else ""
    small = scaler(png) if scaler else png
    return {"aria": aria, "focus": focus or "(no control has focus)", "png": png, "image": small,
            "aria_digest": digest(aria), "png_digest": digest(png)}


def make_scaler(browser, width=640, height=360):
    """Downscale a screenshot in a blank page of the same browser (no PIL needed).

    Runs in its own page, never the game's.
    """
    page = browser.new_page(viewport={"width": width, "height": height})

    def scale(png: bytes) -> bytes:
        b64 = base64.b64encode(png).decode()
        page.set_content(f'<body style="margin:0"><img src="data:image/png;base64,{b64}" '
                         f'style="width:{width}px;height:{height}px;display:block"></body>')
        return page.screenshot(type="jpeg", quality=80)
    return scale


QA_JS = """() => {
  const c = window.VEFR_COMBAT || {};
  return {region: c.region || null, at: (c.hero && c.hero.at) || null,
          hp: (c.hero && c.hero.hp) || null};
}"""


def observe_qa(page) -> dict:
    """QA only: engine state for the evidence file.  Never goes into a prompt."""
    try:
        return page.evaluate(QA_JS)
    except Exception as e:  # noqa: BLE001 - a failed read is evidence, not a crash
        return {"error": str(e)[:200]}


class BrowserGame:
    """One woven game in one fresh browser context."""

    def __init__(self, browser, html: Path, *, seed: str, viewport, canary=False,
                 settle_ms=250, reduced_motion=False):
        self.settle_ms = settle_ms
        self.errors: list[str] = []
        self.context = browser.new_context(
            viewport={"width": viewport[0], "height": viewport[1]},
            reduced_motion="reduce" if reduced_motion else "no-preference")
        for js in init_scripts(seed, canary):
            self.context.add_init_script(js)
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(
            f"console.error: {m.text}"))
        from vefr.devtools import _page_uri  # the player's own ?vefr-seed= seam
        self.page.goto(_page_uri(html, seed))
        self.page.wait_for_timeout(600)
        self.scaler = make_scaler(browser)

    def observe(self) -> dict:
        return observe_player(self.page, self.scaler)

    def qa(self) -> dict:
        return observe_qa(self.page)

    def press(self, key: str) -> None:
        self.page.keyboard.press(key)
        self.page.wait_for_timeout(self.settle_ms)

    def idle(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)

    def settle(self, step_ms: int = 300, max_ms: int = 6000) -> None:
        """Wait until the on-screen text stops changing, as a person would.

        Some controls keep going after the key (Explore walks on a timer,
        490-autoexplore.js), so a fixed wait would make the result depend on
        how long the model took to answer, and replay could not match it.
        """
        prev = self.page.locator("body").aria_snapshot()
        for _ in range(max_ms // step_ms):
            self.page.wait_for_timeout(step_ms)
            now = self.page.locator("body").aria_snapshot()
            if now == prev:
                return
            prev = now

    def shot(self, path: Path) -> None:
        self.page.screenshot(path=str(path))

    def close(self) -> None:
        self.context.close()


# ---- the loop ------------------------------------------------------------
@dataclass
class Limits:
    decisions: int = 50
    inputs: int = 150
    wall_seconds: float = 1200.0
    input_tokens: int = 400_000
    malformed_in_a_row: int = 2
    unchanged_in_a_row: int = 8   # a loop guard, logged as player evidence, not a harness failure


@dataclass
class RunState:
    step: int = 0
    inputs: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    malformed: int = 0
    unchanged: int = 0
    journal: list = field(default_factory=list)
    recent: list = field(default_factory=list)
    stop: str = ""


def describe_change(prev: dict, now: dict) -> str:
    if prev is None:
        return "first look"
    aria = prev["aria_digest"] != now["aria_digest"]
    screen = prev["png_digest"] != now["png_digest"]
    if aria and screen:
        return "the screen and the on-screen text changed"
    if aria:
        return "the on-screen text changed"
    if screen:
        return "the picture changed, the on-screen text did not"
    return "nothing visible changed"


def build_prompt(state: RunState, obs: dict, limits: Limits, last: str, text_only=False) -> str:
    """The text half of one decision.  Built ONLY from player-side data."""
    notes = "\n".join(f"- {n}" for n in state.journal[-20:]) or "- (none yet)"
    recent = "\n".join(state.recent[-6:]) or "(this is your first look)"
    return (
        f"Decision {state.step + 1} of {limits.decisions}. "
        f"Keys used so far: {state.inputs} of {limits.inputs}.\n\n"
        f"Result of your last action: {last}\n\n"
        f"Your journal:\n{notes}\n\n"
        f"Your recent actions:\n{recent}\n\n"
        f"What the screen's accessible text says now (ARIA snapshot):\n{obs['aria']}\n\n"
        f"Keyboard focus is on: {obs.get('focus') or '(unknown)'}\n\n"
        + ("There is no picture: you only have the text above. Don't describe what you can't see."
           if text_only else "The attached image is the current screen.")
    )


def run_loop(game, policy, out: Path, limits: Limits, *, clock=time.monotonic,
             system_prompt: str = "", text_only=False) -> RunState:
    """Observe, decide, act, until a stop rule fires.  Writes the player and QA files."""
    out.mkdir(parents=True, exist_ok=True)
    shots = out / "shots"
    shots.mkdir(exist_ok=True)
    trace = (out / "trace.jsonl").open("w", encoding="utf-8")
    prompts = (out / "prompts.jsonl").open("w", encoding="utf-8")
    qa = (out / "qa.jsonl").open("w", encoding="utf-8")
    st = RunState()
    start = clock()
    prev = None
    last = "none yet - the game has just opened"
    obs = game.observe()
    game.shot(shots / "000-start.png")
    seen_lines: set[str] = set(obs["aria"].splitlines())
    try:
        while True:
            if st.step >= limits.decisions:
                st.stop = f"decision cap reached ({limits.decisions})"
                break
            if st.inputs >= limits.inputs:
                st.stop = f"key-input cap reached ({limits.inputs})"
                break
            if clock() - start > limits.wall_seconds:
                st.stop = f"wall-clock cap reached ({limits.wall_seconds:.0f}s)"
                break
            if st.tokens_in >= limits.input_tokens:
                st.stop = f"input-token budget reached ({st.tokens_in})"
                break
            if game.errors:
                st.stop = f"page error: {game.errors[0][:200]}"
                break
            prompt = build_prompt(st, obs, limits, last, text_only)
            prompts.write(json.dumps({"step": st.step + 1, "system": system_prompt,
                                      "text": prompt, "image": not text_only}) + "\n")
            t0 = clock()
            reply = policy.decide(prompt, None if text_only else obs["image"])
            latency = round((clock() - t0) * 1000)
            st.tokens_in += reply.get("tokens_in") or 0
            st.tokens_out += reply.get("tokens_out") or 0
            rec = {"step": st.step + 1, "latency_ms": latency,
                   "tokens_in": reply.get("tokens_in"), "tokens_out": reply.get("tokens_out"),
                   "raw": (reply.get("text") or "")[:1200]}
            try:
                d = parse_decision(reply.get("text", ""))
            except ActionError as e:
                st.malformed += 1
                st.step += 1
                rec.update({"refused": str(e), "keys": []})
                trace.write(json.dumps(rec) + "\n")
                last = f"your reply was refused ({e}); answer with one JSON object as described"
                if st.malformed >= limits.malformed_in_a_row:
                    st.stop = f"{st.malformed} malformed replies in a row"
                    break
                continue
            st.malformed = 0
            act = d["action"]
            keys = keys_for(act)
            room = limits.inputs - st.inputs
            sent = keys[:room]
            st.step += 1
            if d["note"]:
                st.journal.append(f"(step {st.step}) {d['note']}")
            rec.update({"thought": d["thought"], "note": d["note"], "action": act,
                        "keys": sent, "truncated": len(sent) < len(keys)})
            if act["type"] == "finish":
                rec["result"] = "finished"
                trace.write(json.dumps(rec) + "\n")
                st.stop = f"agent finished: {act['reason']}"
                break
            # When the keys went in, so replay can keep the same rhythm: some UI
            # runs on real time (the message panel folds after 6 s, 110-the-library.js).
            rec["t_ms"] = round((clock() - start) * 1000)
            for k in sent:
                game.press(k)
            if act["type"] == "wait":
                game.idle(1000)
            game.settle()
            st.inputs += len(sent)
            prev, obs = obs, game.observe()
            last = describe_change(prev, obs)
            st.unchanged = st.unchanged + 1 if last == "nothing visible changed" else 0
            new_lines = [ln for ln in obs["aria"].splitlines() if ln not in seen_lines]
            seen_lines.update(new_lines)
            rec.update({"result": last, "aria_digest": obs["aria_digest"],
                        "png_digest": obs["png_digest"], "new_text": new_lines[:20],
                        "aria": obs["aria"], "errors": list(game.errors)})
            if new_lines and any("dialog" in ln or "heading" in ln for ln in new_lines) \
                    or st.step % 10 == 0:
                name = f"{st.step:03d}.png"
                game.shot(shots / name)
                rec["shot"] = f"shots/{name}"
            trace.write(json.dumps(rec) + "\n")
            qa.write(json.dumps({"step": st.step, **game.qa()}) + "\n")
            summary = f"{st.step}. {json.dumps(act)} -> {last}"
            st.recent.append(summary)
            if st.unchanged >= limits.unchanged_in_a_row:
                st.stop = (f"{st.unchanged} actions in a row changed nothing visible "
                           "(kept as player evidence)")
                break
    finally:
        try:
            game.shot(shots / "999-end.png")
        except Exception:  # noqa: BLE001
            pass
        trace.close()
        prompts.close()
        qa.close()
    return st


# ---- policies ------------------------------------------------------------
class RandomPolicy:
    """No model: a seeded random choice over the vocabulary.  For plumbing runs."""

    def __init__(self, seed: str):
        self.rng = random.Random(seed)

    def decide(self, prompt, image) -> dict:
        kind = self.rng.choice(["move"] * 6 + sorted(SINGLE) + ["wait"])
        act = {"type": kind}
        if kind == "move":
            act.update({"dir": self.rng.choice(sorted(DIRS)), "steps": self.rng.randint(1, 3)})
        return {"text": json.dumps({"thought": "random", "action": act})}


class ScriptedPolicy:
    """Tests: replies are given in advance."""

    def __init__(self, replies):
        self.replies = list(replies)

    def decide(self, prompt, image) -> dict:
        r = self.replies.pop(0) if self.replies else '{"action": {"type": "finish", "reason": "script ended"}}'
        return r if isinstance(r, dict) else {"text": r}


class ModelPolicy:
    """One OpenAI-compatible chat call per decision.  Stateless: each call is
    the system prompt plus one user message, so cost per decision is bounded."""

    def __init__(self, chat, system_prompt: str):
        self.chat = chat
        self.system = system_prompt

    def decide(self, prompt, image) -> dict:
        content = [{"type": "text", "text": prompt}]
        if image is not None:
            b64 = base64.b64encode(image).decode()
            content.append({"type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        return self.chat([{"role": "system", "content": self.system},
                          {"role": "user", "content": content}])


# ---- leak audit ----------------------------------------------------------
def leak_audit(out: Path, hidden_facts: list[str], canary: bool) -> dict:
    """Search every prompt the agent was sent for things it must not have seen."""
    text = (out / "prompts.jsonl").read_text(encoding="utf-8")
    found = {}
    if canary:
        for name, value in CANARIES.items():
            if value in text:
                found[f"canary:{name}"] = value
    for fact in hidden_facts:
        if len(fact) >= 24 and fact in text:
            found["hidden fact"] = fact[:80]
    return {"canary_planted": canary, "hidden_facts_checked": len(hidden_facts),
            "leaks": found, "ok": not found}
