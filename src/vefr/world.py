"""The world pack loader - the seam between the engine and the story.

The engine (src/vefr) never hardcodes world content. Everything the
story owns - phases, voices, bonds, regions (town and dungeon), the
surface - lives in a pack directory. Two shapes are supported:

  Flat shape (legacy / simple packs):
    worlds/<name>/
      world.json
      logbok.md
      ledger.md
      map.md
      voices/*.md                 # speaker voice prompts
      voices/<name>.fragments.md  # optional: speakable lines for
                                  # offline play (bullet lines)

  Acts shape (multi-region, self-contained per act):
    worlds/<name>/
      world.json              # engine contract: title, phases, surface, acts[]
      logbok.md               # pack-level canon (shared across acts)
      ledger.md               # pack-level voice anchors (shared)
      acts/
        act-1/
          world.json          # act-level contract: id, title, regions, speakers,
                              #   enemies, bosses, transitions, vault_intro
          town/
            map.md
            contract.json     # region metadata (legend, pois, hero_start, ...)
            voices/*.md
            sprites/*
            tiles/*           # optional: the region's own ground pictures
          dungeon/
            map.md
            contract.json
            voices/*.md
            sprites/*
            tiles/*

  REGIONS + TRANSITIONS (doors between maps): an act's `regions` is a
  list (or dict) of region names, one directory each. A region's map
  lives in its `map.md`; its geometry (legend, pois, poi_text,
  hero_start, sanctuary_tiles, watch, water_by_phase, flood_tiles,
  tile, bg, `fog` and the colours) lives in that region's
  `contract.json`. `fog` (true, or {"radius": N}) makes the woven player
  draw the region dark until it is explored - a lit circle around the
  hero, walked ground remembered dimmed, the rest black. Omit it and the
  region is drawn whole (a town).
  An act's `transitions` is a list of doors between those maps:

      {"from": "town", "at": [4, 5],
       "to": "cottage", "to_at": [4, 3]}

  `at` is the tile the door stands on in `from`; `to_at` is where the
  hero lands in `to`. A door is used with Interact, never stepped
  through by accident. A speaker may carry `"region": "<region name>"`;
  a
  speaker with no `region` belongs to the act's first region. Each
  loaded region carries its own `speakers` dict (the act's speakers
  filtered to that region), while the act's `speakers` keeps all of
  them.

The loader returns a single canonical shape regardless of which on-disk
shape the pack uses: top-level keys are the world's metadata (title,
phases, surface, logbok, ledger, acts), and `acts` is ALWAYS a list
with at least one element. Flat packs are loaded as a single implicit
act so every consumer can use the same access pattern.

  world = load_world()
  world["title"]                          # the world's title
  world["phases"]                         # {whispers: ..., doubts: ..., ...}
  world["surface"]                        # "combat" | "investigation" | "plain"
  world["acts"]                           # [act1, act2, ...] - always a list
  world["_current_act"]                   # 0 for now; future PRs advance this
  current_act(world)                      # world["acts"][world["_current_act"]]
  current_act(world)["regions"]["town"]   # the town of the active act

SURFACE: world.json may declare a 'surface' field - one of 'combat',
'investigation', 'plain'. The surface is the *grammar* the player
sees (HP bars, encounter prompts, investigation dice), not the
engine's actual behavior. The engine never gates the player on HP,
attack, or roll results - the surface is a costume over the
underlying rumor engine. Default surface is 'combat' for
back-compat with existing packs.

JOURNEY: the engine's story structure is the Hero's Journey, told
through four Elder Futhark runes. The mapping lives in journey.py.
Packs can rename their phases (any keys the author wants) but the
journey-stage anchors are positional - first phase in `phases` maps
to the first rune, and so on.

PACK LAW (per act): every act may declare how it plays -
  `floor`   - how hard the numbers bite: 'costume' (default; the
              HP bar is a costume, the player never drops to
              zero), 'story' (failure bends the narrative), or
              'stakes' (the numbers bite). The engine owns no
              opinion; each world declares its own floor.
  `tone`    - the act's position on the ridiculous-literal dial
              ('literal' | 'warm' | 'deadpan' | 'ridiculous' |
              'absurd'). The storyteller prompt carries it.
  `ruleset` - which ruleset module the act plays under
              ('ambient' default; ruleset modules land in future
              PRs).
  `verbs`   - the act's own action vocabulary. When declared, it
              replaces the engine's costume verbs entirely (a
              cooking act can offer plate/flip/serve).
  `enemies` / `bosses` - reserved shape for the rulesets that need
              them; validated, echoed by inspect, consumed by
              ruleset modules as they land.
  `transitions` - the act's doors between regions: a list of
              {from, at, to, to_at} steps (see REGIONS + TRANSITIONS
              above). The woven player honours them; maplab.validate
              checks the door tiles. Validated, echoed by inspect,
              consumed by ruleset modules as they land.
All of these are optional; absent means the engine's defaults, so
every existing pack loads unchanged.

ITEMS / LOOT (first slice): world.json may carry an optional top-level
  `items` catalog, keyed by id:
      {"cloudy-potion": {"name": "a cloudy potion", "sprite": "potion"}}
  `name` is plain words; `sprite` names an entry in `player.sprites` and
  is optional. A region enemy may carry `drops` (a list of catalog ids),
  and a chest book (`chest: yes`) may carry `drops:` (a comma-separated
  list of catalog ids in its front matter). A killed enemy leaves its
  drop on the floor it died on; walking onto a drop takes it into the
  bag (`localStorage['vefr-bag-<world>']`). The woven player bakes the
  catalog (`VEFR_ITEMS`) and each drop. An item may also carry optional
  `value` (a positive int: what a shop pays and asks), `heal` (a positive
  int) and `use` (a verb such as `drink`); with none of them the item
  bakes exactly as before. ADR 0017 gives a drop hidden traits and an
  `identified` flag that starts false; the town reads a thing where a
  pack names a reader (IDENTIFY SERVICE below).
  An item may carry an optional `light`, in one of two forms:
      {"light": {"radius": 2, "turns": 5}}   # wider for a while
      {"light": {"reveal": true}}            # the whole region at once
  `radius` (int 1..20) widens the fog's lit circle by that many tiles for
  `turns` (int 1..999) hero turns, then it gutters out; `reveal` marks
  every tile of the region explored in one use. Using either from the Bag
  spends one copy; in a region with no dark (or the player's fog turned
  off) it says so and spends nothing. With no `light` the item bakes
  exactly as before. maplab checks the shape and ranges.

ROLLED ITEMS (ADR 0017, T3 slices 1-2): an item may also carry a `rarity`
  (one plain word), `traits` (a list of plain words) and an optional
  `roll`:
      {"ring": {"name": "a brass ring", "rarity": "common",
                "roll": {"rarity": {"common": 60, "rare": 30, "odd": 10},
                         "traits": ["keen", "brave", "swift"],
                         "chance": 50, "max": 1}}}
  `roll.rarity` is the item's own table of pack-chosen names and whole
  weights; `traits` is the pool a draw takes hidden traits from;
  `chance` (int 0..100, default 100) is how often a draw bears one at
  all, and `max` (int 0..4, default 1) how many at once. On a generated
  floor a monster's drop is drawn from that monster's own loot stream and
  the rarity and traits from a second named stream off the same floor key
  and monster (`v3|<key>|roll|<mob id>|<item id>`), so the same run always
  drops the same thing and two monsters never share a roll. The drawn
  instance rides on the drop and then in the bag as
  `{"item": id, "rarity": ..., "traits": [...], "identified": false}`;
  the bag strip and the Bag panel name the item and its rarity together
  from the moment of pickup, and the traits stay hidden - in no part of
  the page - until the thing has been read (IDENTIFY SERVICE below).
  Reading sets `identified` on that instance in the bag and saves it; it
  never re-draws, so a rarity and its traits are the ones the drop drew.
  Once read, the traits are named in the bag row and in the HUD strip's
  `aria-label`, in the same pass and with nothing behind a timer, so the
  reveal is instant with motion off or on. An item with no `roll` is the
  bare id it always was, unless it declared a fixed `rarity`/`traits`, in
  which case those ride along unchanged. maplab checks the shape, the
  ranges, and the four refusals: a `rarity` outside the item's own
  table, a trait that is not one plain word, a `roll` with no rarity
  table, and a `roll` that asks for traits and names no pool.

IDENTIFY SERVICE (ADR 0017, T3 slice 2): a speaker whose spec carries
  `"identify": "true"` (also `yes`/`1`/`true`) is the reader of its
  region, the same flag a shopkeeper carries and read the same way.
  Standing beside that speaker and using the world's interact verb opens
  an Identify panel listing the carried, not-yet-read things; reading one
  sets `identified: true` on THAT instance in
  `localStorage['vefr-bag-<world>']` and writes the bag back, so the
  record that loads next run is the read one. Reading draws nothing and
  calls no model - the traits were drawn once, at the drop - so nothing
  in the panel is random, timed or model-written, and nothing needs a
  second roll refused. With no `identify` anywhere a pack has no reader,
  the interact verb never offers one, and the woven player is the same
  file plus this panel's code. maplab refuses three: an `identify` that
  is some other word, an `identify` that is not the word true at all (an
  object or a number could carry a chance, a roll or a model), and a
  speaker that offers identify in a region the pack does not have.

SPELLS (ADR 0018): world.json may carry an optional top-level `spells`
  block: the schools the pack teaches and the spells in them.
      {"spells": {"schools": ["ember", "tide"],
                  "spells": [{"id": "ember-bolt", "name": "an ember bolt",
                              "school": "ember", "level": 1, "heal": 3}]}}
  `schools` is a list of the pack's own plain words and `spells` a list of
  records; `id`, `name` and `school` are required and `level` and `heal`
  are not. A spell with a `level` is learned when the hero's level
  reaches it, read from the `growth` block's own derived level - there is
  no second level counter and the level cap (the length of `levels.xp`)
  does not move, so a spell written above that table is never learned by
  level. A spell with no `level` waits for a book. A spellbook is an
  ordinary `items` entry carrying one more optional key, `spell` (the id
  it teaches), so a book found as loot is a drop like every other drop and
  what it teaches follows from the id the draw already chose - no second
  draw, no second stream. Reading it is the `use` verb the bag already
  has; casting a known spell from the Bag panel recovers its `heal` and
  never above the max. maplab checks the shape and the four refusals: a
  school the block does not declare, a `level` under 1, a book teaching a
  spell the pack does not declare, and a spell with no school. What a
  school does in play, and what a spell does beyond healing, are not
  decided here.

REWARD (first slice): `world.player` may carry `gold`, the starting
  purse (a non-negative int; default 0), kept per world at
  `localStorage['vefr-gold-<world>']`. A speaker whose spec carries
  `"shop": "true"` (also `yes`/`1`) keeps its region's shop - at most one
  per region, the first named wins. Standing beside that speaker and
  using the world's interact verb opens a Trade panel (sell carried
  things with a `value`, buy catalog things with a `value`); a carried
  thing with a `heal` can be used from the Bag panel. The woven player
  bakes `VEFR_HERO.gold` and `VEFR_SHOPS` ({region: speaker key}). All of
  it is optional: a pack that names none of it bakes the player it had
  before.

RPG CORE (ADR 0021): every key opt-in, and a pack that names none of them
  bakes and plays exactly as before. world.json may carry `fight`
  ({"miss": 0-50, "crit": 0-50, "crit_times": 2|3, "turns": bool}: rolled
  blows from a named seeded stream, and a turn for every drink, use or
  cast) and `traits` ({word: {"hp"|"atk"|"guard"|"mana": -9..9,
  "crit": -50..50, "kill_heal"|"thorns"|"sting": 1..9, "opener": 2..3,
  "curse": true}}: what a rolled or fixed trait does, worn or carried in a
  bag). `player` may carry `guard` (0-99) and `mana` (0-999). An item's
  `mods` may hold `guard` and `mana` beside `atk` and `hp`, and an item may
  `casts` a spell id on `charges` (1-20), an item's `roll` may tie its
  trait count to its rarity with `per_rarity`, and an item marked `pouch: true`
  is carried without taking a bag place. A spell may cost `mana` (1-99)
  and do one of `heal`, `harm` (1-99, with `range` 1-20) or `ward`
  ({"guard": 1-9, "turns": 1-20}). A shopkeeper speaker may carry `stock`
  (item ids, or {"item", "flag"}) and `markup` (100-500). A Blueprint
  family's `defaults` may carry `guard`, `drop_chance` (0-100) and `gold`
  ([lo, hi]). The `descent` block may carry `resume: "deepest-landing"`
  and `fall: "home"`, and the `time` block `rest_heals: true`. A
  Section's `curve` is read at play through `vefr.mob_stats`. An act's
  `verbs` entry may be {"verb", "label"}, and the verb `cast` casts the
  first harmful spell the hero knows. See `docs/guides/rpg-core.md`.

GRAMMARS: `world.json` may carry a top-level `grammars` object: a
set of tiny, hand-written sentence recipes the engine expands
offline, with no model and no baked pool. Each grammar maps a rule
name to a non-empty list of strings and must carry an `origin` rule,
where expansion starts; `#rule#` inside a string expands to one
entry of that rule, and every other character is kept as written:

  "grammars": {
    "whisper": {"origin": ["#who# says #news#."],
                "who": ["the innkeeper"],
                "news": ["the road east is watched"]},
    "weather": {"origin": ["#sky# over #place#."],
                "sky": ["Rain"], "place": ["the town"]},
    "name":    {"origin": ["#adj# #noun#"],
                "adj": ["Grey"], "noun": ["Hollow"]}
  }

Every `#rule#` must name a rule in the same grammar, and the
expander caps one expansion at 200 draws, so a grammar that points at
itself stops instead of looping. The engine reads `whisper` when a
woven player has no live endpoint, no pool, and no fragment banks
(the woven file carries the same algorithm in `web/packaged.html`);
`weather` on arriving in a region; `name` to name a floor that
`norns delve` generates. Every part is optional and a pack with no
`grammars` behaves exactly as it always has. maplab validates the
block. See grammar.py and docs/guides/grammars.md.

STEFNA / BELL VOICE: a pack may declare an optional top-level
`stefna_voice` (string naming which speaker writes the sealed letter;
absent means "the pack's first declared voice"). Every voice declared
in the pack must carry a non-empty `strike` string prompt for that
letter.

VOICES CONVENTION: flat packs place voice prompt files at pack-level
`voices/<name>.md`. Acts-shaped packs place them at the region level
under `acts/<id>/<region>/voices/<name>.md`, discovered by convention
matching the file stem. Flat and acts resolution is unified via
`resolve_voice_file()`.

TILES CONVENTION: a region may bring its own ground pictures in a
`tiles/` directory beside `sprites/` (flat packs use pack-level
`tiles/`). A tile is named by its file stem - `stone-wall.webp` is the
picture for the legend's `"tile": "stone-wall"`. A tile may have
numbered variants tried in order: `stone-wall.webp` is variant 1 and
is optional, then `stone-wall.2.webp`, `stone-wall.3.webp`, and so
on. A name with only numbered files is legal - there is no required
unnumbered file. The player picks a variant deterministically, so the
same pack always looks the same; a pack with no tiles/ resolves tiles
from the engine set exactly as before.
A legend entry may also name `"edges": "lane-edges"`: ONE picture in
`tiles/` cut into a 4 x 4 sheet, whose piece (north 1 + east 2 + south 4
+ west 8 for each neighbour sharing the symbol) is drawn over the tile so
one ground blends into the next (docs/guides/rulesets.md, "A ground that
blends"). A legend naming no edges draws exactly as before.
A Section (`sections/<id>.json`) may name `decor`: pictures from the
pack's `props/` scattered over its generated floors, `on` a floor tile or
a wall face, about one for `every` tiles (docs/guides/rulesets.md, the
Section contract). Decor never blocks and is not part of a floor's
identity; a Section naming none draws exactly as before.

SAVES (rule saves): world.json may carry an optional top-level `saves`
  block choosing how much of a run the rules remember:

      {"saves": {"rules": "persist" | "reset", "legacy": "fresh" | "from-log"}}

  `rules` is `reset` (the default, and when the block or key is absent:
  today's behavior, with no new storage key read or written) or
  `persist` (flags, fired markers, beliefs and the engine's items
  survive a reload and are cleared by Start over). `legacy` (persist
  mode) is `fresh` (the default) or `from-log`, which marks as fired
  the rules the WHY log proves fired. `starts` fires once per save in
  persist mode. maplab validates the block; a pack with none loads and
  bakes exactly as before. See docs/adr/0009-rule-saves.md and
  docs/guides/rules.md.

VISIBLE ENGINE: every load step is recorded to the weave log so the
author can see exactly what the loader did. See weave.py.

BLUEPRINTS (acts shape only): a pack may carry an optional
`blueprint.json` at its root and the `blueprint.lock.json` written
beside it by `vefr normalize`. The Blueprint is the edited truth for
the regions it owns; normalize expands it into those regions'
committed `enemies` lists. A pack without one is unchanged, and a flat
pack may not carry one. See docs/guides/blueprint.md and
docs/adr/0008-blueprint-format.md.
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from .paths import pack_dir
from .weave import weave

log = logging.getLogger(__name__)

VALID_SURFACES = ("combat", "investigation", "plain")
# How hard the numbers bite is the pack's law, not the engine's.
#   costume - HP tracks as a number; the player never drops to
#             zero; the bar is a costume (the classic vefr way).
#   story   - failure bends the narrative instead of ending it
#             (the ruleset defines how; future PRs).
#   stakes  - the numbers bite (the ruleset defines how; future
#             PRs).
# The default is `costume` so every existing pack behaves exactly
# as it did before floors existed.
VALID_FLOORS = ("costume", "story", "stakes")
# The act's position on the ridiculous-literal dial. The
# storyteller prompt carries it; mechanics never branch on it.
VALID_TONES = ("literal", "warm", "deadpan", "ridiculous", "absurd")
REQUIRED_FLAT = ("title", "phases", "voices", "bonds", "town")


def creed_from(config: dict) -> str:
    """The world's creed - the one governing line of a pack.

    `gold_rule` is the pre-rename field name (the term belonged to one
    author's game). It is read forever so packs written before the
    rename keep their line; maplab writes the value back as `creed`.
    """
    return config.get("creed") or config.get("gold_rule", "")


class PackError(RuntimeError):
    """A world pack failed to load. The error message names the pack
    and the cause so the author can fix it without reading the stack."""


def _read_json(path: Path, *, what: str) -> dict:
    if not path.exists():
        raise PackError(f"missing {what}: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise PackError(f"invalid JSON in {what} ({path}): {e}") from e


def _read_text(path: Path, *, what: str) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _discover_voices(voices_dir: Path) -> dict:
    """Convention: every *.md under voices/ is a speaker voice file,
    named by the file's stem. The loader returns {stem: content}.
    `<stem>.fragments.md` files are NOT voices - they are the
    speaker's offline whisper bank (see _discover_fragments)."""
    if not voices_dir.is_dir():
        return {}
    out = {}
    for sf in sorted(voices_dir.glob("*.md")):
        if sf.name.endswith(".fragments.md"):
            continue
        out[sf.stem] = sf.read_text(encoding="utf-8")
    return out


def _discover_fragments(voices_dir: Path) -> dict:
    """Convention: `<name>.fragments.md` beside a voice file carries
    that speaker's speakable fragments - short lines the author
    writes by hand so a packaged game with no woven pool and no
    model can still hear them. Bullet lines speak; every other line
    is a note to the author. The loader returns
    {name: [lines]} with the `.fragments` suffix stripped. Optional
    per voice: a pack without fragment banks keeps the honest
    silence it has always had."""
    if not voices_dir.is_dir():
        return {}
    out: dict[str, list[str]] = {}
    for sf in sorted(voices_dir.glob("*.fragments.md")):
        lines: list[str] = []
        for raw in sf.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("- ") and len(line) > 2:
                lines.append(line[2:].strip())
        if lines:
            out[sf.name[: -len(".fragments.md")]] = lines
    return out


def fragments_for_pack(pack: Path) -> dict[str, list[str]]:
    """Every fragment bank in a pack, by speaker key.

    Walks the same convention voice discovery walks - the pack
    root's voices/ (flat shape) plus every act region's voices/
    (acts shape) - so a region's fragment bank travels with its
    own speakers. Later files never override earlier lines: banks
    with the same speaker key merge in file order, deduplicated.
    """
    out: dict[str, list[str]] = {}
    roots = [pack / "voices"]
    acts_dir = pack / "acts"
    if acts_dir.is_dir():
        for act_dir in sorted(acts_dir.iterdir()):
            if not act_dir.is_dir() or act_dir.name.startswith("."):
                continue
            for region_dir in sorted(act_dir.iterdir()):
                if region_dir.is_dir() and (region_dir / "voices").is_dir():
                    roots.append(region_dir / "voices")
    for root in roots:
        for key, lines in _discover_fragments(root).items():
            merged = out.setdefault(key, [])
            for ln in lines:
                if ln not in merged:
                    merged.append(ln)
    return out


def _discover_sprites(sprites_dir: Path) -> dict:
    """Convention: every file under sprites/ is a named sprite. The
    loader returns {name: relative_path}. The web layer resolves the
    path against the act's static mount.

    A `<key>.sheet.json` sidecar describes an optional walk sheet for
    the sprite beside it; it is never a sprite of its own, so it is
    skipped here (`*.sheet.json` is read by the weaver and validator).
    """
    if not sprites_dir.is_dir():
        return {}
    out = {}
    for f in sorted(sprites_dir.rglob("*")):
        if f.is_file() and not f.name.endswith(".sheet.json"):
            out[f.stem] = str(f.relative_to(sprites_dir))
    return out


# A numbered tile variant: the stem ends in `.<digits>` (`.2`, `.10`).
_TILE_VARIANT_RE = re.compile(r"^(?P<base>.+)\.(?P<num>\d+)$")
# A grid tile: ONE picture drawn as a COLSxROWS block of cells, `wood-floor.grid3x3.webp`. The player
# draws cell (x mod COLS, y mod ROWS) of it, so a floor painted as one scene repeats only every
# COLS tiles instead of every tile. No slicing and no extra files: one picture, one inlined copy.
_TILE_GRID_RE = re.compile(r"^(?P<base>.+)\.grid(?P<cols>\d+)x(?P<rows>\d+)$")
TILE_GRID_MAX = 8  # cells per side; 2..8 keeps the picture, and the bake, small


def tile_grid(stem_or_name: str) -> tuple[str, int, int] | None:
    """(base name, cols, rows) when this stem is a VALID grid picture, else None.

    Valid means 1..TILE_GRID_MAX on each side and at least two cells. A stem that looks like a grid
    but is not valid returns None here; maplab's validator reports it by name.
    """
    m = _TILE_GRID_RE.match(stem_or_name)
    if not m:
        return None
    cols, rows = int(m.group("cols")), int(m.group("rows"))
    if not (1 <= cols <= TILE_GRID_MAX and 1 <= rows <= TILE_GRID_MAX and cols * rows >= 2):
        return None
    return m.group("base"), cols, rows


# The picture suffixes a tile may use. The engine set also carries
# jpg/jpeg, but a pack's tiles/ is the webp/png shape the naming
# convention documents.
_TILE_SUFFIXES = (".webp", ".png")


def _discover_tiles(tiles_dir: Path) -> dict[str, list[str]]:
    """Convention: every picture under tiles/ names a tile ground.

    A tile may carry several pictures, tried by the player in order:
    `stone-wall.webp` is variant 1 and is optional, then
    `stone-wall.2.webp`, `stone-wall.3.webp`, ... in numeric order. A
    name with only numbered files is legal (the unnumbered file is
    not required). The loader returns {name: [paths in order]}, paths
    relative to tiles_dir, mirroring _discover_sprites. Non-image
    files and dotfiles are ignored; a missing tiles_dir returns {}.

    # NOTE: a variant shipped as both .webp and .png (for example
    # stone-wall.webp and stone-wall.png) is ambiguous. The winner is
    # the filename that sorts first - '.png' before '.webp' - so the
    # same pack always bakes the same picture, deterministically.
    # Packs should ship one suffix per variant.
    """
    if not tiles_dir.is_dir():
        return {}
    # Numbered variant -> chosen path, per tile name. The sort-first
    # suffix wins, so a doubled .webp/.png variant collapses to one.
    picked: dict[str, dict[int, str]] = {}
    for f in sorted(tiles_dir.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(tiles_dir)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if f.suffix.lower() not in _TILE_SUFFIXES:
            continue
        stem = f.name[: -len(f.suffix)]
        grid = tile_grid(stem)
        m = _TILE_VARIANT_RE.match(stem)
        if grid:
            # A grid picture sorts ahead of everything for its name (key -1), so a baker that
            # sees it first knows the name is a grid. It wins over variants of the same name.
            base, num = grid[0], -1
        elif m:
            base, num = m.group("base"), int(m.group("num"))
        else:
            # The unnumbered picture is variant 1; key 0 keeps it
            # ahead of every numbered file, even a stray `.1`.
            base, num = stem, 0
        path = str(rel)
        by_num = picked.setdefault(base, {})
        prev = by_num.get(num)
        if prev is None or path < prev:
            by_num[num] = path
    return {base: [by_num[n] for n in sorted(by_num)]
            for base, by_num in picked.items()}


def _load_region(region_dir: Path, *, region_name: str, act_id: str) -> dict:
    """Load one region (town or dungeon) from its directory.

    Convention: a region directory has map.md, optionally voices/,
    sprites/ and tiles/, and optionally a `contract.json` for region
    metadata (legend, watch, sanctuary_tiles, etc.) that used
    to live inline in the act's world.json. The loader picks up
    whatever is there - the engine never requires the contract
    file, but a multi-region pack is much more useful with it.
    """
    if not region_dir.is_dir():
        weave("region.missing", act=act_id, region=region_name,
              hint=f"no directory at {region_dir}")
        return {"map_text": "", "voices": {}, "fragments": {},
                "sprites": {}, "contract": {}, "tiles": {}}

    map_text = _read_text(region_dir / "map.md",
                          what=f"{act_id}/{region_name}/map.md")
    voices = _discover_voices(region_dir / "voices")
    fragments = _discover_fragments(region_dir / "voices")
    sprites = _discover_sprites(region_dir / "sprites")
    tiles = _discover_tiles(region_dir / "tiles")
    contract: dict = {}
    contract_path = region_dir / "contract.json"
    if contract_path.exists():
        contract = _read_json(contract_path,
                              what=f"{act_id}/{region_name}/contract.json")

    weave("region.loaded", act=act_id, region=region_name,
          map_lines=len(map_text.splitlines()) if map_text else 0,
          speakers=len(voices), sprites=len(sprites), tiles=len(tiles),
          has_contract=bool(contract))
    return {
        "map_text": map_text,
        "voices": voices,
        "fragments": fragments,
        "sprites": sprites,
        "contract": contract,
        "tiles": tiles,
    }


def _load_act(act_dir: Path) -> dict:
    """Load one act from its directory. Returns the act dict.

    Self-contained: each act carries its own regions, speakers,
    enemies, bosses, transitions, vault_intro. The pack-level
    logbok/ledger are inherited at read time by the consumer.
    """
    if not act_dir.is_dir():
        raise PackError(f"act directory does not exist: {act_dir}")

    contract = _read_json(act_dir / "world.json",
                          what=f"{act_dir.name}/world.json")
    act_id = contract.get("id") or act_dir.name

    required = ("id", "title", "regions")
    missing = [k for k in required if k not in contract]
    if missing:
        raise PackError(
            f"act '{act_id}' is missing required keys: {missing}"
        )

    regions = {}
    for region_name in contract["regions"]:
        region_dir = act_dir / region_name
        regions[region_name] = _load_region(region_dir,
                                            region_name=region_name,
                                            act_id=act_id)

    speakers = contract.get("speakers", {})
    # A speaker belongs to the region it names (`region`); a speaker
    # with no `region` belongs to the act's first region. The act
    # keeps every speaker; each region gets only its own, so the
    # player draws the right people on the right map.
    first_region = next(iter(contract["regions"]), None)
    for region_name, region in regions.items():
        region["speakers"] = {
            key: spec
            for key, spec in speakers.items()
            if (spec.get("region", first_region) if isinstance(spec, dict)
                else first_region) == region_name
        }

    act = {
        "id": act_id,
        "title": contract["title"],
        "regions": regions,
        "speakers": speakers,
        "enemies": contract.get("enemies", []),
        "bosses": contract.get("bosses", []),
        "transitions": contract.get("transitions", []),
        "start": contract.get("start", {}),
        "vault_intro": contract.get("vault_intro", ""),
        "verbs": contract.get("verbs", []),
        "floor": contract.get("floor", "costume"),
        "tone": contract.get("tone", ""),
        "ruleset": contract.get("ruleset", "ambient"),
        "cooking": contract.get("cooking", {}),
        "desk": contract.get("desk", {}),
    }
    weave("act.loaded", act=act_id, title=act["title"],
          regions=list(regions.keys()),
          speakers=len(act["speakers"]),
          enemies=len(act["enemies"]),
          bosses=len(act["bosses"]),
          transitions=len(act["transitions"]))
    return act


def _flat_to_act(config: dict, pack: Path) -> dict:
    """Convert a legacy flat-shape world.json into the always-array
    shape's single implicit act. The flat shape is:

      { title, phases, voices, bonds, speakers, surface, town, ... }

    The act form is:

      { id: <pack name>, title, regions: {town: <town dict>},
        speakers, enemies: [], bosses: [], transitions: [], ... }

    The legacy `voices` block (each speaker's full system prompt)
    and `speakers` block (NPC positions + seeds) are kept separate
    in the flat shape. In the act form, the speaker's `voice_file`
    pointer resolves to a region voice file (convention).
    """
    town = config.get("town", {})
    town_region = {
        "map_text": _read_text(pack / "map.md", what=f"{pack.name}/map.md"),
        "voices": _discover_voices(pack / "voices"),
        "fragments": _discover_fragments(pack / "voices"),
        "sprites": _discover_sprites(pack / "sprites"),
        "tiles": _discover_tiles(pack / "tiles"),
    }
    flat_speakers = config.get("speakers", {})
    # The flat shape has one implicit region; every speaker belongs to it.
    town_region["speakers"] = flat_speakers
    return {
        "id": pack.name,
        "title": config["title"],
        "regions": {"town": town_region},
        "speakers": flat_speakers,
        "enemies": config.get("enemies", []),
        "bosses": config.get("bosses", []),
        "transitions": config.get("transitions", []),
        "vault_intro": config.get("vault_intro", ""),
        "verbs": config.get("verbs", []),
        "floor": config.get("floor", "costume"),
        "tone": config.get("tone", ""),
        "ruleset": config.get("ruleset", "ambient"),
        "cooking": config.get("cooking", {}),
        "desk": config.get("desk", {}),
        "_town_legacy": town,
    }


def _attach_journey(world: dict) -> None:
    """Attach the journey-stage anchors to each phase by position.
    The pack's `phases` dict is ordered (Python 3.7+ preserves
    insertion order); we zip it with journey.py's DEFAULT_PHASES.
    Packs that rename phases still get the engine's bones.
    """
    from .journey import DEFAULT_PHASES, PHASE_JOURNEY_RUNE
    world["_journey"] = []
    phase_keys = list(world["phases"].keys())
    if len(phase_keys) < len(DEFAULT_PHASES):
        return
    for i, stage_key in enumerate(DEFAULT_PHASES):
        world["_journey"].append({
            "pack_phase": phase_keys[i],
            **PHASE_JOURNEY_RUNE[stage_key],
        })


def _apply_surface(world: dict, pack_name: str) -> None:
    if "surface" not in world:
        world["surface"] = "combat"
    elif world["surface"] not in VALID_SURFACES:
        raise PackError(
            f"world pack '{pack_name}' has invalid surface "
            f"{world['surface']!r}; expected one of {VALID_SURFACES}"
        )


def _load_library(pack: Path) -> list[dict]:
    from .library import load_library
    return load_library(pack)


@lru_cache(maxsize=8)
def load_world(name: str | None = None) -> dict:
    """Load a world pack. Returns the always-array canonical shape.

    Cached: 8 entries, by pack name. Callers that need to bust the
    cache (testing, builder edits) should call `load_world.cache_clear()`.

    The pack directory comes from `pack_dir()`, which prefers the
    read-write canon mount (`/app/worlds/<name>/`) and falls back
    to the read-only template mount (`/app/worlds-template/<name>/`).
    This means an author's edits in the rw volume always win over
    any engine template that happens to share a pack name.
    """
    from .paths import pack_dir as _pack_dir, template_dir as _tdir, worlds_dir as _wdir
    d = _pack_dir(name)
    # `source` is 'canon' when the pack resolved to the rw mount,
    # 'template' when it fell back to the ro one. We compare
    # `d.parent` against the resolved template/worlds dirs so
    # the dev-box layout (where neither path is exactly /app/...)
    # still reports the right source.
    try:
        d.parent.samefile(_wdir())
        source = "canon"
    except (FileNotFoundError, OSError):
        try:
            d.parent.samefile(_tdir())
            source = "template"
        except (FileNotFoundError, OSError):
            source = "dev"
    weave("pack.load.start", pack=d.name, path=str(d), source=source)

    if not d.is_dir():
        raise PackError(f"pack directory does not exist: {d}")

    # Acts shape: worlds/<name>/world.json + worlds/<name>/acts/<id>/
    pack_contract_path = d / "world.json"
    acts_dir = d / "acts"
    if acts_dir.is_dir():
        config = _read_json(pack_contract_path, what=f"{d.name}/world.json")
        acts = []
        for act_dir in sorted(acts_dir.iterdir()):
            if not act_dir.is_dir() or act_dir.name.startswith("."):
                continue
            acts.append(_load_act(act_dir))
        if not acts:
            raise PackError(f"pack '{d.name}' has acts/ but no act subdirectories")
        # Synthesize a `_town_legacy` block on the first act from
        # its region's contract.json + map. This is what the
        # validator and older tests read; it keeps the public
        # shape stable as the on-disk layout migrates from
        # inline `town: { ... }` to per-region `town/contract.json`
        # + `town/map.md`.
        first_act = acts[0]
        first_region = next(iter(first_act["regions"].values()), None)
        if first_region is not None:
            legacy = dict(first_region.get("contract", {}))
            # The map is in map_text (a string) in the acts shape;
            # the validator wants a list of rows. Convert.
            map_text = first_region.get("map_text", "")
            if map_text and "map" not in legacy:
                legacy["map"] = [ln for ln in map_text.splitlines() if ln.strip()]
            first_act["_town_legacy"] = legacy
    else:
        # Flat shape: worlds/<name>/world.json with legacy keys.
        config = _read_json(pack_contract_path, what=f"{d.name}/world.json")
        missing = [k for k in REQUIRED_FLAT if k not in config]
        if missing:
            raise PackError(
                f"world pack '{d.name}' is missing required keys: {missing}"
            )
        acts = [_flat_to_act(config, d)]

    # Pack-level metadata - shared across all acts.
    world = {
        "name": d.name,
        "title": config.get("title") or acts[0]["title"],
        "description": config.get("description", ""),
        "creed": creed_from(config),
        "phases": config["phases"],
        "logbok": _read_text(d / "logbok.md", what=f"{d.name}/logbok.md"),
        "ledger": _read_text(d / "ledger.md", what=f"{d.name}/ledger.md"),
        "voices": config.get("voices", {}),
        "fragments": fragments_for_pack(d),
        "bonds": config.get("bonds", {}),
        "bond_draw": config.get("bond_draw", ""),
        "forge_texture": config.get("forge_texture", ""),
        "surface": config.get("surface", "combat"),
        "grammars": config.get("grammars", {}),
        "acts": acts,
        # The Library: authored books (library/*.md); see library.py.
        "library": _load_library(d),
        "_current_act": 0,
        "_shape": "acts" if acts_dir.is_dir() else "flat",
    }
    _apply_surface(world, d.name)
    _attach_journey(world)
    weave("pack.load.end", pack=d.name, acts=len(acts),
          shape=world["_shape"], surface=world["surface"])
    return world


def current_act(world: dict | None = None) -> dict:
    """Return the active act. The default index is world["_current_act"]
    (0 for the first PR; future PRs advance it via journal events).
    """
    if world is None:
        world = load_world()
    idx = world.get("_current_act", 0)
    return world["acts"][idx]


def current_town(world: dict | None = None) -> dict:
    """The town region of the current act. Convenience for the
    single-region case (the first PR): a flat pack has only the
    `town` region.
    """
    act = current_act(world)
    return act["regions"].get("town", {})


def resolve_voice_file(rel: str, world: dict | None = None) -> Path:
    """Find a voice file by relative path. Convention-driven search:

      1. acts/<current>/<region>/voices/<basename>     (convention)
      2. pack_root/<rel>                              (flat fallback)

    The speaker's `voice_file` field is a short stem in the new
    shape ("voices/keeper.md" -> "keeper.md" in the region's
    voices dir). The fallback lets flat packs keep working
    unchanged. Raises PackError if the file does not exist.
    """
    if world is None:
        world = load_world()
    act = current_act(world)
    pack_name = world.get("name") or world.get("title") or "pack"
    pack = pack_dir(world["name"])
    basename = Path(rel).name
    acts_root = pack / "acts" / act["id"]
    if acts_root.is_dir():
        for region_dir in acts_root.iterdir():
            if not region_dir.is_dir():
                continue
            candidate = region_dir / "voices" / basename
            if candidate.exists():
                return candidate
    legacy = pack / rel
    if legacy.exists():
        return legacy
    raise PackError(f"pack '{pack_name}' missing voice file for '{rel}' (looked in {acts_root} and {legacy})")


def phase_tone(phase: str, world: dict | None = None) -> str:
    """The prose tone the engine threads into every generation for
    the given phase. The pack's own `phases` dict is the source."""
    if world is None:
        world = load_world()
    phases = world["phases"]
    if phase in phases:
        return phases[phase]
    return next(iter(phases.values()))


def pack_phase_to_journey(phase_key: str,
                          world: dict | None = None) -> dict[str, str] | None:
    """Look up the journey-stage for a pack's phase key by position.
    Returns None if the pack has fewer phases than journey stages
    (a partial pack is allowed but doesn't anchor every stage).
    """
    if world is None:
        world = load_world()
    for entry in world.get("_journey", []):
        if entry["pack_phase"] == phase_key:
            return entry
    return None


def discover_packs() -> list[dict]:
    """Every pack the engine can see, with the source marked.

    Walks both the read-write canon mount and the read-only template
    mount, dedupes by name (canon wins on conflict), and returns a
    list of {name, source, path} dicts. The /api/builder/worlds
    route uses this to populate the world picker.

    The list is sorted by name, not by source, so the picker is
    stable. Engine templates sit next to the author's canon in
    the same list; the source tag tells the author which is
    which.
    """
    from .paths import template_dir, worlds_dir
    seen: dict[str, dict] = {}
    for source, base in (("canon", worlds_dir()), ("template", template_dir())):
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*/world.json")):
            pack_name = p.parent.name
            if pack_name in seen:
                # Canon beats template - if both have the same pack
                # name, keep the canon entry.
                continue
            seen[pack_name] = {
                "name": pack_name,
                "source": source,
                "path": str(p.parent),
            }
    return sorted(seen.values(), key=lambda d: d["name"])
