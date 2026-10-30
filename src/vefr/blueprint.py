"""Blueprint formats 1, 2 and 3 - expand a small source into enemy
records, into things, and into places.

A pack may carry a `blueprint.json` at its root: the edited truth for the
regions it owns. This module is the library half of
`docs/adr/0008-blueprint-format.md` (format 1), `docs/adr/0010` (format
2, `things`; format 3, `places`): the versioned readers, the closed key
sets, the validator and the expander. It adds no runtime and no rule
language - a pack word grants no authority.

Format 1 is acts-shape only. `expand` returns `{region_key: [record]}`
in file order; each record's keys follow `FIELD_ORDER` and absent keys
are skipped. Format 3 keeps that shape and adds `places`: a door, a
stair or a sign, placed by a sentence that only `vefr normalize`
resolves, and written into the region's own `map.md`. Format 2 keeps
format 1's shape and adds `things`, a list at the top level rather than
a region key: one thing is either in the pack from the start or carried
by one enemy instance in any region the Blueprint owns. Nothing here
reads the clock, the network or a model.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
from collections import deque
from pathlib import Path

from . import library
from .maplab import _map_tile_walkable, load_pack

NORMALIZER_VERSION = 1

# One sentence for a version this VEFR does not read, wherever it is
# reached from, so the author reads the same refusal either way.
VERSION_SENTENCE = "blueprint version must be the integer 1, 2 or 3"

TOP_KEYS = frozenset({"blueprint", "families", "regions", "things"})
# `things` is format 2's own top key, so the two formats beside it keep
# their own set rather than borrowing the new one: a format-1 file that
# brings one is a file asking for a format it is not.
TOP_KEYS_V1 = frozenset({"blueprint", "families", "regions"})
FAMILY_KEYS = frozenset({"defaults", "extends"})
# ADR 0021 added `guard` (what a blow at the monster loses), `drop_chance`
# (the share of its kills that drop anything) and `gold` (the coins a kill
# pays, as [lo, hi]); ADR 0024 added `skills` (what it can do besides walk
# up and bite). `rpg.family_errors` checks their values.
FIELD_KEYS = frozenset({"name", "sprite", "hp", "atk", "xp", "sight", "drops",
                        "guard", "drop_chance", "gold", "skills"})
REGION_KEYS = frozenset({"enemies", "places"})
# Format 1 closed its regions on `enemies` alone, and it still does: a
# format-1 file carrying `places` is a file asking for a format it is
# not, so read_v1 keeps its own set rather than borrowing the new one.
REGION_KEYS_V1 = frozenset({"enemies"})
INSTANCE_KEYS = frozenset({"id", "family", "at", "properties"})
# `id` and `from` are the Blueprint's own; the rest are exactly the
# fields `cli._player_items` reads off an `items` entry, in the order it
# writes them, so a thing expands into the ordinary hand-written shape.
THING_KEYS = frozenset({
    "id", "from", "name", "sprite", "value", "heal", "use", "keep",
    "slot", "mods", "light",
})
ITEM_ORDER = ("name", "sprite", "value", "heal", "use", "keep", "light",
              "slot", "mods")
PLACE_KEYS = frozenset({
    "id", "kind", "at", "glyph", "tile", "base", "label", "text",
    "to", "to_at", "needs", "locked_text",
})
# A place is one of these three things on a tile; the key rules follow
# from which one it is (`to` for a door and a stair, a `label` for a
# sign), which is why an unknown kind is refused before any of them.
PLACE_KINDS = ("door", "stair", "sign")

FIELD_ORDER = ("id", "name", "sprite", "at", "hp", "atk", "xp", "sight", "drops",
               "guard", "drop_chance", "gold", "skills")


class BlueprintRefusal(ValueError):
    """A pack that must not be woven or published: its Blueprint output is
    stale or invalid. The message is the same sentence `vefr check` prints;
    the front doors print it without a traceback."""


class BlueprintError(Exception):
    """A Blueprint that cannot be read or expanded.

    `str(err)` is one plain sentence; `.pointer` is the JSON pointer of
    the offending value ("" when the error names no value).
    """

    def __init__(self, message: str, pointer: str = "") -> None:
        super().__init__(message)
        self.pointer = pointer


def _esc(token: object) -> str:
    """Escape one pointer token: `~` -> `~0`, `/` -> `~1`."""
    return str(token).replace("~", "~0").replace("/", "~1")


def _check_keys(obj: dict, allowed: frozenset[str], base: str) -> None:
    """Refuse any key of `obj` that is not in `allowed`.

    `base` is the pointer of `obj` itself; the pointer of an offending
    key is `base`/escaped-key.
    """
    for key in obj:
        if key not in allowed:
            raise BlueprintError(
                f"unknown key {key!r} at {base or '/'}",
                f"{base}/{_esc(key)}",
            )


def read(path: str | Path) -> dict:
    """Parse a Blueprint JSON file and return it unchanged."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BlueprintError(f"blueprint file {path} could not be read") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise BlueprintError(f"blueprint file {path} is not valid JSON") from exc


def read_v1(source: dict) -> dict:
    """Validate a format-1 Blueprint against the closed key sets."""
    return _read(source, 1)


def read_v2(source: dict) -> dict:
    """Validate a format-2 Blueprint: format 1's acts shape plus
    `things`, a list at the top level rather than a region key, because
    one thing is not in one place."""
    return _read(source, 2)


def read_v3(source: dict) -> dict:
    """Validate a format-3 Blueprint: format 1's acts shape plus
    `places`, whose records carry a placement sentence rather than a
    coordinate."""
    return _read(source, 3)


def _read(source: dict, version: int) -> dict:
    """The reader body the three formats share, closed on their own key
    sets.

    Only the version, the top keys, the region keys and `places` or
    `things` differ, so one body keeps the readers from drifting into
    three dialects of one format.
    """
    if not isinstance(source, dict):
        raise BlueprintError("blueprint must be a JSON object", "")
    if type(source.get("blueprint")) is not int or source.get("blueprint") != version:
        raise BlueprintError(VERSION_SENTENCE, "/blueprint")
    _check_keys(source, TOP_KEYS if version == 2 else TOP_KEYS_V1, "")

    families = source.get("families", {})
    if not isinstance(families, dict):
        raise BlueprintError("families must be an object", "/families")
    for name, family in families.items():
        base = f"/families/{_esc(name)}"
        if not isinstance(family, dict):
            raise BlueprintError("a family must be an object", base)
        _check_keys(family, FAMILY_KEYS, base)
        if "extends" in family and not isinstance(family["extends"], str):
            raise BlueprintError("extends must name one family", f"{base}/extends")
        defaults = family.get("defaults", {})
        if not isinstance(defaults, dict):
            raise BlueprintError("defaults must be an object", f"{base}/defaults")
        _check_keys(defaults, FIELD_KEYS, f"{base}/defaults")

    regions = source.get("regions", {})
    if not isinstance(regions, dict):
        raise BlueprintError("regions must be an object", "/regions")
    region_keys = REGION_KEYS if version == 3 else REGION_KEYS_V1
    for rkey, region in regions.items():
        base = f"/regions/{_esc(rkey)}"
        if not isinstance(region, dict):
            raise BlueprintError("a region must be an object", base)
        _check_keys(region, region_keys, base)
        enemies = region.get("enemies", [])
        if not isinstance(enemies, list):
            raise BlueprintError("enemies must be a list", f"{base}/enemies")
        for i, instance in enumerate(enemies):
            ibase = f"{base}/enemies/{i}"
            if not isinstance(instance, dict):
                raise BlueprintError("an enemy must be an object", ibase)
            _check_keys(instance, INSTANCE_KEYS, ibase)
            if not isinstance(instance.get("id"), str) or not instance["id"]:
                raise BlueprintError("enemy is missing its id (a non-empty string)", f"{ibase}/id")
            if not isinstance(instance.get("family"), str):
                raise BlueprintError("enemy must name one family as a string", f"{ibase}/family")
            at = instance.get("at")
            if at is not None and not (
                isinstance(at, list) and len(at) == 2
                and all(type(n) is int for n in at)
            ):
                raise BlueprintError("at must be [x, y] whole numbers", f"{ibase}/at")
            properties = instance.get("properties", {})
            if not isinstance(properties, dict):
                raise BlueprintError("properties must be an object", f"{ibase}/properties")
            _check_keys(properties, FIELD_KEYS, f"{ibase}/properties")
        if version == 3:
            _check_places(region.get("places", []), f"{base}/places")
    if version == 2:
        _check_things(source.get("things", []), "/things")
    return source


def _check_things(things: object, base: str) -> None:
    """Every refusal a `things` list can draw, before any pack is read.

    Shape only: what a thing says about itself. A `name` is required
    rather than defaulted, because `cli._player_items` drops an item
    entry with no name and the player would never meet the thing.
    """
    if not isinstance(things, list):
        raise BlueprintError("things must be a list", base)
    seen: set = set()
    for i, thing in enumerate(things):
        tbase = f"{base}/{i}"
        if not isinstance(thing, dict):
            raise BlueprintError("a thing must be an object", tbase)
        _check_keys(thing, THING_KEYS, tbase)
        for key in ("id", "name"):
            if not isinstance(thing.get(key), str) or not thing[key]:
                raise BlueprintError(
                    f"thing is missing its {key} (a non-empty string)",
                    f"{tbase}/{key}")
        if thing["id"] in seen:
            raise BlueprintError(
                f"duplicate thing id {thing['id']!r}", f"{tbase}/id")
        seen.add(thing["id"])
        # The id is one token of the `/items/<id>` pointer that owns the
        # written entry, and the writer stores the token as it stands
        # rather than un-escaping it - so an id holding `/` or `~` would
        # bake an entry under a name nothing reads back, and the next
        # check would call the pack stale for good. Refused here, where
        # the author is still editing a source.
        if "/" in thing["id"] or "~" in thing["id"]:
            raise BlueprintError(
                f"thing id {thing['id']!r} may not hold / or ~ (it would "
                f"be a pointer token)", f"{tbase}/id")
        if "from" in thing and (
                not isinstance(thing["from"], str) or not thing["from"]):
            raise BlueprintError(
                "from must name one enemy instance (a non-empty string)",
                f"{tbase}/from")
        # The guide gives each of these a shape, and the item reader
        # drops a value it cannot use with nothing said: a `value` of
        # "4" or a `sprite` of 3 would bake an item that is quietly not
        # what the author wrote, and the loss would only show at the
        # weave. A broken `light`, `slot` or `mods` is named by the pack
        # validator instead, so it needs no rule here. Refused at the
        # reader, with the record's own pointer.
        if "sprite" in thing and (not isinstance(thing["sprite"], str)
                                  or not thing["sprite"]):
            raise BlueprintError(
                "sprite must name a picture key (a non-empty string)",
                f"{tbase}/sprite")
        for key in ("value", "heal"):
            if key in thing and not (type(thing[key]) is int
                                     and thing[key] > 0):
                raise BlueprintError(
                    f"{key} must be a positive whole number",
                    f"{tbase}/{key}")
        if "use" in thing and (not isinstance(thing["use"], str)
                               or not thing["use"].strip()):
            raise BlueprintError(
                "use must be one verb (a non-empty string)", f"{tbase}/use")
        if "keep" in thing and thing["keep"] is not True:
            raise BlueprintError(
                "keep is true or nothing (a bool)", f"{tbase}/keep")


def _check_places(places: object, base: str) -> None:
    """Every refusal a `places` list can draw, before any pack is read.

    Shape only: what a place says about itself. The keys a kind may not
    carry are refused here because a closed key set is a promise a
    reader can check without a map - `label` is a sign's, `needs` a
    door's, and neither means anything the other kind can use.
    """
    if not isinstance(places, list):
        raise BlueprintError("places must be a list", base)
    seen: set = set()
    for i, place in enumerate(places):
        pbase = f"{base}/{i}"
        if not isinstance(place, dict):
            raise BlueprintError("a place must be an object", pbase)
        _check_keys(place, PLACE_KEYS, pbase)
        pid = place.get("id")
        if not isinstance(pid, str) or not pid:
            raise BlueprintError(
                "place is missing its id (a non-empty string)", f"{pbase}/id")
        if pid in seen:
            raise BlueprintError(f"duplicate place id {pid!r}", f"{pbase}/id")
        seen.add(pid)
        kind = place.get("kind")
        if kind not in PLACE_KINDS:
            raise BlueprintError(
                f"unknown place kind {kind!r} (a door, a stair or a sign)",
                f"{pbase}/kind")
        if not isinstance(place.get("at"), str) or not place["at"].strip():
            raise BlueprintError(
                "at must be one placement sentence (a string)", f"{pbase}/at")
        if not isinstance(place.get("glyph"), str) or len(place["glyph"]) != 1:
            raise BlueprintError(
                "a place must name its glyph (one character)", f"{pbase}/glyph")
        # A door and a stair are one movement, so `to` and `to_at` come
        # together and both are required; a sign moves nobody, so it may
        # carry neither.
        if kind == "sign":
            for key in ("to", "to_at"):
                if key in place:
                    raise BlueprintError(
                        f"a sign may not name a {key} (it leads nowhere)",
                        f"{pbase}/{key}")
        else:
            for key in ("to", "to_at"):
                if key not in place:
                    raise BlueprintError(
                        f"a {kind} must name the region it leads to and where "
                        f"it lands ({key} and to_at together)", f"{pbase}/{key}")
            if not isinstance(place.get("to"), str) or not place["to"]:
                raise BlueprintError(
                    "to must name one region (a non-empty string)",
                    f"{pbase}/to")
            if not isinstance(place.get("to_at"), str) or not place["to_at"]:
                raise BlueprintError(
                    "to_at must be a plain coordinate x,y (a string)",
                    f"{pbase}/to_at")
        for key in ("label", "text"):
            if key in place and kind != "sign":
                raise BlueprintError(
                    f"{key} is sign-only, and this place is a {kind}",
                    f"{pbase}/{key}")
            if key in place and not isinstance(place[key], str):
                raise BlueprintError(f"{key} must be a string", f"{pbase}/{key}")
        for key in ("needs", "locked_text"):
            if key in place and kind != "door":
                raise BlueprintError(
                    f"{key} is door-only, and this place is a {kind}",
                    f"{pbase}/{key}")
            if key in place and not isinstance(place[key], str):
                raise BlueprintError(f"{key} must be a string", f"{pbase}/{key}")
        if "tile" in place and not isinstance(place["tile"], str):
            raise BlueprintError("tile must be a name (a string)", f"{pbase}/tile")
        base_value = place.get("base")
        if "base" in place and not (
            isinstance(base_value, list)
            and all(isinstance(c, str) for c in base_value)
        ):
            raise BlueprintError(
                "base must be a list of colour strings, copied whole",
                f"{pbase}/base")


READERS = {1: read_v1, 2: read_v2, 3: read_v3}


# ------------------------------------------------- the placement sentences
#
# `at` is written as English, not as a coordinate, so a hand-written
# `map.md` can move and the pack still says what it meant. `vefr
# normalize` resolves it once, here, and writes the character into the
# map: `x,y`; `far:ANCHOR` and `near:ANCHOR`; `off:A>B`; `dead-end`.
# Words are ANDed left to right over the walkable tiles, so a sentence
# narrows and never widens. `room:N` is deliberately absent: nothing in
# a hand-written `map.md` says what a room is, so its malformed form is
# refused rather than guessed at.

_COORD = re.compile(r"^(-?\d+),(-?\d+)$")
_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class _RegionGeo:
    """What one region offers a placement sentence: its map rows under
    its own legend, and the anchors its records already name.

    The legend is read from the contract on disk, so a tile this module
    measures is the tile the validator and the woven player measure.
    """

    def __init__(self, region_key: str, rows: list[str], contract: dict) -> None:
        self.region_key = region_key
        self.rows = rows
        self.contract = contract
        self.legend = contract.get("legend") or {}
        # The tile each place already resolved to, so a later place may
        # anchor an earlier one and a source cannot contradict itself.
        self.placed: dict[str, tuple] = {}
        self.tiles = sorted(
            ((x, y) for y, row in enumerate(rows) for x in range(len(row))
             if self.walkable(x, y)),
            key=lambda t: (t[1], t[0]),
        )

    def walkable(self, x: int, y: int) -> bool:
        """Walkable or not, exactly as `maplab` says: the legend's bool
        `solid` first, its own blocked fallback otherwise. Off the map
        is not walkable, and `None` from the helper says so."""
        return _map_tile_walkable(self.rows, self.legend, x, y) is True

    def distances(self, start: tuple) -> dict:
        """BFS path distance from `start` over the walkable tiles.

        The 4-neighbourhood, because that is what `maplab.reach` walks:
        a place is placed where the hero can actually walk.
        """
        seen = {start: 0}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in _STEPS:
                here = (x + dx, y + dy)
                if here not in seen and self.walkable(*here):
                    seen[here] = seen[(x, y)] + 1
                    queue.append(here)
        return seen

    def anchor(self, name: str) -> tuple | None:
        """The tile `name` stands for, or None when it names nothing.

        Resolved in one order, so a name is never ambiguous: `start` is
        the region's `hero_start`, then a place id in the same region
        (a later place may anchor an earlier one), then the LABEL of a
        poi - a poi label is its own id everywhere else in the engine.
        """
        if name == "start":
            hero = self.contract.get("hero_start")
            if (isinstance(hero, list) and len(hero) == 2
                    and all(type(n) is int for n in hero)):
                return (hero[0], hero[1])
            return None
        if name in self.placed:
            return self.placed[name]
        for key, label in (self.contract.get("pois") or {}).items():
            if label == name:
                return _parse_cell(str(key))
        return None


def _parse_cell(token: str) -> tuple | None:
    """Read one `x,y` cell key (a poi key, a lock pointer)."""
    match = _COORD.match(token.strip())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)))


def _pick(region_key: str, place_id: str, word: str,
          candidates: set) -> tuple:
    """One tile out of several that answer a word equally well.

    A digest of the record's own id and its region, and nothing else:
    the same source then picks the same tile every run, and adding a
    second record cannot move the first one's tile - which is the whole
    reason a tie-break may not be a shared stream. No pack carries a
    seed today, so the id stands in for one.
    """
    ordered = sorted(candidates, key=lambda t: (t[1], t[0]))
    if len(ordered) == 1:
        return ordered[0]
    digest = hashlib.sha256(
        f"{region_key}\x1f{place_id}\x1f{word}".encode()).hexdigest()
    return ordered[int(digest, 16) % len(ordered)]


def _word_candidates(word: str, geo: _RegionGeo, place_id: str,
                     pointer: str) -> set:
    """The tiles one word of an `at` sentence admits.

    An anchor that names nothing, a word that is not one of the five,
    and a `room:` are all refusals here rather than empty sets, because
    the author has to know which of the two went wrong.
    """
    match = _COORD.match(word)
    if match:
        x, y = int(match.group(1)), int(match.group(2))
        if _map_tile_walkable(geo.rows, geo.legend, x, y) is None:
            raise BlueprintError(
                f"the coordinate ({x},{y}) is off the map of region "
                f"{geo.region_key!r}", pointer)
        return {(x, y)}
    if word == "dead-end":
        return {t for t in geo.tiles
                if sum(1 for dx, dy in _STEPS
                       if geo.walkable(t[0] + dx, t[1] + dy)) == 1}
    for prefix in ("far:", "near:"):
        if word.startswith(prefix):
            return _distance_candidates(geo, word[len(prefix):], pointer,
                                        near=prefix == "near:")
    if word.startswith("off:"):
        left, sep, right = word[len("off:"):].partition(">")
        if not sep or not left or not right:
            raise BlueprintError(
                f"the word {word!r} names two anchors as A>B", pointer)
        return _off_route_candidates(geo, left, right, pointer)
    if word.startswith("room:"):
        raise BlueprintError(
            f"the word {word!r} is not a placement word in this format "
            f"(a room is not named on a hand-written map.md)", pointer)
    raise BlueprintError(f"unknown word {word!r} in the at sentence", pointer)


def _anchor_tile(geo: _RegionGeo, name: str, pointer: str) -> tuple:
    """One anchor's tile, or one plain sentence naming the `at` field."""
    if not name:
        raise BlueprintError(
            "an anchor word ends in a colon and names nothing", pointer)
    tile = geo.anchor(name)
    if tile is None:
        raise BlueprintError(
            f"unknown anchor {name!r} in the at sentence of region "
            f"{geo.region_key!r} (start, a place id, or a poi label)",
            pointer)
    if not geo.walkable(*tile):
        raise BlueprintError(
            f"the anchor {name!r} is not a walkable tile of region "
            f"{geo.region_key!r}", pointer)
    return tile


def _distance_candidates(geo: _RegionGeo, name: str, pointer: str,
                         *, near: bool) -> set:
    """`far:` and `near:`: the walkable tiles at the extreme distance
    from an anchor, measured as the hero walks."""
    tile = _anchor_tile(geo, name, pointer)
    reached = geo.distances(tile)
    if near:
        # A sign "near" the start is not the start: a place on the
        # hero's own tile is a tile the hero never leaves.
        reached.pop(tile, None)
    if not reached:
        raise BlueprintError(
            f"no walkable tile is {'near' if near else 'far'} the anchor "
            f"{name!r} in region {geo.region_key!r}", pointer)
    best = min(reached.values()) if near else max(reached.values())
    return {t for t, d in reached.items() if d == best}


def _off_route_candidates(geo: _RegionGeo, left: str, right: str,
                          pointer: str) -> set:
    """`off:A>B`: the walkable tiles on no shortest route from A to B.

    The union of every shortest path, not one of them: a tile is "on a
    route" when some route runs through it, so a detour is a tile whose
    distances to A and to B do not add up to the distance between them.
    """
    a = _anchor_tile(geo, left, pointer)
    b = _anchor_tile(geo, right, pointer)
    from_a = geo.distances(a)
    from_b = geo.distances(b)
    if b not in from_a:
        raise BlueprintError(
            f"the anchors {left!r} and {right!r} are not joined by a walkable "
            f"route in region {geo.region_key!r}", pointer)
    span = from_a[b]
    routes = {t for t in from_a
              if t in from_b and from_a[t] + from_b[t] == span}
    spare = {t for t in geo.tiles if t not in routes}
    if not spare:
        raise BlueprintError(
            f"every tile of region {geo.region_key!r} is on a route between "
            f"{left!r} and {right!r}", pointer)
    return spare


def _resolve_at(sentence: str, geo: _RegionGeo, place_id: str,
                pointer: str) -> tuple:
    """The one tile an `at` sentence names, or one plain sentence.

    Words are ANDed left to right over the walkable tiles, so an
    impossible sentence (a dead end that is also the far side of the
    room) ends as an empty set and is refused before anything is
    written.
    """
    candidates = set(geo.tiles)
    chosen = ""
    for word in sentence.split():
        candidates &= _word_candidates(word, geo, place_id, pointer)
        chosen = word
        if not candidates:
            break
    if not candidates:
        raise BlueprintError(
            f"the at sentence {sentence!r} names no tile of region "
            f"{geo.region_key!r}", pointer)
    return _pick(geo.region_key, place_id, chosen, candidates)


def _region_geo(pack: Path, region_key: str, pointer: str) -> _RegionGeo:
    """Read one region's map and contract for the sentences to measure.

    The rows are the non-blank lines of `map.md`, the same view
    `maplab._region_geo` gives the validator, so a sentence and the
    door check can never disagree about where a tile is.
    """
    directory = Path(_region_dir(pack, region_key, pointer))
    map_path = directory / "map.md"
    if not map_path.is_file():
        raise BlueprintError(
            f"region {region_key!r} has no map.md to place a glyph in", pointer)
    rows = [line for line in map_path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    try:
        contract = json.loads(
            (directory / "contract.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        contract = {}
    if not isinstance(contract, dict):
        contract = {}
    return _RegionGeo(region_key, rows, contract)


def _legend_value(place: dict, geo: _RegionGeo, pointer: str) -> dict:
    """The legend entry one place's glyph gets.

    `solid: false` on every kind, because `_map_tile_walkable` reads a
    bool `solid` and falls back to its blocked list without one - so a
    glyph like `T` would be solid and the door check would refuse the
    pack. The base is the region's own `.` base copied whole, which is
    why one form needs no conversion.
    """
    glyph = place["glyph"]
    base = place.get("base")
    if base is None:
        dot = (geo.legend.get(".") or {}) if isinstance(geo.legend, dict) else {}
        if not isinstance(dot, dict) or not isinstance(dot.get("base"), list):
            raise BlueprintError(
                f"region {geo.region_key!r} has no '.' base to copy for the "
                f"glyph {glyph!r}", f"{pointer}/base")
        base = copy.deepcopy(dot["base"])
    value = {"base": copy.deepcopy(base), "solid": False}
    if "tile" in place:
        value["tile"] = place["tile"]
    return value


def _cell_pointer(tile: tuple) -> str:
    """The lock's name for one owned `map.md` cell."""
    return f"/{tile[0]},{tile[1]}"


def _transition_index(pointer: str) -> int | None:
    """The list index an owned `/transitions/N` pointer names."""
    if pointer.startswith("/transitions/"):
        try:
            return int(pointer[len("/transitions/"):])
        except ValueError:
            return None
    return None


def _lock_outputs(lock: dict) -> dict:
    """The pointers one lock says its Blueprint owns, as
    `{relative file: {pointer}}`. A format-1 lock names one pointer per
    output; a format-3 lock names every one it owns."""
    owned: dict = {}
    for entry in (lock or {}).get("outputs") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            continue
        pointers = entry.get("pointers")
        if not isinstance(pointers, list):
            pointers = ([entry["pointer"]]
                        if isinstance(entry.get("pointer"), str) else [])
        owned.setdefault(entry["file"], set()).update(
            p for p in pointers if isinstance(p, str))
    return owned


def _owned_pointers(pack: Path) -> dict:
    """The pointers the lock beside a pack says this Blueprint owns.

    Read before every write, because a pointer this Blueprint wrote
    last time is the one place it may overwrite: anything else in the
    file belongs to the hand and is left exactly as it is found.
    """
    try:
        lock = json.loads((pack / LOCK_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return _lock_outputs(lock) if isinstance(lock, dict) else {}


def _planned_transitions(expanded: dict) -> dict:
    """Every act transition the source calls for, per act, in source
    order, so one act's doors keep one another's numbering."""
    acts: dict[str, list] = {}
    for region_key, entry in expanded.items():
        act = region_key.partition("/")[0]
        for place in entry["places"]:
            if place["transition"] is not None:
                acts.setdefault(act, []).append(place["transition"])
    return acts


def _transition_slots(rel: str, owned: dict, length: int, wanted: int) -> list:
    """Where this run's act transitions sit in the act's list.

    The slots the last lock claims are reused, so a second
    `vefr normalize` updates the doors it wrote instead of standing a
    second set up beside them; anything beyond them is appended after
    every hand-written entry, which keeps the hand's own `transition N`
    numbers where they were.
    """
    mine = sorted(i for i in (_transition_index(p)
                              for p in owned.get(rel, set()))
                  if i is not None)
    keep = min(len(mine), wanted)
    return mine[:keep] + [length + n for n in range(keep, wanted)]


def _read_json(path: Path) -> dict:
    """One JSON object off disk, or an empty one (never a crash)."""
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _set_pointer(data: dict, pointer: str, value) -> None:
    """Write one flat pointer (`/key` or `/key/other`) where it is.

    Every pointer this module owns is one level under a hand-written
    key - a legend glyph, a poi cell, a transition - so the walk is
    short and the hand keys keep the order and the values they had.
    """
    parts = [p for p in pointer.split("/") if p]
    if not parts:
        return
    for part in parts[:-1]:
        nested = data.get(part)
        if not isinstance(nested, dict):
            nested = {}
            data[part] = nested
        data = nested
    data[parts[-1]] = value


def _get_pointer(data: dict, pointer: str):
    """The value one flat pointer names, or None when it is not there."""
    parts = [p for p in pointer.split("/") if p]
    here: object = data
    for part in parts:
        if not isinstance(here, dict) or part not in here:
            return None
        here = here[part]
    return here


def _write_map_cells(path: Path, cells: dict, region_key: str) -> str:
    """Put each glyph into its row of `map.md`, keeping every other
    byte: the prose around the map, the blank lines, the trailing
    newline.

    `cells` maps a row number to `(glyph, x, y)`; only that one
    character of that one line changes.
    """
    out: list[str] = []
    row = -1
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        if not line.strip():
            out.append(line)
            continue
        row += 1
        if row not in cells:
            out.append(line)
            continue
        glyph, x, y = cells[row]
        body = line.rstrip("\r\n")
        if x >= len(body):
            raise BlueprintError(
                f"the map of region {region_key!r} has no column {x} on "
                f"row {y}", f"/regions/{_esc(region_key)}")
        out.append(body[:x] + glyph + body[x + 1:] + line[len(body):])
    return "".join(out)


def _pack_items(pack_dir: Path) -> dict:
    """The pack's `items` catalog as the file holds it, loader first."""
    items = None
    try:
        items = load_pack(pack_dir).get("items")
    except (OSError, ValueError, KeyError, SystemExit):
        items = None
    if not isinstance(items, dict):
        try:
            world = json.loads((pack_dir / "world.json").read_text(encoding="utf-8"))
            items = world.get("items")
        except (OSError, ValueError):
            items = None
    return items if isinstance(items, dict) else {}


def _declared_items(pack_dir: Path) -> set[str]:
    """The item ids the player can really be given.

    The catalog `weave` bakes, not the raw `items` keys the file holds:
    `cli._player_items` drops an entry with no `name`, so a drop naming
    it passes a raw-key check and then pays nothing at play, and there
    is no honest way to call that declared.

    "Real" is read by `library._declared_items`, the same read the chest
    check, the region enemy and the Section families read, so a Blueprint
    family and a chest book cannot hold two opinions about one id. The
    caller adds this Blueprint's own things to the answer, which the
    weave bakes too.
    """
    return library._declared_items(_pack_items(pack_dir))


def _written_items(pack_dir: Path) -> set[str]:
    """Every id `items` names on disk, named or not.

    A file question rather than a catalog one: "does a hand-written
    entry already hold this key?" is about the file, whatever the item
    reader would make of it.
    """
    return set(_pack_items(pack_dir))


def _refuse_unknown_item(item_id, word: str, where: str,
                         offered: set, written: set) -> None:
    """Refuse an id the player can never be given, naming which failure.

    `offered` is what the weave bakes (the catalog, plus this
    Blueprint's own things) and `written` every key on disk, so the
    sentence can tell a typo (the pack never declared it) from an entry
    the item reader drops (declared, but with no `name`, so the weave
    filters the drop and the player is given nothing at all).
    """
    if not isinstance(item_id, str):
        raise BlueprintError(f"unknown item {item_id!r} in {word}", where)
    if item_id in offered:
        return
    if item_id in written:
        raise BlueprintError(
            f"the item {item_id!r} in {word} is not one the player can be "
            f"given: an `items` entry with no `name` is dropped from the "
            f"weave", where)
    raise BlueprintError(f"unknown item {item_id!r} in {word}", where)


def _pack_item(pack: Path, item_id: str):
    """The `items` entry `world.json` holds under that id, or None.

    The committed value, read from the same file the writer and the
    stale check read, so "is this entry ours?" is one comparison
    against what a thing would write.
    """
    items = _read_json(pack / "world.json").get("items")
    return items.get(item_id) if isinstance(items, dict) else None


def _region_dir(pack_dir: Path, region_key: str, pointer: str) -> str:
    """Resolve acts/<act>/<region> under `pack_dir`, guarded by `_inside`."""
    from .cli import _inside  # lazy: cli will import this module

    parts = region_key.split("/")
    if len(parts) != 2:
        raise BlueprintError(
            f"region key {region_key!r} is not <act>/<region>", pointer
        )
    base = os.path.realpath(pack_dir)
    # Guard the raw key against the pack root first: an act of `..` makes
    # `acts/../<region>` normalise back inside the pack, so the
    # acts-relative probe alone cannot see the traversal. Then guard the
    # acts-relative directory itself. No Blueprint string becomes a path
    # except through `_inside`.
    if _inside(base, *parts) is None:
        raise BlueprintError(f"region {region_key!r} is outside the pack", pointer)
    act, region = parts
    target = _inside(base, "acts", act, region)
    if target is None:
        raise BlueprintError(f"region {region_key!r} is outside the pack", pointer)
    if not os.path.isdir(target):
        raise BlueprintError(f"region directory {region_key!r} does not exist", pointer)
    return target


def _resolve_family(family: str, families: dict) -> tuple[list[str], dict]:
    """Resolve `family` to its root-first chain and its merged fields.

    `chain` is the family and its parent chain, root first. `fields` maps
    each surviving field to `(value, pointer)`: `value` is the source
    object itself (callers deep-copy it) and `pointer` names the
    declaration that won. A later value replaces an earlier one whole.
    Unknown parents and cycles fail with a pointer: a self-cycle names
    the family, a longer cycle names `/families`.
    """
    chain: list[str] = []
    seen: set[str] = set()
    current = family
    while True:
        if current in seen:
            if len(chain) == 1:
                raise BlueprintError(
                    f"family {current!r} extends itself (cycle)",
                    f"/families/{_esc(current)}",
                )
            raise BlueprintError("family inheritance has a cycle", "/families")
        seen.add(current)
        chain.append(current)
        parent = families[current].get("extends")
        if parent is None:
            break
        if parent not in families:
            raise BlueprintError(
                f"unknown parent {parent!r}",
                f"/families/{_esc(current)}/extends",
            )
        current = parent

    ordered = list(reversed(chain))
    fields: dict = {}
    for name in ordered:
        defaults = families[name].get("defaults") or {}
        for key, value in defaults.items():
            fields[key] = (value, f"/families/{_esc(name)}/defaults/{key}")
    return ordered, fields


def resolve_family(source: dict, family_id: str) -> dict:
    """The base record of one family: its merged defaults, root first.

    A Section pack names families by id and carries no records of its
    own (ADR 0014), so a Section that wants a family's `hp` and `atk`
    asks for them here. This is the same resolution `plan` does - the
    same chain, the same whole-value replacement, the same three
    refusals with the same pointers (unknown family, cycle, unknown
    parent) - returning the record instead of a list of records.

    The returned dict is the caller's to keep and to scale: the values
    are deep-copied out of `source`, so mutating what comes back cannot
    reach back into the Blueprint. The keys are the closed enemy fields
    `FIELD_KEYS` and no others; this function reads a Blueprint, it does
    not widen one.
    """
    if not isinstance(source, dict):
        raise BlueprintError("blueprint must be a JSON object", "")
    families = source.get("families", {})
    if not isinstance(families, dict):
        raise BlueprintError("families must be an object", "/families")
    if not isinstance(family_id, str):
        raise BlueprintError("a family id must be a string", "/families")
    if family_id not in families:
        raise BlueprintError(
            f"unknown family {family_id!r}", f"/families/{_esc(family_id)}")
    _chain, fields = _resolve_family(family_id, families)
    return {key: copy.deepcopy(value) for key, (value, _p) in fields.items()}


def expand(source: dict, *, pack_dir: str | Path) -> dict[str, list[dict]]:
    """Validate `source`, then expand it into `{region_key: [records]}`.

    The enemy records are the whole return value, as format 1 defined
    it. Format 3's places and format 2's things are expanded (and so
    refused when they cannot be) on the way past, and picked up by the
    writer through `plan`.
    """
    return {key: entry["enemies"]
            for key, entry in plan(source, pack_dir=pack_dir)[0].items()}


def plan(source: dict, *, pack_dir: str | Path) -> tuple[dict[str, dict], list[dict]]:
    """What one Blueprint writes: per region the enemy records, the
    places they stand beside and the pointers each owns, and then the
    things, which belong to the pack rather than to one region.

    Everything is resolved before anything is written, so an impossible
    sentence, an unknown item, an unreachable carrier or a hand-written
    door in the way leaves the pack exactly as it was found.
    """
    version = source.get("blueprint") if isinstance(source, dict) else None
    reader = READERS.get(version) if type(version) is int else None
    if reader is None:
        raise BlueprintError(VERSION_SENTENCE, "/blueprint")
    source = reader(source)
    pack = Path(pack_dir)
    families = source.get("families") or {}
    regions = source.get("regions") or {}
    declared = _declared_items(pack)
    written = _written_items(pack)
    owned = _owned_pointers(pack)
    listed = source.get("things") or []
    # A thing's own id is an item this Blueprint declares, so a carrier
    # in this same file may drop it without tripping the check that
    # refuses an unknown item in `drops`. A thing always carries a name,
    # so its entry bakes.
    items = declared | {thing["id"] for thing in listed}

    # Every family is resolved, used or not: an unused family with an
    # unknown parent or a cycle is still a broken Blueprint.
    for name in families:
        _resolve_family(name, families)

    out: dict[str, dict] = {}
    for region_key, region in regions.items():
        rbase = f"/regions/{_esc(region_key)}"
        _region_dir(pack, region_key, rbase)
        records = _expand_enemies(
            region.get("enemies") or [], rbase, families, items, written)
        entry = {
            "enemies": records,
            # A format-3 region that says nothing about `enemies` owns
            # no `enemies` list: the hand keeps whatever it wrote.
            "owns_enemies": version == 1 or "enemies" in region,
            "places": [],
        }
        if version == 3 and region.get("places"):
            entry["places"] = _expand_places(
                pack, region_key, region, rbase, items, written, owned)
        out[region_key] = entry
    things = _expand_things(pack, source, listed, out, written, owned)
    return out, things


def _expand_enemies(instances: list, rbase: str, families: dict,
                    items: set, written: set) -> list[dict]:
    """One region's enemy records, in file order."""
    records: list[dict] = []
    seen_ids: set = set()
    for i, instance in enumerate(instances):
        ibase = f"{rbase}/enemies/{i}"

        family = instance.get("family")
        if family not in families:
            raise BlueprintError(
                f"unknown family {family!r}", f"{ibase}/family"
            )
        _chain, fields = _resolve_family(family, families)
        for key, value in (instance.get("properties") or {}).items():
            fields[key] = (value, f"{ibase}/properties/{key}")
        record = {
            key: copy.deepcopy(value)
            for key, (value, _pointer) in fields.items()
        }

        if "id" in instance:
            record["id"] = copy.deepcopy(instance["id"])
        if "at" not in instance:
            raise BlueprintError(
                "instance is missing its at position", f"{ibase}/at"
            )
        record["at"] = copy.deepcopy(instance["at"])

        iid = instance.get("id")
        if iid in seen_ids:
            raise BlueprintError(
                f"duplicate instance id {iid!r}", f"{ibase}/id"
            )
        seen_ids.add(iid)

        drops, where = fields.get("drops", (None, ""))
        if isinstance(drops, list):
            for drop in drops:
                _refuse_unknown_item(drop, "drops", where, items, written)

        records.append({key: record[key] for key in FIELD_ORDER if key in record})
    return records


def _expand_things(pack: Path, source: dict, listed: list,
                   expanded: dict, written: set, owned: dict) -> list[dict]:
    """The `items` entries one source's things write, and the drops they
    append to their carriers.

    A thing reaches the pack two ways: the item entry always, and a drop
    when it names a carrier. The carrier is looked up in the expanded
    records, so a `from` may only reach an instance of a region this
    Blueprint owns - a Blueprint writes the regions it owns and nothing
    else, and a drop in a region it does not own would land in a file no
    lock of its names. An instance id is unique within its region and
    not across the source, so a `from` that reaches two owned regions
    is refused rather than resolved to whichever came last.
    """
    carriers: dict = {}
    for region_key, records in expanded.items():
        for record in records["enemies"]:
            carriers.setdefault(record.get("id"), []).append(
                (region_key, record))
    out: list[dict] = []
    for i, thing in enumerate(listed):
        base = f"/things/{i}"
        tid = thing["id"]
        pointer = f"/items/{_esc(tid)}"
        item = {"name": copy.deepcopy(thing["name"]),
                "sprite": thing.get("sprite") or tid}
        for key in ITEM_ORDER[2:]:
            if key in thing:
                item[key] = copy.deepcopy(thing[key])
        # A hand-written entry is the ordinary shape and no lock of ours
        # names it, so a thing may not take one over; a pointer our own
        # lock already owns is this Blueprint's from last time. An entry
        # that holds exactly what this thing would write is neither: a
        # lock that no longer names it only means the list was edited
        # (deleting `things` and putting it back), and the round trip
        # has to work.
        if (tid in written and pointer not in owned.get("world.json", set())
                and _pack_item(pack, tid) != item):
            raise BlueprintError(
                f"the pack declares the item {tid!r} by hand, and a thing "
                f"may not take it over", f"{base}/id")
        record = {"id": tid, "source": base, "item": item, "pointer": pointer}
        carrier = thing.get("from")
        if carrier is not None:
            found = carriers.get(carrier) or []
            if len(found) > 1:
                raise BlueprintError(
                    f"the instance {carrier!r} is in two owned regions "
                    f"({', '.join(repr(key) for key, _ in found)}), and a "
                    f"from may name only one", f"{base}/from")
            if not found:
                _refuse_carrier(pack, expanded, carrier, f"{base}/from")
            target = found[0][1]
            drops = target.setdefault("drops", [])
            if tid in drops:
                raise BlueprintError(
                    f"the carrier {carrier!r} already drops {tid!r}",
                    f"{base}/from")
            # Appended, not prepended: the hand wrote that list, and a
            # thing is an arrival rather than a re-ordering of it.
            drops.append(tid)
        out.append(record)
    return out


def _refuse_carrier(pack: Path, expanded: dict, carrier: str,
                    pointer: str) -> None:
    """Name which of the `from` refusals this is, because the author has
    to know whether the instance is missing, out of reach, or standing in
    a region this source names without owning that region's `enemies` -
    three different fixes, and the last one used to be told the first."""
    on_disk = _pack_enemies(pack)
    found = [region_key for region_key, records in on_disk.items()
             if any(record.get("id") == carrier for record in records)]
    for region_key in found:
        entry = expanded.get(region_key)
        if entry is not None and not entry["owns_enemies"]:
            raise BlueprintError(
                f"the region {region_key!r} is in this blueprint but "
                f"declares no enemies, so the instance {carrier!r} is not "
                f"one this blueprint writes", pointer)
    if found:
        raise BlueprintError(
            f"this blueprint owns no region with the instance {carrier!r}",
            pointer)
    raise BlueprintError(
        f"from names no instance {carrier!r} in any region of this pack",
        pointer)


def _pack_enemies(pack: Path) -> dict[str, list[dict]]:
    """Every enemy record the pack holds on disk, per region key, owned
    or not.

    Read only to tell the `from` refusals apart, so a carrier in a
    region this Blueprint does not own is named as that rather than as
    an id nothing has - and a carrier in a region the source names
    without owning its `enemies` is named as that rather than as one no
    region has.
    """
    out: dict[str, list[dict]] = {}
    acts = Path(_inside_pack(pack, "acts"))
    if not acts.is_dir():
        return out
    for act in sorted(p for p in acts.iterdir() if p.is_dir()):
        act_dir = _inside_pack(pack, f"acts/{act.name}")
        for region in sorted(p for p in Path(act_dir).iterdir() if p.is_dir()):
            region_dir = _inside_pack(pack, f"acts/{act.name}/{region.name}")
            records = _read_json(
                Path(region_dir) / "contract.json").get("enemies") or []
            out[f"{act.name}/{region.name}"] = [
                record for record in records if isinstance(record, dict)]
    return out


def _expand_places(pack: Path, region_key: str, region: dict, rbase: str,
                   items: set, written: set, owned: dict) -> list[dict]:
    """One region's places, each resolved to the tile it stands on.

    Places resolve in source order, so a later one may anchor an
    earlier one, and each one is a value the writer can compare against
    what is on disk: the legend entry, the act transition, the poi and
    the map cell, named by the pointers this Blueprint owns.
    """
    geo = _region_geo(pack, region_key, rbase)
    act, _, name = region_key.partition("/")
    contract_rel = f"acts/{act}/{name}/contract.json"
    act_rel = f"acts/{act}/world.json"
    hand = _hand_transitions(pack, act_rel, owned)
    out: list[dict] = []
    for i, place in enumerate(region.get("places") or []):
        pbase = f"{rbase}/places/{i}"
        pid = place["id"]
        at = _resolve_at(place["at"], geo, pid, f"{pbase}/at")
        geo.placed[pid] = at
        glyph = place["glyph"]
        legend = _legend_value(place, geo, pbase)
        legend_pointer = f"/legend/{_esc(glyph)}"
        existing = (geo.legend or {}).get(glyph)
        if (existing is not None and existing != legend
                and legend_pointer not in owned.get(contract_rel, set())):
            raise BlueprintError(
                f"the glyph {glyph!r} is already in the legend of region "
                f"{region_key!r} with another value", f"{pbase}/glyph")
        record = {
            "id": pid,
            "kind": place["kind"],
            "at": [at[0], at[1]],
            "glyph": glyph,
            "legend": legend,
            "legend_pointer": legend_pointer,
            "poi_pointer": "",
            "poi_text_pointer": "",
            "transition": None,
        }
        if place["kind"] == "sign":
            # A sign with no label is a glyph and nothing else: it is a
            # tile the hero stands on, not a named place.
            if place.get("label"):
                record["poi_pointer"] = f"/pois/{at[0]},{at[1]}"
                record["label"] = place["label"]
            if place.get("text"):
                record["poi_text_pointer"] = f"/poi_text/{at[0]},{at[1]}"
                record["text"] = place["text"]
        else:
            to_at = _parse_cell(place["to_at"])
            if to_at is None:
                raise BlueprintError(
                    f"to_at {place['to_at']!r} is not a plain coordinate x,y",
                    f"{pbase}/to_at")
            transition = {"from": name, "at": [at[0], at[1]], "to": place["to"],
                          "to_at": [to_at[0], to_at[1]]}
            needs = place.get("needs")
            if needs is not None:
                _refuse_unknown_item(
                    needs, "needs", f"{pbase}/needs", items, written)
                transition["requires"] = {"item": needs}
            if place.get("locked_text") is not None:
                transition["locked_text"] = place["locked_text"]
            for _index, written in hand:
                if (written.get("from") == name
                        and list(written.get("at") or []) == record["at"]):
                    raise BlueprintError(
                        f"a transition already leaves region {name!r} at "
                        f"({at[0]},{at[1]}), where this place stands",
                        f"{pbase}/at")
            record["transition"] = transition
        out.append(record)
    return out


def _hand_transitions(pack: Path, rel: str, owned: dict) -> list:
    """The act's transitions this Blueprint did not write, as
    `(index, transition)`.

    A transition the lock already claims is this Blueprint's own from
    last time, so a re-run updates it where it is instead of setting up
    a second door beside the first - and the refusal below is about a
    door standing in a place's way, not about authorship.
    """
    act, _, _name = rel.rpartition("/")
    data = _read_json(Path(_inside_pack(pack, act)) / "world.json")
    mine = owned.get(rel, set())
    out = []
    for index, entry in enumerate(data.get("transitions") or []):
        pointer = f"/transitions/{index}"
        if pointer in mine or not isinstance(entry, dict):
            continue
        out.append((index, entry))
    return out


def _inside_pack(pack: Path, rel: str) -> str:
    """One pack-relative directory, resolved through the same guard
    every other path in this module goes through (`cli._inside`)."""
    from .cli import _inside

    target = _inside(os.path.realpath(pack), *rel.split("/"))
    if target is None:
        raise BlueprintError(f"the act directory {rel!r} is outside the pack", "")
    return target


def canonical_hash(source: dict) -> str:
    """The SHA-256 of `source` in canonical JSON form."""
    payload = json.dumps(
        source, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


# ------------------------------------------------------------------ the lock
#
# `vefr normalize` owns two things beyond the Blueprint: the generated
# `enemies` list of every region the Blueprint names, and a sidecar,
# `blueprint.lock.json`, that records what wrote them (source hash,
# normalizer and format versions, per-record provenance). Both are
# written with the same canonical serializer, so a second run over an
# unchanged Blueprint leaves identical bytes.

BLUEPRINT_FILE = "blueprint.json"
LOCK_FILE = "blueprint.lock.json"


def _write_json(path: Path, data) -> None:
    """Write JSON the way the pack writer does: 2-space, UTF-8, newline."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _lock_data(source: dict, expanded: dict) -> dict:
    """The lock body for one successful expansion of `source`."""
    families = source.get("families") or {}
    regions = source.get("regions") or {}
    outputs = []
    for region_key, _records in expanded.items():
        instance_list = (regions.get(region_key) or {}).get("enemies") or []
        entries = []
        for i, instance in enumerate(instance_list):
            properties = instance.get("properties")
            entries.append({
                "source": f"/regions/{_esc(region_key)}/enemies/{i}",
                "families": _resolve_family(instance.get("family"), families)[0],
                "overrides": sorted(properties) if isinstance(properties, dict) else [],
            })
        act, _, region = region_key.partition("/")
        outputs.append({
            "file": f"acts/{act}/{region}/contract.json",
            "pointer": "/enemies",
            "records": entries,
        })
    return {
        "blueprint": 1,
        "normalizer": NORMALIZER_VERSION,
        "source_sha256": canonical_hash(source),
        "outputs": outputs,
    }


def _lock_data_things(source: dict, expanded: dict, things: list) -> dict:
    """The lock body for a format-2 expansion: format 1's source hash
    and enemy provenance, plus the `world.json` item entries and one
    record per thing.

    The pointers are format 1's, so a hand edit to a written item is
    stale by the same rule as a hand edit to a generated enemy, and one
    thing may share a carrier with another because the appended id is
    part of the enemy record the `/enemies` check already compares.
    """
    lock = _lock_data(source, expanded)
    lock["blueprint"] = 2
    if things:
        lock["outputs"].insert(0, {
            "file": "world.json",
            "pointers": [thing["pointer"] for thing in things],
            "records": [{"source": thing["source"], "id": thing["id"]}
                        for thing in things],
        })
    return lock


def _lock_data_places(source: dict, expanded: dict, slots: dict) -> dict:
    """The lock body for a format-3 expansion: format 1's source hash
    and enemy provenance, plus one output per owned file naming every
    pointer that file carries from the source.

    The `map.md` cell is a pointer like any other, so a hand edit to a
    generated glyph reads as stale by the same rule as a hand edit to a
    generated enemy - and a pointer the source no longer owns is simply
    gone from the list, which is what leaves an old glyph's legend entry
    alone.
    """
    families = source.get("families") or {}
    regions = source.get("regions") or {}
    outputs: list[dict] = []
    acts: dict[str, list] = {}
    for region_key, entry in expanded.items():
        act, _, region = region_key.partition("/")
        instance_list = (regions.get(region_key) or {}).get("enemies") or []
        records = []
        for i, instance in enumerate(instance_list):
            properties = instance.get("properties")
            records.append({
                "source": f"/regions/{_esc(region_key)}/enemies/{i}",
                "families": _resolve_family(instance.get("family"), families)[0],
                "overrides": sorted(properties) if isinstance(properties, dict) else [],
            })
        pointers: list[str] = []
        places: list[dict] = []
        if entry["owns_enemies"]:
            pointers.append("/enemies")
        for i, place in enumerate(entry["places"]):
            for pointer, _value in _place_contract_values(place):
                if pointer not in pointers:
                    pointers.append(pointer)
            places.append({
                "source": f"/regions/{_esc(region_key)}/places/{i}",
                "kind": place["kind"],
                "at": place["at"],
                "glyph": place["glyph"],
            })
            if place["transition"] is not None:
                acts.setdefault(act, []).append(place)
        if not pointers and not places:
            continue
        outputs.append({
            "file": f"acts/{act}/{region}/contract.json",
            "pointers": pointers,
            "records": records,
            "places": places,
        })
        if places:
            outputs.append({
                "file": f"acts/{act}/{region}/map.md",
                "pointers": [_cell_pointer((p["at"][0], p["at"][1]))
                             for p in entry["places"]],
                "records": [],
            })
    for act, places in acts.items():
        outputs.append({
            "file": f"acts/{act}/world.json",
            "pointers": [f"/transitions/{index}" for index in
                         slots.get(act, [])],
            "records": [],
        })
    return {
        "blueprint": 3,
        "normalizer": NORMALIZER_VERSION,
        "source_sha256": canonical_hash(source),
        "outputs": outputs,
    }


def _contract_path(pack: Path, region_key: str) -> Path:
    """The guarded `contract.json` of one Blueprint-owned region.

    The region directory is resolved through `_region_dir`, which is the
    only place a Blueprint string becomes a path (`cli._inside`).
    """
    directory = _region_dir(pack, region_key, f"/regions/{_esc(region_key)}")
    return Path(directory) / "contract.json"


def check_errors(pack_dir) -> list[str]:
    """Every Blueprint problem in `pack_dir` as plain sentences.

    Empty when the pack carries neither a Blueprint nor a lock - and in
    that case nothing else is read. A present Blueprint is checked for
    the acts shape, its lock, the reader/normalizer versions, and
    freshness (the lock's source hash and every owned `enemies` list
    against what this VEFR expands now). Stale messages name the file
    and the record pointer so the author knows what to run.
    """
    pack = Path(pack_dir)
    source_path = pack / BLUEPRINT_FILE
    lock_path = pack / LOCK_FILE
    has_source = source_path.is_file()
    has_lock = lock_path.is_file()
    if not has_source and not has_lock:
        return []
    # Format 1 is acts-shape only: a flat pack with a Blueprint is
    # refused before the lock is even considered.
    if has_source and not (pack / "acts").is_dir():
        return [f"a Blueprint needs an acts/ directory, but {pack} has none"]
    if has_source and not has_lock:
        return [f"blueprint.json has no blueprint.lock.json beside it - "
                f"run 'vefr normalize --pack {pack} --out {pack}'"]
    if has_lock and not has_source:
        return ["blueprint.lock.json has no blueprint.json beside it - "
                "delete the lock or restore the Blueprint"]

    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [f"{lock_path.name} is not valid JSON"]
    if not isinstance(lock, dict):
        return [f"{lock_path.name} must be a JSON object"]

    # A format or normalizer this VEFR does not know can produce output
    # this VEFR cannot compare honestly, so it fails before expanding.
    known_formats = sorted(READERS)
    newer: list[str] = []
    normalizer = lock.get("normalizer")
    if type(normalizer) is int and normalizer > NORMALIZER_VERSION:
        newer.append(
            f"blueprint.lock.json was written by a newer normalizer "
            f"({normalizer}); this VEFR knows {NORMALIZER_VERSION}")
    version = lock.get("blueprint")
    if type(version) is int and version > max(known_formats):
        newer.append(
            f"blueprint.lock.json names a newer format ({version}); "
            f"this VEFR reads {known_formats}")
    if newer:
        return newer

    try:
        source = read(source_path)
        expanded, things = plan(source, pack_dir=pack)
    except BlueprintError as exc:
        return [f"blueprint: {exc} ({exc.pointer})"]

    errors: list[str] = []
    if lock.get("source_sha256") != canonical_hash(source):
        errors.append(
            "blueprint output is stale: the Blueprint changed since "
            "blueprint.lock.json was written - run 'vefr normalize "
            f"--pack {pack} --out {pack}'")
    for region_key, entry in expanded.items():
        if not entry["owns_enemies"]:
            continue
        records = entry["enemies"]
        rel = f"acts/{region_key}/contract.json"
        pointer = "/enemies"
        try:
            contract = json.loads(
                _contract_path(pack, region_key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            errors.append(f"{rel}: {pointer} is stale (the contract could not "
                          f"be read) - run 'vefr normalize --pack {pack} "
                          f"--out {pack}'")
            continue
        on_disk = contract.get("enemies") if isinstance(contract, dict) else None
        if on_disk == records:
            continue
        # Name the first differing record when the lists line up; a
        # differing length or shape can only name the list itself.
        if isinstance(on_disk, list) and len(on_disk) == len(records):
            for i, (committed, wanted) in enumerate(zip(on_disk, records)):
                if committed != wanted:
                    pointer = f"/enemies/{i}"
                    break
        errors.append(f"{rel}: {pointer} is stale (the committed value "
                      f"differs from what this VEFR expands) - run "
                      f"'vefr normalize --pack {pack} --out {pack}'")
    for sentence in _place_stale_errors(pack, expanded, lock):
        errors.append(sentence)
    errors.extend(_thing_stale_errors(pack, things))
    return errors


def _thing_stale_errors(pack: Path, things: list) -> list[str]:
    """A stale sentence per written `items` entry that no longer holds
    what the thing says it should.

    Format 1's rule over the pointers a thing owns. The carrier's own
    record is not read here: the appended drop is part of the enemy
    record the `/enemies` check already compares, so naming the same
    value twice would be one stale thing with two sentences.
    """
    if not things:
        return []
    items = _read_json(pack / "world.json").get("items")
    items = items if isinstance(items, dict) else {}
    return [_stale(pack, "world.json", thing["pointer"])
            for thing in things
            if items.get(thing["id"]) != thing["item"]]


def _place_stale_errors(pack: Path, expanded: dict, lock: dict) -> list[str]:
    """Every owned place value that no longer matches the source.

    Format 1's rule, over every pointer a place owns: the legend entry,
    the poi and its text, the act transition, and the cell in
    `map.md`. A hand edit to any of them is stale, because the next
    `vefr normalize` would put the glyph back and the author would not
    know why their map changed. A pointer this Blueprint does not own
    is not read at all, so a second region's hand legend entry is
    nobody's business.
    """
    errors: list[str] = []
    owned = _lock_outputs(lock)
    contracts: dict[str, dict] = {}
    for region_key, entry in expanded.items():
        if not entry["places"]:
            continue
        rel = f"acts/{region_key}/contract.json"
        if rel not in contracts:
            contracts[rel] = _read_json(_contract_path(pack, region_key))
        contract = contracts[rel]
        for place in entry["places"]:
            for pointer, value in _place_contract_values(place):
                if _get_pointer(contract, pointer) == value:
                    continue
                errors.append(_stale(pack, rel, pointer))
        errors.extend(_map_stale_errors(pack, region_key, entry))
    errors.extend(_transition_stale_errors(pack, expanded, owned))
    return errors


def _place_contract_values(place: dict) -> list[tuple[str, object]]:
    """The `contract.json` pointers one place owns, with what it writes."""
    out = [(place["legend_pointer"], place["legend"])]
    if place["poi_pointer"]:
        out.append((place["poi_pointer"], place["label"]))
    if place["poi_text_pointer"]:
        out.append((place["poi_text_pointer"], place["text"]))
    return out


def _map_rows(pack: Path, region_key: str) -> list[str] | None:
    """The region's `map.md` rows, or None when the file is not there."""
    try:
        text = _map_path(pack, region_key).read_text(encoding="utf-8")
    except OSError:
        return None
    return [line for line in text.splitlines() if line.strip()]


def _map_path(pack: Path, region_key: str) -> Path:
    """The guarded `map.md` of one region. The glyph lives in the map
    itself, not in a weave-time overlay, so deleting the Blueprint
    leaves a pack that still works."""
    return Path(_region_dir(
        pack, region_key, f"/regions/{_esc(region_key)}")) / "map.md"


def _map_stale_errors(pack: Path, region_key: str, entry: dict) -> list[str]:
    """A stale sentence per owned `map.md` cell that holds another
    character than the glyph."""
    rows = _map_rows(pack, region_key)
    rel = f"acts/{region_key}/map.md"
    out: list[str] = []
    for place in entry["places"]:
        x, y = place["at"]
        if (rows is None or y >= len(rows) or x >= len(rows[y])
                or rows[y][x] == place["glyph"]):
            continue
        out.append(_stale(pack, rel, _cell_pointer((x, y))))
    return out


def _transition_stale_errors(pack: Path, expanded: dict,
                             owned: dict) -> list[str]:
    """A stale sentence per owned act transition that no longer holds
    what the source says it should."""
    errors: list[str] = []
    acts = _planned_transitions(expanded)
    for act, wanted in acts.items():
        rel = f"acts/{act}/world.json"
        data = _read_json(Path(_inside_pack(pack, f"acts/{act}")) / "world.json")
        listed = data.get("transitions")
        listed = listed if isinstance(listed, list) else []
        for index, transition in zip(
                _transition_slots(rel, owned, len(listed), len(wanted)), wanted):
            if index < len(listed) and listed[index] == transition:
                continue
            errors.append(_stale(pack, rel, f"/transitions/{index}"))
    return errors


def _stale(pack: Path, rel: str, pointer: str) -> str:
    """One stale sentence, in format 1's shape: the file, the pointer,
    and the command that puts it back."""
    return (f"{rel}: {pointer} is stale (the committed value differs from "
            f"what this VEFR expands) - run 'vefr normalize --pack {pack} "
            f"--out {pack}'")


def notes(pack_dir) -> list[str]:
    """A note when an older normalizer wrote a still-equal lock.

    Not an error (the output matches): the author is told to re-run
    `vefr normalize` to refresh the recorded version. Empty for a pack
    with no Blueprint and no lock, or a current one.
    """
    pack = Path(pack_dir)
    source_path = pack / BLUEPRINT_FILE
    lock_path = pack / LOCK_FILE
    if not source_path.is_file() or not lock_path.is_file():
        return []
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(lock, dict):
        return []
    normalizer = lock.get("normalizer")
    if type(normalizer) is int and normalizer < NORMALIZER_VERSION:
        return [f"blueprint.lock.json was written by normalizer {normalizer}; "
                f"re-run 'vefr normalize --pack {pack} --out {pack}'"]
    return []


class NormalizeResult:
    """What `normalize` wrote, or (read-only) what it found.

    `fresh` is True only when the committed output already matches;
    `errors` are plain sentences (whole-pack validation errors on a
    refresh); `regions` maps each owned region key to its record count.
    """

    def __init__(self, fresh: bool, errors: list[str],
                 regions: dict[str, int]) -> None:
        self.fresh = fresh
        self.errors = errors
        self.regions = regions


def normalize(pack_dir, out=None) -> NormalizeResult:
    """Validate and expand a Blueprint, optionally writing the output.

    `out` None is read-only. `out` equal to the pack refreshes it in
    place, restoring the previous bytes if the whole-pack validation
    fails. Any other `out` must not exist or be an empty directory: the
    pack is copied there, refreshed and validated there, and the
    original is never touched.
    """
    pack = Path(pack_dir)
    if out is None:
        return _normalize_read_only(pack)
    out_path = Path(out)
    if os.path.realpath(out_path) == os.path.realpath(pack):
        return _refresh_in_place(pack)
    return _normalize_copy(pack, out_path)


def _region_counts(expanded: dict) -> dict[str, int]:
    return {key: len(records) for key, records in expanded.items()}


def _normalize_read_only(pack: Path) -> NormalizeResult:
    errors = check_errors(pack)
    regions: dict[str, int] = {}
    source_path = pack / BLUEPRINT_FILE
    if source_path.is_file():
        try:
            expanded = expand(read(source_path), pack_dir=pack)
        except BlueprintError:
            pass
        else:
            regions = _region_counts(expanded)
    return NormalizeResult(not errors, errors, regions)


def _normalize_copy(pack: Path, out: Path) -> NormalizeResult:
    real_pack, real_out = os.path.realpath(pack), os.path.realpath(out)
    if real_out == real_pack or real_out.startswith(real_pack + os.sep):
        return NormalizeResult(
            False, [f"output directory {out} is inside the pack - choose "
                    "a directory outside it"], {})
    created = not out.exists()
    if not created:
        if not out.is_dir():
            return NormalizeResult(
                False, [f"output path {out} is not a directory"], {})
        if any(out.iterdir()):
            return NormalizeResult(
                False,
                [f"output directory {out} is not empty - refusing to write "
                 "into it"],
                {})
    try:
        # symlinks=True keeps a link as a link: a pack must never pull a
        # file from outside itself into the copy.
        shutil.copytree(pack, out, symlinks=True, dirs_exist_ok=True)
    except OSError as exc:
        _discard(out, created)
        return NormalizeResult(False, [f"could not copy {pack} to {out}: {exc}"], {})
    result = _refresh_in_place(out)
    if result.errors:
        _discard(out, created)  # a failed refresh leaves nothing behind
    return result


def _discard(out: Path, created: bool) -> None:
    """Remove what `_normalize_copy` wrote: the directory it made, or the
    contents of the empty directory it was given."""
    if created:
        shutil.rmtree(out, ignore_errors=True)
        return
    for child in out.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def _restore(backups: dict) -> None:
    """Put every touched file back, deleting one that did not exist before."""
    for path, data in backups.items():
        if data is None:
            if path.exists():
                path.unlink()
        else:
            path.write_bytes(data)


def _refresh_in_place(pack: Path) -> NormalizeResult:
    source_path = pack / BLUEPRINT_FILE
    lock_path = pack / LOCK_FILE
    if not source_path.is_file():
        return NormalizeResult(
            False, [f"{source_path} does not exist - nothing to normalize"], {})
    try:
        source = read(source_path)
        expanded, things = plan(source, pack_dir=pack)
    except BlueprintError as exc:
        return NormalizeResult(False, [f"blueprint: {exc} ({exc.pointer})"], {})
    regions = _region_counts(expanded)
    version = source.get("blueprint")

    touched: list[Path] = []
    slots: dict[str, list] = {}
    owned = _owned_pointers(pack)
    try:
        for region_key in expanded:
            touched.append(_contract_path(pack, region_key))
        if version == 2 and things:
            touched.append(pack / "world.json")
        if version == 3:
            for region_key, entry in expanded.items():
                if entry["places"]:
                    touched.append(_map_path(pack, region_key))
            for act, wanted in _planned_transitions(expanded).items():
                data = _read_json(Path(_inside_pack(pack, f"acts/{act}"))
                                  / "world.json")
                listed = data.get("transitions")
                length = len(listed) if isinstance(listed, list) else 0
                slots[act] = _transition_slots(
                    f"acts/{act}/world.json", owned, length, len(wanted))
                touched.append(Path(_inside_pack(pack, f"acts/{act}"))
                               / "world.json")
    except BlueprintError as exc:
        return NormalizeResult(False, [f"blueprint: {exc} ({exc.pointer})"], regions)

    # Snapshot every file this refresh will touch before touching any of
    # them, so a failing whole-pack validation can put the pack back.
    backups: dict[Path, bytes | None] = {}
    for path in touched:
        backups[path] = path.read_bytes() if path.is_file() else None
    backups[lock_path] = lock_path.read_bytes() if lock_path.is_file() else None

    for region_key, entry in expanded.items():
        contract = _contract_path(pack, region_key)
        contract_data: dict = {}
        if contract.is_file():
            try:
                loaded = json.loads(contract.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                loaded = {}
            if isinstance(loaded, dict):
                contract_data = loaded
        if entry["owns_enemies"]:
            contract_data["enemies"] = entry["enemies"]
        for place in entry["places"]:
            # Each of these is a pointer this Blueprint owns, so it is
            # written where it stands; every other key of the contract
            # is the hand's and is left exactly as it was found.
            for pointer, value in _place_contract_values(place):
                _set_pointer(contract_data, pointer, value)
        if entry["owns_enemies"] or entry["places"]:
            _write_json(contract, contract_data)
        if entry["places"]:
            map_path = _map_path(pack, region_key)
            cells = {place["at"][1]: (place["glyph"], place["at"][0],
                                      place["at"][1])
                     for place in entry["places"]}
            map_path.write_text(_write_map_cells(map_path, cells, region_key),
                                encoding="utf-8")
    for act, wanted in _planned_transitions(expanded).items():
        path = Path(_inside_pack(pack, f"acts/{act}")) / "world.json"
        data = _read_json(path)
        listed = data.get("transitions")
        listed = list(listed) if isinstance(listed, list) else []
        for index, transition in zip(slots[act], wanted):
            while len(listed) <= index:
                listed.append(None)
            listed[index] = transition
        data["transitions"] = listed
        _write_json(path, data)
    if things:
        # One `items` entry per thing, written where the pointer says and
        # with nothing invented: a record that gave three keys gets three.
        world = _read_json(pack / "world.json")
        for thing in things:
            _set_pointer(world, thing["pointer"], thing["item"])
        _write_json(pack / "world.json", world)
    if version == 3:
        _write_json(lock_path, _lock_data_places(source, expanded, slots))
    elif version == 2:
        _write_json(lock_path, _lock_data_things(
            source, {key: entry["enemies"] for key, entry in expanded.items()},
            things))
    else:
        _write_json(lock_path, _lock_data(
            source, {key: entry["enemies"] for key, entry in expanded.items()}))

    # The whole normalized pack, through today's validator (which now
    # also runs this module's freshness check): only this second pass
    # can see cross-references.
    from .maplab import validate as _validate

    try:
        errors = _validate(load_pack(pack), pack_dir=pack)
    except Exception:
        _restore(backups)
        raise
    if errors:
        _restore(backups)
        return NormalizeResult(False, errors, regions)
    return NormalizeResult(True, [], regions)
