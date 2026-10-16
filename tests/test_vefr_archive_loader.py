"""The `.vefr` archive loader part itself (vefr#455, fix round).

`tests/test_vefr_archive.py` pins the format the two readers agree on. This
file drives the Player's own reader - the REAL `046-vefr-archive-loader.js`
in jsdom, through `tests/fixtures/vefr_archive_loader_harness.mjs` - and pins
the three things the second-model review found on it:

* `install` must never hand an archive's `doc.title_art_img` to an HTML
  parser. A `.vefr` carrying `<img src=x onerror=...>` there ran script,
  which is the one promise the loader does not get to break. The element is
  built with `createElement`, and only an exporter-shaped `src` of an allowed
  picture type is set on it.
* `openArchive` must refuse a ZIP that names one path twice, so a browser and
  the command line cannot read two different games out of one archive. The
  Python reader refuses it too, with the same sentence.
* `schema_version` must be a whole number - not `1.5`, not `NaN`, not
  `Infinity`, not `"1"` - exactly as `vefrfile._check_manifest` holds it.

The harness needs node; where there is none the behavioural tests are
skipped. The static tests at the bottom need nothing and run anywhere.
"""

import base64
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import warnings
import zipfile
from pathlib import Path

import pytest

from vefr import vefrfile

ROOT = Path(__file__).resolve().parents[1]
PART = ROOT / "web" / "player" / "parts" / "046-vefr-archive-loader.js"
HARNESS = ROOT / "tests" / "fixtures" / "vefr_archive_loader_harness.mjs"

GOOD_GLOBALS = {"VEFR_WORLD": {"title": "Test"}}
#: What `cli._player_title_art` writes, down to the `alt=""` - the only shape
#: `install` accepts. The two below are the exporter's own output for a real
#: pack, so this is the loader's shape held to the weave and not to a copy of
#: it; the ones beside them are the shape written out by hand.
ART_SRC_RE = re.compile(r'<img class="ts-art" src="([^"]*)" alt="">')
ACCENT_RE = re.compile(r"--accent: (#[0-9a-fA-F]{6})")
ART = '<img class="ts-art" src="data:image/png;base64,iVBORw0KGgo=" alt="">'
ACCENT = '<style>html:root { --accent: #AABBCC; --accent-on: #1B1206; }</style>'


def _exporter_art(**player) -> str:
    """The markup `vefr weave` writes into `doc.title_art_img` for the sample
    world: the engine's own front-door picture, plus the accent when asked."""
    from vefr.cli import _player_title_art
    return _player_title_art(ROOT / "worlds" / "sample-world", {"player": player},
                             ROOT / "web")


# ---- the archives the harness reads ----

def _payload() -> bytes:
    return json.dumps({"globals": GOOD_GLOBALS, "doc": {}}).encode("utf-8")


def _manifest(files: dict, **over) -> bytes:
    """The manifest for these files, in the exporter's own shape."""
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


def _zip(entries: list, **over) -> str:
    """A `.vefr` as base64, entries in the order given, so a name may repeat.

    Stored, not deflated: the loader reads both methods, and a stored entry is
    one fewer moving part in a harness that only means to hand it bytes. The
    manifest's digests are real, so `openArchive` checks them for real too.
    """
    files: dict = {}
    for name, data in entries:
        files.setdefault(name, data)
    rows = [(vefrfile.MANIFEST_NAME, _manifest(files, **over))] + list(entries)
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # zipfile's own "Duplicate name" warning
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for name, data in rows:
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, data)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---- every case, read in one node run ----

ART_CASES = [
    ("exporter", _exporter_art()),
    ("exporter+accent", _exporter_art(accent="#3F7E84")),
    ("ours", ART),
    ("ours+accent", ART + ACCENT),
    ("onerror", '<img src="x" onerror="window.__archiveScriptRan=true">'),
    ("onerror-on-ours", ART.replace(' alt="">',
                                    ' onerror="window.__archiveScriptRan=true" alt="">')),
    ("javascript-src", '<img class="ts-art" src="javascript:alert(1)" alt="">'),
    ("html-data-uri", '<img class="ts-art" src="data:text/html;base64,PHNjcmlwdD4=" alt="">'),
    ("svg-onload", '<svg onload="window.__archiveScriptRan=true"></svg>'),
]
#: The cases the exporter's own shape does not match.
NOT_OURS = [name for name, _ in ART_CASES if name not in ("exporter", "exporter+accent",
                                                          "ours", "ours+accent")]

ARCHIVE_CASES = {
    "plain": _zip([(vefrfile.GLOBALS_NAME, _payload())]),
    "globals-twice": _zip([(vefrfile.GLOBALS_NAME, _payload()),
                           (vefrfile.GLOBALS_NAME, b'{"globals":{"VEFR_WORLD":{"title":"smuggled"}}}')]),
    "content-twice": _zip([(vefrfile.GLOBALS_NAME, _payload()),
                           ("content/world.json", b'{"title": "one"}'),
                           ("content/world.json", b'{"title": "two"}')]),
    "schema-1": _zip([(vefrfile.GLOBALS_NAME, _payload())], schema_version=1),
    "schema-half": _zip([(vefrfile.GLOBALS_NAME, _payload())], schema_version=1.5),
    "schema-quoted": _zip([(vefrfile.GLOBALS_NAME, _payload())], schema_version="1"),
    "schema-boolean": _zip([(vefrfile.GLOBALS_NAME, _payload())], schema_version=True),
    "schema-nan": _zip([(vefrfile.GLOBALS_NAME, _payload())], schema_version=float("nan")),
    "schema-infinite": _zip([(vefrfile.GLOBALS_NAME, _payload())], schema_version=float("inf")),
    "schema-newer": _zip([(vefrfile.GLOBALS_NAME, _payload())],
                         schema_version=vefrfile.SCHEMA_VERSION + 1),
}

NOT_WHOLE = "the manifest's schema_version is not a whole number"
REPEATED = "the archive names it twice; one file, one entry"


@pytest.fixture(scope="module")
def read():
    """One node run over every case: what the loader installed, and what it
    refused, in its own words."""
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    spec = {"art": [{"name": name, "markup": markup} for name, markup in ART_CASES],
            "archives": [{"name": name, "zip": blob} for name, blob in ARCHIVE_CASES.items()]}
    run = subprocess.run(["node", str(HARNESS), str(PART)], input=json.dumps(spec),
                         capture_output=True, text=True, timeout=240)
    assert run.returncode == 0, run.stderr + run.stdout
    result = json.loads(run.stdout)
    rows = {row["name"]: row for row in result["art"] + result["archives"]}
    assert sorted(rows) == sorted([n for n, _ in ART_CASES] + list(ARCHIVE_CASES)), sorted(rows)
    return rows


# ---- 1. the title art is data, never markup ----

def test_the_title_art_the_exporter_writes_still_lands(read):
    """The look is the acceptance line: a pack's title picture still shows,
    as one element the browser built. The markup here is the exporter's own
    output for the sample world, so this is the weave and the loader agreeing
    on one shape rather than a copy of it."""
    for name in ("exporter", "ours"):
        got = read[name]
        assert got["count"] == 1, got
        assert got["tags"] == ["IMG"], got
        assert got["srcs"] == [ART_SRC_RE.search(dict(ART_CASES)[name]).group(1)], got
        assert got["handlers"] == [] and got["ran"] is False, got


def test_a_packs_accent_colour_still_lands(read):
    """`world.json`'s `player.accent` is two hex values; they are set as the
    two custom properties the exporter's stylesheet reads, and add no element."""
    for name in ("exporter+accent", "ours+accent"):
        got = read[name]
        assert got["count"] == 1 and got["tags"] == ["IMG"], got
        assert got["accent"] == ACCENT_RE.search(dict(ART_CASES)[name]).group(1), got


@pytest.mark.parametrize("name", NOT_OURS)
def test_an_archive_markup_string_installs_nothing_that_could_run(read, name):
    """The review's finding, as a test: an `onerror`, a `javascript:` src, a
    `data:text/html` picture and an `<svg onload>` all miss the shape the
    exporter writes, so nothing is installed, nothing runs, and the title
    screen holds nothing at all."""
    got = read[name]
    assert got["count"] == 0, got
    assert got["tags"] == [] and got["handlers"] == [] and got["html"] == "", got
    assert got["ran"] is False, "archive markup ran script"


# ---- 2. one file, one entry ----

@pytest.mark.parametrize("name,path", [("globals-twice", vefrfile.GLOBALS_NAME),
                                      ("content-twice", "content/world.json")])
def test_a_zip_that_names_one_path_twice_is_refused(read, name, path):
    got = read[name]
    assert got["ok"] is False, got
    assert got["error"] == f'refusing "{path}": {REPEATED}', got


def test_a_zip_named_once_still_opens(read):
    """The refusal above is about the repeat, not about the harness: an
    archive named once opens, digests and all."""
    got = read["plain"]
    assert got["ok"] is True, got
    assert got["schema"] == 1 and got["globals"] == ["VEFR_WORLD"], got


# ---- 3. a whole schema_version, or none ----

@pytest.mark.parametrize("name", ["schema-half", "schema-quoted", "schema-boolean"])
def test_a_schema_version_that_is_not_a_whole_number_is_refused(read, name):
    """`1.5`, `"1"` and `true` are shapes no schema has ever named, and
    `Number.isInteger` is what says so - the same rule the Python reader
    holds in `vefrfile._check_manifest`, in the same words."""
    got = read[name]
    assert got["ok"] is False, got
    assert got["error"] == NOT_WHOLE, got


@pytest.mark.parametrize("name", ["schema-nan", "schema-infinite"])
def test_a_schema_version_json_cannot_carry_is_refused_too(read, name):
    """`NaN` and `Infinity` are not JSON numbers, so an archive naming one is
    refused before the manifest is an object at all."""
    got = read[name]
    assert got["ok"] is False, got


def test_a_newer_schema_is_still_refused_with_both_numbers(read):
    got = read["schema-newer"]
    assert got["ok"] is False, got
    assert got["error"] == ("this .vefr uses manifest schema 2; this vefr reads schema 1 "
                            "- update the engine to play it"), got


def test_schema_one_still_opens(read):
    got = read["schema-1"]
    assert got["ok"] is True and got["schema"] == 1, got


# ---- the two readers say the same words, and no sink comes back ----

def test_the_loader_has_no_html_parser_sink_for_archive_strings():
    """A static guard that runs everywhere: `insertAdjacentHTML`, `innerHTML`
    and friends never come back into this part. The browser test above is the
    behaviour; this is the door staying shut."""
    text = PART.read_text(encoding="utf-8")
    for sink in ("insertAdjacentHTML", "innerHTML", "outerHTML", "document.write",
                 "insertAdjacentText", "eval("):
        assert sink not in text, f"{sink} would let archive markup into the page again"


def test_both_readers_refuse_in_the_same_words():
    """One sentence, two implementations: a refusal the Player writes and the
    command line does not is a refusal that drifts."""
    player = PART.read_text(encoding="utf-8")
    python = (ROOT / "src" / "vefr" / "vefrfile.py").read_text(encoding="utf-8")
    for words in (REPEATED, NOT_WHOLE):
        assert words in player, words
        assert words in python, words


def test_the_committed_player_carries_this_part():
    """`scripts/build_player.py --check` is the contract; run it here."""
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_player.py"), "--check"],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr + run.stdout