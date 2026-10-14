"""The touch controls on a phone: the joystick, the smart button, the Bag and B buttons, the quick slots, and Settings.

The joystick scenarios are the six the prototype was accepted against (a
land-and-step, b hold-steps, c release-stops, d no stray actions, e panel
cancels the walk, f repeated interaction, g lockout), run against the sample
world with synthetic touch PointerEvents. Movement goes from the joystick
straight to the game's move(); no key events are synthesised.
"""

from contextlib import contextmanager
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
PHONE = {"width": 390, "height": 844}

SCENARIO_NAMES = [
    "a-land-and-step",
    "b-hold-steps",
    "c-release-stops",
    "d-no-stray-actions",
    "e-panel-cancels",
    "f-repeated-interaction",
    "g-lockout",
]

SCENARIOS = r"""
async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const JOY = { x: 100, y: 700 };
  const ev = (type, x, y, id) => new PointerEvent(type, { pointerId: id, clientX: x, clientY: y,
    bubbles: true, cancelable: true, pointerType: 'touch', isPrimary: id === 1 });
  const down = (x, y) => document.getElementById('touch-zone').dispatchEvent(ev('pointerdown', x, y, 1));
  const move = (x, y) => window.dispatchEvent(ev('pointermove', x, y, 1));
  const up = (x, y) => window.dispatchEvent(ev('pointerup', x, y, 1));
  const log = () => window.__vefrTouch.log.slice();
  const steps = (es) => es.filter((e) => e.kind === 'step');
  const acts = (es) => es.filter((e) => e.kind === 'action');
  const tally = (es) => { const c = {}; for (const e of es) c[e.kind] = (c[e.kind] || 0) + 1; return JSON.stringify(c); };
  const results = [];
  const scen = async (name, body, judge) => {
    const from = log().length;
    let info = {};
    try { info = (await body()) || {}; } catch (err) { results.push({ name, pass: false, detail: 'body threw ' + err }); return; }
    const es = log().slice(from);
    const v = judge(es, info);
    results.push({ name, pass: !!v.pass, detail: v.detail });
  };
  const tapStep = async (dx, dy) => { down(JOY.x, JOY.y); move(JOY.x + dx, JOY.y + dy); await sleep(40); up(JOY.x + dx, JOY.y + dy); };
  results.push({ name: 'boot', pass: !!window.__vefrTouch, detail: 'instrumentation present' });
  results.push({ name: 'in-game', pass: getComputedStyle(document.getElementById('touch-zone')).display === 'block',
                 detail: 'zone display ' + getComputedStyle(document.getElementById('touch-zone')).display });
  await scen('a-land-and-step', async () => {
    down(JOY.x, JOY.y); move(JOY.x + 50, JOY.y); await sleep(50); up(JOY.x + 50, JOY.y);
  }, (es) => {
    const s = steps(es);
    return { pass: s.length === 1 && s[0].dir === 'right' && acts(es).length === 0,
             detail: `${s.length} step(s) ${s.map((x) => x.dir).join(',') || '-'}; ${tally(es)}` };
  });
  await sleep(300);
  await scen('b-hold-steps', async () => {
    down(JOY.x, JOY.y); move(JOY.x + 50, JOY.y); await sleep(1000);
    const tUp = performance.now(); up(JOY.x + 50, JOY.y); return { tUp };
  }, (es, info) => {
    const s = steps(es);
    const gaps = s.slice(1).map((x, i) => x.t - s[i].t);
    const held = s.length ? info.tUp - s[0].t : 0;
    const expected = 1 + Math.floor(held / 200);
    const stop = es.find((e) => e.kind === 'stop');
    const lag = stop ? stop.t - info.tUp : Infinity;
    const even = gaps.every((g) => g >= 150 && g <= 260);
    return { pass: s.length > 0 && Math.abs(s.length - expected) <= 1 && even && lag >= 0 && lag <= 60,
             detail: `${s.length} steps over ${Math.round(held)} ms (expected ${expected} +-1), gaps [${gaps.map(Math.round).join(', ')}], stop ${Math.round(lag)} ms after release` };
  });
  await scen('c-release-stops', async () => { await sleep(600); }, (es) => {
    return { pass: steps(es).length === 0, detail: `${steps(es).length} step(s) after release; ${tally(es)}` };
  });
  await scen('d-no-stray-actions', async () => {
    down(JOY.x, JOY.y); const started = Date.now();
    for (let k = 0; Date.now() - started < 1500; k++) {
      const a = (k * 2 * Math.PI) / 60;
      move(JOY.x + 50 * Math.cos(a), JOY.y + 50 * Math.sin(a)); await sleep(16);
    }
    up(JOY.x, JOY.y);
  }, (es) => {
    return { pass: steps(es).length > 0 && acts(es).length === 0,
             detail: `${steps(es).length} step(s), ${acts(es).length} action(s)` };
  });
  await sleep(300);
  await scen('e-panel-cancels', async () => {
    down(JOY.x, JOY.y); move(JOY.x - 50, JOY.y); await sleep(300);
    document.getElementById('touch-bag').click();
    await sleep(800);
    up(JOY.x - 50, JOY.y);
    const bagOpen = !document.getElementById('menu').hidden;
    const b = document.getElementById('touch-b');
    const bShown = getComputedStyle(b).display !== 'none';
    b.click();
    await sleep(100);
    return { bagOpen, bShown, menuHiddenAfterB: document.getElementById('menu').hidden };
  }, (es, info) => {
    const blocked = es.findIndex((e) => e.kind === 'blocked');
    const before = blocked < 0 ? steps(es) : steps(es.slice(0, blocked));
    const after = blocked < 0 ? [] : steps(es.slice(blocked));
    return { pass: info.bagOpen && info.bShown && info.menuHiddenAfterB && before.length >= 1 && after.length === 0,
             detail: `${before.length} step(s) before the bag, ${after.length} after; bag open ${info.bagOpen}; B shown ${info.bShown}; menu closed by B ${info.menuHiddenAfterB}` };
  });
  await scen('f-repeated-interaction', async () => {
    const dirs = [[1, 0], [0, 1], [-1, 0], [0, -1]];
    const sm = document.getElementById('touch-smart');
    let reached = !sm.classList.contains('gbtn--dim');
    let d = 0; const seq = [];
    for (let len = 1; seq.length < 80; len++) for (let leg = 0; leg < 2; leg++) { for (let i = 0; i < len; i++) seq.push(dirs[d]); d = (d + 1) % 4; }
    for (let i = 0; !reached && i < seq.length; i++) {
      await tapStep(seq[i][0] * 50, seq[i][1] * 50); await sleep(250);
      reached = !sm.classList.contains('gbtn--dim');
    }
    const label = sm.getAttribute('aria-label');
    const holdFrom = log().length;
    const r = sm.getBoundingClientRect();
    sm.dispatchEvent(ev('pointerdown', r.x + r.width / 2, r.y + r.height / 2, 1));
    await sleep(1500);
    sm.click();
    return { reached, label, holdFrom };
  }, (es, info) => {
    const n = acts(log().slice(info.holdFrom)).length;
    return { pass: !!info.reached && n === 1,
             detail: `${info.reached ? `reached "${info.label}"` : 'no interactable reached'}; ${n} action(s) across hold` };
  });
  await scen('g-lockout', async () => {
    await sleep(400);
    const sm = document.getElementById('touch-smart');
    sm.click(); sm.click();
    await sleep(400);
  }, (es) => {
    return { pass: acts(es).length === 1 && es.some((e) => e.kind === 'blocked' && e.reason === 'lockout'),
             detail: `${acts(es).length} action(s) from two clicks inside 300 ms` };
  });
  return results;
}
"""


@pytest.fixture(scope="module")
def woven_sample(tmp_path_factory):
    d = tmp_path_factory.mktemp("touch-sample")
    html = d / "sample.html"
    html.write_text(cli.weave_html(ROOT / "worlds" / "sample-world"), encoding="utf-8")
    return html


def enter(page):
    page.click("#ts-enter")
    if page.is_visible("#config"):
        page.click("#cfg-save")
    page.wait_for_function("window.VEFR_COMBAT", timeout=15000)
    page.wait_for_timeout(500)


@contextmanager
def touch_phone(browser, woven, size=PHONE):
    ctx = browser.new_context(viewport=size, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    try:
        page.goto(woven.as_uri())
        enter(page)
        yield page
    finally:
        ctx.close()


def open_display(page):
    page.click("#menu-open")
    page.click('[data-panel="display"]')


def close_menu(page):
    """Back to play: the controls hide while a panel is open, and Escape from Display only returns to the menu."""
    page.click("#menu-close")
    page.wait_for_timeout(150)


SHOWN = """id => getComputedStyle(document.getElementById(id)).display !== 'none'"""
RECT = """id => { const r = document.getElementById(id).getBoundingClientRect();
                  return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; }"""


@pytest.fixture(scope="module")
def joystick_run(browser, woven_sample):
    ctx = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    try:
        page.goto(woven_sample.as_uri())
        enter(page)
        results = page.evaluate(SCENARIOS)
        yield {"results": {r["name"]: r for r in results}, "errors": errors}
    finally:
        ctx.close()


def test_the_touch_layer_is_live_in_game(joystick_run):
    res = joystick_run["results"]
    assert res["boot"]["pass"], res["boot"]["detail"]
    assert res["in-game"]["pass"], res["in-game"]["detail"]


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_joystick_scenario(joystick_run, name):
    res = joystick_run["results"][name]
    assert res["pass"], f"{name}: {res['detail']}"


def test_no_page_errors_during_the_touch_scenarios(joystick_run):
    assert not joystick_run["errors"], joystick_run["errors"][:5]


def test_a_fine_pointer_gets_no_touch_layer(browser, woven_sample):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    page = ctx.new_page()
    try:
        page.goto(woven_sample.as_uri())
        enter(page)
        info = page.evaluate("""() => {
          const shown = id => getComputedStyle(document.getElementById(id)).display !== 'none';
          return { zone: shown('touch-zone'), cluster: shown('touch-cluster'), settings: shown('touch-settings'),
                   interact: shown('interact'), classes: [...document.body.classList] };
        }""")
        assert not info["zone"] and not info["cluster"] and not info["settings"], info
        assert info["interact"], "the desktop Interact button is not shown"
        assert not [c for c in info["classes"] if c.startswith("touch-")], info["classes"]
    finally:
        ctx.close()


def test_the_joystick_is_the_default_and_the_d_pad_setting_swaps_it(browser, woven_sample):
    with touch_phone(browser, woven_sample) as page:
        assert page.evaluate(SHOWN, "touch-zone")
        assert not page.evaluate("document.body.classList.contains('touch-dpad')")
        open_display(page)
        page.check('input[name="touch-move"][value="dpad"]')
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        assert page.evaluate("document.body.classList.contains('touch-dpad')")
        assert page.evaluate(SHOWN, "touch-zone") is False
        assert page.evaluate("getComputedStyle(document.querySelector('#stage .dpad')).display") == "grid"
        page.reload()
        enter(page)
        assert page.evaluate("document.body.classList.contains('touch-dpad')"), \
            "the D-pad choice did not survive a reload"
        assert page.evaluate(SHOWN, "touch-zone") is False


def test_control_size_scales_the_buttons_with_a_48px_floor(browser, woven_sample):
    with touch_phone(browser, woven_sample) as page:
        open_display(page)
        page.fill("#touch-size", "150")
        scale = page.evaluate("parseFloat(document.body.style.getPropertyValue('--touch-scale'))")
        assert scale == pytest.approx(1.5)
        assert page.inner_text("#touch-size-out") == "150%"
        close_menu(page)
        assert page.evaluate(RECT, "touch-smart")["w"] == pytest.approx(108, abs=1)
        open_display(page)
        page.fill("#touch-size", "75")
        assert page.inner_text("#touch-size-out") == "75%"
        close_menu(page)
        smart = page.evaluate(RECT, "touch-smart")
        bag = page.evaluate(RECT, "touch-bag")
        assert smart["w"] >= 48 and bag["w"] >= 48, f"touch buttons below the 48 px floor: smart {smart}, bag {bag}"
        page.reload()
        enter(page)
        open_display(page)
        assert page.inner_text("#touch-size-out") == "75%", "the control size did not survive a reload"


def test_left_handed_mirrors_the_joystick_and_the_cluster(browser, woven_sample):
    with touch_phone(browser, woven_sample) as page:
        width = page.evaluate("innerWidth")
        zone = page.evaluate(RECT, "touch-zone")
        cluster = page.evaluate(RECT, "touch-cluster")
        assert zone["l"] <= 1 and cluster["r"] >= width - 14, "right-handed layout is not the default"
        open_display(page)
        page.check("#touch-left")
        close_menu(page)
        assert page.evaluate("document.body.classList.contains('touch-left')")
        zone = page.evaluate(RECT, "touch-zone")
        cluster = page.evaluate(RECT, "touch-cluster")
        assert zone["r"] >= width - 1, f"the joystick zone did not move to the right: {zone}"
        assert cluster["l"] <= 14, f"the cluster did not move to the left: {cluster}"
        page.reload()
        enter(page)
        assert page.evaluate("document.body.classList.contains('touch-left')"), \
            "left-handed did not survive a reload"


def test_a_phone_shows_two_buttons_on_the_world(browser, woven_sample):
    """The world keeps the screen: the smart button and Bag are the only buttons over it (owner, 2026-10-13).
    Listen and Explore were a phone's taps for Q and O (issue #431); they confused a player, so a phone no
    longer draws them; the keyboard keeps both, and the Journal, where whispers are kept, asks for one."""
    with touch_phone(browser, woven_sample) as page:
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        shown = page.evaluate("""() => [...document.querySelectorAll('.touch-cluster button')]
          .filter(b => b.getClientRects().length > 0).map(b => b.id)""")
        assert sorted(shown) == ["touch-bag", "touch-smart"], f"buttons over the world: {shown}"
        page.keyboard.press("o")
        page.wait_for_timeout(150)
        assert page.get_attribute("#explore", "aria-pressed") == "true", "O no longer explores"
        page.keyboard.press("o")
        # The Journal keeps the whispers and asks for one itself.
        page.tap("#menu-open")
        page.tap("#journal-whisper")
        page.wait_for_function("!document.getElementById('npc-box').hidden", timeout=5000)
        assert page.evaluate("document.getElementById('menu').hidden"), "the menu stayed over the whisper"
        assert page.inner_text("#npc-line").strip(), "the Journal's whisper opened an empty speech box"
        # Issue #470: the rumor is overheard, not said to whoever is standing here.
        assert page.inner_text("#npc-name").startswith("You overhear "), page.inner_text("#npc-name")
        assert not errors, errors[:5]


def test_the_first_run_hint_names_what_a_phone_shows(browser, woven_sample):
    """Issue #431: a phone has no Talk button; the hint names the round smart button, which says Talk near someone."""
    with touch_phone(browser, woven_sample) as page:
        hint = page.inner_text("#status")
        assert hint == "Move on the left. Near someone, tap the round button.", hint
        assert page.evaluate(SHOWN, "touch-smart"), "the hint names a button the phone does not show"


def test_a_drag_on_the_map_never_moves_the_page(browser, woven_sample):
    """A real touch drag (not a synthetic PointerEvent) on the play area is held.

    touch-action: none is the first guard; some phone browsers still rubber-band
    the page or pull to refresh past it, so the page also refuses to overscroll
    and the play area cancels its own touchmoves.
    """
    with touch_phone(browser, woven_sample) as page:
        page.evaluate("""() => { window.__held = [0, 0];
          document.addEventListener('touchmove', e => { window.__held[e.defaultPrevented ? 0 : 1]++; }); }""")
        cdp = page.context.new_cdp_session(page)
        x, y = PHONE["width"] - 60, PHONE["height"] // 2
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        for i in range(1, 8):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y - 40 * i}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        page.wait_for_timeout(200)
        info = page.evaluate("""() => ({ held: window.__held, scroll: [scrollX, scrollY],
          html: getComputedStyle(document.documentElement).overscrollBehaviorY,
          body: getComputedStyle(document.body).overflow })""")
        assert info["held"][0] > 0 and info["held"][1] == 0, info
        assert info["scroll"] == [0, 0], info
        assert info["html"] == "none" and info["body"] == "hidden", info
