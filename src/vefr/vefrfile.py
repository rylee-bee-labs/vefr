"""The `.vefr` game archive - one portable, inspectable file for a game.

A `.vefr` is a ZIP with a fixed shape:

    manifest.json         the contract: schema, runtime, identity, digests
    content/...           the pack's own authored files, as written
    assets/...            the pack's pictures and sounds, as written
    data/globals.json     the playable payload: the window.VEFR_* globals

ADR 0019 records the owner's decision (vefr#455): a `.vefr` is content
and assets plus a manifest, the shared Player supplies the engine, and
`vefr weave`'s self-contained HTML stays exactly as it was. This module
is the format's one implementation; `vefr archive` is its front door.

Three rules hold the shape together:

* **One bake.** `data/globals.json` is woven by `cli.weave_html` itself,
  with the player template's own data block swapped for a JSON skeleton
  built from the same `window.VEFR_X = {{x_json}};` lines. There is no
  second exporter to drift from the weave, and a test asserts the two
  carry identical globals.
* **Deterministic.** The same pack exports byte-for-byte the same
  archive: entries sorted, timestamps pinned to the ZIP epoch, no
  wall-clock and no machine paths in the manifest.
* **Untrusted on the way in.** Every load validates before a byte of the
  payload reaches the player: entry names (no traversal, no absolute
  paths, no symlinks), entry count and size caps against decompression
  bombs, the compression method, the file suffixes (data and pictures
  only - never a script), the manifest schema and runtime floor, every
  file's digest, and every URL the payload carries. A refusal is one
  plain sentence naming what was wrong.

Load is a read-only inspection (`vefr archive --inspect`, the tests);
nothing is ever unpacked to disk. The Player's own reader is the mirror
of `load_archive` in `web/player/parts/045-vefr-archive-loader.js`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# ---- the contract, in one place ----

FORMAT = "vefr-archive"
SCHEMA_VERSION = 1
PLAYER_CONTRACT = "vefr-player/1"
MANIFEST_NAME = "manifest.json"
GLOBALS_NAME = "data/globals.json"

#: Authored text: it travels as `content/`, readable and re-usable.
TEXT_SUFFIXES = frozenset({
    ".md", ".json", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini",
})
#: Pictures, sounds and fonts: they travel as `assets/`, byte for byte.
ASSET_SUFFIXES = frozenset({
    ".png", ".webp", ".jpg", ".jpeg", ".gif", ".svg", ".bmp", ".ico",
    ".mp3", ".ogg", ".wav", ".m4a", ".aac", ".flac",
    ".woff", ".woff2", ".ttf", ".otf",
})

#: A load reads at most this much, in total and per entry. A pack's own
#: art is the only thing that ever approaches the per-entry cap; the
#: total cap is what a zip bomb runs into.
MAX_ENTRIES = 4096
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
#: A declared-to-actual ratio past this is a decompression bomb, not art.
MAX_RATIO = 200

#: The data URI types the payload may carry. A `data:text/html` in a
#: game file is not a picture; the player never runs archive content, but
#: nothing that can execute belongs in an archive either.
SAFE_DATA_TYPES = frozenset({
    "image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml",
    "image/bmp", "audio/mpeg", "audio/ogg", "audio/wav", "audio/webm",
    "font/woff", "font/woff2",
})

_URL_RE = re.compile(r"https?://[^\s\"'<>)\\]+")
_GLOBAL_LINE_RE = re.compile(r"^window\.(VEFR_[A-Z0-9_]+) = \{\{([a-z0-9_]+)\}\};$")
_DATA_BLOCK_RE = re.compile(
    r"(?ms)^// ---- inlined world pack ----$.*?"
    r"^window\.VEFR_[A-Z0-9_]+ = \{\{[a-z0-9_]+\}\};\n")
_UNFILLED_KEY_RE = re.compile(r'"VEFR_[A-Z0-9_]+"\s*:\s*\{\{[a-z0-9_]+\}\}\s*,?')
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".vefr"}


class ArchiveRefusal(Exception):
    """One plain sentence: what was wrong with an archive, and why refused."""


def _refuse(sentence: str) -> None:
    raise ArchiveRefusal(sentence)


# ---- the player's data block, and the bake that feeds it ----

def _engine_version() -> str:
    """The engine that wrote an archive (the player reads it, never runs it)."""
    try:
        from importlib.metadata import version
        return version("vefr")
    except Exception:  # a source checkout with no installed dist
        return "0.0.0-dev"


def player_template() -> str:
    """The shared Player source - `web/packaged.html`, the one woven template.

    Read through `cli._template_candidates`, so a wheel, a container and
    a source checkout all resolve the same file the weave folds over.
    """
    from .cli import _template_candidates
    candidates = _template_candidates()
    path = next((p for p in candidates if p.exists()), candidates[0])
    return path.read_text(encoding="utf-8")


def _globals_skeleton(template: str) -> str:
    """A JSON object with one key per baked global, in template order.

    Built from the player's own `window.VEFR_X = {{x_json}};` lines, so a
    new global joins the archive the day it joins the weave - there is no
    second list to keep in step.
    """
    pairs = [(m.group(1), m.group(2)) for m in
             (_GLOBAL_LINE_RE.match(line) for line in template.splitlines()) if m]
    if not pairs:
        _refuse("the player template names no window.VEFR_* globals; "
                "the archive has nothing to load")
    body = ",".join(f'{json.dumps(name)}: {{{{{ph}}}}}' for name, ph in pairs)
    return "{" + body + "}"


def bake(pack: Path, *, pool: dict | None = None) -> tuple[dict, dict]:
    """Weave one pack into `(globals, doc)` - the archive's playable payload.

    `globals` is what the weave writes into `window.VEFR_*`, key for key.
    `doc` is the four page-level values the template folds in around it
    (`title`, `tagline`, `title_art_img`, `fonts_css`), so a Player that
    loads an archive wears the same skin and faces as the woven file.

    The weave is the only bake: a Blueprint that would refuse `vefr weave`
    refuses here too, with the same sentence.
    """
    from .cli import weave_html
    doc: dict = {}
    text = weave_html(pack, pool=pool,
                      template=_globals_skeleton(player_template()), doc=doc)
    # A pack that declares no spells has its whole `VEFR_SPELLS` line
    # dropped by the weave (the player's additive rule). In the JSON
    # skeleton that leaves an unfilled key; the game reads a missing
    # global as no spells, so the key goes with it.
    try:
        globals_ = json.loads(_UNFILLED_KEY_RE.sub('', text))
    except ValueError as exc:
        _refuse(f"the woven payload for {Path(pack).name} is not valid JSON: {exc}")
    if not isinstance(globals_, dict):
        _refuse(f"the woven payload for {Path(pack).name} is not a JSON object")
    return globals_, {k: doc.get(k, "") for k in
                      ("title", "tagline", "title_art_img", "fonts_css")}


def player_html(archive_name: str, *, template: str | None = None) -> str:
    """The shared Player build: the template with its baked data block removed.

    What `vefr archive --player` writes beside the archive. It is the same
    engine as the woven file - the parts, byte for byte - with the one
    difference that the game data now arrives from a `.vefr` at runtime,
    installed by the loader part before any part that reads a global has
    run. A woven file is untouched: the block it folds is still there.
    """
    text = player_template() if template is None else template
    if not _DATA_BLOCK_RE.search(text):
        _refuse("the player template has no inlined world pack block; "
                "the archive Player cannot be built from it")
    text = _DATA_BLOCK_RE.sub("", text, count=1)
    # The page-level placeholders are filled from the archive's `doc` at
    # load; empty here so an un-loaded Player never shows `{{title}}`.
    for placeholder in ("{{title}}", "{{tagline}}", "{{title_art_img}}", "{{fonts_css}}"):
        text = text.replace(placeholder, "")
    marker = "// ---- .vefr archive loader"
    if marker not in text:
        _refuse("the player template has no .vefr archive loader block")
    return text.replace(
        marker,
        f"window.vefrArchiveUrl = {json.dumps(archive_name)};\n{marker}",
        1)


# ---- the manifest ----

def _allowed_url(globals_: dict) -> list[str]:
    """The one URL a pack may bake: the shelf it says it was published from."""
    hero = globals_.get("VEFR_HERO")
    hero = hero if isinstance(hero, dict) else {}
    url = hero.get("library_url")
    if isinstance(url, str) and url.strip().lower().startswith(("http://", "https://")):
        return [url.strip()]
    return []


def _capabilities(pack: Path) -> list[str]:
    """The features this pack uses, read from `docs/features.json`.

    The audited catalog is the one source of "what VEFR can do", so the
    archive names capabilities with it instead of inventing a list. A box
    with no catalog beside it still exports; the manifest simply names
    none, and a Player does not refuse on capabilities it cannot read.
    """
    try:
        from .features import load_catalog, scan_pack
        used = scan_pack(pack, catalog=load_catalog())
    except Exception:
        return []
    return sorted({row["id"] for row in used if row.get("used")})


def _license(pack: Path) -> str:
    """The pack's own licence line, when it ships one (the credit travels)."""
    for name in ("LICENSE", "LICENSE.md", "COPYING", "COPYING.md"):
        path = pack / name
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                text = line.strip().lstrip("#").strip()
                if text:
                    return text
    return "unstated - the pack ships no licence file"


def _classify(rel: str) -> str | None:
    """`content/`, `assets/`, or None for a file an archive does not carry.

    No suffix at all is content: a pack's `LICENSE` and `README` travel,
    because a game that leaves its credit behind is not the same game.
    """
    suffix = Path(rel).suffix.lower()
    if not suffix or suffix in TEXT_SUFFIXES:
        return "content"
    if suffix in ASSET_SUFFIXES:
        return "assets"
    return None


def _pack_files(pack: Path) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Every archiveable file in the pack, as `(arcname, bytes)`, plus refusals.

    Authored text becomes `content/`, pictures and sounds `assets/`, both
    byte for byte and in sorted order. A file of any other kind - a
    script, a binary the player cannot draw - is left out and named in the
    refusal list, so an author learns about it instead of wondering where
    it went. Symlinks and dotfiles never travel.
    """
    out: list[tuple[str, bytes]] = []
    skipped: list[str] = []
    root = os.path.realpath(pack)
    for path in sorted(pack.rglob("*")):
        rel = path.relative_to(pack).as_posix()
        if any(part.startswith(".") or part in _SKIP_DIRS for part in path.relative_to(pack).parts):
            continue
        if path.is_symlink():
            skipped.append(f"{rel}: a link, which never travels in an archive")
            continue
        if not path.is_file():
            continue
        if os.path.realpath(path).find(root) != 0:  # pragma: no cover - belt
            skipped.append(f"{rel}: outside the pack")
            continue
        where = _classify(rel)
        if where is None:
            skipped.append(f"{rel}: not content and not an asset the player can use")
            continue
        data = path.read_bytes()
        if len(data) > MAX_ENTRY_BYTES:
            _refuse(f"{rel} is {len(data)} bytes; an archive entry may be at "
                    f"most {MAX_ENTRY_BYTES} bytes")
        out.append((f"{where}/{rel}", data))
    return sorted(out), skipped


def manifest_for(pack: Path, globals_: dict, doc: dict, *,
                 files: list[tuple[str, bytes]], skipped: list[str]) -> dict:
    """The manifest for one pack: contract, identity, policy, digests."""
    payload = json.dumps({"globals": globals_, "doc": doc},
                         ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    entries = list(files) + [(GLOBALS_NAME, payload)]
    digests = [{"path": name, "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}
               for name, data in entries]
    title = doc.get("title") or Path(pack).name
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION,
        "engine_version": _engine_version(),
        "runtime": {
            "player_contract": PLAYER_CONTRACT,
            "min_schema_version": SCHEMA_VERSION,
            "live_model": "optional - the Player may be given an endpoint by the player",
        },
        "game": {"id": Path(pack).name, "title": title, "pack": Path(pack).name},
        "data": {"globals": GLOBALS_NAME},
        "capabilities": _capabilities(Path(pack)),
        "network": {"policy": "offline-only", "allowed_urls": _allowed_url(globals_)},
        "provenance": {
            "source": Path(pack).name,
            "license": _license(Path(pack)),
            "content_files": sum(1 for name, _ in files if name.startswith("content/")),
            "asset_files": sum(1 for name, _ in files if name.startswith("assets/")),
            "not_carried": skipped,
        },
        "files": sorted(digests, key=lambda row: row["path"]),
    }


def build_archive(pack: Path, out: Path, *, pool: dict | None = None,
                  player: Path | None = None) -> dict:
    """Write `<out>` (a `.vefr`) for `pack`; return the manifest written.

    Deterministic: same pack in, same bytes out - sorted entries, the ZIP
    epoch for every timestamp, no wall-clock and no machine paths. The
    manifest is the first entry, so `unzip -l` and a hex editor both meet
    the contract before the content.
    """
    pack = Path(pack)
    if not (pack / "world.json").is_file():
        _refuse(f"pack not found at {pack}: a .vefr is woven from a pack with a world.json")
    globals_, doc = bake(pack, pool=pool)
    files, skipped = _pack_files(pack)
    manifest = manifest_for(pack, globals_, doc, files=files, skipped=skipped)
    payload = json.dumps({"globals": globals_, "doc": doc},
                         ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in [(MANIFEST_NAME,
                            json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                       indent=1).encode("utf-8")),
                           *files, (GLOBALS_NAME, payload)]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if player is not None:
        write_player(Path(player), out.name)
    return manifest


def write_player(path: Path, archive_name: str, *, template: str | None = None) -> Path:
    """Write the shared Player build beside an archive; return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(player_html(archive_name, template=template), encoding="utf-8")
    return path


# ---- loading: everything is untrusted until it has been read ----

@dataclass
class Loaded:
    """One validated archive: its manifest and its playable payload."""

    manifest: dict
    globals: dict
    doc: dict
    names: list[str] = field(default_factory=list)


def _safe_entry_name(name: str) -> None:
    """Refuse an entry name that could escape the archive or mean nothing."""
    if not name or name.strip() != name:
        _refuse(f'refusing the entry "{name}": an archive name may not be padded')
    if "\\" in name:
        _refuse(f'refusing the entry "{name}": archive names use "/"')
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        _refuse(f'refusing the entry "{name}": archive paths are relative')
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts):
        _refuse(f'refusing the entry "{name}": the path leaves the archive')
    if name != MANIFEST_NAME and not name.startswith(("content/", "assets/")) \
            and name != GLOBALS_NAME:
        _refuse(f'refusing the entry "{name}": an archive holds a manifest, '
                "content/, assets/ and the game data - nothing else")


def _check_suffix(name: str) -> None:
    if name == MANIFEST_NAME or name == GLOBALS_NAME:
        return
    if _classify(name) is None:
        _refuse(f'refusing "{name}": an archive carries data and pictures, '
                "never anything that could run")


def _read_entry(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """Read one entry, capped: the zip bomb runs into the cap, not the disk."""
    if info.file_size > MAX_ENTRY_BYTES:
        _refuse(f'refusing "{info.filename}": the archive declares '
                f"{info.file_size} bytes; an entry may be at most {MAX_ENTRY_BYTES}")
    if info.compress_size and info.file_size / max(info.compress_size, 1) > MAX_RATIO:
        _refuse(f'refusing "{info.filename}": it expands '
                f"{info.file_size // max(info.compress_size, 1)}x, past the "
                f"{MAX_RATIO}x a picture ever needs")
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        _refuse(f'refusing "{info.filename}": the archive uses a compression '
                "this Player does not read")
    chunks: list[bytes] = []
    total = 0
    with zf.open(info) as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ENTRY_BYTES:
                _refuse(f'refusing "{info.filename}": it expands past '
                        f"{MAX_ENTRY_BYTES} bytes")
            chunks.append(chunk)
    return b"".join(chunks)


def _check_manifest(manifest: object) -> dict:
    """Schema and runtime floor, or a refusal that names both numbers."""
    if not isinstance(manifest, dict):
        _refuse("manifest.json is not a JSON object")
    if manifest.get("format") != FORMAT:
        _refuse(f'this file is not a .vefr archive: manifest format '
                f"{manifest.get('format')!r}, expected {FORMAT!r}")
    version = manifest.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        _refuse("the manifest's schema_version is not a number")
    if version > SCHEMA_VERSION:
        _refuse(f"this .vefr uses manifest schema {version}; this vefr reads "
                f"schema {SCHEMA_VERSION} - update the engine to play it")
    runtime = manifest.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    floor = runtime.get("min_schema_version")
    if isinstance(floor, int) and not isinstance(floor, bool) and floor > SCHEMA_VERSION:
        _refuse(f"this .vefr needs a newer Player: it asks for schema {floor} "
                f"at least, this Player reads schema {SCHEMA_VERSION}")
    game = manifest.get("game")
    if not isinstance(game, dict) or not isinstance(game.get("id"), str) \
            or not game["id"].strip():
        _refuse("the manifest names no game id")
    if not isinstance(manifest.get("files"), list):
        _refuse("the manifest lists no files")
    return manifest


def _check_payload(payload: object, manifest: dict) -> tuple[dict, dict]:
    """The game data: a JSON object of `VEFR_*` globals, and its doc block."""
    if not isinstance(payload, dict):
        _refuse(f"{GLOBALS_NAME} is not a JSON object")
    globals_ = payload.get("globals")
    doc = payload.get("doc")
    if not isinstance(globals_, dict):
        _refuse(f'{GLOBALS_NAME} carries no "globals" object')
    for key in globals_:
        if not (isinstance(key, str) and re.fullmatch(r"VEFR_[A-Z0-9_]+", key)):
            _refuse(f'{GLOBALS_NAME} names "{key}": the game data is only '
                    "window.VEFR_* globals")
    _check_urls(globals_, manifest)
    _check_urls(doc if isinstance(doc, dict) else {}, manifest)
    return globals_, (doc if isinstance(doc, dict) else {})


def _walk(value):
    """Every string inside a JSON value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _check_urls(value: object, manifest: dict) -> None:
    """Every URL the payload names must be one the manifest declared.

    The archive is offline content: it may point back at the shelf the
    pack was published from, and at nothing else. A `data:` URI may only
    carry a picture, a sound or a font.
    """
    network = manifest.get("network")
    network = network if isinstance(network, dict) else {}
    allowed = [u for u in (network.get("allowed_urls") or []) if isinstance(u, str)]
    for text in _walk(value):
        for url in _URL_RE.findall(text):
            if not any(url == a or url.startswith(a.rstrip("/") + "/") for a in allowed):
                _refuse(f"the game data points at {url}, which its manifest "
                        "does not declare - an archive reaches no network")
        for uri in re.findall(r"data:([a-zA-Z0-9.+/-]+)[;,]", text):
            if uri.lower() not in SAFE_DATA_TYPES:
                _refuse(f"the game data carries a data:{uri} URI; an archive "
                        "carries pictures, sounds and fonts")


def load_archive(path) -> Loaded:
    """Read, validate and return one archive. Raises `ArchiveRefusal`.

    Nothing is unpacked: every refusal happens before a byte of the game
    data is handed back, and the caller that wants the pictures gets them
    by name through `zf`.
    """
    path = Path(path)
    if not path.is_file():
        _refuse(f"no archive at {path}")
    if not zipfile.is_zipfile(path):
        _refuse(f"{path.name} is not a .vefr archive: a .vefr is a ZIP file")
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        _refuse(f"{path.name} is not a readable ZIP: {exc}")
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if not infos:
            _refuse(f"{path.name} is an empty ZIP: it holds no manifest and no game")
        if len(infos) > MAX_ENTRIES:
            _refuse(f"{path.name} holds {len(infos)} entries; an archive may "
                    f"hold at most {MAX_ENTRIES}")
        total = sum(i.file_size for i in infos)
        if total > MAX_TOTAL_BYTES:
            _refuse(f"{path.name} expands to {total} bytes; an archive may "
                    f"expand to at most {MAX_TOTAL_BYTES}")
        for info in infos:
            _safe_entry_name(info.filename)
            _check_suffix(info.filename)
        names = {info.filename for info in infos}
        if MANIFEST_NAME not in names:
            _refuse(f"{path.name} has no {MANIFEST_NAME}: it is not a .vefr archive")
        if GLOBALS_NAME not in names:
            _refuse(f"{path.name} has no {GLOBALS_NAME}: it carries no game to play")

        manifest = _check_manifest(_read(zf, _one(infos, MANIFEST_NAME), "manifest.json"))
        declared = {row["path"]: row for row in manifest["files"]
                    if isinstance(row, dict) and isinstance(row.get("path"), str)}
        for info in infos:
            if info.filename == MANIFEST_NAME:
                continue
            row = declared.get(info.filename)
            if row is None:
                _refuse(f'"{info.filename}" is in the archive but not in its manifest')
            data = _read_entry(zf, info)
            if len(data) != row.get("bytes"):
                _refuse(f'"{info.filename}" is {len(data)} bytes; its manifest '
                        f"says {row.get('bytes')}")
            digest = hashlib.sha256(data).hexdigest()
            if digest != row.get("sha256"):
                _refuse(f'"{info.filename}" does not match its manifest digest')
        for path_name in declared:
            if path_name not in names:
                _refuse(f'"{path_name}" is in the manifest but not in the archive')

        payload = _read(zf, _one(infos, GLOBALS_NAME), GLOBALS_NAME)
        globals_, doc = _check_payload(payload, manifest)
    return Loaded(manifest=manifest, globals=globals_, doc=doc,
                  names=sorted(names))


def _one(infos: list[zipfile.ZipInfo], name: str) -> zipfile.ZipInfo:
    for info in infos:
        if info.filename == name:
            return info
    _refuse(f"{name} is missing from the archive")  # pragma: no cover


def _read(zf: zipfile.ZipFile, info: zipfile.ZipInfo, label: str) -> object:
    """Read and JSON-parse one entry; malformed JSON is a refusal, not a crash."""
    raw = _read_entry(zf, info)
    try:
        return json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        _refuse(f"{label} is not UTF-8 text")
    except ValueError as exc:
        _refuse(f"{label} is not valid JSON: {exc}")