"""The Library - books and notes a world keeps, and the studio's own shelf.

A pack may carry a `library/` folder of markdown books, one file each:

    worlds/<name>/library/a-miners-note.md

    ---
    title: A Miner's Note
    found: map            # shelf | map | resident | earned  (default: shelf)
    at: [7, 4]            # map: the tile the book lies on (x, y)
    region: town          # map: which region (default: town)
    speaker: keeper       # resident: the voice that hands it over
    when: bell            # earned: what has to happen first
    kind: note            # book | note | terminal  (default: book)
    status: draft         # draft | approved  (default: approved) - vefr #339
    ---
    The first page.

    * * *

    The second page.

A line holding only `* * *` starts a new page. The author writes every
word; the engine only reads, checks and shows them. No model call ever
touches a book (the Library is a deterministic surface, like export).

The engine's own shelf lives in `web/library/` in the same format: the
studio handbook, how games are made. It belongs to no world.

Earned books name the moment that unlocks them (`when`). The events the
engine knows are in EARNED_EVENTS; `book:<id>` means "after reading that
book". The finding itself happens in play (a later slice); this module
defines the contract, loads it, and validates it.
"""

from __future__ import annotations

import re
from pathlib import Path

FOUND_KINDS = ("shelf", "map", "resident", "earned")
BOOK_KINDS = ("book", "note", "terminal")
# Moments an earned book can wait for. `book:<id>` is checked separately.
EARNED_EVENTS = ("bell", "first-visit", "act-complete", "rumor-verified")
PAGE_BREAK = "* * *"

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)
_AT_RE = re.compile(r"^\[\s*(-?\d+)\s*,\s*(-?\d+)\s*\]$")


def studio_shelf_dir() -> Path:
    """The engine's own shelf: web/library/ (shipped in the image with web/)."""
    from .paths import app_home
    return app_home() / "web" / "library"


def parse_book(text: str, book_id: str) -> dict:
    """Parse one book file into its canonical shape.

    Unknown front-matter keys are kept under `extra` so a pack can carry
    notes for itself without the engine rejecting them. Values are plain
    strings except `at`, which becomes [x, y] when it reads as two ints.
    """
    meta: dict[str, object] = {}
    body = text
    m = _FRONT_RE.match(text.replace("\r\n", "\n"))
    if m:
        for line in m.group(1).splitlines():
            if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key, value = key.strip(), value.strip()
            if key != "title":
                # an inline "  # comment" after a value is a note, not data
                value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
            meta[key] = value
        body = m.group(2)

    at = meta.get("at")
    if isinstance(at, str):
        am = _AT_RE.match(at)
        at = [int(am.group(1)), int(am.group(2))] if am else at

    pages = [p.strip() for p in re.split(r"(?m)^\s*\*\s\*\s\*\s*$", body)]
    known = {"title", "found", "at", "region", "speaker", "when", "kind",
             "act", "place", "status"}
    return {
        "id": book_id,
        "title": str(meta.get("title", "")).strip(),
        "found": str(meta.get("found", "shelf")).strip() or "shelf",
        "at": at,
        "region": str(meta.get("region", "town")).strip() or "town",
        "place": str(meta.get("place", "")).strip(),
        "act": str(meta.get("act", "")).strip(),
        "speaker": str(meta.get("speaker", "")).strip(),
        "when": str(meta.get("when", "")).strip(),
        "kind": str(meta.get("kind", "book")).strip() or "book",
        # `status` marks the words draft or approved (vefr #339). It is
        # read by `vefr check --release` and never by play, so an absent
        # key - every book written before it - is `approved`.
        "status": str(meta.get("status", "approved")).strip() or "approved",
        "pages": pages,
        "extra": {k: v for k, v in meta.items() if k not in known},
    }


def load_shelf(folder: Path) -> list[dict]:
    """Every *.md book in a folder, in filename order. Missing folder = []."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    books = []
    for f in sorted(folder.glob("*.md")):
        if f.name.lower() == "readme.md":
            continue
        books.append(parse_book(f.read_text(encoding="utf-8"), f.stem))
    return books


def load_library(pack: Path) -> list[dict]:
    """A pack's books: worlds/<name>/library/*.md."""
    return load_shelf(Path(pack) / "library")


# The `chest` flag's spellings, read from a book's front matter `extra`:
# the same set `cli` reads when it bakes the book into the player.
CHEST_TRUE = ("yes", "true", "1")


def _drop_ids(value) -> list[str]:
    """The ids a chest book's `drops` line names, as written.

    A comma-separated list in the front matter (`extra`, like `chest`
    itself); blank parts skipped, first-seen order kept. `cli._drop_ids`
    is the engine's own read of the same line, and filters the ids it
    keeps by the catalog - this is the list before that filter, which is
    the list the author wrote and the one a refusal is about.
    """
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        return []
    out: list[str] = []
    for part in parts:
        pid = str(part).strip()
        if pid and pid not in out:
            out.append(pid)
    return out


def _declared_items(items) -> set[str] | None:
    """The ids the pack's `items` catalog really holds, or None for no catalog.

    An entry with no `name`, or with a blank id, is dropped from what
    `weave` bakes (`cli._player_items`) and the bag refuses an id the
    baked catalog does not hold (`bagAdd`), so an id under such an entry
    is an id no drop can ever hand over. This is the catalog the player
    will really get, not the one the author wrote. An empty dict is the
    honest answer for a pack that declares no catalog at all: it holds
    nothing, and a chest that drops from it holds nothing.

    None rather than an empty set means the caller had no catalog to
    read against at all, and every drop check is skipped: a pack checked
    without its items is checked, not refused.
    """
    if items is None:
        return None
    if not isinstance(items, dict):
        return set()
    return {key for iid, spec in items.items()
            if (key := str(iid).strip())
            and isinstance(spec, dict) and str(spec.get("name", "")).strip()}


# The value a caller hands `_drop_payout_errors` when the pack wrote no
# `drops` key at all, which is NOT the same thing as a `drops` line that
# names nothing. Carrying nothing is legal; promising something and being
# unable to pay it is the bug.
NO_DROPS = object()


def _drop_payout_errors(where: str, what: str, value,
                        declared: set[str] | None) -> list[str]:
    """Why a `drops` line hands the player nothing (empty = fine).

    THE rule for every `drops` in the engine, and there is one on purpose.
    Four keys reached a 2026-10-08 game as chests whose `drops` the
    catalog could not answer, each validated green, each one a run that
    could not be finished (`giveChestDrops`, `placeDrops` and `bagAdd` all
    drop or refuse an id the baked catalog does not hold). The same shape
    then turned up on a region enemy's `drops`, on a Blueprint family's
    and on a Section family's, and three of those four each carried their
    own idea of what a real item is. This is the one idea: read against
    `_declared_items` - the catalog the weave really bakes - through the
    ids `cli._drop_ids` really keeps, so the check and the bake agree by
    construction rather than by four copies of a rule.

    Three shapes are said out loud, all of them from the line the author
    wrote:

    * `NO_DROPS` - the key is not there at all - is NOT one of them. A
      chest holds its note and nothing else, a monster that carries
      nothing is a legitimate monster, and most Section families name no
      drops. Left alone on purpose.
    * a line that names no id is a refusal, because it promises a
      payout and names nothing to pay it with.
    * an id no declared item answers for is a refusal, named one by one.
      A list where every id is dead gets the "holds nothing" sentence
      instead, because that is the whole truth about it.

    `declared` is None when the caller had no catalog to read against at
    all (no pack directory, an unreadable `world.json`), and then every
    drop check is skipped rather than wrong.
    """
    if declared is None or value is NO_DROPS:
        return []
    named = _drop_ids(value)
    if not named:
        return [f"{where}: {what} holds nothing - its 'drops' line names no item"]
    dead = [pid for pid in named if pid not in declared]
    if len(dead) == len(named):
        return [f"{where}: {what} holds nothing - its drops name no item "
                "world.json declares"]
    return [f"{where}: drop {pid!r} is not an item world.json declares"
            for pid in dead]


def _chest_drop_errors(where: str, book: dict, declared: set[str] | None) -> list[str]:
    """Why a chest book holds nothing the player can take (empty = fine).

    A chest gives the note it holds and whatever its `drops` names
    (`giveChestDrops` in the woven player), so a chest book that names a
    drop is promising an item. Four keys reached a 2026-10-08 game as
    chests whose `drops` the catalog could not answer, each validated
    green, and each one a run that could not be finished: a drop the bag
    will not take is a drop that was never there.

    Two shapes are said out loud, both from the `drops` line the author
    wrote: a line that names no id at all, and ids that resolve to no
    item. A book with no `drops` line is NOT one of them - it holds its
    note and nothing else, which is a thing a pack may mean - so it is
    left alone here. Both shapes, and the carve-out, are
    `_drop_payout_errors`'s: this function decides only whether the book
    IS a chest, and then hands the line to the one rule every other
    `drops` in the engine is read by.
    """
    if declared is None:
        return []
    extra = book.get("extra") if isinstance(book.get("extra"), dict) else {}
    if str(extra.get("chest", "")).strip().lower() not in CHEST_TRUE:
        return []
    return _drop_payout_errors(where, "the chest",
                               extra.get("drops", NO_DROPS), declared)


def _walkable(town: dict, x: int, y: int) -> bool:
    m = town.get("map") or []
    if y < 0 or y >= len(m) or x < 0 or x >= len(m[0]):
        return False
    entry = (town.get("legend") or {}).get(m[y][x], {})
    if isinstance(entry.get("solid"), bool):
        return entry["solid"] is False
    return m[y][x] not in "#~"


def validate_books(books: list[dict], *, town: dict | None = None,
                   speakers: object = None, regions: set | None = None,
                   descent: dict | None = None,
                   items: object = None) -> list[str]:
    """Every contract check for a shelf. Returns problems (empty = good).

    `town` is the validator's town block (map + legend) for map books;
    `speakers` is the act's speakers (a dict or a list of names).

    `regions` (every region the pack's acts declare) and `descent` (its
    resolved descent block) make a map book's region a checked fact. On
    2026-10-08 Cottage removed its authored cellar and six books went on
    naming regions that no longer existed: nothing could find them, and
    every check stayed green. A map book now names a declared region or a
    floor of the generated descent (`<section>-<cycle>-<floor>`). A generated
    floor is redrawn every run and whenever its Section changes, so a book on
    one names `place: near-up | near-down | anywhere` instead of a tile, and
    the floor chooses the tile each run (`delve.place_books`); every pinned
    book must find a free tile in each of `PIN_RUNS` runs. Without `regions`
    the region is not checked, as before.

    `items` is the pack's catalog, which is what a chest's `drops` is read
    against: a chest that names no item of it opens on nothing, and without
    the catalog there is nothing to read the drops against, so a caller that
    passes no catalog gets no drop check (the other checks are as before).
    """
    errors: list[str] = []
    ids = {b["id"] for b in books}
    if isinstance(speakers, dict):
        speaker_names = set(speakers)
    elif isinstance(speakers, list):
        speaker_names = {s if isinstance(s, str) else s.get("name", s.get("id", "")) for s in speakers}
    else:
        speaker_names = set()

    pinned: dict[str, tuple[int, list]] = {}
    declared = _declared_items(items)
    for b in books:
        where = f"library book '{b['id']}'"
        if not _ID_RE.match(b["id"]):
            errors.append(f"{where}: file names are lowercase letters, digits and dashes")
        if not b["title"]:
            errors.append(f"{where}: needs a title")
        errors.extend(_chest_drop_errors(where, b, declared))
        if not b["pages"] or not all(p for p in b["pages"]):
            errors.append(f"{where}: every page needs words (check for an empty page around '* * *')")
        if b["kind"] not in BOOK_KINDS:
            errors.append(f"{where}: kind must be one of {', '.join(BOOK_KINDS)}")
        found = b["found"]
        if found not in FOUND_KINDS:
            errors.append(f"{where}: found must be one of {', '.join(FOUND_KINDS)}")
            continue
        if b.get("place") and found != "map":
            errors.append(f"{where}: place goes with found: map, on a generated floor")
        if found == "map":
            at = b["at"]
            region = b["region"] or "town"
            floor = _generated_floor(region, descent) if regions is not None else None
            if b.get("place"):
                problems = _place_problems(where, b, region, floor, regions, descent)
                errors.extend(problems)
                if not problems and floor is not None:
                    pinned.setdefault(region, (floor, []))[1].append(b)
            elif not (isinstance(at, list) and len(at) == 2):
                errors.append(f"{where}: a map book needs at: [x, y]"
                              + (", or on a generated floor place: near-up, near-down or anywhere"
                                 if floor is not None else ""))
            elif region == "town" and town is not None and not _walkable(town, at[0], at[1]):
                errors.append(f"{where}: at {at} is off the map or not walkable ground")
            elif regions is not None:
                errors.extend(_region_problems(where, region, at, regions, descent))
        elif found == "resident":
            if not b["speaker"]:
                errors.append(f"{where}: a given book needs speaker: <who hands it over>")
            elif speaker_names and b["speaker"] not in speaker_names:
                errors.append(f"{where}: speaker '{b['speaker']}' is not one of this act's residents")
        elif found == "earned":
            when = b["when"]
            if when.startswith("book:"):
                if when[5:] not in ids:
                    errors.append(f"{where}: when '{when}' names a book this library doesn't have")
            elif when not in EARNED_EVENTS:
                errors.append(
                    f"{where}: when must be one of {', '.join(EARNED_EVENTS)} or book:<id>")
    for region, (depth, here) in sorted(pinned.items()):
        errors.extend(_sweep_pins(region, depth, here, descent))
    return errors


def found_words(book: dict) -> str:
    """How a book is found, in plain words (the studio shows this)."""
    f = book.get("found")
    if f == "map":
        at = book.get("at")
        return f"lies on the map at {at[0]}, {at[1]}" if isinstance(at, list) and len(at) == 2 else "lies on the map"
    if f == "resident":
        return f"given by {book.get('speaker') or 'a resident'}"
    if f == "earned":
        when = book.get("when", "")
        if when.startswith("book:"):
            return f"earned after reading '{when[5:]}'"
        return {"bell": "earned when the bell rings", "first-visit": "earned on the first visit",
                "act-complete": "earned when the act is done",
                "rumor-verified": "earned when a rumor is proven true"}.get(when, "earned")
    return "on the shelf from the start"


_FLOOR_NAME = re.compile(r"^(.*)-(\d+)-(\d+)$")


def _region_problems(where: str, region: str, at, regions: set,
                     descent: dict | None) -> list[str]:
    """Why a map book's region or tile cannot be found in play (empty = fine)."""
    if region in regions:
        return []
    floor = _generated_floor(region, descent)
    if floor is None:
        have = ", ".join(sorted(regions)) or "none"
        example = ""
        sections = (descent or {}).get("sections") or []
        if sections and isinstance(sections[0], dict) and sections[0].get("id"):
            example = f", or a generated floor such as {sections[0]['id']}-0-1"
        return [f"{where}: region '{region}' is not a region of this pack; it has {have}{example}"]
    return [f"{where}: {region} is a generated floor, redrawn every run (New descent) and whenever its "
            f"Section changes, so a fixed tile can land in a wall; give place: near-up, near-down or "
            f"anywhere instead of at"]


def _generated_floor(region: str, descent: dict | None) -> int | None:
    """The depth a generated floor name plays at, or None if it is not one of the descent's."""
    m = _FLOOR_NAME.match(region)
    if not m or not isinstance(descent, dict):
        return None
    sections = [s for s in (descent.get("sections") or []) if isinstance(s, dict)]
    counts = [s.get("floors") if isinstance(s.get("floors"), int) else 0 for s in sections]
    total = sum(counts)
    cycle, k = int(m.group(2)), int(m.group(3))
    before = 0
    for section, count in zip(sections, counts):
        if section.get("id") == m.group(1):
            return cycle * total + before + k if 1 <= k <= count else None
        before += count
    return None


PIN_RUNS = 200      # the runs `vefr check` draws for each floor that holds a pinned book


def _place_problems(where: str, b: dict, region: str, floor: int | None, regions: set | None,
                    descent: dict | None) -> list[str]:
    """Why a book's `place` cannot be used as written (empty = fine)."""
    from . import delve
    if regions is not None and floor is None:
        if region in regions:
            return [f"{where}: place is for a book on a generated floor; {region} is drawn by hand, "
                    f"so give at: [x, y]"]
        return _region_problems(where, region, None, regions, descent)
    if b["place"] not in delve.BOOK_PLACES:
        return [f"{where}: place must be {', '.join(delve.BOOK_PLACES[:-1])} or {delve.BOOK_PLACES[-1]}"]
    if b["at"] is not None:
        return [f"{where}: a book with place takes no at; the floor chooses its tile each run"]
    return []


def _sweep_pins(region: str, depth: int, books: list, descent: dict) -> list[str]:
    """Every pinned book on `region` finds a free tile in each of PIN_RUNS runs."""
    from . import delve
    wanted = [{"id": b["id"], "place": b["place"]} for b in books]
    if any(b["place"] in delve.VAULT_PLACES for b in wanted) and not delve.floor_plan(descent, depth, 0).get("vault"):
        return [f"library book '{b['id']}': place {b['place']} needs the vault on its Section's warden floor, "
                f"and {region} has none" for b in wanted if b["place"] in delve.VAULT_PLACES]
    missing: dict[str, int] = {}
    for run in range(PIN_RUNS):
        got = delve.place_books(delve.floor_plan(descent, depth, run), wanted)
        for b in wanted:
            if b["id"] not in got:
                missing.setdefault(b["id"], run)
    return [f"library book '{book_id}': {region} has no free tile for it in run {run}"
            for book_id, run in sorted(missing.items())]
