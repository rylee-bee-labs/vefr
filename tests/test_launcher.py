"""The game-neutral launcher around the existing woven Player (vefr#454, step 1).

Rylee's decision (2026-10-16, issue #454 comment 6222137761) chose a
SMALL shared, game-neutral launcher around the existing woven Player:
games keep their own identity and skins, and the launcher reuses what
exists rather than duplicating controls or building a new framework.

This is the first smallest step of that: a page that lists the woven
games the server holds and opens each one in the existing Player,
whole. The listing reads each game's own baked <title> - the game's
identity, never the launcher's - and opening hands the game the full
woven player inside one sandboxed frame, exactly the regime the studio
play pane already ships. Nothing here changes how a game plays: no
player part and no weave byte is touched.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vefr.main import app

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "four-phase-pack"


@pytest.fixture
def weave_dir(tmp_path, monkeypatch):
    """A temp, server-owned weave dir; nothing on disk is shared."""
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setenv("VEFR_WEAVE_DIR", str(out))
    return out


def _woven_file(out_dir: Path, name: str, title: str | None, *,
                when: float = 1_000_000) -> Path:
    """A stand-in woven game: a real file the server would have written."""
    head = f"<title>{title}</title>" if title is not None else ""
    p = out_dir / name
    p.write_text(f"<!doctype html><html><head>{head}</head>"
                 f"<body><h1 id='ts-title'>{title or name}</h1></body></html>",
                 encoding="utf-8")
    os.utime(p, (when, when))
    return p


# ── the page ────────────────────────────────────────────────────────────


def test_the_launcher_is_its_own_page_not_the_studio():
    """GET /launcher serves a page of its own - not app.html, not a pack.

    The launcher owns no title screen and no controls (the game's own
    title screen is the game's); it names no pack; and it opens games
    in one sandboxed frame, the same regime as the studio play pane.
    """
    client = TestClient(app)
    r = client.get("/launcher")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert r.headers["cache-control"] == "no-cache"
    body = r.text

    # Its own page: the shipped web/launcher.html, byte for byte.
    assert body == (WEB / "launcher.html").read_text(encoding="utf-8")
    # The list, the play surface, and the frame that carries a game.
    assert 'id="launcher-games"' in body
    assert 'id="launcher-surface"' in body
    assert 'sandbox="allow-scripts"' in body
    assert 'src="/static/launcher.js"' in body
    # Not the studio, and no second title screen inside the launcher:
    # a game's Begin button stays the game's own.
    assert "app.html" not in body and "VEFR_STUDIO" not in body
    assert "title-screen" not in body and "ts-enter" not in body
    # Game-neutral: no pack's name is baked into the shell.
    for pack_name in ("Emberfield", "sample-world", "Four Phase"):
        assert pack_name not in body


def test_the_launcher_js_opens_games_through_the_launcher_routes():
    """The page's own code, pinned where a stale URL would 404 live:
    it lists via /api/launcher/games and opens via /api/launcher/play/,
    and a game's strings reach the DOM as text, never as markup -
    an imported pack's title is not trusted here."""
    js = (WEB / "launcher.js").read_text(encoding="utf-8")
    assert "fetch('/api/launcher/games')" in js
    assert "'/api/launcher/play/' + encodeURIComponent" in js
    # A woven game's title is placed as text; no game string is markup.
    assert "innerHTML" not in js
    assert ".textContent = game.title" in js
    # Leaving a game stops it: the frame is emptied, not left running.
    assert "removeAttribute('src')" in js


# ── listing ────────────────────────────────────────────────────────────


def test_listing_names_each_game_by_its_own_title(weave_dir):
    """The list is the games the server wove, newest first, each under
    the title the game itself baked into its <title> - the launcher
    adds no name of its own."""
    _woven_file(weave_dir, "emberfield-2026-10-15.html", "Emberfield",
                when=1_000_000)
    _woven_file(weave_dir, "cottage-2026-10-16.html", "Cottage of the Breeze",
                when=2_000_000)

    r = TestClient(app).get("/api/launcher/games")
    assert r.status_code == 200
    assert r.json() == {
        "games": [
            {"name": "cottage-2026-10-16.html",
             "title": "Cottage of the Breeze",
             "play_url": "/api/launcher/play/cottage-2026-10-16.html"},
            {"name": "emberfield-2026-10-15.html",
             "title": "Emberfield",
             "play_url": "/api/launcher/play/emberfield-2026-10-15.html"},
        ]
    }


def test_listing_falls_back_to_the_file_name_without_a_title(weave_dir):
    _woven_file(weave_dir, "plain-2026-10-16.html", None)
    games = TestClient(app).get("/api/launcher/games").json()["games"]
    assert games == [{"name": "plain-2026-10-16.html",
                      "title": "plain-2026-10-16",
                      "play_url": "/api/launcher/play/plain-2026-10-16.html"}]


def test_listing_only_names_woven_html(weave_dir):
    """What is not a woven .html file the server wrote is not a game:
    notes, archives and directories never reach the list."""
    _woven_file(weave_dir, "game.html", "A Game")
    (weave_dir / "notes.txt").write_text("not a game", encoding="utf-8")
    (weave_dir / "game.vefr").write_bytes(b"PK\x03\x04 not listed either")
    (weave_dir / "nested").mkdir()

    games = TestClient(app).get("/api/launcher/games").json()["games"]
    assert [g["name"] for g in games] == ["game.html"]


def test_listing_an_empty_house_is_an_empty_list(weave_dir):
    assert TestClient(app).get("/api/launcher/games").json() == {"games": []}


# ── opening ────────────────────────────────────────────────────────────


@pytest.fixture
def woven(weave_dir, tmp_path, monkeypatch):
    """A real weave of the fixture pack, through the served builder,
    so opening is proven against the actual shipped player bytes."""
    pack = tmp_path / "worlds" / "four-phase-pack"
    shutil.copytree(FIXTURE, pack, dirs_exist_ok=True)
    monkeypatch.setattr("vefr.paths.pack_dir", lambda name=None: pack)
    client = TestClient(app)
    r = client.post("/api/builder/weave", json={})
    assert r.status_code == 200, r.text
    return r.json()


def test_opening_serves_the_existing_player_whole(woven):
    """Opening a game hands the player over whole: the woven document,
    its own title screen included, inline with the sandbox CSP."""
    client = TestClient(app)
    r = client.get(f"/api/launcher/play/{woven['name']}")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("inline")
    assert r.headers["content-security-policy"] == "sandbox allow-scripts"
    body = r.text
    assert body.lstrip().lower().startswith("<!doctype")
    # The game's own face arrives intact: its title screen and its name.
    assert 'id="ts-title"' in body
    assert "Four Phase Pack" in body


def test_opening_refuses_names_the_server_did_not_write(woven, weave_dir):
    client = TestClient(app)
    for bad in ("..%2fworld.json", "a%2Fb.html", "nope.txt", ".hidden.html",
                "absent.html"):
        r = client.get(f"/api/launcher/play/{bad}")
        assert r.status_code == 404, bad


def test_the_launcher_and_the_studio_pane_open_the_same_way(woven):
    """Both doors to a woven game must hold the same line: the same
    file, inline, behind the same sandbox CSP. If one door ever
    loosens, this fails - the sandbox is a security property, not a
    styling choice."""
    client = TestClient(app)
    launcher = client.get(f"/api/launcher/play/{woven['name']}")
    studio = client.get(f"/api/builder/weave/play/{woven['name']}")
    assert launcher.status_code == studio.status_code == 200
    for header in ("content-disposition", "content-security-policy"):
        assert launcher.headers[header] == studio.headers[header], header
    assert launcher.content == studio.content