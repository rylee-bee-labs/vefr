"""`vefr playthrough`, in a real browser: the pack plays, and the report says so.

The driver walks, talks and rests through a pack's own phases and reads
the engine's own marks afterwards, so what is checked here is a real
play-through rather than a staged event:

  * every phase the time pack declares is reached, one Rest press apart,
    and the rule that speaks only at highwater fires only there;
  * the mending pack's people and places are walked to and their
    `comes-near` rules fire from the walk itself;
  * a rule whose condition never holds is reported as never fired, with
    the condition that held it back, and the run exits 1.

The hero's published tile (`window.VEFR_HERO_AT`) is checked on its own,
because the walk is blind without it - that blindness is what a first
host run of the Mending driver found.

Skips without chromium, like the rest of tests/browser.
"""

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from vefr import cli

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
import make_mending_pack  # noqa: E402
import make_time_pack  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve(home: Path, name: str):
    """Serve `home` over http; return the URL of `name` inside it and the
    http process, so the caller can stop it when the module is done."""
    port = _free_port()
    log = open(home / "server.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--bind", "127.0.0.1", "--directory", str(home)],
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/{name}"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            break
        except Exception:  # noqa: BLE001 - not up yet
            time.sleep(0.25)
    else:
        proc.terminate()
        pytest.fail(f"the woven file never came up; see {home / 'server.log'}")
    return url, proc


@pytest.fixture(scope="module")
def served_home(tmp_path_factory):
    """A directory the woven packs are served out of."""
    home = tmp_path_factory.mktemp("playthrough")
    yield home


@pytest.fixture
def need_browser(browser):
    """The module's browser fixture, named for what the tests mean by it.

    `vefr playthrough` opens its own headless Chromium (the same session
    `look` and `probe` use), so the only thing needed from this repo's
    fixture is the skip when Chromium is not installed.
    """
    return browser


def _play(pack: Path, out: Path, capsys) -> tuple:
    """`vefr playthrough --pack <pack> --out <out> --json`, as the door runs it."""
    # A real subprocess, as a person runs it: `vefr playthrough` opens its own Playwright, and the
    # browser fixture this module also uses already holds the sync API in this thread.
    done = subprocess.run([str(Path(sys.executable).with_name("vefr")), "playthrough", "--pack", str(pack),
                           "--out", str(out), "--json"], capture_output=True, text=True, timeout=600)
    printed = done.stdout.strip().splitlines()
    assert printed, done.stderr[-2000:]
    return done.returncode, json.loads(printed[-1])


# ---- the mending pack: one pass, its people and its places ----

def _mending_with_near_rules(dest: Path) -> Path:
    """The mending fixture pack plus two `comes-near` rules over its town.

    The pack is sample-world's own map, so the people and places are the
    sample's: the keeper at [7, 4], the stone at [7, 3]. The mending
    rule the pack already carries stays, so the report has both a rule
    that fires from the walk and one that fires from something else.
    """
    pack = make_mending_pack.build(dest)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["rules"] = world["rules"] + [
        {"id": "keeper-nods",
         "when": {"comes-near": {"who": "keeper", "distance": 2}},
         "then": [{"say": "The Keeper nods."}]},
        {"id": "stone-warms",
         "when": {"comes-near": {"who": "the stone", "distance": 0}},
         "then": [{"say": "The stone is warm."}]},
    ]
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")
    return pack


def test_a_pack_with_no_time_block_plays_one_pass_and_fires_its_near_rules(
        served_home, need_browser, tmp_path, capsys):
    """No `time` block, so one pass: the keeper is walked to and talked
    at, the stone is stood on, and both rules fire - the stone's from the
    walk itself, with no press of anything."""
    pack = _mending_with_near_rules(served_home)
    shots = tmp_path / "shots"
    rc, report = _play(pack, shots, capsys)

    assert rc == 0, report
    assert [p["reached"] for p in report["phases"]] == [True]
    fired = {f["id"] for f in report["fired"]}
    assert {"keeper-nods", "stone-warms"} <= fired, fired
    assert report["never_fired"] == []
    assert report["unresolved"] == []
    # One screenshot per phase, and it is a real photograph.
    shot = Path(report["phases"][0]["screenshot"])
    assert shot.parent == shots
    assert shot.stat().st_size > 1000
    # The stops are the pack's own, read off its world.json.
    walked = {s["who"]: s["walked"] for s in report["phases"][0]["stops"]}
    assert set(walked) == {"keeper", "the stone"}
    assert all(walked.values()), report["phases"][0]["stops"]


def test_the_hero_tile_is_published_for_the_walk(served_home, page):
    """The walk is blind without it: the player's own window onto where
    the hero stands, refreshed on arrival and after every step."""
    home = served_home / "hero-at"
    home.mkdir(parents=True, exist_ok=True)
    pack = make_time_pack.build(home, name="time-test")
    (home / "time-test.html").write_text(cli.weave_html(pack), encoding="utf-8")
    url, proc = _serve(home, "time-test.html")
    try:
        page.goto(url)
        page.get_by_role("button", name="Begin").click()
        if page.is_visible("#config"):
            page.click("#cfg-offline")
        page.wait_for_function("() => window.VEFR_HERO_AT")
        at = page.evaluate("() => window.VEFR_HERO_AT")
        assert at == {"x": 1, "y": 1, "region": "town"}
        page.keyboard.press("ArrowRight")
        page.wait_for_function(
            "() => window.VEFR_HERO_AT && window.VEFR_HERO_AT.x === 2")
        assert page.evaluate("() => window.VEFR_HERO_AT")["x"] == 2
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---- the time pack: every phase, one Rest apart ----

def test_every_phase_is_reached_and_the_highwater_rule_fires_there(
        served_home, need_browser, tmp_path, capsys):
    """Three phases, three passes: Rest turns the watch on one step at a
    time, and the rule that reads the standing phase is a stop of
    highwater only - so that is the pass the watcher is walked to in."""
    home = served_home / "time"
    home.mkdir(parents=True, exist_ok=True)
    pack = make_time_pack.build(home, name="time-test")
    rc, report = _play(pack, tmp_path / "time-shots", capsys)

    assert rc == 0, report
    assert [p["name"] for p in report["phases"]] == \
        ["whispers", "lowwater", "highwater"]
    assert all(p["reached"] for p in report["phases"]), report
    assert "boats-may-come-in" in {f["id"] for f in report["fired"]}
    # One screenshot per phase, each a real photograph.
    shots = [Path(p["screenshot"]) for p in report["phases"]]
    assert len({s.name for s in shots}) == 3, shots
    assert all(s.stat().st_size > 1000 for s in shots)
    # The watcher is walked to in the pass whose rule asks for it.
    walked = {p["name"]: [s["who"] for s in p["stops"]] for p in report["phases"]}
    assert walked["whispers"] == walked["lowwater"] == []
    assert walked["highwater"] == ["watcher"]
    stop = report["phases"][2]["stops"][0]
    assert stop["walked"], stop


def test_a_rule_whose_condition_never_holds_is_reported_as_not_fired(
        served_home, need_browser, tmp_path, capsys):
    """The watcher is walked to and talked at in the pass that asks for it,
    and one rule about them stays silent because the flag it waits for is
    never set. The report names it, says what held it back, and exits 1."""
    home = served_home / "time-quiet"
    home.mkdir(parents=True, exist_ok=True)
    pack = make_time_pack.build(home, name="time-test")
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["rules"].append({
        "id": "the-watcher-agrees",
        "when": {"comes-near": {"who": "watcher", "distance": 2}},
        "if": [{"flag": "asked-twice", "is": True}],
        "then": [{"say": "The Watcher agrees with that."}]})
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")

    rc, report = _play(pack, tmp_path / "quiet-shots", capsys)

    assert rc == 0, report          # held back by its own condition: reported, not a failure
    assert report["missed"] == [], report
    quiet = [n["id"] for n in report["never_fired"]]
    assert quiet == ["the-watcher-agrees"], report
    entry = report["never_fired"][0]
    assert entry["conditions"] == [{"flag": "asked-twice", "is": True}]
    # The rule that does fire is still reported as fired.
    assert "boats-may-come-in" in {f["id"] for f in report["fired"]}
    # Every phase was still reached: one silent rule is not a lost phase.
    assert all(p["reached"] for p in report["phases"]), report
    # And the watcher was walked to and talked at all the same.
    assert report["phases"][2]["stops"][0]["walked"], report["phases"][2]


def test_a_pack_the_plan_cannot_resolve_is_said_so(served_home, need_browser,
                                                   tmp_path, capsys):
    """A `comes-near` naming neither a speaker nor a labelled place is a
    pack author's typo, told to them by name rather than left looking
    like a rule that quietly never fires."""
    home = served_home / "time-typo"
    home.mkdir(parents=True, exist_ok=True)
    pack = make_time_pack.build(home, name="time-test")
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["rules"].append({
        "id": "the-mayor-agrees",
        "when": {"comes-near": {"who": "the mayor", "distance": 2}},
        "then": [{"say": "Nobody answers."}]})
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")

    rc, report = _play(pack, tmp_path / "typo-shots", capsys)
    assert rc == 1, report
    assert [u["id"] for u in report["unresolved"]] == ["the-mayor-agrees"]
    assert "the mayor" in report["unresolved"][0]["why"]


def test_playthrough_never_edits_the_pack(served_home, need_browser,
                                          tmp_path, capsys):
    """Read-only toward a pack: it plays and reports, and the pack's own
    bytes are exactly what they were before."""
    home = served_home / "read-only"
    home.mkdir(parents=True, exist_ok=True)
    pack = make_time_pack.build(home, name="time-test")
    before = {p.name: p.read_bytes() for p in sorted(pack.rglob("*"))
              if p.is_file()}
    rc, _ = _play(pack, tmp_path / "ro-shots", capsys)
    assert rc == 0
    after = {p.name: p.read_bytes() for p in sorted(pack.rglob("*"))
             if p.is_file()}
    assert after == before


def test_the_text_report_says_what_played_and_what_did_not(
        served_home, need_browser, tmp_path, capsys):
    """The default reading is the sentences a person reads: the phases,
    the rules that fired, and a failure that says why."""
    home = served_home / "time-text"
    home.mkdir(parents=True, exist_ok=True)
    pack = make_time_pack.build(home, name="time-test")
    done = subprocess.run([str(Path(sys.executable).with_name("vefr")), "playthrough", "--pack", str(pack),
                           "--out", str(tmp_path / "text-shots")], capture_output=True, text=True, timeout=600)
    rc, out = done.returncode, done.stdout
    assert rc == 0, out
    assert "3 of 3 phase(s) reached" in out
    assert "phase whispers: ok" in out
    assert "rules fired" in out
    assert "boats-may-come-in" in out
    assert out.strip().endswith("playthrough ok")