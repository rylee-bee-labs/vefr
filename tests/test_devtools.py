"""vefr publish / look / probe, and doctor's tooling rows (src/vefr/devtools.py).

The verbs are thin: `cmd_publish`, `cmd_look`, `cmd_probe` in vefr.cli hand
their args to vefr.devtools (the way cmd_find hands to vefr.find); the front
door contract is pinned in tests/test_cli_help.py. Hermetic: publish runs
against a fake gallery script; look/probe need Playwright + Chromium and skip
without them (VEFR_BROWSER_REQUIRED=1 makes a missing browser a failure).
"""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import vefr.cli as cli
from vefr import devtools

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))


# ---------------------------------------------------------------- publish

@pytest.fixture
def fake_gallery(tmp_path, monkeypatch):
    out = tmp_path / "gal"
    out.mkdir()
    script = tmp_path / "fake-gallery"
    script.write_text(
        "#!/usr/bin/env bash\n"
        f'OUT="{out}"\n'
        'printf "%s\\n" "$@" > "$OUT/args"\n'
        'stat -c %a "$3" > "$OUT/mode"\n'
        'test -f "$3/index.html" && echo yes > "$OUT/idx"\n'
        'exit 0\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("VEFR_GALLERY", str(script))
    return out


def _publish(**kw):
    base = dict(pack=str(SAMPLE), project=None, sha=None, live=False,
                dry_run=False)
    base.update(kw)
    return cli.cmd_publish(SimpleNamespace(**base))


def test_publish_weaves_into_a_readable_dir_and_calls_the_gallery(fake_gallery):
    assert _publish(sha="abc1234") == 0
    args = (fake_gallery / "args").read_text().split()
    assert args[:3] == ["build", "sample-world", args[2]]   # project = pack dir name
    assert args[args.index("--sha") + 1] == "abc1234"
    assert "--live" not in args
    assert (fake_gallery / "idx").read_text().strip() == "yes"
    assert (fake_gallery / "mode").read_text().strip() == "755"   # not mktemp's 700


def test_publish_flags(fake_gallery):
    assert _publish(project="my-game", sha="abc1234", live=True) == 0
    args = (fake_gallery / "args").read_text().split()
    assert args[1] == "my-game" and "--live" in args


def test_publish_sha_defaults_to_the_packs_git_head(fake_gallery, tmp_path):
    repo = tmp_path / "game"
    shutil_copy = __import__("shutil").copytree
    shutil_copy(SAMPLE, repo / "worlds" / "sample-world")
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True)  # noqa: E731
    run("git", "init", "-q")
    run("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
        "-q", "--allow-empty", "-m", "x")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()
    assert _publish(pack=str(repo / "worlds" / "sample-world")) == 0
    args = (fake_gallery / "args").read_text().split()
    assert args[args.index("--sha") + 1] == head


def test_publish_dry_run_does_not_call_the_gallery(fake_gallery, capsys):
    assert _publish(sha="abc1234", dry_run=True) == 0
    assert not (fake_gallery / "args").exists()
    assert "build sample-world" in capsys.readouterr().out


def test_publish_without_a_gallery_says_so(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("VEFR_GALLERY", str(tmp_path / "nope"))
    assert _publish(sha="abc1234") == 2
    assert "gallery" in capsys.readouterr().err.lower()


# ---------------------------------------------------- look / probe (browser)

def _need_browser():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as e:      # noqa: BLE001
        if os.environ.get("VEFR_BROWSER_REQUIRED") == "1":
            pytest.fail(f"browser required but unavailable: {e}")
        pytest.skip(f"no Chromium for Playwright: {e}")


@pytest.fixture(scope="module")
def woven(tmp_path_factory):
    out = tmp_path_factory.mktemp("devtools") / "sample.html"
    out.write_text(cli.weave_html(SAMPLE), encoding="utf-8")
    return out


def test_look_writes_a_screenshot_and_lists_text_over_the_map(woven, tmp_path, capsys):
    _need_browser()
    png = tmp_path / "look.png"
    rc = cli.cmd_look(SimpleNamespace(
        html=str(woven), pack=None, out=str(png), steps="ArrowDown,ArrowRight",
        json=True))
    assert rc == 0
    assert png.stat().st_size > 1000
    report = json.loads(capsys.readouterr().out)
    assert report["screenshot"] == str(png)
    ids = {e["id"] for e in report["overlay_text"]}
    assert "status" in ids                  # the how-to-move line the player shows
    for e in report["overlay_text"]:
        assert set(e) >= {"id", "text", "y"}


def test_probe_fires_events_and_prints_the_why_records(tmp_path, capsys):
    _need_browser()
    import make_events_pack
    pack = make_events_pack.build(tmp_path)
    html = tmp_path / "events.html"
    html.write_text(cli.weave_html(pack), encoding="utf-8")
    rc = cli.cmd_probe(SimpleNamespace(
        html=str(html), pack=None,
        fire=["reads:what=the-fixture-note"], json=True))
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    ids = [w["id"] for w in report["why"]]
    assert "the-note-closed" in ids
    assert report["flags"].get("read-it") is True
    assert report["fired"][0]["event"] == "reads"


def test_probe_rejects_a_malformed_fire_spec(tmp_path, capsys):
    rc = cli.cmd_probe(SimpleNamespace(
        html=str(tmp_path / "x.html"), pack=None, fire=["nonsense"], json=True))
    assert rc == 2
    assert "event:key=value" in capsys.readouterr().err


# ------------------------------------------------------------ playthrough

def test_the_plan_is_read_off_the_pack_not_written_here(tmp_path):
    """Every phase the time pack declares, and the one stop its only
    `comes-near` rule asks for - the watcher, one tile's reach, in the
    phase the rule's own `if` names. Nothing in the plan knows the pack
    by heart: a second pack's phases come out the same way."""
    import make_time_pack

    pack = make_time_pack.build(tmp_path)
    plan = devtools.playthrough_plan(pack)
    assert plan["rest"] is True
    assert [p["name"] for p in plan["phases"]] == ["whispers", "lowwater", "highwater"]
    high = plan["phases"][2]
    assert [s["who"] for s in high["stops"]] == ["watcher"]
    assert high["stops"][0]["kind"] == "speaker"
    assert high["stops"][0]["rules"] == ["boats-may-come-in"]
    # A rule whose `if` names one phase is a stop of that phase only.
    assert plan["rules"]["boats-may-come-in"]["phases"] == ["highwater"]


def test_a_pack_with_no_time_block_gets_one_pass(tmp_path):
    """No `"time"` block means nothing turns the watch on, so there is
    no second phase to walk - the plan is one pass over the first."""
    import make_time_pack

    pack = make_time_pack.build(tmp_path, name="no-time-test", time_block=None)
    plan = devtools.playthrough_plan(pack)
    assert plan["rest"] is False
    assert [p["name"] for p in plan["phases"]] == ["whispers"]
    assert plan["phases"][0]["stops"] == []      # its rule asks for highwater


def test_the_plan_finds_a_speaker_and_a_labelled_place(tmp_path):
    """`comes-near` names a speaker key or a POI label; the plan resolves
    both to the tile the hero walks to, and says so when it can resolve
    neither."""
    import make_mending_pack

    pack = make_mending_pack.build(tmp_path)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["rules"] = [
        {"id": "keeper-nods", "when": {"comes-near": {"who": "keeper", "distance": 2}},
         "then": [{"say": "The Keeper nods."}]},
        {"id": "stone-warms", "when": {"comes-near": {"who": "the stone", "distance": 0}},
         "then": [{"say": "The stone is warm."}]},
        {"id": "nobody-here", "when": {"comes-near": {"who": "the mayor", "distance": 1}},
         "then": [{"say": "Someone answers."}]},
    ]
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")

    plan = devtools.playthrough_plan(pack)
    stops = {(s["who"], s["kind"]): s for s in plan["phases"][0]["stops"]}
    assert stops[("keeper", "speaker")]["at"] == [7, 4]
    assert stops[("the stone", "place")]["at"] == [7, 3]
    # One pass (no `time` block), and both rules are asked in it.
    assert [p["name"] for p in plan["phases"]] == ["dusk"]
    # The rule that names nothing the pack declares is named as such,
    # not left to look like a rule that simply never fires.
    assert [u["id"] for u in plan["unresolved"]] == ["nobody-here"]
    assert "the mayor" in plan["unresolved"][0]["why"]


def test_two_rules_about_one_person_are_one_walk(tmp_path):
    """Two rules about the keeper are one stop, at the widest reach
    either declared - the event the game sends then satisfies both."""
    import make_mending_pack

    pack = make_mending_pack.build(tmp_path)
    world = json.loads((pack / "world.json").read_text(encoding="utf-8"))
    world["rules"] = [
        {"id": "close-by", "when": {"comes-near": {"who": "keeper", "distance": 1}},
         "then": [{"say": "Close."}]},
        {"id": "nearby", "when": {"comes-near": {"who": "keeper", "distance": 3}},
         "then": [{"say": "Nearby."}]},
    ]
    (pack / "world.json").write_text(json.dumps(world), encoding="utf-8")

    plan = devtools.playthrough_plan(pack)
    stops = plan["phases"][0]["stops"]
    assert len(stops) == 1
    assert stops[0]["distance"] == 3
    assert sorted(stops[0]["rules"]) == ["close-by", "nearby"]


def test_a_rule_is_asked_in_every_phase_unless_it_names_one(tmp_path):
    """`{"phase": "x"}` asks for that phase and `not` asks for the rest;
    a rule that names no phase is asked everywhere, because a flag it
    waits for can be set in any phase before it is retried."""
    rule = {"id": "r", "when": {"comes-near": {"who": "keeper", "distance": 1}},
            "then": [{"say": "x"}]}
    phases = ["one", "two", "three"]
    assert devtools._phases_of(rule, phases) == phases
    assert devtools._phases_of({**rule, "if": [{"phase": "two"}]}, phases) == ["two"]
    assert devtools._phases_of(
        {**rule, "if": [{"not": {"phase": "two"}}]}, phases) == ["one", "three"]
    assert devtools._phases_of(
        {**rule, "if": [{"all-of": [{"phase": "one"}, {"phase": "three"}]}]},
        phases) == ["one", "three"]


def test_the_walk_is_a_real_path_over_the_maps_own_geometry():
    """The path steps around what the pack's legend calls solid, and says
    so when a tile cannot be reached at all."""
    w = {"town": {"map": ["#####",
                          "#...#",
                          "#.#.#",
                          "#####"],
                  "legend": {".": {"base": ["#fff"]},
                             "#": {"base": ["#000"], "solid": True}}}}
    assert devtools.walk_path(w, "town", (1, 1), (3, 1)) == [(1, 0), (1, 0)]
    # The wall column at x=2 is walked around, never through.
    around = devtools.walk_path(w, "town", (1, 1), (3, 2))
    assert around == [(1, 0), (1, 0), (0, 1)]
    walked = [(1, 1)]
    for dx, dy in around:
        walked.append((walked[-1][0] + dx, walked[-1][1] + dy))
    assert (2, 2) not in walked, f"the path walked into the wall: {walked}"
    assert devtools.walk_path(w, "town", (1, 1), (2, 2)) is None
    assert devtools.walk_path(w, "town", (1, 1), (1, 1)) == []
    assert devtools.walk_path(w, "nowhere", (1, 1), (3, 1)) is None


def test_the_walk_presses_the_keys_the_player_chose():
    """The player's own keybinds are asked first, so a save whose keys
    were changed walks on those letters; the shipped defaults answer for
    any direction the table does not name."""
    assert devtools._key_for(1, 0) == "ArrowRight"
    assert devtools._key_for(0, -1, {"up": ["w", "ArrowUp"]}) == "w"
    assert devtools._key_for(1, 0, {"up": ["w"]}) == "ArrowRight"
    assert devtools._key_for(2, 0) is None
    assert devtools._rest_key({"rest": ["q"]}) == "q"
    assert devtools._rest_key() == "r"


def test_the_report_names_the_rules_that_stayed_silent_and_why():
    """A rule a reached phase asked for, that never fired, is reported
    with the why-log's sentence when the log has one and the pack's own
    conditions when it does not."""
    plan = {"world": "test", "unresolved": [], "rules": {
        "spoke": {"id": "spoke", "who": "keeper", "distance": 2,
                  "phases": ["dusk"], "conditions": []},
        "quiet": {"id": "quiet", "who": "keeper", "distance": 2,
                  "phases": ["dusk"], "conditions": [{"flag": "ever", "is": True}]},
        "later": {"id": "later", "who": "keeper", "distance": 2,
                  "phases": ["dawn"], "conditions": []}}}
    run = {"phases": [{"name": "dusk", "reached": True, "screenshot": "a.png"},
                      {"name": "dawn", "reached": False}],
           "fired": ["spoke"],
           "why": [{"id": "spoke", "why": "rule 'spoke' fired: the hero came near keeper"}]}
    report = devtools.playthrough_report(plan, run)
    assert report["ok"] is False
    assert [f["id"] for f in report["fired"]] == ["spoke"]
    assert "came near keeper" in report["fired"][0]["why"]
    # `quiet` is named, with the pack's own condition; `later` belongs to
    # a phase this run never reached, so it is not this run's business.
    assert [n["id"] for n in report["never_fired"]] == ["quiet"]
    assert report["never_fired"][0]["held_by"] is None
    assert report["never_fired"][0]["conditions"] == [{"flag": "ever", "is": True}]
    assert report["unreachable"] == ["dawn"]

    # The why-log's own sentence is used when it has one.
    run["why"].append({"id": "quiet", "why": "rule 'quiet' fired: later"})
    report = devtools.playthrough_report(plan, run)
    assert report["never_fired"][0]["held_by"].startswith("rule 'quiet' fired:")


def test_the_report_is_ok_when_every_phase_and_every_rule_is_satisfied():
    plan = {"world": "test", "unresolved": [], "rules": {
        "spoke": {"id": "spoke", "who": "keeper", "distance": 2,
                  "phases": ["dusk"], "conditions": []}}}
    run = {"phases": [{"name": "dusk", "reached": True}], "fired": ["spoke"],
           "why": [{"id": "spoke", "why": "rule 'spoke' fired"}]}
    assert devtools.playthrough_report(plan, run)["ok"] is True


def test_playthrough_needs_a_pack_to_plan_from(capsys):
    rc = devtools.playthrough(pack=None)
    assert rc == 2
    assert "--pack" in capsys.readouterr().err


# ------------------------------------------------------ doctor tooling rows

def test_tooling_checks_report_each_tool_with_a_fix_hint(tmp_path):
    (tmp_path / "root" / "node_modules" / "jsdom").mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".cache" / "ms-playwright" / "chromium-1").mkdir(parents=True)
    (home / ".agents" / "bin").mkdir(parents=True)
    (home / ".agents" / "bin" / "gallery").write_text("#!/bin/sh\n")
    rows = devtools.tooling_checks(tmp_path / "root", which=lambda n: "/bin/" + n,
                                   home=home)
    by = {name: (status, detail) for name, status, detail in rows}
    assert set(by) >= {"node", "jsdom", "chromium", "gallery"}
    assert all(s == "ok" for s, _ in by.values()), by

    rows = devtools.tooling_checks(tmp_path / "empty", which=lambda n: None,
                                   home=tmp_path / "nohome")
    by = {name: (status, detail) for name, status, detail in rows}
    for name in ("node", "jsdom", "chromium", "gallery"):
        assert by[name][0] == "missing", name
        assert by[name][1], f"{name} needs a fix hint"
    assert "npm ci" in by["jsdom"][1]
    assert "playwright install" in by["chromium"][1]


def test_doctor_prints_the_tooling_rows_but_never_fails_on_them(monkeypatch, tmp_path, capsys):
    from test_doctor import _patch
    args = _patch(monkeypatch, tmp_path)
    monkeypatch.setattr(devtools, "tooling_checks", lambda root, **kw: [
        ("node", "ok", "v24"), ("jsdom", "missing", "npm ci"),
        ("chromium", "ok", "chromium-1"), ("gallery", "missing", "see skills/gallery")])
    rc = cli.cmd_doctor(args)
    out = capsys.readouterr().out
    assert rc == 0                                   # a missing dev tool is not a failure
    assert "4 ok, 0 failed, 1 skipped" in out        # the existing summary is unchanged
    assert "tooling" in out.lower()
    assert "jsdom" in out and "npm ci" in out


def test_the_command_guide_documents_the_new_verbs():
    guide = (ROOT / "docs" / "guides" / "vefr-command.md").read_text(encoding="utf-8")
    for verb in ("vefr publish", "vefr look", "vefr probe", "vefr playthrough"):
        assert verb in guide, verb
    assert "tooling" in guide.lower()          # doctor's new rows are mentioned
