"""Agent Player Lab: actions, limits, stop rules and information leakage.

    uv run --group test pytest experiments/agent-player/test_agent_player.py -q

The browser test needs Chromium (`APL_CHROMIUM=<path>` to point at one).
"""

import ast
import inspect
import json
import os
import textwrap

import pytest

import apl


# ---- the closed vocabulary ----------------------------------------------
@pytest.mark.parametrize("action,keys", [
    ({"type": "move", "dir": "left", "steps": 3}, ["ArrowLeft"] * 3),
    ({"type": "move", "dir": "up"}, ["ArrowUp"]),
    ({"type": "interact"}, ["f"]),
    ({"type": "talk"}, ["e"]),
    ({"type": "confirm"}, ["Enter"]),
    ({"type": "back"}, ["Escape"]),
    ({"type": "wait"}, []),
])
def test_valid_actions_map_to_keys(action, keys):
    assert apl.keys_for(apl.validate_action(action)) == keys


@pytest.mark.parametrize("action", [
    {"type": "teleport"},
    {"type": "move", "dir": "north"},
    {"type": "move", "dir": "up", "steps": 6},
    {"type": "move", "dir": "up", "steps": 0},
    {"type": "move", "dir": "up", "steps": "2"},
    {"type": "move", "dir": "up", "steps": True},
    {"type": "talk", "to": "the cat"},
    {"type": "press", "key": "F12"},
    {"type": "finish"},
    {"type": "finish", "reason": "  "},
    "talk",
    None,
])
def test_anything_else_is_refused(action):
    with pytest.raises(apl.ActionError):
        apl.validate_action(action)


def test_parse_decision_is_strict():
    d = apl.parse_decision('sure! {"thought": "t", "action": {"type": "talk"}, "note": "n"}')
    assert d == {"thought": "t", "action": {"type": "talk"}, "note": "n"}
    for bad in ["no json here", '{"thought": "x"}', '{"action": {"type": "talk"}, "eval": "x"}',
                '{"action": {"type": "talk"}']:
        with pytest.raises(apl.ActionError):
            apl.parse_decision(bad)


def test_thinking_blocks_are_ignored():
    reply = '<think>maybe {"action": {"type": "back"}}</think>{"action": {"type": "talk"}}'
    assert apl.parse_decision(reply)["action"] == {"type": "talk"}
    with pytest.raises(apl.ActionError):  # cut off mid-thought: no decision, not a guess
        apl.parse_decision('<think>I will {"action": {"type": "talk"}} and')


# ---- the loop, against a fake game --------------------------------------
class FakeGame:
    """Stands in for the browser.  `moves` makes the screen change on arrow keys."""

    def __init__(self, changes=True, error_at=None):
        self.keys, self.errors, self.n = [], [], 0
        self.changes, self.error_at = changes, error_at

    def observe(self):
        aria = f"- status: tick {self.n if self.changes else 0}"
        return {"aria": aria, "png": b"x", "image": b"x",
                "aria_digest": apl.digest(aria), "png_digest": "p"}

    def qa(self):
        return {"region": "secret-room", "at": [1, 2]}

    def press(self, k):
        self.keys.append(k)
        self.n += 1
        if self.error_at and len(self.keys) >= self.error_at:
            self.errors.append("pageerror: boom")

    def idle(self, ms):
        pass

    def settle(self):
        pass

    def shot(self, path):
        path.write_bytes(b"")


def move(dir="right", steps=1):
    return json.dumps({"action": {"type": "move", "dir": dir, "steps": steps}})


def test_decision_cap(tmp_path):
    st = apl.run_loop(FakeGame(), apl.ScriptedPolicy([move()] * 60), tmp_path, apl.Limits(decisions=50))
    assert st.step == 50 and st.stop.startswith("decision cap")


def test_input_cap_counts_every_key_and_truncates(tmp_path):
    g = FakeGame()
    st = apl.run_loop(g, apl.ScriptedPolicy([move(steps=5)] * 40), tmp_path, apl.Limits(inputs=12))
    assert len(g.keys) == 12 and st.inputs == 12 and st.stop.startswith("key-input cap")
    last = [json.loads(ln) for ln in (tmp_path / "trace.jsonl").read_text().splitlines()][-1]
    assert last["truncated"] is True


def test_two_malformed_replies_stop(tmp_path):
    st = apl.run_loop(FakeGame(), apl.ScriptedPolicy(["nope", "still nope"]), tmp_path, apl.Limits())
    assert st.stop == "2 malformed replies in a row"


def test_one_malformed_reply_is_forgiven(tmp_path):
    st = apl.run_loop(FakeGame(), apl.ScriptedPolicy(["nope", move(), "nope", move()]), tmp_path,
                      apl.Limits(decisions=4))
    assert st.stop.startswith("decision cap")


def test_unchanged_screens_stop_as_evidence(tmp_path):
    st = apl.run_loop(FakeGame(changes=False), apl.ScriptedPolicy([move()] * 20), tmp_path,
                      apl.Limits(unchanged_in_a_row=8))
    assert st.step == 8 and "kept as player evidence" in st.stop


def test_page_error_stops(tmp_path):
    st = apl.run_loop(FakeGame(error_at=3), apl.ScriptedPolicy([move()] * 10), tmp_path, apl.Limits())
    assert st.stop.startswith("page error")


def test_token_budget_stops(tmp_path):
    reply = {"text": move(), "tokens_in": 300, "tokens_out": 10}
    st = apl.run_loop(FakeGame(), apl.ScriptedPolicy([reply] * 10), tmp_path, apl.Limits(input_tokens=1000))
    assert st.step == 4 and st.stop.startswith("input-token budget")


def test_wall_clock_stops(tmp_path):
    t = iter(range(0, 10_000, 100))
    st = apl.run_loop(FakeGame(), apl.ScriptedPolicy([move()] * 50), tmp_path,
                      apl.Limits(wall_seconds=250), clock=lambda: next(t))
    assert st.stop.startswith("wall-clock cap")


def test_agent_may_finish_early(tmp_path):
    fin = json.dumps({"action": {"type": "finish", "reason": "tried everything near the door"}})
    st = apl.run_loop(FakeGame(), apl.ScriptedPolicy([move(), fin]), tmp_path, apl.Limits())
    assert st.step == 2 and st.stop == "agent finished: tried everything near the door"


# ---- information leakage -------------------------------------------------
SCRIPT_CALLS = {"evaluate", "evaluate_handle", "eval_on_selector", "eval_on_selector_all",
                "add_script_tag", "expose_function", "expose_binding", "inner_html", "content"}


def test_player_observation_never_runs_page_script():
    """The player path may only screenshot and read the ARIA tree: no script, no raw DOM."""
    for fn in (apl.observe_player, apl.build_prompt, apl.make_scaler):
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        called = {n.func.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert not called & SCRIPT_CALLS, (fn.__name__, called & SCRIPT_CALLS)


def test_text_only_prompt_does_not_promise_a_picture(tmp_path):
    apl.run_loop(FakeGame(), apl.ScriptedPolicy([move()] * 2), tmp_path, apl.Limits(), text_only=True)
    prompts = [json.loads(ln) for ln in (tmp_path / "prompts.jsonl").read_text().splitlines()]
    assert prompts and all("attached image" not in p["text"] and "no picture" in p["text"] for p in prompts)


def test_qa_state_never_reaches_a_prompt(tmp_path):
    apl.run_loop(FakeGame(), apl.ScriptedPolicy([move()] * 5), tmp_path, apl.Limits())
    prompts = (tmp_path / "prompts.jsonl").read_text()
    trace = (tmp_path / "trace.jsonl").read_text()
    assert "secret-room" in (tmp_path / "qa.jsonl").read_text()
    assert "secret-room" not in prompts and "secret-room" not in trace


def test_leak_audit_catches_canaries_and_hidden_facts(tmp_path):
    fact = "A sentence that only a deep floor's book contains."
    (tmp_path / "prompts.jsonl").write_text(json.dumps({"text": "fine"}) + "\n")
    assert apl.leak_audit(tmp_path, [fact], canary=True)["ok"]
    (tmp_path / "prompts.jsonl").write_text(json.dumps({"text": apl.CANARIES["hidden"] + fact}))
    leaks = apl.leak_audit(tmp_path, [fact], canary=True)["leaks"]
    assert set(leaks) == {"canary:hidden", "hidden fact"}


FIXTURE = """<!doctype html><html><body>
<main><h1>A visible room</h1><p role="status">You see a door.</p>
<button autofocus>Open <kbd>F</kbd></button><span class="sr" style="position:absolute;left:-9999px">Screen reader hint</span>
<div hidden>Secret: the key is under the rug</div>
<div style="display:none">Undiscovered room: the vault</div></main>
<script>window.VEFR_SECRET_FLAG = "the-king-is-asleep";</script></body></html>"""


def test_browser_observation_hides_what_a_player_cannot_perceive(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    page_file = tmp_path / "fixture.html"
    page_file.write_text(FIXTURE)
    with sync_api.sync_playwright() as pw:
        exe = os.environ.get("APL_CHROMIUM")
        try:
            browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"no Chromium: {e}")
        ctx = browser.new_context(viewport={"width": 640, "height": 360})
        for js in apl.init_scripts("seed", canary=True):
            ctx.add_init_script(js)
        page = ctx.new_page()
        page.goto(page_file.as_uri())
        obs = apl.observe_player(page, apl.make_scaler(browser, 320, 180))
        browser.close()
    aria = obs["aria"]
    assert "You see a door." in aria and "Screen reader hint" in aria
    assert "Open" in obs["focus"]
    for secret in ["under the rug", "the vault", "the-king-is-asleep", *apl.CANARIES.values()]:
        assert secret not in aria
    assert obs["image"][:2] == b"\xff\xd8"  # a JPEG thumbnail, not the full PNG
