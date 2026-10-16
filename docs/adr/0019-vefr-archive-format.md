# 0019 - The `.vefr` game archive: content, assets, and a manifest

Date: 2026-10-16

## Status

**Accepted (first slice).** The owner's decision is recorded below and
this ADR implements it; the compatibility policy and the manifest are the
part of the format that is now fixed for `schema_version` 1. What remains
is listed plainly under *Not in this slice*.

Rylee's words, from the rolling interview (issue #455 comment 6221583883,
relayed as Sol #525):

> "For VEFR #455, I choose A: a portable .vefr archive containing game
> content, assets and a manifest, with the shared Player providing the
> engine. Keep standalone HTML export separately."

That settles the a/b/c architecture question the issue posed - declarative
source archive, baked payload, or a transitional dual export. **A wins.**
This ADR does not re-open it.

## Context

`vefr weave` writes one self-contained HTML file: the pack is resolved,
every picture is inlined as a data URI, and the result folds into
`web/packaged.html`. It is a good artifact for a person and a bad one for
a program: you cannot diff it, you cannot read the pack back out of it,
and nothing tells a Player which engine version it needs.

Nothing in the tree described a *game artifact* that is inspectable and
versioned. ADR 0016's JSON Session Capsule and Action Tape are player
history, not the game; this is the game.

The engine already knows every seam an archive needs:

* `cli.weave_html` is the only bake, and it is a pure function of a pack;
* `maplab.load_pack` / `blueprint.check_errors` are the runtime checks an
  archive inherits by being woven;
* the Player reads `window.VEFR_*` globals and nothing else.

## Decision

### 1. A `.vefr` is a ZIP with a fixed shape

```
manifest.json         the contract: schema, runtime, identity, digests
content/...           the pack's authored files, byte for byte
assets/...            the pack's pictures, sounds and fonts, byte for byte
data/globals.json     the playable payload: the window.VEFR_* globals
```

Authored text (`.md`, `.json`, `.txt`, `.yaml`, ...) and any file with no
suffix at all - a pack's `LICENSE`, its `README` - become `content/`.
Pictures, sounds and fonts become `assets/`. Anything else - a `.py`, a
`.sh`, a blob the player cannot draw - is **left out of the archive** and
named on the console at export, so an author learns about it rather than
wondering where it went. An archive never carries a file that could run.

An archive is unpackable and readable with `unzip`, `less`, a hex editor
and `jq`. That is the point of the shape: `unzip -p game.vefr
content/world.json` is the pack's own file.

### 2. One bake, two containers

`data/globals.json` is woven by `cli.weave_html` itself. `vefrfile` hands
the weave a JSON skeleton built from the player template's own
`window.VEFR_X = {{x_json}};` lines, so the archive carries exactly the
globals a woven HTML of that pack carries - key for key - and a global
added to the Player tomorrow joins the archive the day it joins the weave.
There is no second exporter to drift.

`tests/test_vefr_archive.py` asserts the equality directly, for Emberfield
and for a skinned fixture pack.

`weave_html` grew two additive keywords for this: `template=` (fold the
same substitutions over a different template) and `doc=` (a dict to fill
with the four page-level values the template folds in around the data).
With neither argument, every existing pack weaves byte for byte as before.

### 3. The manifest

```json
{
  "format": "vefr-archive",
  "schema_version": 1,
  "engine_version": "2.1.0",
  "runtime": {
    "player_contract": "vefr-player/1",
    "min_schema_version": 1,
    "live_model": "optional - the Player may be given an endpoint by the player"
  },
  "game": {"id": "emberfield", "title": "Emberfield", "pack": "emberfield"},
  "data": {"globals": "data/globals.json"},
  "capabilities": ["library", "items", "sound"],
  "network": {"policy": "offline-only", "allowed_urls": []},
  "provenance": {
    "source": "emberfield",
    "license": "CC BY-SA 4.0",
    "content_files": 15,
    "asset_files": 22,
    "not_carried": ["notes/plan.py: not content and not an asset the player can use"]
  },
  "files": [
    {"path": "content/world.json", "bytes": 2607, "sha256": "ba9b1b15affb..."}
  ]
}
```

Each answer the issue asked for, and where it comes from:

| Question | Answer |
|---|---|
| Runtime / version | `schema_version` (the format), `runtime.min_schema_version` (the Player floor), `runtime.player_contract` (which Player shape), `engine_version` (who wrote it) |
| Pack / asset identity | `game.id`; every file's SHA-256 and length in `files` |
| Offline guarantees | `network.policy: "offline-only"`; the only URLs an archive may name are `network.allowed_urls` |
| Optional live-model features | `runtime.live_model` - the game plays with no model at all; a model is the *player's* choice, made in the Player, never read from the archive |
| Licensing / provenance | `provenance.license` (the pack's own licence line), `provenance.source`, and the pack's `content/` verbatim, credit included |

`capabilities` is read from `docs/features.json` through
`vefr.features.scan_pack` - the audited catalog, not a second list of what
a game can do. A box without the catalog beside it still exports; the
manifest simply names none, and no Player refuses on a capability it
cannot read.

### 4. Compatibility policy

* **A manifest names one `schema_version`.** A Player reads the version it
  was built with and every earlier one it still understands. The number is
  a whole number or the archive is refused: `1.5`, `NaN`, `Infinity` and a
  quoted `"1"` are shapes no schema has ever named, and both readers refuse
  them in the same words.
* **Newer than the Player reads** → refuse, naming both numbers. An old
  engine must never guess at a format it has not seen.
* **Older** → read it, provided the payload shape still fits the Player's
  own globals. This is the forward-compatible half.
* **`runtime.min_schema_version` above what the Player reads** → refuse,
  as a separate sentence from the schema check: the file is readable in
  principle but asks for a Player this one is not.
* **A refused archive is never partially installed.** Validation happens
  before any byte of the payload reaches the page.
* **A schema bump is a breaking change to the format, not to the game.**
  `vefr weave` keeps working whatever the archive schema is; the two are
  independent artifacts.

### 5. Refusals

Every refusal is one plain sentence naming what was wrong, in both readers
(`vefrfile.load_archive` and the Player's loader part). The loaders refuse,
in this order:

```
this file is not a .vefr archive: a .vefr is a ZIP file
refusing "data/globals.json": the archive names it twice; one file, one entry
refusing the entry "content/../../etc/passwd": the path leaves the archive
refusing the entry "/etc/passwd": archive paths are relative
refusing "content/run.py": an archive carries data and pictures, never anything that could run
refusing the entry "secrets.txt": an archive holds a manifest, content/, assets/ and the game data - nothing else
refusing "assets/floor.png": it expands 1000x, past the 200x a picture ever needs
refusing "assets/floor.png": it expands past 67108864 bytes
this .vefr holds 5000 entries; an archive may hold at most 4096
this .vefr has no manifest.json: it is not a .vefr archive
the manifest's schema_version is not a whole number
this .vefr uses manifest schema 3; this vefr reads schema 1 - update the engine to play it
this .vefr needs a newer Player: it asks for schema 2 at least, this Player reads schema 1
"content/world.json" does not match its manifest digest
"content/world.json" is in the archive but not in its manifest
"content/world.json" is in the manifest but not in the archive
data/globals.json names "rm_rf": the game data is only window.VEFR_* globals
the game data points at https://elsewhere.test/x, which its manifest does not declare - an archive reaches no network
the game data carries a data:text/html URI; an archive carries pictures, sounds and fonts
```

Bounds: 4096 entries, 64 MB per entry, 256 MB expanded, and a
declared-to-actual expansion ratio above 200x. The ratio is what a
decompression bomb runs into; a real PNG never approaches it.

The load never unpacks to disk: `vefr archive --inspect` validates and
prints, and the Player holds bytes in memory.

### 6. The shared Player, and the one honest gate

`vefr archive` writes two files by default:

```
dist/emberfield.vefr            the archive
dist/emberfield.player.html     the shared Player that opens it
```

The Player build is `web/packaged.html` with the baked data block
removed - the same parts, byte for byte, with the game arriving from the
archive at run time. A woven file keeps that block, so `vefr weave` is
untouched.

The gate is the whole design. Several parts read a `window.VEFR_*` global
**once, while the page parses** (`080`'s `MODEL_OPTIONAL`, the `LIBRARY_KEY`
/ `BAG_KEY` / `GOLD_KEY` save keys, `448`'s tile loaders). An archive
arrives asynchronously - a browser cannot inflate a ZIP synchronously - so
installing it as it arrives would leave those reads looking at an empty
world: the game would save to `vefr-bag-world` and draw no ground.

So the loader (`web/player/parts/046-vefr-archive-loader.js`, before
`050`) does this:

1. if this tab already holds the archive (sessionStorage), install it
   **synchronously**, before any part parses;
2. otherwise fetch it (`?vefr=`, the archive this build was written
   beside, or a file dropped on the page), validate it, cache it, and
   **reload once** - so the next parse starts with the game already in
   place.

The reload is the honest way to be early rather than late. It costs one
page load, once per tab session.

The cache is `sessionStorage`, not the player's `store` helper: it is a
same-session fast path that must not outlive the session (a stale archive
in `localStorage` would outlive the file it came from), and it is bounded -
about 3.5 MB. A larger game says so in one sentence and points at
`vefr weave`.

In a woven file the whole block is dormant: `window.VEFR_ARCHIVE_URL` is
empty, nothing is fetched, and the title screen is untouched.

Install never parses an archive string as markup. The four `doc` values
are set as data: `title`, `tagline` and `fonts_css` are text, and the
title picture is the one exception worth spelling out, because it is the
only one the weave writes as a tag. `cli._player_title_art` writes exactly
one shape - `<img class="ts-art" src="data:image/..." alt="">`, plus at
most a `<style>` carrying the pack's two accent colours - so the loader
accepts exactly that shape and nothing else. The `src` is lifted as a
string, it has to be an inline picture of a type an archive may carry, and
the element it lands in is one the browser builds; the accent becomes two
custom properties on `documentElement`. Markup that is not the exporter's
- an `onerror`, a `javascript:` src, a second tag - is simply not
installed. The same promise holds for the whole archive: a ZIP that names
one path twice is refused rather than read as whichever of the two this
reader happened to meet first.

### 7. Determinism

The same pack exports the same bytes: entries sorted, `manifest.json`
first, every timestamp pinned to the ZIP epoch, no wall-clock and no
machine paths in the manifest. Two exports of Emberfield are byte
identical, and a test says so.

## Alternatives

**A baked playable payload ZIP (issue option B).** Rejected by the owner,
and the reason holds: it makes a second copy of the engine that must be
rebuilt for every engine change, and the woven HTML already is that
artifact.

**A transitional dual export (option C).** Superseded: `vefr weave` keeps
running unchanged, which *is* the dual export, with no new code path.

**JSON with a sidecar ZIP of assets.** Would make the manifest the only
thing a tool has to trust and the art unverifiable against it. One ZIP,
one digest list, one validation pass.

**Uncompressed archives.** Bigger files, no integrity story worth having.

## Not in this slice

Named, so the next hand does not have to guess:

* **Assets as files.** Today the payload carries pictures as data URIs, so
  the Player needs no asset plumbing and the archive duplicates the pack's
  bytes (raw under `assets/`, base64 inside `globals.json`). The next
  schema version replaces a data URI with an `assets/` reference and the
  Player resolves it to a blob URL; that also lifts the session-storage
  ceiling, which is the one limit a large art pack hits today.
* **A browser-suite test that opens a real `.vefr`.** The ZIP reader, the
  `DecompressionStream` path and the reload gate are JavaScript, and this
  slice ran without Node or a browser in the sandbox. The Python side is
  fully tested; the Player side needs one Playwright case before anyone
  calls the round trip proven in a browser.
* **Multi-act / progression archives**, saves inside an archive, signing,
  and a `.vefr` in the studio's publish flow.

## Acceptance

* `schema_version` 1, the runtime policy, the manifest and the refusal
  sentences are documented here, with examples.
* Round trip: Emberfield's archive globals are its woven globals, key for
  key. Determinism: two exports, identical bytes. Rejection: 20 refusal
  tests, each asserting the words.
* Existing output is intact: `vefr weave` weaves the same game it always
  did, `scripts/build_player.py --check` is green, and a woven file sleeps
  through the loader.
* Skins, fonts, pictures and credits survive with the same look - pinned
  against a skinned fixture pack.
* Reuse, not a clone: the bake is `weave_html`, the refusals come from the
  weave's Blueprint check and `vefr check`'s loader, and capabilities come
  from `docs/features.json`.