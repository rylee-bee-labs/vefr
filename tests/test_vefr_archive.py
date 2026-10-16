"""The `.vefr` archive: one bake, deterministic bytes, and refusals (vefr#455).

ADR 0019 records the owner's decision - a portable, inspectable, versioned
content-and-assets archive, with the shared Player supplying the engine and
`vefr weave`'s standalone HTML untouched beside it.

What is pinned here:

* the round trip - an archive's game globals are the woven file's game
  globals, key for key, so `.vefr` and HTML of one pack are one game;
* determinism - the same pack exports the same bytes twice;
* the manifest - Emberfield round-trips, and a skinned pack keeps its skin
  pictures and its credit;
* every refusal a loader owes untrusted content, each asserted on the
  words, so the Player's mirror of them cannot drift quietly;
* the Player build `vefr archive` writes: the same parts with the baked
  block gone, and a dormant loader in every woven file.

The loader's own reading of a ZIP is exercised by the browser suite; this
file pins the format both sides agree on.
"""

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from vefr import cli, vefrfile

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "worlds" / "sample-world"

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
import make_skin_pack  # noqa: E402


# ---- helpers: a well-formed archive, and hands for breaking it ----

GOOD_GLOBALS = {"VEFR_WORLD": {"title": "Test"}, "VEFR_REGIONS": {}}


def _zip(path: Path, files: dict) -> Path:
    """Write a ZIP by hand, with the same determinism the exporter uses."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return path


def _manifest_bytes(files: dict, **over) -> bytes:
    rows = [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in sorted(files.items())]
    manifest = {
        "format": vefrfile.FORMAT,
        "schema_version": vefrfile.SCHEMA_VERSION,
        "engine_version": "test",
        "runtime": {"player_contract": vefrfile.PLAYER_CONTRACT,
                    "min_schema_version": vefrfile.SCHEMA_VERSION},
        "game": {"id": "test", "title": "Test", "pack": "test"},
        "data": {"globals": vefrfile.GLOBALS_NAME},
        "capabilities": [],
        "network": {"policy": "offline-only", "allowed_urls": []},
        "provenance": {"source": "test", "license": "test"},
        "files": rows,
    }
    manifest.update(over)
    return json.dumps(manifest, indent=1).encode("utf-8")


def _payload(globals_payload=None) -> bytes:
    return json.dumps({"globals": globals_payload or GOOD_GLOBALS,
                       "doc": {"title": "Test", "tagline": ""}}).encode("utf-8")


def _valid(tmp_path, *, payload=None, globals_payload=None, extra=None,
           manifest=None) -> Path:
    """One archive that loads, with every seam a refusal test needs open."""
    payload = payload if payload is not None else _payload(globals_payload)
    files = {vefrfile.GLOBALS_NAME: payload}
    if extra:
        files.update(extra)
    files[vefrfile.MANIFEST_NAME] = manifest if manifest is not None else _manifest_bytes(files)
    return _zip(tmp_path / "test.vefr", files)


def _rewritten(tmp_path, manifest: dict, globals_payload=None, extra=None) -> Path:
    """The same archive with a hand-edited manifest (digests recomputed)."""
    payload = _payload(globals_payload)
    files = {vefrfile.GLOBALS_NAME: payload}
    if extra:
        files.update(extra)
    return _valid(tmp_path, payload=payload, extra=extra,
                  manifest=_manifest_bytes(files, **manifest))


def _woven_globals(html: str) -> dict:
    """The `window.VEFR_*` globals a woven HTML carries, read back off it.

    Only the names the player template bakes are read: the parts set
    several other `window.VEFR_*` globals of their own at run time, and
    those are the engine's, not the pack's.
    """
    names = {m.group(1) for m in re.finditer(
        r"^window\.(VEFR_[A-Z0-9_]+) = \{\{\w+\}\};$", vefrfile.player_template(), re.M)}
    out = {}
    for match in re.finditer(r"^window\.(VEFR_[A-Z0-9_]+) = (.*);\s*$", html, re.M):
        if match.group(1) in names:
            out[match.group(1)] = json.loads(match.group(2))
    return out


# ---- the round trip: one bake, two containers ----

def test_the_archive_carries_the_weaves_own_game(tmp_path):
    """Emberfield: the archive's globals are the woven file's, key for key."""
    archive = vefrfile.build_archive(SAMPLE, tmp_path / "emberfield.vefr")
    loaded = vefrfile.load_archive(tmp_path / "emberfield.vefr")
    woven = _woven_globals(cli.weave_html(SAMPLE))
    assert woven, "the woven file bakes no globals to compare against"
    assert sorted(loaded.globals) == sorted(woven)
    assert loaded.globals == woven
    assert loaded.doc["title"] == woven["VEFR_WORLD"]["title"]
    assert loaded.doc["tagline"]
    assert archive["game"]["id"] == "sample-world"
    assert archive["runtime"]["min_schema_version"] == vefrfile.SCHEMA_VERSION
    # The payload names only what the Player reads.
    assert all(key.startswith("VEFR_") for key in loaded.globals)


def test_the_same_pack_exports_the_same_bytes_twice(tmp_path):
    """Determinism is the point of a versioned archive: same in, same out."""
    first = tmp_path / "one.vefr"
    second = tmp_path / "two.vefr"
    vefrfile.build_archive(SAMPLE, first)
    vefrfile.build_archive(SAMPLE, second)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as zf:
        names = zf.namelist()
        stamps = {info.date_time for info in zf.infolist()}
    assert names[0] == vefrfile.MANIFEST_NAME
    assert names == sorted(names, key=lambda n: (n != vefrfile.MANIFEST_NAME, n))
    assert stamps == {(1980, 1, 1, 0, 0, 0)}, "an archive timestamp would make it non-reproducible"


def test_a_pack_skin_and_its_credit_survive_the_round_trip(tmp_path):
    """A skinned pack keeps its skin, its pictures and its credit (the
    acceptance line: the same look, not a plainer one)."""
    pack = make_skin_pack.build(tmp_path / "skinned")
    vefrfile.build_archive(pack, tmp_path / "skinned.vefr")
    loaded = vefrfile.load_archive(tmp_path / "skinned.vefr")
    skin = loaded.globals["VEFR_SKIN"]
    assert skin["name"] == "test-skin"
    assert "Rylee and Claude" in skin["credit"]
    assert skin["parts"]["panel"]["file"].startswith("data:image/png;base64,")
    assert skin["parts"]["button"]["hover"].startswith("data:image/png;base64,")
    assert "assets/skins/test-skin/panel.png" in loaded.names
    assert "assets/skins/test-skin/cursor.png" in loaded.names
    assert "content/world.json" in loaded.names
    assert loaded.doc["title"]


def test_an_archive_is_a_zip_any_tool_can_open(tmp_path):
    """Inspectable with ordinary tools: the content is the pack, verbatim."""
    path = tmp_path / "emberfield.vefr"
    vefrfile.build_archive(SAMPLE, path)
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        world = zf.read("content/world.json")
        assert world == (SAMPLE / "world.json").read_bytes()
        logbok = zf.read("content/logbok.md").decode("utf-8")
        assert logbok == (SAMPLE / "logbok.md").read_text(encoding="utf-8")
        manifest = json.loads(zf.read(vefrfile.MANIFEST_NAME))
    assert manifest["provenance"]["content_files"] >= 10
    assert manifest["network"] == {"policy": "offline-only", "allowed_urls": []}
    assert "library_url" not in json.dumps(manifest["network"])


# ---- the manifest, and the version a Player reads ----

def test_the_manifest_names_what_the_engine_already_knows(tmp_path):
    """Capabilities come from `docs/features.json`, not a second list."""
    manifest = vefrfile.build_archive(SAMPLE, tmp_path / "emberfield.vefr")
    from vefr.features import load_catalog, scan_pack
    catalog = {feat["id"] for feat in load_catalog()}
    expected = sorted({row["id"] for row in scan_pack(SAMPLE, catalog=load_catalog())
                       if row.get("used")})
    assert manifest["capabilities"] == expected
    assert set(manifest["capabilities"]) <= catalog


def test_a_newer_schema_is_refused_with_both_numbers(tmp_path):
    archive = _rewritten(tmp_path, {"schema_version": 3})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert str(refusal.value) == (
        "this .vefr uses manifest schema 3; this vefr reads schema 1 "
        "- update the engine to play it")


def test_an_old_schema_still_loads(tmp_path):
    """Forward-compatible within v1: the payload shape, not the number, rules."""
    archive = _rewritten(tmp_path, {"schema_version": 1})
    assert vefrfile.load_archive(archive).globals == GOOD_GLOBALS


def test_a_manifest_that_demands_a_newer_player_is_refused(tmp_path):
    """Two version gates, two sentences: the file's own schema, and the
    floor it asks the Player to meet."""
    files = {vefrfile.GLOBALS_NAME: json.dumps({"globals": GOOD_GLOBALS, "doc": {}}).encode()}
    files[vefrfile.MANIFEST_NAME] = _manifest_bytes(
        files, runtime={"player_contract": vefrfile.PLAYER_CONTRACT,
                        "min_schema_version": vefrfile.SCHEMA_VERSION + 1})
    archive = _zip(tmp_path / "newer.vefr", files)
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "needs a newer Player" in str(refusal.value)


@pytest.mark.parametrize("version", [1.5, "1", True, None, float("nan"), float("inf")])
def test_a_schema_version_that_is_not_a_whole_number_is_refused(tmp_path, version):
    """The version is a whole number or the archive is not one: `1.5`, a
    quoted `"1"`, a boolean, `NaN` and `Infinity` are shapes no schema has
    ever named. The Player's reader says the same sentence (vefr#455 fix
    round), so an archive cannot be read one way on the command line and
    another way in a browser."""
    archive = _rewritten(tmp_path, {"schema_version": version})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert str(refusal.value) == "the manifest's schema_version is not a whole number"


def test_a_runtime_floor_that_is_not_a_whole_number_is_ignored(tmp_path):
    """The floor the manifest asks the Player to meet is a whole number or
    it is no floor at all: a `1.5` cannot smuggle a gate past either reader."""
    files = {vefrfile.GLOBALS_NAME: json.dumps({"globals": GOOD_GLOBALS, "doc": {}}).encode()}
    files[vefrfile.MANIFEST_NAME] = _manifest_bytes(
        files, runtime={"player_contract": vefrfile.PLAYER_CONTRACT,
                        "min_schema_version": 1.5})
    archive = _zip(tmp_path / "half-floor.vefr", files)
    assert vefrfile.load_archive(archive).globals == GOOD_GLOBALS, \
        "a floor no exporter writes is ignored, not obeyed and not fatal"


def test_a_file_that_is_not_an_archive_is_refused(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("just some notes", encoding="utf-8")
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(path)
    assert "not a .vefr archive" in str(refusal.value)


def test_a_zip_with_no_manifest_is_refused(tmp_path):
    archive = _zip(tmp_path / "empty.vefr", {"content/world.json": b"{}"})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "has no manifest.json" in str(refusal.value)


def test_a_manifest_that_is_not_json_is_refused(tmp_path):
    archive = _valid(tmp_path, manifest=b"{ this is not json")
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "manifest.json is not valid JSON" in str(refusal.value)


def test_a_payload_that_is_not_json_is_refused(tmp_path):
    payload = b"nope"
    archive = _zip(tmp_path / "bad-json.vefr", {
        vefrfile.GLOBALS_NAME: payload,
        vefrfile.MANIFEST_NAME: _manifest_bytes({vefrfile.GLOBALS_NAME: payload})})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "not valid JSON" in str(refusal.value)


def test_a_global_that_is_not_a_global_is_refused(tmp_path):
    archive = _valid(tmp_path, globals_payload={"VEFR_WORLD": {}, "rm_rf": 1})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert 'names "rm_rf"' in str(refusal.value)


# ---- untrusted content: names, sizes, methods, bytes ----

def _two_of_one(path: Path, name: str, first: bytes, second: bytes) -> Path:
    """A ZIP that names the same path twice - legal, and ambiguous."""
    payload = _payload()
    files = {vefrfile.GLOBALS_NAME: payload}
    files[vefrfile.MANIFEST_NAME] = _manifest_bytes(files)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry, data in ((vefrfile.MANIFEST_NAME, files[vefrfile.MANIFEST_NAME]),
                            (name, first), (name, second)):
            info = zipfile.ZipInfo(entry, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return path


@pytest.mark.parametrize("name", [vefrfile.GLOBALS_NAME, "content/world.json"])
def test_a_path_the_archive_names_twice_is_refused(tmp_path, name):
    """One file, one entry: a ZIP may repeat a path, and then two readers
    disagree about which of the two is the game. The Player's reader refuses
    the same archive for the same reason (vefr#455 fix round)."""
    payload = _payload()
    first = payload if name == vefrfile.GLOBALS_NAME else b'{"title": "one"}'
    second = _payload({"VEFR_WORLD": {"title": "smuggled"}}) \
        if name == vefrfile.GLOBALS_NAME else b'{"title": "two"}'
    archive = _two_of_one(tmp_path / "twice.vefr", name, first, second)
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert str(refusal.value) == (
        f'refusing "{name}": the archive names it twice; one file, one entry')


def test_a_name_that_leaves_the_archive_is_refused(tmp_path):
    archive = _valid(tmp_path, extra={"content/../../escape.md": b"gotcha"})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "the path leaves the archive" in str(refusal.value)


def test_an_absolute_name_is_refused(tmp_path):
    archive = _valid(tmp_path, extra={"/etc/passwd.md": b"x"})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "archive paths are relative" in str(refusal.value)


def test_a_file_an_archive_does_not_carry_is_refused(tmp_path):
    archive = _valid(tmp_path, extra={"content/run.py": b"print('hi')"})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "never anything that could run" in str(refusal.value)


def test_an_entry_outside_the_shape_is_refused(tmp_path):
    archive = _valid(tmp_path, extra={"secrets.txt": b"x"})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "nothing else" in str(refusal.value)


def test_a_decompression_bomb_is_refused(tmp_path):
    bomb = b"\0" * (4 * 1024 * 1024)
    archive = _valid(tmp_path, extra={"assets/floor.png": bomb})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "past the 200x a picture ever needs" in str(refusal.value)


def test_too_many_entries_is_refused(tmp_path):
    many = {f"content/note-{n}.md": b"x" for n in range(vefrfile.MAX_ENTRIES + 1)}
    archive = _valid(tmp_path, extra=many)
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "an archive may hold at most" in str(refusal.value)


def test_a_file_whose_bytes_changed_is_refused(tmp_path):
    """The digest is what says an entry is the one the manifest meant."""
    archive = _valid(tmp_path, extra={"content/world.json": b'{"title": "Emberfield"}'})
    files = {}
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            files[info.filename] = zf.read(info.filename)
    files["content/world.json"] = b'{"title": "emberfield"}'  # same length, other bytes
    tampered = _zip(tmp_path / "tampered.vefr", files)
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(tampered)
    assert '"content/world.json" does not match its manifest digest' == str(refusal.value)


def test_a_file_the_manifest_forgot_is_refused(tmp_path):
    archive = _valid(tmp_path, extra={"content/extra.md": b"surprise"})
    files = {}
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            files[info.filename] = zf.read(info.filename)
    del files["content/extra.md"]
    shrunk = _zip(tmp_path / "shrunk.vefr", files)
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(shrunk)
    assert "in the manifest but not in the archive" in str(refusal.value)


# ---- the network policy: an archive is offline content ----

def test_an_undeclared_url_is_refused(tmp_path):
    archive = _valid(tmp_path, globals_payload={
        "VEFR_WORLD": {}, "VEFR_HERO": {"library_url": "https://elsewhere.test/games/x"}})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "reaches no network" in str(refusal.value)


def test_a_declared_url_loads(tmp_path):
    """The shelf a pack was published from is the one URL an archive may name."""
    url = "https://shelf.test/games/x"
    payload = json.dumps({"globals": {"VEFR_WORLD": {}, "VEFR_HERO": {"library_url": url}},
                          "doc": {}}).encode()
    files = {vefrfile.GLOBALS_NAME: payload}
    manifest = json.loads(_manifest_bytes(files))
    manifest["network"] = {"policy": "offline-only", "allowed_urls": [url]}
    files[vefrfile.MANIFEST_NAME] = _manifest_bytes(
        files, network={"policy": "offline-only", "allowed_urls": [url]})
    archive = _zip(tmp_path / "shelf.vefr", files)
    assert vefrfile.load_archive(archive).globals["VEFR_HERO"]["library_url"] == url


def test_a_packs_declared_shelf_is_the_only_url_it_bakes(tmp_path):
    manifest = vefrfile.build_archive(SAMPLE, tmp_path / "emberfield.vefr")
    loaded = vefrfile.load_archive(tmp_path / "emberfield.vefr")
    urls = vefrfile._allowed_url(loaded.globals)
    assert urls == manifest["network"]["allowed_urls"]
    assert "VEFR_HERO" in loaded.globals


def test_a_data_uri_that_could_execute_is_refused(tmp_path):
    archive = _valid(tmp_path, globals_payload={
        "VEFR_SKIN": {"backdrop": "data:text/html;base64,PHNjcmlwdD4="}})
    with pytest.raises(vefrfile.ArchiveRefusal) as refusal:
        vefrfile.load_archive(archive)
    assert "pictures, sounds and fonts" in str(refusal.value)


def test_a_picture_data_uri_is_fine(tmp_path):
    archive = _valid(tmp_path, globals_payload={
        "VEFR_SPRITES": {"hero": "data:image/png;base64,iVBORw0KGgo="}})
    assert vefrfile.load_archive(archive).globals["VEFR_SPRITES"]["hero"].startswith(
        "data:image/png")


# ---- the CLI ----

def _args(**over):
    base = {"pack": str(SAMPLE), "out": None, "player": None, "no_player": False,
            "pool": 0, "inspect": None, "json": False}
    base.update(over)
    return SimpleNamespace(**base)


def test_the_cli_writes_an_archive_and_its_player(tmp_path, capsys):
    out = tmp_path / "emberfield.vefr"
    assert cli.cmd_archive(_args(out=str(out))) == 0
    said = capsys.readouterr().out
    assert out.is_file()
    assert (tmp_path / "emberfield.player.html").is_file()
    assert "inspect it any time" in said
    assert cli.cmd_archive(_args(out=str(out), no_player=True)) == 0
    assert "wrote" in capsys.readouterr().out


def test_the_cli_inspects_an_archive(tmp_path, capsys):
    out = tmp_path / "emberfield.vefr"
    cli.cmd_archive(_args(out=str(out), no_player=True))
    capsys.readouterr()
    assert cli.cmd_archive(_args(inspect=str(out))) == 0
    said = capsys.readouterr().out
    assert "Emberfield" in said
    assert "manifest schema 1" in said
    assert vefrfile.GLOBALS_NAME in said
    assert cli.cmd_archive(_args(inspect=str(out), json=True)) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["format"] == vefrfile.FORMAT


def test_the_cli_refuses_a_bad_archive(tmp_path, capsys):
    path = tmp_path / "bad.vefr"
    path.write_bytes(b"not a zip at all")
    assert cli.cmd_archive(_args(inspect=str(path))) == 1
    assert "refusing" in capsys.readouterr().out


def test_the_cli_reports_a_missing_pack(tmp_path, capsys):
    assert cli.cmd_archive(_args(pack=str(tmp_path / "nowhere"))) == 1
    assert "pack not found" in capsys.readouterr().out


# ---- the shared Player ----

def test_the_player_build_drops_the_baked_block_and_names_the_archive(tmp_path):
    player = vefrfile.write_player(tmp_path / "emberfield.player.html", "emberfield.vefr")
    html = player.read_text(encoding="utf-8")
    assert 'window.vefrArchiveUrl = "emberfield.vefr";' in html
    assert "window.VEFR_WORLD = {" not in html, "the Player must not bake a game of its own"
    assert "{{title}}" not in html and "{{fonts_css}}" not in html
    assert "// ---- .vefr archive loader" in html
    assert "{{world_json}}" not in html, "an unfilled placeholder would not parse"


def test_a_woven_file_keeps_its_baked_block_and_sleeps_through_the_loader(tmp_path):
    """The standalone HTML is unchanged: same game, and the loader is inert."""
    woven = cli.weave_html(SAMPLE)
    assert "window.VEFR_WORLD = " in woven
    assert "window.vefrArchiveUrl = window.vefrArchiveUrl || '';" in woven
    names = {m.group(1) for m in
             re.finditer(r"^window\.(VEFR_[A-Z0-9_]+) = \{\{\w+\}\};$",
                         vefrfile.player_template(), re.M)}
    assert len(_woven_globals(woven)) == len(names) - 1, "only VEFR_SPELLS may be absent"


def test_the_loader_runs_before_the_baked_block():
    """The archive has to be in place before any part reads a global."""
    manifest = json.loads((ROOT / "web" / "player" / "manifest.json").read_text(encoding="utf-8"))
    loader = manifest.index("046-vefr-archive-loader.js")
    assert loader < manifest.index("050-inlined-world-pack.js")
    assert loader < manifest.index("080-endpoint-join-post.js"), \
        "a part that reads a global while the page parses runs after the loader"
    assert loader < manifest.index("448-asset-loaders.js")


def test_the_committed_player_is_the_parts_on_disk():
    """`scripts/build_player.py --check` is the contract; run it here."""
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_player.py"), "--check"],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr + run.stdout