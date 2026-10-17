"""maplab - the map toolkit for world packs.

The lab-wrapper pattern, first piece: one validator shared by the
tests and the CLI, so the map can never be wrong in a way the
tests do not also check.

Subcommands:
  validate  [--pack DIR]            run every geometry check offline
  build     --segments FILE         rebuild the map from run-length
                                    segments: {"rows": [[["H", 4], ...], ...]}
  verify    --url URL               validate the map as actually served
                                    by a live deployment (closes the
                                    baked-but-not-deployed gap)

Walkability mirrors town.js exactly: legend solid flag wins, else
the legacy blocked-char fallback. Reachability is checked in the
least restrictive water state (low water everywhere).
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from . import library, shapes
from .paths import world_name as _default_world_name
from .world import VALID_FLOORS, VALID_TONES
from .world import creed_from as _creed_from

BLOCKED_FALLBACK = ['~', 'B', '#', 'T', 'M']

# A `#rule#` reference inside a grammar entry; the same pattern the
# expander (grammar.py) and the woven player walk.
_GRAMMAR_REF = re.compile(r"#([A-Za-z0-9_][A-Za-z0-9_.-]*)#")


def load_pack(pack_dir: Path) -> dict:
    """Read a pack's world.json and return a single shape that the
    validator can consume.

    The on-disk shape is one of two:

      Flat shape (legacy): a single world.json with title, phases,
        voices, bonds, town at the top level.
      Acts shape: a pack-level world.json + acts/<id>/world.json
        per act. The map lives in acts/<id>/<region>/map.md.

    The validator downstream reads `w['town']`, `w['speakers']`,
    `w['phases']`, and `w['voices']`. We build a unified dict so
    the validator never has to know which on-disk shape it came
    from. Acts-shape packs are validated against the current act's
    first region (the town in the canary shape).

    The optional `growth` block (design/growth.md) is carried through
    only when the pack declares it, so a pack without one loads
    exactly as before. The optional `skin` field (design/ui-skin.md)
    is carried the same way: only when the pack declares it, so a pack
    without one loads exactly as before. The optional `saves` block
    (docs/adr/0009-rule-saves.md) and the optional `descent` block
    (slice E1) ride through the same way, as does the optional `spells`
    block (ADR 0018).
    """
    pack = Path(pack_dir)
    config = json.loads((pack / 'world.json').read_text(encoding='utf-8'))
    if 'acts' in config or (pack / 'acts').is_dir():
        acts_dir = pack / 'acts'
        first_act_dir = next(
            (d for d in sorted(acts_dir.iterdir())
             if d.is_dir() and not d.name.startswith('.')),
            None,
        )
        if first_act_dir is None:
            raise SystemExit(f'{pack}/acts has no act directories')
        act = json.loads((first_act_dir / 'world.json').read_text(encoding='utf-8'))
        # Pick the first region for the validator's unified `town` (the
        # canary has only `town`; full per-region geometry is still a
        # follow-on). Transition checks, however, read every region's
        # map + legend, exposed below as `regions`.
        regions_list = list(act.get('regions', {}) or {})
        region_name = regions_list[0] if regions_list else None

        def _region_geo(act_dir, rname):
            """One region's map rows + contract, read from disk."""
            rdir = act_dir / rname
            rcontract: dict = {}
            cp = rdir / 'contract.json'
            if cp.exists():
                rcontract = json.loads(cp.read_text(encoding='utf-8'))
            rows: list[str] = []
            mp = rdir / 'map.md'
            if mp.exists():
                rows = [
                    ln for ln in mp.read_text(encoding='utf-8').splitlines()
                    if ln.strip()
                ]
            if not rows:
                rows = rcontract.get('map', [])
            return rcontract, rows

        contract: dict = {}
        map_lines: list[str] = []
        if region_name:
            contract, map_lines = _region_geo(first_act_dir, region_name)
        # Every region's geometry, for the door checks. `map` is the
        # rows; `legend` is what makes a tile walkable.
        regions_geo: dict[str, dict] = {}
        for rname in regions_list:
            rcontract, rrows = _region_geo(first_act_dir, rname)
            regions_geo[rname] = {
                'map': rrows,
                'legend': rcontract.get('legend', {}),
                'enemies': rcontract.get('enemies', []),
            }
            if 'props' in rcontract:
                regions_geo[rname]['props'] = rcontract['props']
        # The town's metadata can live in three places, in priority
        # order: the region's contract.json (new, convention-driven),
        # the act's _town_legacy (transitional), or the act's
        # inline `town` block (the very first acts-shape PR had
        # this). Read all three, the highest priority wins.
        region_legacy = act.get('_town_legacy', {}) or act.get('town', {})
        merged = {**region_legacy, **contract}
        # The map lives in acts/<id>/<region>/map.md in the new
        # shape. If it's there, parse it; otherwise fall back to
        # whatever the contract holds.
        if not map_lines:
            map_lines = merged.get('map', [])
        # Every speaker is carried: a book's giver may live in any region.
        # The geometry check below looks only at the first region's own.
        all_speakers = act.get('speakers', {})
        # Props are carried only when the contract has them, so a pack without props loads as before.
        town_props = {'props': merged['props']} if 'props' in merged else {}
        unified = {
            'name': pack.name,
            'title': config.get('title', act.get('title', pack.name)),
            'description': config.get('description', ''),
            'creed': _creed_from(config),
            'phases': config['phases'],
            'voices': config.get('voices', {}),
            'bonds': config.get('bonds', {}),
            'speakers': all_speakers,
            'surface': config.get('surface', 'combat'),
            'grammars': config.get('grammars', {}),
            'town': {
                'map': map_lines,
                'legend': merged.get('legend', {}),
                'pois': merged.get('pois', {}),
                'watch': merged.get('watch', {}),
                'sanctuary_tiles': merged.get('sanctuary_tiles', []),
                'water_by_phase': merged.get('water_by_phase', {}),
                'flood_tiles': merged.get('flood_tiles', []),
                'hero_start': merged.get('hero_start', [1, 1]),
                'tile': merged.get('tile', 32),
                'bg': merged.get('bg', '#131311'),
                'hero_color': merged.get('hero_color', '#e8e5df'),
                'speaker_color': merged.get('speaker_color', '#8b939c'),
                'speaker_head': merged.get('speaker_head', '#d8d5df'),
                **town_props,
            },
            '_act_id': first_act_dir.name,
            '_region': region_name,
            'transitions': act.get('transitions', []),
            'regions': regions_geo,
            # the pack's own `player` block, kept for checks (never written back: write_pack names its keys)
            '_player': config.get('player'),
        }
        # The four optional rule-catalog keys, carried through ONLY
        # when the pack declares them: a pack that declares none
        # gets a dict with exactly the keys it had before. Purely
        # additive; nothing else reads them yet. The validator's
        # defaults ({} / []) live beside the validator, not here.
        for key in ('flags', 'claims', 'people', 'rules'):
            if key in config:
                unified[key] = config[key]
        # The optional growth block, carried through ONLY when the
        # pack declares it (design/growth.md).
        if 'growth' in config:
            unified['growth'] = config['growth']
        # The optional spells block (ADR 0018), carried through the same
        # way: the schools the pack teaches and the spells in them.
        if 'spells' in config:
            unified['spells'] = config['spells']
        # The optional recipes block (E2, mending), carried through the
        # same way: two carried things that become one.
        if 'recipes' in config:
            unified['recipes'] = config['recipes']
        # The optional descent block (slice E1), carried through ONLY when
        # the pack declares it: a pack with none loads exactly as before.
        if 'descent' in config:
            unified['descent'] = config['descent']
        # The optional town-states block (ADR 0015, E8c), carried through
        # ONLY when the pack declares it: a pack with none loads exactly
        # as before, and no region of it ever changes.
        if 'town_states' in config:
            unified['town_states'] = config['town_states']
        # The optional saves block, carried through ONLY when the pack
        # declares it (docs/adr/0009-rule-saves.md): a pack with none
        # loads exactly as before.
        if 'saves' in config:
            unified['saves'] = config['saves']
        # The optional skin folder, carried through ONLY when the pack
        # declares it (design/ui-skin.md): a pack with none loads as
        # before, and `world.json` has no `skin` key to bake.
        if 'skin' in config:
            unified['skin'] = config['skin']
        # The pack-level item catalog, carried through ONLY when the
        # pack declares one: an acts-shape pack keeps `items` at the
        # pack level, so the validator's item/light checks can see it.
        # A pack with no `items` loads exactly as before.
        if 'items' in config:
            unified['items'] = config['items']
        # The optional sticker album (design/album.md), carried through
        # ONLY when the pack declares it: a pack with no album loads
        # exactly as before, and the validator sees nothing new.
        if 'album' in config:
            unified['album'] = config['album']
        # The optional sound block (docs/guides/rulesets.md), carried
        # through ONLY when the pack declares it: a pack with no sound
        # loads exactly as before, and the validator sees nothing new.
        if 'sound' in config:
            unified['sound'] = config['sound']
        # The optional time block (the Rest action, the rail lock and the
        # phase save), carried through ONLY when the pack declares it: a
        # pack with no `time` loads exactly as before, its phase lives in
        # memory only as it always has, and the validator sees nothing new.
        if 'time' in config:
            unified['time'] = config['time']
        # The optional music block (vefr #502), carried through ONLY when
        # the pack declares it: a pack with no music loads exactly as
        # before, and the validator sees nothing new.
        if 'music' in config:
            unified['music'] = config['music']
        if 'display' in config:
            unified['display'] = config['display']
        # The optional bag block (bag capacity): carried through ONLY when
        # the pack names one, so a pack with no bag keeps the unbounded bag.
        if 'bag' in config:
            unified['bag'] = config['bag']
        # The pack's own words for the action-critical lines the engine
        # speaks (vefr #259), carried through ONLY when the pack declares
        # them: a pack with none loads exactly as before, and the
        # validator sees nothing new.
        if 'player_words' in config:
            unified['player_words'] = config['player_words']
        # The optional display block (pixel art), carried through ONLY when
        # the pack declares it: a pack with none is drawn exactly as before.
        if 'display' in config:
            unified['display'] = config['display']
        # Every act, in sorted order, each with its own world.json
        # fields plus `region_geo` (that act's own maps + contracts).
        # The validator checks act 2 and later against their own
        # regions; the first act's flat keys above stay exactly as
        # they were. Purely additive.
        acts_out: list[dict] = []
        for act_dir in (d for d in sorted(acts_dir.iterdir())
                        if d.is_dir() and not d.name.startswith('.')):
            act_cfg = json.loads(
                (act_dir / 'world.json').read_text(encoding='utf-8'))
            entry = dict(act_cfg)
            act_regions = list(act_cfg.get('regions', {}) or {})
            # The regions ride in the loader's canonical shape (a dict
            # of name -> {map_text, contract}), which the woven player
            # already reads; `region_geo` below is the validator's
            # flat view of the same ground.
            entry['regions'] = {}
            act_geo: dict[str, dict] = {}
            for rname in act_regions:
                rcontract, rrows = _region_geo(act_dir, rname)
                entry['regions'][rname] = {
                    'map_text': '\n'.join(rrows),
                    'contract': rcontract,
                }
                act_geo[rname] = {
                    'map': rrows,
                    'legend': rcontract.get('legend', {}),
                    'enemies': rcontract.get('enemies', []),
                }
            entry['region_geo'] = act_geo
            acts_out.append(entry)
        unified['acts'] = acts_out
        return unified
    config['_player'] = config.get('player')
    return config


def walkable(w: dict, x: int, y: int, flooded: set | None = None) -> bool:
    m = w['town']['map']
    if y < 0 or y >= len(m) or x < 0 or x >= len(m[0]):
        return False
    if flooded and f'{x},{y}' in flooded:
        return False
    if prop_blocks(w['town'].get('props'), x, y):
        return False
    e = w['town']['legend'].get(m[y][x], {})
    if isinstance(e.get('solid'), bool):
        return e['solid'] is False
    return m[y][x] not in BLOCKED_FALLBACK


PROP_FRAMES_MIN, PROP_FRAMES_MAX = 1, 12
PROP_FPS_MIN, PROP_FPS_MAX = 1, 12
PROP_FPS_DEFAULT = 4


def _whole_pair(v, lo: int = 0) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(_is_whole(n) and n >= lo for n in v)


def prop_blocks(props, x: int, y: int) -> bool:
    """True when a prop's blocking cells cover tile (x, y).

    A prop blocks every cell of its footprint unless `block` names it
    open: a row of '#' is blocked, '.' is open. A malformed entry blocks
    nothing here; the validator names it.
    """
    for p in props or []:
        if not isinstance(p, dict) or not _whole_pair(p.get('at')):
            continue
        ax, ay = p['at']
        size = p.get('size', [1, 1])
        if not _whole_pair(size, 1):
            continue
        if not (ax <= x < ax + size[0] and ay <= y < ay + size[1]):
            continue
        block = p.get('block')
        if not isinstance(block, list):
            return True
        row = block[y - ay] if y - ay < len(block) else ''
        if isinstance(row, str) and row[x - ax:x - ax + 1] == '#':
            return True
    return False


def prop_at(props, x: int, y: int) -> int | None:
    """The index of the first prop whose blocking cells cover (x, y), or None."""
    for i, p in enumerate(props or []):
        if prop_blocks([p], x, y):
            return i
    return None


def region_geometry(w: dict) -> dict:
    """Every region the first act plays in: `{name: {map, legend, enemies}}`.

    The validator's unified shape carries `regions` for an acts-shape
    pack; an act read straight off the loader carries `map_text` and a
    contract instead; and a flat pack has one implicit region, named so
    a door or a scenario written against it can still be checked. One
    reading, shared by the transition checks and `vefr.scenarios`.
    """
    region_geo = w.get('regions')
    if not isinstance(region_geo, dict) and w.get('acts'):
        region_geo = {}
        for rname, rdata in (w['acts'][0].get('regions') or {}).items():
            contract = rdata.get('contract') or {}
            rows = [ln for ln in (rdata.get('map_text') or '').splitlines()
                    if ln.strip()]
            region_geo[rname] = {'map': rows,
                                 'legend': contract.get('legend', {}),
                                 'enemies': contract.get('enemies', []),
                                 'props': contract.get('props', [])}
    if not isinstance(region_geo, dict):
        region_geo = {}
    if not region_geo and isinstance(w.get('town'), dict):
        region_geo = {w.get('_region') or 'town': {
            'map': w['town'].get('map', []),
            'legend': w['town'].get('legend', {}),
            'enemies': w['town'].get('enemies', []),
            'props': w['town'].get('props', []),
        }}
    return region_geo


def _map_tile_walkable(map_rows: list, legend: dict,
                       x: int, y: int) -> bool | None:
    """Walkability of one tile on a named region's map. Mirrors
    `walkable`, but takes the map + legend directly (the validator's
    unified `town` is only the first region). Returns None when the
    tile is off the map, so the caller can tell "outside" from
    "solid"."""
    if not map_rows or y < 0 or y >= len(map_rows) or x < 0 or x >= len(map_rows[0]):
        return None
    e = (legend or {}).get(map_rows[y][x], {})
    if isinstance(e.get('solid'), bool):
        return e['solid'] is False
    return map_rows[y][x] not in BLOCKED_FALLBACK


def reach(w: dict, start: tuple, flooded: set | None = None) -> set:
    seen = {tuple(start)}
    stack = [tuple(start)]
    while stack:
        x, y = stack.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and walkable(w, *n, flooded=flooded):
                seen.add(n)
                stack.append(n)
    return seen


def grammar_errors(grammars) -> list[str]:
    """Every problem with a pack's `grammars` block (empty = good).

    The block is optional and additive: a pack with none passes. A
    pack with one gets it checked here rather than at play time,
    because a grammar that cannot expand is a pack-authoring typo, and
    the author should read about it from `norns validate` and not
    from a silent whisper.

    The three laws (see grammar.py): every grammar is an object of
    rules, every rule is a non-empty list of strings, `origin` is
    required, and every `#rule#` names a rule in the same grammar.
    Messages name the grammar and the rule, so one line says which
    `#thing#` to fix.
    """
    errors: list[str] = []
    if not isinstance(grammars, dict):
        return ["grammars must be an object of named grammars"]
    for gname, rules in grammars.items():
        if not isinstance(rules, dict):
            errors.append(f"grammar '{gname}' must be an object of rules")
            continue
        if 'origin' not in rules:
            errors.append(f"grammar '{gname}' needs an 'origin' rule - "
                          'expansion starts there')
        for rname, entries in rules.items():
            if not isinstance(entries, list) or not entries or not all(
                    isinstance(e, str) for e in entries):
                errors.append(f"grammar '{gname}' rule '{rname}' must be a "
                              'non-empty list of strings')
                continue
            for entry in entries:
                for ref in _GRAMMAR_REF.findall(entry):
                    if ref not in rules:
                        errors.append(
                            f"grammar '{gname}' rule '{rname}' references "
                            f"'{ref}', which is not a rule in that grammar")
    return errors


def item_light_errors(item_id, spec) -> list[str]:
    """Every problem with an item's optional `light` field (empty = good).

    `light` is optional and additive: an item without one passes. An
    item with one must name exactly one usable form - a radius form
    (`radius` and `turns` together, in range) or a reveal form
    (`reveal: true`). A pack author reads a clear, named line from
    `norns validate` instead of meeting a torch that does nothing.
    """
    light = spec.get('light')
    if light is None:
        return []
    label = str(spec.get('name') or item_id)
    where = f"item '{label}'"
    if not isinstance(light, dict) or isinstance(light, bool):
        return [f"{where} light must be an object"]
    errors: list[str] = []
    has_radius, has_turns = 'radius' in light, 'turns' in light
    radius, turns = light.get('radius'), light.get('turns')
    reveal = light.get('reveal')
    if has_radius and (isinstance(radius, bool) or not isinstance(radius, int)
                       or not 1 <= radius <= 20):
        errors.append(f"{where} light radius must be an integer 1..20")
    if has_turns and (isinstance(turns, bool) or not isinstance(turns, int)
                      or not 1 <= turns <= 999):
        errors.append(f"{where} light turns must be an integer 1..999")
    if 'reveal' in light and not isinstance(reveal, bool):
        errors.append(f"{where} light reveal must be true or false")
    radius_form = has_radius and has_turns
    reveal_form = reveal is True
    if not radius_form and not reveal_form:
        errors.append(f"{where} light needs radius and turns, or reveal: true")
    return errors


# Equipment (design/equipment.md, build step 1; #217 track A). The five
# slots and the two stats a worn thing may change are the pack contract,
# so they are written once here and read by both the validator (which
# names a broken shape) and the bake (which carries only a usable one).
SLOTS = ('hand', 'body', 'head', 'feet', 'charm')
MOD_STATS = ('atk', 'hp')
# A worn thing is held on the hero, not in the hand that pours a potion
# or carries a torch: these three may not sit beside a `slot`.
WORN_FORBIDDEN = ('heal', 'light', 'use')


def _mod_value_ok(v) -> bool:
    """True for a usable mods value: a whole number 0 to 9, not a bool."""
    return _is_whole(v) and 0 <= v <= 9


def item_slot_and_mods(spec) -> tuple:
    """The item's usable `(slot, mods)`, read once for the validator and the bake.

    `slot` is None when the item is not wearable (it declared no slot, or
    one the contract does not allow). `mods` is empty unless a valid slot
    carries a fully valid `mods`, so a keepsake stays a keepsake and a
    broken pair is a silent no-op in play - `item_slot_errors` is what
    names it for the author.
    """
    if not isinstance(spec, dict):
        return None, {}
    slot = spec.get('slot')
    if slot not in SLOTS:
        return None, {}
    mods = spec.get('mods')
    if not isinstance(mods, dict) or isinstance(mods, bool):
        return slot, {}
    clean = {k: v for k, v in mods.items()
             if k in MOD_STATS and _mod_value_ok(v)}
    return slot, (clean if len(clean) == len(mods) else {})


def item_slot_errors(item_id, spec, keys: frozenset = frozenset()) -> list[str]:
    """Every problem with an item's optional `slot` and `mods` (empty = good).

    `slot` is one of SLOTS, and `mods` (only with a slot) is an object of
    whole numbers 0 to 9 for atk and hp. Both are additive: an item with
    neither plays exactly as it did. A worn thing may still be worth gold
    or kept, but it is not drunk, lit or spent, so `heal`, `light` and
    `use` may not sit beside a slot; and a thing a locked door names as
    its key is a key, not a keepsake. `keys` is the set of ids a door's
    `requires` names, collected by the caller (`_door_key_items`).
    """
    label = str(spec.get('name') or item_id)
    # Name the words and the id when they differ: an author looking at a
    # catalog needs the id to find the entry they have to fix.
    where = (f"item '{label}'" if label == item_id
             else f"item '{label}' ({item_id})")
    slot, _ = item_slot_and_mods(spec)
    if 'slot' in spec and slot is None:
        return [f"{where} slot must be one of {', '.join(SLOTS)}"]
    if 'mods' in spec:
        mods = spec.get('mods')
        if not isinstance(mods, dict) or isinstance(mods, bool):
            return [f"{where} mods must be an object holding only "
                    f"{' and '.join(MOD_STATS)}"]
        bad = [str(k) if k not in MOD_STATS else f"{k} {v}"
               for k, v in mods.items()
               if k not in MOD_STATS or not _mod_value_ok(v)]
        if bad:
            return [f"{where} mods may only hold {' and '.join(MOD_STATS)}, "
                    f"each a whole number 0 to 9; not allowed: "
                    f"{', '.join(bad)}"]
        if slot is None:
            return [f"{where} mods need a slot: only a worn thing has mods"]
    if slot is not None:
        for field in WORN_FORBIDDEN:
            if field in spec:
                return [f"{where} slot cannot go with {field}: a worn thing "
                        f"is not drunk, lit or spent"]
        if item_id in keys:
            return [f"{where} is a locked door's key, so it cannot wear a slot"]
    return []


# ---- rolled loot (ADR 0017): what a drawn item may be -----------------------
# The bounds here are the draw's, not an author's: a whole weight, a whole
# percentage, at most RARITY_NAMES names and TRAIT_POOL traits, so every
# draw is one floor of a named stream and `int(rng() * total)` stays under
# 2**31 in any pack that passes. Nothing else in the engine scales a
# floating point number out of a pack, and nothing else should.
RARITY_NAMES_MAX = 64
RARITY_WEIGHT_MAX = 9999
TRAIT_POOL_MAX = 16

# What a roll asks for: any of these three keys and the pack has asked for
# a hidden trait, so a `traits` pool that is empty beside them is a refusal
# rather than a roll that can only ever come back bare.
ROLL_ASKS = ('traits', 'chance', 'max')


def item_rarity_of(spec) -> str:
    """The item's own fixed `rarity`, or '' - one plain word, nothing else."""
    if not isinstance(spec, dict):
        return ''
    rarity = spec.get('rarity')
    if isinstance(rarity, str) and shapes.WORD.fullmatch(rarity):
        return rarity
    return ''


def item_traits_of(spec) -> list:
    """The `traits` list of this record - the item's own fixed traits, or a
    roll's pool: plain words, once each, in pack order, at most
    TRAIT_POOL_MAX."""
    if not isinstance(spec, dict):
        return []
    listed = spec.get('traits')
    if not isinstance(listed, list) or isinstance(listed, bool):
        return []
    out: list[str] = []
    for word in listed:
        if not isinstance(word, str) or not shapes.WORD.fullmatch(word):
            continue
        if word not in out:
            out.append(word)
        if len(out) >= TRAIT_POOL_MAX:
            break
    return out


def item_rarity_table(spec) -> list:
    """The `roll.rarity` table of this record: `[(name, weight)]` in pack
    order, at most RARITY_NAMES_MAX, with every name that is not a plain
    word and every weight that is not a whole number 1..RARITY_WEIGHT_MAX
    dropped. A table the pack can draw from is a list; a table it cannot
    is empty, and `item_roll_errors` is what names it."""
    if not isinstance(spec, dict):
        return []
    table = spec.get('rarity')
    if not isinstance(table, dict) or isinstance(table, bool):
        return []
    out: list[tuple] = []
    for name, weight in table.items():
        if not isinstance(name, str) or not shapes.WORD.fullmatch(name):
            continue
        if isinstance(weight, bool) or not isinstance(weight, int):
            continue
        if not 1 <= weight <= RARITY_WEIGHT_MAX:
            continue
        out.append((name, weight))
        if len(out) >= RARITY_NAMES_MAX:
            break
    return out


def item_roll_of(spec) -> dict:
    """The item's drawable `roll`, read once for the validator, the bake
    and the draw - `{}` when the pack names none worth drawing.

    `{'rarity': [(name, weight)], 'traits': [...], 'chance': 0..100,
    'max': 0..4}` with the defaults already resolved: a pack that named a
    pool and no `chance` gets 100, and a pack that named no pool gets no
    traits at all rather than a draw that cannot answer. A roll needs both
    halves - a rarity table and a trait pool - so a roll that declared one
    and not the other draws nothing and is named by `item_roll_errors`.
    """
    if not isinstance(spec, dict):
        return {}
    roll = spec.get('roll')
    if not isinstance(roll, dict) or isinstance(roll, bool):
        return {}
    rarity = item_rarity_table(roll)
    pool = item_traits_of(roll)
    if not rarity or not pool:
        return {}
    chance = roll.get('chance')
    if isinstance(chance, bool) or not isinstance(chance, int) or not 0 <= chance <= 100:
        chance = 100
    top = roll.get('max')
    if isinstance(top, bool) or not isinstance(top, int) or not 0 <= top <= 4:
        top = 1
    return {'rarity': rarity, 'traits': pool, 'chance': chance, 'max': top}


def item_roll_errors(item_id, spec) -> list[str]:
    """Every problem with an item's optional `rarity`, `traits` and `roll`
    (empty = good). ADR 0017.

    Four refusals, each one sentence naming the item and the field:

    - a `rarity` that is not one of the names the item's own `roll`
      declares (an item with no roll may be fixed at any plain word);
    - a trait that is not one plain word;
    - a `roll` that declares no rarity table, or a table with no whole
      weight in it;
    - a `roll` that asks for traits and names no trait pool.

    All four are additive: an item with none of the three keys passes, and
    so does every item written before this slice.
    """
    label = str(spec.get('name') or item_id) if isinstance(spec, dict) else str(item_id)
    where = (f"item '{label}'" if label == item_id
             else f"item '{label}' ({item_id})")
    errors = [f"{where} {p.sentence}"
              for p in shapes.check_item(spec, at=f'items.{item_id}')]
    named = spec.get('roll') if isinstance(spec, dict) else None
    if not isinstance(named, dict) or isinstance(named, bool):
        return errors          # the shape refusal above already spoke
    names = [name for name, _ in item_rarity_table(named)]
    if 'rarity' in named and isinstance(named['rarity'], dict) \
            and not isinstance(named['rarity'], bool):
        # A roll that names no table at all, or names one that is not an
        # object, already has its sentence from the shape table above.
        if not names:
            errors.append(f"{where} roll must declare a rarity table of names "
                          f"and whole weights, such as {{\"common\": 60}}")
        rarity = item_rarity_of(spec)
        if rarity and names and rarity not in names:
            errors.append(f"{where} rarity must be one of the names its roll "
                          f"declares: {_names_sentence(names)}")
    if any(key in named for key in ROLL_ASKS) and not item_traits_of(named):
        errors.append(f"{where} roll asks for traits but names no trait pool")
    return errors


def _names_sentence(names: list) -> str:
    """`a`, `a and b`, `a, b and c` - the pack's own rarity names, listed."""
    if len(names) == 1:
        return names[0]
    return ', '.join(names[:-1]) + ' and ' + names[-1]


# ---- the identify service (ADR 0017, T3 slice 2) --------------------------
# A pack names the place a thing is read at the way it already names a
# shop: a speaker carries `"identify": "true"` (also `yes`, `1`, or the
# boolean true) and is the service of its region. Reading is not a draw
# and not a model call - the rarity and the traits were drawn once, at
# the drop, and this only reads them back - so the declaration can only
# ever be that one word, and the three refusals below are what keeps it
# so. Nothing here is baked: `VEFR_WORLD` already carries the speaker,
# flag and all, so a pack that names no service weaves the bytes it did.
IDENTIFY_TRUE = ('true', 'yes', '1')


def identifies(spec) -> bool:
    """True when this speaker's spec declares the region's identify service.

    The one reader, mirrored by the player's twin in
    `web/player/parts/195-the-identify-service.js`, so a pack that passes
    here is a pack that offers the service in play. A blank string is
    silence, exactly as a blank `shop` is.
    """
    if not isinstance(spec, dict):
        return False
    value = spec.get('identify')
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in IDENTIFY_TRUE


def _pack_region_names(w: dict) -> frozenset:
    """Every region the pack declares, from the acts shape and the flat one
    alike. Empty when the pack declares none - a legacy single-region world
    with no `regions` of its own - so a caller can tell "nowhere" from
    "this pack names no regions"."""
    names: set = set()
    geo = w.get('regions')
    if isinstance(geo, dict):
        names.update(name for name in geo if isinstance(name, str))
    for act in (w.get('acts') or []):
        if isinstance(act, dict) and isinstance(act.get('regions'), dict):
            names.update(name for name in act['regions'] if isinstance(name, str))
    return frozenset(names)


def identify_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional identify service (empty = good).

    ADR 0017, T3 slice 2. Three refusals, each one plain sentence naming
    the speaker and the field, in the voice of `item_roll_errors`:

    - an `identify` that is some other word - it names a service this
      pack does not have;
    - an `identify` that is not the word true at all (an object, a
      number, a list): identifying reads what the drop drew, so anything
      that could carry a chance, a roll or a model is refused rather than
      quietly ignored;
    - a speaker that offers identify in a region the pack does not have,
      which is a service nobody can ever walk up to.

    All three are additive: a pack that names no `identify` passes, and
    so does every pack written before this slice.
    """
    speakers = w.get('speakers')
    if not isinstance(speakers, dict) or not speakers:
        return []
    regions = _pack_region_names(w)
    first = next(iter(sorted(regions)), None)
    errors: list[str] = []
    for key, spec in speakers.items():
        if not isinstance(spec, dict) or 'identify' not in spec:
            continue
        name = spec.get('name') or key
        where = (f"speaker '{name}'" if name == key
                 else f"speaker '{name}' ({key})")
        value = spec.get('identify')
        if not identifies(spec):
            if value is None or value is False or (
                    isinstance(value, str) and not value.strip()):
                # A flag that says no is silence, exactly as a blank
                # `shop` is: there is no service, and nothing to say.
                continue
            if isinstance(value, str):
                errors.append(f"{where} identify names '{value.strip()}', "
                              "which is not a service this pack has: write "
                              "true to make this speaker the one that reads "
                              "things")
            else:
                errors.append(f"{where} identify must be the word true: a "
                              "thing is read once, at the place the pack "
                              "names, so identifying carries no chance, no "
                              "roll and no model")
            continue
        if first is not None:
            served = spec.get('region', first)
            if isinstance(served, str) and served not in regions:
                errors.append(f"{where} offers identify in region '{served}', "
                              "which this pack does not have")
    return errors


def _door_key_items(w: dict) -> frozenset:
    """The item ids a locked door names as its key, from every act.

    A key stays in the bag so it can open its door more than once, so the
    check that a key is not worn has to see locks declared in later acts
    too, not just the first.
    """
    keys: set = set()
    listed = [w.get('transitions')]
    for act in (w.get('acts') or []):
        if isinstance(act, dict):
            listed.append(act.get('transitions'))
    for transitions in listed:
        for t in (transitions or []):
            req = t.get('requires') if isinstance(t, dict) else None
            if isinstance(req, dict) and isinstance(req.get('item'), str):
                keys.add(req['item'])
    return frozenset(keys)


# The speech-box limit the pack contract already uses: a `say` line
# longer than this would be cut off by the woven player's box, so it
# is a pack-authoring error here instead.
RULE_SAY_LIMIT = 280

# A pack may declare this many rules; past it the mistakes in a rule
# stack outweigh any single rule's worth.
RULE_LIMIT = 40

# The event vocabulary is the schema table's, in the pack contract's
# order: what an event is called, and the payload it carries. Both
# names below are read from `shapes.EVENTS` - the one place either is
# typed, which is what `vefr`'s pack contract, the two `when` validators
# and the woven player's JS twin all have to agree on. S3 generates that
# twin from the same table.
RULE_EVENTS = tuple(shapes.EVENTS)

# The payload each event carries, keyed by event name.
RULE_EVENT_KEYS = {name: tuple(key.name for key in fields)
                   for name, fields in shapes.EVENTS.items()}

# The keys a condition may name. The `flag` form is the one condition
# in the contract with two top-level keys: {"flag": ..., "is": ...}.
# `phase` reads the STANDING phase - the one the watch is at while the
# event happens, whatever the event was - so a rule can wait for the
# right hour instead of for the event that turns it (vefr E3).
RULE_CONDITION_KEYS = ('has', 'flag', 'is', 'believes', 'not-believes',
                       'is-in', 'phase', 'not', 'all-of')

# The keys an action may name. `takes` is `give`'s pair: remove one
# copy of an item from what the hero carries (a delivery, a turn-in).
RULE_ACTION_KEYS = ('say', 'show', 'hide', 'reveal', 'give', 'takes',
                    'set', 'unset', 'believes', 'stops-believing', 'tells',
                    'weather', 'point-to', 'complete-act')


def _rule_known_ids(w: dict, pack_dir: Path | None) -> dict:
    """Every id a rule may name, resolved from the loaded pack.

    One identity model: a rule may name only what the pack declares -
    items (world.json), speakers, regions, POI labels (region
    contracts), library book ids (file stems), and region enemy ids.

    Path safety: only files under pack_dir are read, each resolved and
    checked the same way as the pack's own world.json - no id taken
    from pack data ever becomes a filesystem path.
    """
    pack_cfg: dict = {}
    region_contracts: list[dict] = []
    book_ids: set = set()
    act_ids: set = set()
    if pack_dir is not None:
        from .cli import _inside

        base = os.path.realpath(str(pack_dir))

        def _read_in(root: str | None, *parts: str) -> dict:
            # Every probe goes through the house guard first (the same
            # shape region_geo uses): a name that would leave its root
            # resolves to nothing at all.
            found = _inside(root, *parts) if root else None
            if found is None or not os.path.isfile(found):
                return {}
            try:
                loaded = json.loads(Path(found).read_text(encoding='utf-8'))
            except ValueError:
                return {}
            return loaded if isinstance(loaded, dict) else {}

        pack_cfg = _read_in(base, 'world.json')
        # acts-shape regions carry their pois/enemies in contract.json;
        # the flat shape keeps them in world.json's `town` block.
        acts_dir = _inside(base, 'acts')
        if acts_dir and os.path.isdir(acts_dir):
            for act in sorted(os.listdir(acts_dir)):
                if act.startswith('.'):
                    continue
                act_real = _inside(acts_dir, act)
                if act_real is None or not os.path.isdir(act_real):
                    continue
                act_ids.add(act)
                for region in sorted(os.listdir(act_real)):
                    if region.startswith('.'):
                        continue
                    region_real = _inside(act_real, region)
                    if region_real is None or not os.path.isdir(region_real):
                        continue
                    region_contracts.append(_read_in(region_real,
                                                     'contract.json'))
        else:
            town = pack_cfg.get('town')
            if isinstance(town, dict):
                region_contracts.append(town)
        lib_dir = _inside(base, 'library')
        if lib_dir and os.path.isdir(lib_dir):
            for name in sorted(os.listdir(lib_dir)):
                if name.endswith('.md') and not name.startswith('.'):
                    stem = name[:-len('.md')]
                    if stem:
                        book_ids.add(stem)

    items: set = set()
    # An acts-shape pack keeps its items at the pack level and
    # load_pack does not surface them; read them straight from the
    # pack config here rather than changing load_pack's handling.
    for source in (w.get('items'), pack_cfg.get('items')):
        if isinstance(source, dict):
            items |= set(source)
    # A recipe id is nameable the same way (the `mends` event carries
    # one), so it is collected from both shapes the same as items.
    recipes: set = set()
    for source in (w.get('recipes'), pack_cfg.get('recipes')):
        if isinstance(source, list):
            recipes |= {r['id'] for r in source
                        if isinstance(r, dict)
                        and isinstance(r.get('id'), str)}
    people = set(w['speakers']) if isinstance(w.get('speakers'), dict) else set()
    regions = w.get('regions')
    if isinstance(regions, dict):
        places = set(regions)
    elif isinstance(regions, list):
        places = {r for r in regions if isinstance(r, str)}
    else:
        # The flat shape declares no `regions` key; rather than guess
        # at a flat pack's place names, none resolve.
        places = set()
    # POI labels are their own ids (the label is what the runtime
    # sends in `comes-near`/`uses-with` payloads); enemy ids come from
    # the same region contracts as pois.
    pois: set = set()
    enemies: set = set()
    for contract in region_contracts:
        p = contract.get('pois')
        if isinstance(p, dict):
            pois |= {str(v) for v in p.values() if str(v)}
        for e in contract.get('enemies') or []:
            if isinstance(e, dict) and isinstance(e.get('id'), str):
                enemies.add(e['id'])
    flags = w.get('flags') if 'flags' in w else {}
    claims = w.get('claims') if 'claims' in w else {}
    phases = w.get('phases')
    return {
        'items': items,
        'people': people,
        'places': places,
        'pois': pois,
        'books': book_ids,
        'enemies': enemies,
        'acts': act_ids,
        'phases': set(phases) if isinstance(phases, dict) else set(),
        # The verbs a `uses-verb` may name: the acts' own `verbs` lists
        # and every verb an item grants (`pack_verbs`).
        'verbs': pack_verbs(w) | pack_verbs(pack_cfg),
        'recipes': recipes,
        'things': items | people | places | pois | book_ids | enemies,
        # None means "declared but malformed": the shape error in
        # rules_errors already speaks for it, so id checks stay
        # quiet. An absent key defaults to {} and every reference
        # is undeclared.
        'flags': set(flags) if isinstance(flags, dict) else None,
        'claims': set(claims) if isinstance(claims, dict) else None,
    }


def _rule_value_errors(rid: str, where: str, val, kind: str, known: dict) -> list[str]:
    """One id or line value inside a rule, checked against the pack."""
    if kind == 'line':
        if not isinstance(val, str):
            return [f"rule '{rid}' {where} must be words"]
        if len(val) > RULE_SAY_LIMIT:
            return [f"rule '{rid}' {where} is {len(val)} characters - "
                    f"the speech box holds {RULE_SAY_LIMIT}"]
        return []
    if not isinstance(val, str):
        noun = {'person': 'person id', 'claim': 'claim name', 'item': 'item id',
                'place': 'region id', 'thing': 'thing id', 'book': 'book id',
                'enemy': 'enemy id', 'phase': 'phase name', 'verb': 'verb id',
                'recipe': 'recipe id'}[kind]
        return [f"rule '{rid}' {where} must be a {noun}"]
    if kind == 'person':
        if val not in known['people']:
            return [f"rule '{rid}' {where} names person '{val}', "
                    "who is not a speaker in this pack"]
        return []
    if kind == 'claim':
        if known['claims'] is not None and val not in known['claims']:
            return [f"rule '{rid}' {where} names unknown claim '{val}'"]
        return []
    if kind == 'item':
        if val not in known['items']:
            return [f"rule '{rid}' {where} names unknown item '{val}'"]
        return []
    if kind == 'place':
        if val not in known['places']:
            return [f"rule '{rid}' {where} names unknown place '{val}'"]
        return []
    if kind == 'book':
        if val not in known['books']:
            return [f"rule '{rid}' {where} names unknown book '{val}'"]
        return []
    if kind == 'enemy':
        if val not in known['enemies']:
            return [f"rule '{rid}' {where} names unknown enemy '{val}'"]
        return []
    if kind == 'phase':
        if val not in known['phases']:
            return [f"rule '{rid}' {where} names unknown phase '{val}'"]
        return []
    if kind == 'verb':
        if val not in known['verbs']:
            return [f"rule '{rid}' {where} names unknown verb '{val}'"]
    if kind == 'recipe':
        if val not in known['recipes']:
            return [f"rule '{rid}' {where} names unknown recipe '{val}'"]
        return []
    if kind == 'thing' and val not in known['things']:
        return [f"rule '{rid}' {where} names unknown thing '{val}'"]
    return []


def _rule_payload_errors(rid: str, verb: str, val, fields, known: dict) -> list[str]:
    """The object payload of one condition or action.

    `fields` is a tuple of (key, kind) pairs naming every key the
    payload may carry and how each value is checked.
    """
    want = [k for k, _ in fields]
    if not isinstance(val, dict):
        listed = ', '.join(f"'{k}'" for k in want)
        return [f"rule '{rid}' '{verb}' must be an object with {listed}"]
    errors: list[str] = []
    for k in val:
        if k not in want:
            errors.append(f"rule '{rid}' '{verb}' has unknown key '{k}'")
    for k in want:
        if k not in val:
            errors.append(f"rule '{rid}' '{verb}' needs '{k}'")
    for k, kind in fields:
        if k in val:
            errors.extend(_rule_value_errors(rid, f"'{verb}' '{k}'", val[k], kind, known))
    return errors


def _event_where(event: str, fields, key: str) -> str:
    """Where one payload field is, as a sentence names it.

    An event with a single field is named by the event alone; an event
    with two is named by event and field, which is how both the rule
    and the sticker sentences read today.
    """
    return f"when '{event}'" + (f' {key}' if len(fields) > 1 else '')


def _rule_event_errors(rid: str, when, known: dict) -> list[str]:
    """The `when` of one rule: exactly one known event, right payload.

    Which events exist, what each one carries and what kind of pack id
    each field names all come from `shapes.EVENTS`; this function only
    decides whether the pack's own ids answer.
    """
    if not isinstance(when, dict):
        return [f"rule '{rid}' when must be an event object"]
    if len(when) != 1:
        return [f"rule '{rid}' when must name exactly one event"]
    name = next(iter(when))
    if name not in RULE_EVENTS:
        return [f"rule '{rid}' when names unknown event '{name}' - the events are "
                + ', '.join(RULE_EVENTS)]
    payload = when[name]
    if not isinstance(payload, dict):
        return [f"rule '{rid}' when '{name}' carries an object payload"]
    fields = shapes.EVENTS[name]
    want = RULE_EVENT_KEYS[name]
    errors: list[str] = []
    for k in payload:
        if k not in want:
            errors.append(f"rule '{rid}' when '{name}' has unknown key '{k}'")
    for k in want:
        if k not in payload:
            errors.append(f"rule '{rid}' when '{name}' needs key '{k}'")
    if errors:
        return errors
    for field in fields:
        where = _event_where(name, fields, field.name)
        if field.ref is not None:
            errors.extend(_rule_value_errors(rid, where, payload[field.name],
                                             field.ref, known))
            continue
        distance = payload[field.name]
        # A bool is not an int: `true` must not pass as distance 1.
        # 0 is standing on the thing: the player fires tile contact at
        # distance 0, so the vocabulary accepts it.
        if isinstance(distance, bool) or not isinstance(distance, int) \
                or not field.lo <= distance <= field.hi:
            errors.append(f"rule '{rid}' {where} "
                          "must be an integer 0..9 (0 is standing on it)")
    return errors


def _rule_condition_errors(rid: str, cond, known: dict) -> list[str]:
    """One condition of one rule's `if`: ALL of them must pass."""
    if not isinstance(cond, dict):
        return [f"rule '{rid}' condition must be an object naming one check"]
    keys = list(cond)
    if 'flag' in cond or 'is' in cond:
        # The flag form is the one condition with two top-level keys:
        # {"flag": "<flag>", "is": true | false}.
        errors = [f"rule '{rid}' flag condition has unknown key '{k}'"
                  for k in keys if k not in ('flag', 'is')]
        if errors:
            return errors
        if 'flag' not in cond or 'is' not in cond:
            return [f"rule '{rid}' flag condition needs both 'flag' and 'is'"]
        if not isinstance(cond['is'], bool):
            errors.append(f"rule '{rid}' flag condition 'is' must be true or false")
        fname = cond['flag']
        if not isinstance(fname, str):
            errors.append(f"rule '{rid}' flag condition 'flag' must be a flag name")
        elif known['flags'] is not None and fname not in known['flags']:
            errors.append(f"rule '{rid}' reads flag '{fname}', which is not declared in flags")
        return errors
    if len(keys) != 1:
        unknown = [k for k in keys if k not in RULE_CONDITION_KEYS]
        if unknown:
            return [f"rule '{rid}' condition has unknown key '{unknown[0]}'"]
        return [f"rule '{rid}' condition must name exactly one check"]
    key, val = keys[0], cond[keys[0]]
    if key not in RULE_CONDITION_KEYS:
        return [f"rule '{rid}' condition has unknown key '{key}'"]
    if key == 'has':
        return _rule_value_errors(rid, "condition 'has'", val, 'item', known)
    if key in ('believes', 'not-believes'):
        return _rule_payload_errors(rid, key, val,
                                    (('who', 'person'), ('claim', 'claim')), known)
    if key == 'is-in':
        return _rule_payload_errors(rid, 'is-in', val,
                                    (('who', 'person'), ('place', 'place')), known)
    if key == 'phase':
        return _rule_value_errors(rid, "condition 'phase'", val, 'phase', known)
    if key == 'not':
        if not isinstance(val, dict):
            return [f"rule '{rid}' 'not' must wrap a condition"]
        return _rule_condition_errors(rid, val, known)
    # 'all-of': every inner condition must also pass.
    if not isinstance(val, list):
        return [f"rule '{rid}' 'all-of' must be a list of conditions"]
    errors = []
    for sub in val:
        errors.extend(_rule_condition_errors(rid, sub, known))
    return errors


def _rule_action_errors(rid: str, action, known: dict) -> list[str]:
    """One action of one rule's `then`."""
    if not isinstance(action, dict):
        return [f"rule '{rid}' action must be an object naming one thing to do"]
    keys = list(action)
    unknown = [k for k in keys if k not in RULE_ACTION_KEYS]
    if unknown:
        return [f"rule '{rid}' action has unknown key '{unknown[0]}'"]
    if len(keys) != 1:
        return [f"rule '{rid}' action must name exactly one thing to do"]
    key, val = keys[0], action[keys[0]]
    if key == 'say':
        if isinstance(val, str):
            return _rule_value_errors(rid, 'say line', val, 'line', known)
        return _rule_payload_errors(rid, 'say', val,
                                    (('who', 'person'), ('line', 'line')), known)
    if key in ('show', 'hide', 'reveal'):
        return _rule_value_errors(rid, key, val, 'thing', known)
    if key == 'give':
        return _rule_value_errors(rid, 'give', val, 'item', known)
    if key == 'takes':
        return _rule_value_errors(rid, 'takes', val, 'item', known)
    if key in ('set', 'unset'):
        if not isinstance(val, str):
            return [f"rule '{rid}' {key} must name a flag"]
        if known['flags'] is not None and val not in known['flags']:
            return [f"rule '{rid}' {key}s flag '{val}', which is not declared in flags"]
        return []
    if key in ('believes', 'stops-believing'):
        return _rule_payload_errors(rid, key, val,
                                    (('who', 'person'), ('claim', 'claim')), known)
    if key == 'tells':
        return _rule_payload_errors(rid, 'tells', val,
                                    (('who', 'person'), ('claim', 'claim'),
                                     ('to', 'person')), known)
    if key == 'weather':
        if val not in ('fog', 'clear'):
            return [f"rule '{rid}' weather must be 'fog' or 'clear'"]
        return []
    if key == 'complete-act':
        if not isinstance(val, str) or not val:
            return [f"rule '{rid}' complete-act must name an act"]
        if val not in known['acts']:
            return [f"rule '{rid}' completes act '{val}', which the pack does not declare"]
        return []
    return _rule_value_errors(rid, 'point-to', val, 'place', known)


def _rule_conflict_message(aid: str, bid: str, then_a, then_b) -> str | None:
    """What two rules' actions disagree about, or None when they agree.

    Only the two conflicts the design names are decided here: two
    different weather values on one event, and one thing shown by a
    rule that another hides on the same event. Anything subtler is
    left alone rather than guessed at.
    """
    if not isinstance(then_a, list) or not isinstance(then_b, list):
        return None

    def _values(actions, key):
        return [a.get(key) for a in actions
                if isinstance(a, dict) and key in a]

    for wa in _values(then_a, 'weather'):
        for wb in _values(then_b, 'weather'):
            if wa != wb:
                return (f"rules '{aid}' and '{bid}' fire on the same event with "
                        f"conflicting actions - one sets weather '{wa}' while "
                        f"the other sets '{wb}'")
    for shown in _values(then_a, 'show'):
        if shown in _values(then_b, 'hide'):
            return (f"rules '{aid}' and '{bid}' fire on the same event with "
                    f"conflicting actions - one shows '{shown}' while the other "
                    "hides it")
    for shown in _values(then_b, 'show'):
        if shown in _values(then_a, 'hide'):
            return (f"rules '{aid}' and '{bid}' fire on the same event with "
                    f"conflicting actions - one shows '{shown}' while the other "
                    "hides it")
    return None


GROWTH_MODES = ('levels', 'practice')
GROWTH_STATS = ('hp', 'atk')
GROWTH_BY = ('strikes', 'hits-taken', 'consoles', 'hurls')


def _is_whole(v) -> bool:
    """True for a whole number (not a bool, which `int` also admits)."""
    return isinstance(v, int) and not isinstance(v, bool)


def _levels_growth_errors(levels: dict) -> list[str]:
    """Every problem with a `levels` growth block (empty = good)."""
    errors: list[str] = []
    xp = levels.get('xp')
    if not isinstance(xp, list) or not xp:
        errors.append("levels 'xp' must be a list of rising whole numbers "
                      'starting at 0')
    else:
        if len(xp) > 20:
            errors.append("levels 'xp' has more than 20 entries")
        if not all(_is_whole(v) for v in xp):
            errors.append("levels 'xp' must be whole numbers")
        elif xp[0] != 0:
            errors.append("levels 'xp' must start at 0")
        elif any(b <= a for a, b in zip(xp, xp[1:])):
            errors.append("levels 'xp' must strictly rise")
    gain = levels.get('gain')
    if gain is not None:
        if not isinstance(gain, dict):
            errors.append("levels 'gain' must be an object of 'hp' and 'atk'")
        else:
            for stat, v in gain.items():
                if stat not in GROWTH_STATS:
                    errors.append(
                        f"levels 'gain' names unknown stat '{stat}'")
                elif not _is_whole(v) or not 0 <= v <= 9:
                    errors.append(
                        f"levels 'gain.{stat}' must be a whole number 0 to 9")
    return errors


def _practice_growth_errors(practice: dict) -> list[str]:
    """Every problem with a `practice` growth block (empty = good)."""
    errors: list[str] = []
    for stat, spec in practice.items():
        if stat not in GROWTH_STATS:
            errors.append(f"practice names unknown stat '{stat}'")
            continue
        if not isinstance(spec, dict):
            errors.append(f"practice '{stat}' must be an object")
            continue
        by = spec.get('by')
        if by not in GROWTH_BY:
            errors.append(f"practice '{stat}' 'by' must be one of "
                          'strikes, hits-taken, consoles, hurls')
        every = spec.get('every')
        if not _is_whole(every) or not 1 <= every <= 99:
            errors.append(
                f"practice '{stat}' 'every' must be a whole number 1 to 99")
        gain = spec.get('gain')
        if not _is_whole(gain) or not 0 <= gain <= 9:
            errors.append(
                f"practice '{stat}' 'gain' must be a whole number 0 to 9")
        cap = spec.get('cap')
        if not _is_whole(cap) or cap < 1:
            errors.append(
                f"practice '{stat}' 'cap' must be a whole number of at least 1")
    return errors


def growth_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `growth` block (empty = good).

    Growth is optional and additive: a pack that declares none gets
    no output at all, exactly as before. A pack that declares one
    picks `levels` or `practice` and carries only that block; every
    other shape is a plain-sentence error naming the field.
    """
    if 'growth' not in w:
        return []
    growth = w.get('growth')
    if not isinstance(growth, dict):
        return ["growth must be an object with a 'mode'"]
    errors: list[str] = []
    mode = growth.get('mode')
    if mode not in GROWTH_MODES:
        errors.append("growth 'mode' must be 'levels' or 'practice'")
        return errors
    block = growth.get(mode)
    if not isinstance(block, dict):
        errors.append(f"growth mode '{mode}' needs a '{mode}' block")
        return errors
    other = 'practice' if mode == 'levels' else 'levels'
    if other in growth:
        errors.append("growth cannot carry both 'levels' and 'practice' "
                      '- choose one mode')
    if mode == 'levels':
        errors.extend(_levels_growth_errors(block))
    else:
        errors.extend(_practice_growth_errors(block))
    return errors


def spells_of(w: dict) -> list:
    """The pack's own spell records, in the order it wrote them.

    Only the records that can be read at all - an object with an `id` -
    are returned, so every caller downstream (the bake, the check, the
    fixture tests) sees the same list and a pack that wrote one broken
    record is still swept rather than skipped.
    """
    block = w.get('spells') if isinstance(w, dict) else None
    if not isinstance(block, dict):
        return []
    listed = block.get('spells')
    if not isinstance(listed, list):
        return []
    return [r for r in listed
            if isinstance(r, dict) and isinstance(r.get('id'), str) and r['id']]


def spell_ids_of(w: dict) -> set:
    """Every spell id the pack declares, for the checks that ask whether a
    name is one of them. An item naming a spell reads this."""
    return {r['id'] for r in spells_of(w)}


def spell_schools_of(w: dict) -> list:
    """The pack's own school names, in pack order, once each: the plain
    words `spells.schools` declared, and nothing else. A school the pack
    did not name is not a school, which is what `spells_errors` says."""
    block = w.get('spells') if isinstance(w, dict) else None
    named = block.get('schools') if isinstance(block, dict) else None
    if not isinstance(named, list):
        return []
    out: list[str] = []
    for word in named:
        if isinstance(word, str) and shapes.WORD.fullmatch(word) and word not in out:
            out.append(word)
    return out


def growth_level_cap(w: dict) -> int:
    """The highest level the pack's own growth table can reach, or 0.

    The `xp` table is a list of steps and the growth engine's level is the
    count of the steps the hero's experience has passed, clamped to the
    table's own length - so the length is the cap. This is the number the
    endless-mode rule holds still and this slice does not move: a spell
    can be written above it, and then nothing teaches it by level.
    """
    growth = w.get('growth') if isinstance(w, dict) else None
    if not isinstance(growth, dict) or growth.get('mode') != 'levels':
        return 0
    levels = growth.get('levels')
    table = levels.get('xp') if isinstance(levels, dict) else None
    return len(table) if isinstance(table, list) else 0


def spells_learnable_at(w: dict, level) -> list:
    """The spells the hero has learned by the time it is level `level`.

    The pack-side reading of the rule `web/player/parts/225-spells.js`
    runs in play, over the same two things it reads there - a spell's own
    `level` and the level the growth block's table allows - so the two
    cannot disagree about the cap. In play the number comes from
    `growthStats().level`, which the growth engine has already clamped;
    here it is clamped the same way first, which is what makes this the
    statement that learning by level never reaches past the cap.

    An empty list for a pack that declares no growth table, no levels
    mode, or no spells: there is no level to learn at, so nothing is
    learned by level and every spell waits for a book.
    """
    cap = growth_level_cap(w)
    if cap < 1 or not isinstance(level, int) or isinstance(level, bool):
        return []
    here = min(level, cap)
    return [r for r in spells_of(w)
            if isinstance(r.get('level'), int) and not isinstance(r.get('level'), bool)
            and 1 <= r['level'] <= here]


def spells_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `spells` block (empty = good).

    Spells are optional and additive: a pack that declares none gets no
    output at all, exactly as before. `shapes` speaks for the block, its
    schools and every spell record in it - a spell with no school at all,
    a `level` under 1, a `heal` that is not a whole number.

    The one question a record cannot answer for itself is the school it
    belongs to: a school is a name the pack chose, and there is no
    closed vocabulary for this table to hold a spell to, so a school the
    block did not declare is named here instead. The other cross-record
    question - an item that grants a spell the pack does not have - is
    `item_spell_errors`, because it is the item's own key that is wrong.
    """
    if 'spells' not in w:
        return []
    records = (w['spells'].get('spells')
               if isinstance(w['spells'], dict) else None)
    errors = [_no_school_sentence(p, records) or p.sentence
              for p in shapes.check(shapes.BLOCKS['spells'], w['spells'],
                                    at='spells')]
    schools = spell_schools_of(w)
    for record in spells_of(w):
        school = record.get('school')
        # A record the shape table has already refused - no school, or a
        # school that is not one plain word - is left to it, so one
        # broken record says one thing.
        if not isinstance(school, str) or not shapes.WORD.fullmatch(school):
            continue
        if school in schools:
            continue
        errors.append(
            f"spell '{record['id']}' must name a school the pack declares, "
            f"and {school!r} is not one"
            + (f"; the pack declares {_names_sentence(schools)}"
               if schools else "; the pack declares no schools at all"))
    return errors


_NO_SCHOOL = re.compile(r'/spells/spells/(\d+)/school')


def _no_school_sentence(problem, records) -> str:
    """The no-school refusal, naming the spell and the file it is in.

    The shape table's own missing-key sentence says `spell must hold a
    school` and names neither which spell nor where it is written, which
    is no help in a pack with twenty of them. The pointer knows which
    record it is, so the sentence is said again with the record's `id`
    (or its place in the list, when it has no `id` either) and the file.
    Every other problem is left as the table said it ('' here).
    """
    if problem.code != 'missing-key':
        return ''
    found = _NO_SCHOOL.fullmatch(problem.pointer)
    if not found or not isinstance(records, list):
        return ''
    index = int(found.group(1))
    record = records[index] if index < len(records) else None
    rid = record.get('id') if isinstance(record, dict) else None
    label = (f"'{rid}'" if isinstance(rid, str) and rid
             else f'spells.spells[{index}]')
    return (f'world.json: spell {label} must hold a school, such as '
            f'{shapes.SPELL.example}')


def item_spell_errors(item_id, spec, spell_ids) -> list[str]:
    """Every problem with an item's optional `spell` key (empty = good).

    ADR 0018. One refusal, one plain sentence naming the item and the
    field: an item that teaches a spell the pack does not declare. A
    spellbook found as loot is an ordinary item, so this is checked
    beside `item_roll_errors` and speaks in the same voice; `spell_ids`
    is the pack's own `spells` block read through `spell_ids_of`, which
    is the only way this function can answer whether the id exists.

    An item with no `spell` passes, and so does every item written before
    this slice.
    """
    taught = spec.get('spell') if isinstance(spec, dict) else None
    if not isinstance(taught, str) or not taught:
        return []          # the shape table already spoke about the type
    if taught in (spell_ids or ()):
        return []
    label = str(spec.get('name') or item_id)
    where = (f"item '{label}'" if label == item_id
             else f"item '{label}' ({item_id})")
    return [f"{where} must teach a spell the pack declares, and {taught!r} "
            f"is not one of its spells"]


# ---- the verbs a carried thing grants (the item-grants slice) -------------

# What carrying a thing may change about a verb: today the one effect is
# extra attack - the extra damage that verb's blow carries. The bounds are a
# worn item's `mods` bounds on purpose, so a pack learns one table and a
# number that would be refused there is refused here too.
VERB_EFFECTS = ('atk',)
VERB_EFFECT_MAX = 9


def _grant_where(item_id, spec) -> str:
    """The item named the way every item sentence names it."""
    label = str(spec.get('name') or item_id)
    return (f"item '{label}'" if label == item_id
            else f"item '{label}' ({item_id})")


def _whole_in(v, lo: int, hi: int) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi


def item_grants_of(spec) -> list[dict]:
    """The verbs this item grants, in the form the bake and the player read.

    `[{verb, label}]` in the pack's own order - which is the order the verb
    row shows them in - with one entry per grant that names a plain-word
    verb and non-empty words for the button. A grant the shape table already
    refused (no verb, no label, a label that is not words) is dropped here
    rather than baked as a button with nothing on it.
    """
    if not isinstance(spec, dict):
        return []
    listed = spec.get('grants')
    if not isinstance(listed, list):
        return []
    out: list[dict] = []
    seen: set = set()
    for grant in listed:
        if not isinstance(grant, dict):
            continue
        verb, label = grant.get('verb'), grant.get('label')
        if not isinstance(verb, str) or not shapes.WORD.fullmatch(verb.strip()):
            continue
        if not isinstance(label, str) or not label.strip():
            continue
        verb = verb.strip()
        if verb in seen:
            continue
        seen.add(verb)
        out.append({'verb': verb, 'label': label.strip()})
    return out


def item_changes_of(spec) -> dict:
    """What carrying this thing does to the verbs it names.

    `{verb: {effect: n}}`, with only the effects and numbers the table
    allows, in the pack's own order. An entry that names a verb no effect
    rides along for is left out rather than baked as a no-op.
    """
    if not isinstance(spec, dict):
        return {}
    listed = spec.get('changes')
    if not isinstance(listed, dict) or isinstance(listed, bool):
        return {}
    out: dict[str, dict] = {}
    for verb, effects in listed.items():
        if not isinstance(verb, str) or not verb.strip():
            continue
        if not isinstance(effects, dict) or isinstance(effects, bool):
            continue
        clean = {k: v for k, v in effects.items()
                 if k in VERB_EFFECTS and _whole_in(v, 0, VERB_EFFECT_MAX)}
        if clean:
            out[verb.strip()] = clean
    return out


def pack_verbs(w: dict) -> set:
    """Every verb id this pack can fire: its acts' own `verbs` lists, and
    every verb an item grants.

    This is what a `uses-verb` rule - or a sticker's `when` - is checked
    against, so a rule may name a verb of the act's own vocabulary or one
    an item hands the hero, and nothing else. Both are read from the pack
    itself: an act's `verbs` is the row the player pressed before this
    slice, and a granted verb is the row this slice added.
    """
    if not isinstance(w, dict):
        return set()
    out: set = set()
    acts = w.get('acts')
    for act in acts if isinstance(acts, list) else []:
        listed = act.get('verbs') if isinstance(act, dict) else None
        if isinstance(listed, list):
            out |= {v.strip() for v in listed
                    if isinstance(v, str) and v.strip()}
    items = w.get('items')
    for spec in items.values() if isinstance(items, dict) else []:
        for grant in item_grants_of(spec):
            out.add(grant['verb'])
    return out


def item_grants_errors(item_id, spec, verb_ids) -> list[str]:
    """Every problem with an item's optional `grants` and `changes` (empty = good).

    Both are additive: an item with neither plays exactly as it did, and
    the shape table has already spoken about anything of the wrong type -
    what is left here are the questions `shapes.check_item` cannot answer
    for itself, in the same voice as `item_spell_errors`.

    Three of them: an item that grants one verb twice (the row would show
    two buttons with the same word, and only one could ever be pressed),
    a `changes` entry naming a verb this pack has not got, and an effect
    that is not one this slice plays. `verb_ids` is the pack's own verb
    set, from `pack_verbs` - the only way this function can answer
    whether the verb exists.
    """
    if not isinstance(spec, dict):
        return []
    where = _grant_where(item_id, spec)
    errors: list[str] = []
    granted = item_grants_of(spec)
    named = [g['verb'] for g in granted]
    listed = spec.get('grants')
    if isinstance(listed, list):
        # A verb granted twice is refused by the reader above (the second
        # is dropped), so the count is read off what the pack wrote.
        counted: dict = {}
        for grant in listed:
            if isinstance(grant, dict) and isinstance(grant.get('verb'), str):
                verb = grant['verb'].strip()
                counted[verb] = counted.get(verb, 0) + 1
        for verb in named:
            if counted.get(verb, 0) > 1:
                errors.append(
                    f"{where} grants the verb '{verb}' more than once: the "
                    "verb row would show two buttons with the same word")
    changes = spec.get('changes')
    if isinstance(changes, dict) and not isinstance(changes, bool):
        known = set(verb_ids or ())
        for verb, effects in changes.items():
            if not isinstance(verb, str) or not verb.strip():
                continue        # the shape table spoke about the key
            name = verb.strip()
            if name not in known:
                errors.append(
                    f"{where} changes the verb '{name}', which is not a verb "
                    "this pack uses: a verb is one of the act's own, or one "
                    "this item grants")
                continue
            if not isinstance(effects, dict) or isinstance(effects, bool):
                errors.append(
                    f"{where} change for the verb '{name}' must be an object "
                    f"holding {' and '.join(VERB_EFFECTS)}")
                continue
            for key, value in effects.items():
                if key not in VERB_EFFECTS:
                    errors.append(
                        f"{where} change for the verb '{name}' may only hold "
                        f"{' and '.join(VERB_EFFECTS)}, not '{key}'")
                elif not _whole_in(value, 0, VERB_EFFECT_MAX):
                    errors.append(
                        f"{where} change {key} for the verb '{name}' must be a "
                        f"whole number 0 to {VERB_EFFECT_MAX}")
    return errors


def saves_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `saves` block (empty = good).

    Rule saves are optional and additive: a pack that declares none
    gets no output at all, exactly as before. A pack that declares one
    chooses `rules` (`persist` or `reset`) and, in persist mode, a
    `legacy` handling (`fresh` or `from-log`); every other shape is a
    plain-sentence error naming the field. See
    `docs/adr/0009-rule-saves.md`.
    """
    if 'saves' not in w:
        return []
    return [p.sentence for p in shapes.check(shapes.BLOCKS['saves'], w['saves'])]


def sound_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `sound` block (empty = good).

    Sound is optional and additive: a pack that declares none gets no
    output at all, exactly as before. A pack that declares one holds
    exactly one key, `theme`, whose value is this slice's only theme;
    every other shape is one plain sentence naming sound. See
    `docs/guides/rulesets.md`.
    """
    if 'sound' not in w:
        return []
    return [p.sentence for p in shapes.check(shapes.BLOCKS['sound'], w['sound'])]


def time_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `time` block (empty = good).

    Time that costs something: `rest` gives the pack a Rest action that
    turns the watch on by one phase per press, `rail: "locked"` takes
    away the free jump in the phase rail so time moves only by resting
    and by rules, and `persist` keeps the standing phase across a reload
    under the save key `vefr-time-<world>`. Every other shape is one
    plain sentence naming time. All three are optional and additive: a
    pack that declares no `time` gets no output here at all and plays and
    saves exactly as before. See `docs/guides/rules.md`.
    """
    if 'time' not in w:
        return []
    return [p.sentence for p in shapes.check(shapes.BLOCKS['time'], w['time'])]


def music_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `music` block (empty = good).

    Music is optional and additive, like sound: a pack that declares
    none gets no output at all, exactly as before, and its audio
    behaves byte for byte as it did. A pack that declares one holds
    exactly one key, `track`, naming one of the engine's synthesized
    ambient beds (`shore` is the only bed in this first slice, vefr
    #502); every other shape is one plain sentence naming music. See
    `docs/guides/rulesets.md`.
    """
    if 'music' not in w:
        return []
    return [p.sentence for p in shapes.check(shapes.BLOCKS['music'], w['music'])]


def bag_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `bag` block (empty = good).

    A pack that names no `bag` keeps the unbounded bag and gets nothing
    here. A pack that names one holds exactly `size`, a whole number of
    places from 1 to 99. See `shapes.BAG` and `docs/guides/rulesets.md`.
    """
    if 'bag' not in w:
        return []
    return _shape_sentences('world.json', shapes.check(shapes.BLOCKS['bag'], w['bag']))


def element_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional resistances (empty = good).

    The pack opts in by naming them: `player.resist` is an object of
    damage type to a whole-number divisor (1 to 9, where 2 is "half"),
    and `player.immune` is a list of damage types nothing can hurt
    the hero with. Both live on the pack's `player` block, which is
    the floor for a whole run (Rylee, 2026-10-03; the gear half that
    sits on top of it is a later slice).

    A pack that declares neither is not this function's business: it
    bakes no resistance, deals untyped damage and plays byte for byte
    as it always did. Every sentence here is one plain refusal naming
    the field and, where a closed set is the reason, the words in it.
    See `docs/guides/elements.md`.
    """
    from . import elements

    # The block `load_pack` already holds: the pack's own `player`, under
    # the name the merged shape keeps it under (`_player`).
    player = w.get('_player') or w.get('player')
    if not isinstance(player, dict):
        return []
    errors: list[str] = []
    choices = ', '.join(elements.DAMAGE_TYPES)
    resist = player.get('resist')
    if resist is not None:
        if not isinstance(resist, dict) or isinstance(resist, bool):
            errors.append(
                "world.json: player.resist must be an object of damage "
                "types to a whole number, such as {\"fire\": 2}")
        else:
            for key, value in resist.items():
                name = elements.normal_type(key)
                if name is None:
                    errors.append(
                        f"world.json: player.resist names {key!r}, which is "
                        f"not a damage type; use one of {choices}")
                    continue
                if not _is_whole(value) or value < 1 or value > elements.MAX_RESIST:
                    errors.append(
                        f"world.json: player.resist '{name}' must be a whole "
                        f"number from 1 to {elements.MAX_RESIST}, where 2 "
                        f"means half the damage")
    immune = player.get('immune')
    if immune is not None:
        if not isinstance(immune, list):
            errors.append(
                "world.json: player.immune must be a list of damage types, "
                "such as [\"cold\"]")
        else:
            for value in immune:
                if elements.normal_type(value) is None:
                    errors.append(
                        f"world.json: player.immune names {value!r}, which is "
                        f"not a damage type; use one of {choices}")
    return errors


def enemy_element_errors(where: str, e: dict) -> list[str]:
    """Every problem with one hazard's `dmg_type` and `burns` (empty = good).

    `where` is the sentence's own prefix - the enemy named by its
    display name, the region it stands in and the act, exactly as
    `_region_enemy_errors` has already built it.

    `dmg_type` is the damage type of the blow that hazard deals, and
    `burns` leaves the hero burning: a `turns` count and a `tick`, the
    two properties the design note says every status effect needs and
    the whole of its data shape. A hazard that names neither deals the
    untyped blow it always dealt, which no resistance can touch.
    """
    from . import elements

    errors: list[str] = []
    choices = ', '.join(elements.DAMAGE_TYPES)
    dtype = e.get('dmg_type')
    if dtype is not None and elements.normal_type(dtype) is None:
        errors.append(
            f"{where} carries dmg_type {dtype!r}, which is not a damage "
            f"type; use one of {choices}")
    burns = e.get('burns')
    if burns is not None:
        if not isinstance(burns, dict) or isinstance(burns, bool):
            errors.append(
                f"{where} burns must be an object holding a turns count and "
                f"a tick, such as {{\"turns\": 3, \"tick\": 1}}")
        else:
            for field in ('turns', 'tick'):
                value = burns.get(field)
                if not _is_whole(value) or value < 1:
                    errors.append(
                        f"{where} burns needs a whole {field} of 1 or more, "
                        f"such as {{\"turns\": 3, \"tick\": 1}}")
            extra = [k for k in burns if k not in ('turns', 'tick')]
            if extra:
                errors.append(
                    f"{where} burns may only hold turns and tick; not "
                    f"allowed: {', '.join(sorted(extra))}")
    return errors


def recipes_of(w: dict) -> list:
    """The pack's recipes: the record list as written, in order."""
    listed = w.get('recipes') if isinstance(w, dict) else None
    return listed if isinstance(listed, list) else []


STAKE_KEYS = ('id', 'when', 'risk', 'reward', 'say')


def stakes_errors(w: dict, pack_dir: Path | None = None) -> list[str]:
    """Every problem with a pack's optional `stakes` block (empty = good), vefr#504.

    The player bakes only the stakes it can offer and drops the rest
    (cli._stake_bakes); this is where the author is TOLD, one plain sentence
    per problem naming the stake: the five keys and no others, a `when` in
    the one shape a rule's `when` has, and an id no other stake took. A pack
    that declares no stakes gets no output at all.
    """
    if 'stakes' not in w:
        return []
    listed = w['stakes']
    # The example `when` is built from the event table, never typed here (tests/test_event_table.py).
    ev = RULE_EVENTS[1]
    when_ex = '{"%s": {%s}}' % (ev, ', '.join('"%s": "..."' % k for k in RULE_EVENT_KEYS[ev]))
    example = ('{"id": "the-wager", "when": %s, "risk": "your lantern", '
               '"reward": "the ferryman\'s map", "say": "..."}' % when_ex)
    if not isinstance(listed, list):
        return [f'stakes must be a list, such as [{example}]']
    errors: list[str] = []
    seen: set = set()
    items = _rule_known_ids(w, pack_dir)['items']
    for index, stake in enumerate(listed):
        if not isinstance(stake, dict):
            errors.append(f'the stake at position {index} must be an object, such as {example}')
            continue
        sid = stake.get('id')
        label = f"stake '{sid}'" if isinstance(sid, str) and sid.strip() else f'stakes[{index}]'
        if not (isinstance(sid, str) and sid.strip()):
            errors.append(f'{label} needs an id')
        elif sid in seen:
            errors.append(f"two stakes share the id '{sid}'")
        else:
            seen.add(sid)
        extra = sorted(k for k in stake if k not in STAKE_KEYS)
        if extra:
            errors.append(f"{label} may only hold {', '.join(STAKE_KEYS)}; not allowed: {', '.join(extra)}")
        # Exactly as strict as the bake (cli._stake_bakes): a non-empty string, not trimmed, so a
        # stake that validates is a stake the player will be offered (#535 review).
        for key in ('risk', 'reward', 'say'):
            if not (isinstance(stake.get(key), str) and stake[key]):
                errors.append(f'{label} needs a {key} line the player can read')
        # risk and reward are things the pack declares: a typo would put the risk down for nothing.
        for key in ('risk', 'reward'):
            val = stake.get(key)
            if isinstance(val, str) and val and val not in items:
                errors.append(f"{label} {key} names unknown item '{val}'")
        when = stake.get('when')
        ok = isinstance(when, dict) and len(when) == 1
        if ok:
            event, payload = next(iter(when.items()))
            ok = (event in RULE_EVENTS and isinstance(payload, dict)
                  and set(payload) == set(RULE_EVENT_KEYS[event]))
            # The same value rules as cli._when_bakes: `distance` a whole number 0..9, every other
            # payload value a non-empty string.
            if ok:
                for k, v in payload.items():
                    if k == 'distance':
                        ok = ok and not isinstance(v, bool) and isinstance(v, int) and 0 <= v <= 9
                    else:
                        ok = ok and isinstance(v, str) and bool(v)
        if not ok:
            errors.append(f"{label} when must be one event in a rule's own shape, such as {when_ex}")
    return errors


def recipes_errors(w: dict, pack_dir: Path | None = None) -> list[str]:
    """Every problem with a pack's optional `recipes` block (empty = good).

    Mending is optional and additive: a pack that declares no recipes
    gets no output at all, exactly as before. `shapes` speaks for each
    record's own keys - an `id`, `inputs` as a list of item ids, an
    `output` and the `say` line - and the cross-record questions are
    asked here, one plain sentence per problem naming the recipe: an
    input or an output the pack's `items` does not declare, `inputs`
    that is not exactly two things, and an id a second recipe already
    took. The item ids come from `_rule_known_ids`, so both pack shapes
    answer the same way.

    Nothing here says what the player does with a recipe - that is the
    woven player's mending part - and no pack without recipes reaches
    any of it.
    """
    if 'recipes' not in w:
        return []
    listed = w['recipes']
    if not isinstance(listed, list):
        return [f'recipes must be a list, such as [{shapes.RECIPE.example}]']
    errors: list[str] = []
    items = _rule_known_ids(w, pack_dir)['items']
    seen: set = set()
    for index, record in enumerate(listed):
        if not isinstance(record, dict):
            errors.append(f'the recipe at position {index} must be an object, '
                          f'such as {shapes.RECIPE.example}')
            continue
        rid = record.get('id')
        label = (f"recipe '{rid}'" if isinstance(rid, str) and rid
                 else f'recipes[{index}]')
        for p in shapes.check(shapes.BLOCKS['recipe'], record,
                              at=f'recipes[{index}]'):
            # The table's own sentences name the block ('recipe must
            # hold its output'); the ones that do are said again with
            # the recipe's own id in front, so a pack with twenty
            # recipes is told which one is wrong. The path-bearing
            # sentences already carry the record's place, and keep the
            # label beside them the way the item errors do.
            sentence = p.sentence
            if sentence.startswith('recipe ') and isinstance(rid, str) and rid:
                sentence = f"recipe '{rid}'" + sentence[len('recipe'):]
                errors.append(sentence)
            else:
                errors.append(f'{label} {sentence}')
        if isinstance(rid, str) and rid:
            if rid in seen:
                errors.append(f"two recipes share the id '{rid}' "
                              '- recipe ids must be unique')
            seen.add(rid)
        inputs = record.get('inputs')
        if isinstance(inputs, list):
            if len(inputs) != 2:
                errors.append(f'{label} inputs must name exactly two '
                              'things to mend')
            for one in inputs:
                if isinstance(one, str) and one and one not in items:
                    errors.append(f"{label} inputs names unknown item '{one}'")
        output = record.get('output')
        if isinstance(output, str) and output and output not in items:
            errors.append(f"{label} output names unknown item '{output}'")
    return errors


def player_words_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `player_words` block.

    The player's own words for the action-critical lines the engine
    speaks (vefr #259: a hint that reads "To reach floor-1, go
    north-west" names a region id where the pack's name for the place
    belongs). A pack may name its own word for any of them and may
    name none: a pack that declares no `player_words` gets nothing here
    at all and plays the engine's own wording byte for byte, which is
    why this says nothing whatever about silence.

    What is refused is a word that is not one: a value that is not a
    string, one that says nothing (empty or only spaces), one that names
    no `{place}` slot for the engine to fill, and one naming a key the
    message table does not have. Each is one plain sentence, with the
    file and the key in front of it. See `docs/guides/rulesets.md`.
    """
    if 'player_words' not in w:
        return []
    return _shape_sentences(
        'world.json', shapes.check(shapes.BLOCKS['player_words'],
                                   w['player_words']))


def display_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `display` block (empty = good).

    `phone_tile` is the drawn tile, in CSS pixels, of a touch phone whose
    map is too big to fit: a whole number from 32 to 72. `pixel_art` names
    the art's native tile size, a whole number from 8 to
    64: the engine then draws every picture at a whole-number scale of it,
    with no smoothing (docs/guides/world-creation.md, "Pixel art").
    `ending_tile` is the tile the ending room is drawn at while the end
    card is up (`complete-act`, cottage-of-the-breeze#166): a whole
    multiple of `pixel_art.native_tile`, checked here because it reads
    one key against another, which the table cannot. A pack
    that declares no `display` gets no output at all.
    """
    if 'display' not in w:
        return []
    problems = shapes.check(shapes.BLOCKS['display'], w['display'])
    return (_shape_sentences('world.json', problems)
            + _ending_tile_sentences(w['display'], problems))


def _ending_tile_sentences(display, problems=()) -> list[str]:
    """The one `display` check that spans keys: `ending_tile` steps in whole
    multiples of the art's own native tile, so the ending room scales in
    whole-number pixel steps with crisp art (cottage-of-the-breeze#166).

    Spoken here and not in `shapes`, because the table bounds one value at
    a time and this reads `ending_tile` against `pixel_art.native_tile`
    beside it. A pack that names no `ending_tile` is never asked about,
    and a value the table already refused (a wrong type, a number out of
    range) is left to that sentence rather than answered twice; a
    `native_tile` the table already refused is not stepped against.
    """
    if not isinstance(display, dict) or 'ending_tile' not in display:
        return []
    refused = {p.pointer for p in problems}
    if '/display/ending_tile' in refused:
        return []          # the table's own sentence about the value spoke
    art = display.get('pixel_art')
    native = art.get('native_tile') if isinstance(art, dict) else None
    if '/display/pixel_art/native_tile' in refused:
        return []          # the table's own sentence about the art spoke
    if not isinstance(native, int) or isinstance(native, bool):
        return ['world.json: /display/ending_tile display.ending_tile must be'
                ' a whole multiple of display.pixel_art.native_tile, and'
                ' this display declares no pixel_art']
    if display['ending_tile'] % native:
        return ['world.json: /display/ending_tile display.ending_tile must be'
                ' a whole multiple of display.pixel_art.native_tile, such'
                f' as {2 * native} for a native_tile of {native}']
    return []


def descent_errors(w: dict, pack_dir=None) -> list[str]:
    """Every problem with a pack's optional `descent` block (empty = good).

    Slice E1: a descent is the run seed, the tile it starts from, and the
    Sections it walks. A Section may be written out in the block or named
    by id and kept in `sections/<id>.json`; the named ones are resolved
    here, so the check sees the same records the bake will. `shapes`
    speaks for the block, its entry tile and each Section in it, and the
    entry tile is also compared against every act's doors (vefr#352). A
    pack that declares no descent gets no output at all, exactly as
    before.
    """
    if 'descent' not in w:
        return []
    from . import delve as delve_mod

    problems = list(shapes.check(shapes.BLOCKS['descent'], w['descent']))
    entry = w['descent'].get('entry') if isinstance(w['descent'], dict) else None
    if isinstance(entry, dict):
        problems.extend(shapes.check(shapes.BLOCKS['descent entry'], entry))
    try:
        resolved = delve_mod.descent_of(w, pack_dir)
    except ValueError as exc:
        return (_shape_sentences('world.json', problems)
                + _entry_collision_sentences(w, entry)
                + [f'world.json: {exc}'])
    problems.extend(shapes.check_descent(resolved))
    return (_shape_sentences('world.json', problems)
            + _entry_collision_sentences(w, entry))


def _is_tile(value) -> bool:
    """Whether a pack coordinate is a real [x, y] tile."""
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) for v in value))


def _same_tile(one, two) -> bool:
    """Whether two pack coordinates are the same [x, y].

    Both must be two real numbers to compare at all: a door written
    with a string or a missing half is `shapes`' and the door checks'
    sentence, not this one's.
    """
    return _is_tile(one) and _is_tile(two) and [int(v) for v in one] == [int(v) for v in two]


def _entry_collision_sentences(w: dict, entry) -> list[str]:
    """Every authored door standing on the descent's own entry tile.

    The entry is a door like any other, so a pack that puts an authored
    transition on the same tile has two ways out of one tile and the
    player gets whichever the woven list holds first - which used to be
    the authored one, leaving the dungeon unreachable by walking while
    both checks passed (vefr#352). So the tile is refused here, with one
    sentence naming the tile and both regions, and the pack author moves
    one of the two. At play the descent entry still wins the tile
    (`claimTile` in the descent part), so a pack woven anyway leads into
    the dungeon rather than past it.

    Every act's doors are read, not just the first act's: an entry tile
    is a pack-level fact, so a door on it in any act is the same
    collision. An acts-shape pack lists act 1's doors twice (once as
    `transitions`, once as `acts[0]['transitions']`), so a sentence is
    only said once.
    """
    if not isinstance(entry, dict):
        return []
    region, at = entry.get('region'), entry.get('at')
    if not isinstance(region, str) or not _is_tile(at):
        return []     # `shapes` says what a malformed entry is, in its own words
    listed = [w.get('transitions')]
    for act in (w.get('acts') or []):
        if isinstance(act, dict):
            listed.append(act.get('transitions'))
    out: list[str] = []
    for transitions in listed:
        for t in (transitions or []):
            if not isinstance(t, dict) or t.get('from') != region:
                continue
            if not _same_tile(t.get('at'), at):
                continue
            sentence = (f"descent.entry.at [{at[0]}, {at[1]}] is the door "
                        f"from '{region}' to '{t.get('to')}': the descent "
                        f"entry and an authored transition cannot share a "
                        f"tile, so move one of them")
            line = f'world.json: {sentence}'
            if line not in out:
                out.append(line)
    return out


def town_states_errors(w: dict) -> list[str]:
    """Every problem with a pack's optional `town_states` block (empty = good).

    ADR 0015 and its Amendment 1 write two shapes for one key: a block for
    a region, or a list of them, one per region. `shapes.check_town_states`
    walks both and owns every sentence, so this only says where the block
    is, plus the one question two records cannot answer between them: a
    `use` that names no region of the pack is a state that could never
    load, and would say nothing at all rather than say so. A pack that
    declares none gets no output at all, exactly as before, and every one
    of its regions plays as it always did."""
    if 'town_states' not in w:
        return []
    declared: set[str] = set()
    for act in w.get('acts') or []:
        if isinstance(act, dict) and isinstance(act.get('regions'), dict):
            declared.update(name for name in act['regions'] if isinstance(name, str))
    problems = shapes.check_town_states(w['town_states'])
    problems.extend(shapes.check_town_regions(w['town_states'], declared))
    return _shape_sentences('world.json', problems)


# ADR 0014 keeps the affix list and the Section packs in files of their
# own, beside the ones above rather than inside `world.json`: one
# `affixes.json` at the pack root, shared by every Section, and one
# `sections/<id>.json` per Section. Both are pack data, both are checked
# by `shapes.py`, and this is the door `vefr check` opens onto them.
AFFIX_FILE = 'affixes.json'
SECTIONS_DIR = 'sections'


def _pack_json(root: Path, name: str):
    """One pack file's JSON, or the sentence that says it cannot be read.

    The name is joined to the pack root, both are resolved, and the
    result is asked whether it is inside that root BEFORE the read - all
    of it here, in the one function that opens the file, so the read
    cannot be reached by a path that has not been through the check.
    That is also the shape the code scanner recognizes as a guard: a
    resolved path, an `is_relative_to` test on it, and the file access
    below the guard.

    A name that escapes is refused and said out loud. `vefr check` is
    pointed at a pack directory, and a pack directory is not a licence to
    read the rest of the disk: `../../etc/passwd` and a plain
    `/etc/passwd` both resolve outside the pack, and both are refused
    rather than read or quietly turned into the pack root.
    """
    base = Path(root).resolve()
    target = (base / name).resolve()
    if not target.is_relative_to(base):
        return None, 'not a file inside the pack'
    try:
        return json.loads(target.read_text(encoding='utf-8')), None
    except OSError as exc:
        return None, f'{target.name} could not be read ({exc.strerror})'
    except ValueError:
        return None, f'{target.name} is not valid JSON'


def _shape_sentences(rel: str, problems) -> list[str]:
    """Every `shapes` problem as `file: pointer sentence`.

    The pointer is half the sentence: ADR 0014's "Validator rejects"
    asks for one plain sentence plus a JSON pointer each, and the
    pointer is the only thing that says which record of a list is wrong.
    """
    return [f'{rel}: {p.pointer} {p.sentence}' for p in problems]


def _family_resolver(pack: Path):
    """A `resolve` callable for a Section's families, or None.

    A Section names a Blueprint family by id and carries no record of its
    own (ADR 0014), so the one question `shapes` cannot answer for itself
    - does this family exist, and does it have `hp` and `atk`? - is asked
    through `blueprint.resolve_family`. A pack with no Blueprint has no
    families to resolve and the family checks are skipped rather than
    answered wrongly, and so is one whose Blueprint cannot be read: the
    Blueprint's own check already speaks for that pack.
    """
    from . import blueprint

    # Resolved, then checked against the pack root, then probed: the
    # guard and the `is_file()` are in the same function on purpose, so
    # the probe cannot be reached with an unchecked path.
    root = Path(pack).resolve()
    source_path = (root / blueprint.BLUEPRINT_FILE).resolve()
    if not source_path.is_relative_to(root):
        return None
    if not source_path.is_file():
        return None
    try:
        source = blueprint.read(source_path)
    except blueprint.BlueprintError:
        return None

    def resolve(family_id: str):
        try:
            return blueprint.resolve_family(source, family_id)
        except blueprint.BlueprintError:
            return None    # an unknown, cyclic or parentless family
    return resolve


def _no_affix_list_sentences(rel: str, section: dict, affixes) -> list[str]:
    """Every affix a Section names in a pack that has no `affixes.json`.

    One sentence plus a JSON pointer each, like every other rejection
    ADR 0014 lists, and the pointer is the entry in `elites.affixes` -
    the same place `check_affixes` points for an id the pack never
    defines, because the mistake is the same one seen from the other
    side: an id nobody can resolve.

    A pack that ships no affix list and names no affix says nothing: both
    files are optional, and a pack that asks for no elite is not asking
    for an affix. What is reported is the pack that wrote the ids and not
    the file, which validated green and then drew a normal monster where
    an elite should have stood, with no sentence anywhere saying so.
    """
    if affixes is not None:
        return []
    return [f'{rel}: /elites/affixes/{i} affix {aid!r} is named but this '
            f'pack has no {AFFIX_FILE}'
            for i, aid in enumerate(shapes.named_affix_ids(section))]


def section_block_errors(section: dict, affixes=None, resolve=None,
                         rel: str = f'{SECTIONS_DIR}/<id>.json',
                         drops=None) -> list[str]:
    """Every sentence `vefr check` prints for one Section pack.

    The Section block of `shapes.py` is the engine's own read of a Section
    (PLAN.md section 2), and this is the one function that turns that read
    into lines: `file: pointer sentence` each, in the order `shapes` emits
    them. `section_errors` below is the only caller in the engine, and
    `tests/golden/validator/cases.json` pins the sentences through here,
    so a change to any of them is a deliberate act.

    `drops` is the callable that says whether a family's `drops` can pay
    the player, handed on to `shapes.check_section` (which may not import
    `vefr`); see `section_errors` for what it is.
    """
    sentences = _shape_sentences(rel, shapes.check_section(section, affixes,
                                                           resolve, drops))
    sentences.extend(_no_affix_list_sentences(rel, section, affixes))
    return sentences


def section_errors(pack_dir) -> list[str]:
    """Every problem with a pack's affix list and its Section packs.

    `shapes.check_section` is the engine's own read of both; this is the
    only path that runs it, so an affix record that is not a record, an
    id used twice, an affix a Section names and the pack never defines, a
    group led by an elite in a Section that names no affix, a family the
    Blueprint does not have, and a Section pack whose own shape is wrong
    are all pack-authoring errors with a sentence and a pointer - the
    ADR's "Validator rejects" list, said where the author is already
    looking.

    The affix list is read on its own first, before any Section: it is
    one list for the whole pack whatever Sections name, so a duplicate id
    is a problem with a pack that ships no Section at all too. A pack
    with neither file gets nothing here and validates exactly as it did
    before - both are E7 additions and neither is required.

    A pack with Sections that NAME affixes and no list to name them in is
    the third thing, and it is said here rather than in `shapes` because
    it is a question about the pack's files: `check_section` skips its
    affix checks when there is no list to read them against, which is
    right for a pack that asks for no elite and wrong for one that asks
    for one, and the difference is the file this module knows the name of.

    A Section family's `drops` are read against the same catalog every
    other `drops` in the engine is: `_pack_declared(root)`, this pack's
    own `world.json` through `library._declared_items`. A monster on a
    generated floor carries exactly what its Blueprint family names, so a
    family naming an id the pack cannot deliver is a pack that promises an
    item it will never hand over. A pack whose `world.json` cannot be read
    gets that one check skipped rather than wrong.

    `shapes` may not import `vefr`, so the reading is passed to it as the
    `drops` callable it already takes its `resolve` through - the same
    door, for the same reason.
    """
    pack = Path(pack_dir)
    root = pack.resolve()
    errors: list[str] = []

    # Both of the two places below resolve a path out of the pack
    # directory this function was handed and check it against the pack
    # root before touching it - here for the affix list, and in
    # `_pack_json` for each Section file - so a pack directory that is a
    # name rather than a place cannot send the check outside itself. The
    # check is written as `is_relative_to` on the resolved path and sits
    # in the same function as the file access, which is the shape the
    # code scanner recognizes as a guard. A name that escapes is REFUSED
    # with a sentence rather than read: these two names are the module's
    # own, so an escape is a mistake to say out loud, and quietly
    # pointing at something outside the pack is how a `..` in a path
    # becomes a file the author never wrote.
    affixes = None
    affix_path = (root / AFFIX_FILE).resolve()
    if not affix_path.is_relative_to(root):
        return [f'{AFFIX_FILE} is not a file inside the pack']
    if affix_path.is_file():
        affixes, problem = _pack_json(root, AFFIX_FILE)
        if problem is not None:
            return [problem]
        errors.extend(_shape_sentences(
            AFFIX_FILE, shapes.check_affixes({}, affixes)))

    sections = (root / SECTIONS_DIR).resolve()
    if not sections.is_relative_to(root):
        errors.append(f'{SECTIONS_DIR} is not a directory inside the pack')
        return errors
    paths = sorted(sections.glob('*.json')) if sections.is_dir() else []
    if not paths:
        return errors
    resolve = _family_resolver(pack)
    declared = _pack_declared(root)

    def drops(section_id, family, record):
        """One sentence if this family's `drops` pay nothing, else None."""
        said = library._drop_payout_errors(
            f'section {section_id!r} family {family!r}', 'the family',
            record.get('drops', library.NO_DROPS)
            if isinstance(record, dict) else library.NO_DROPS,
            declared)
        return said[0] if said else None
    for path in paths:
        rel = path.relative_to(root).as_posix()
        section, problem = _pack_json(root, rel)
        if problem is not None:
            errors.append(f'{rel}: {problem}')
            continue
        if not isinstance(section, dict):
            errors.append(f'{rel}: a Section pack must be a JSON object')
            continue
        errors.extend(section_block_errors(section, affixes, resolve, rel,
                                           drops))
        errors.extend(_warden_key_errors(root, section, rel))
        errors.extend(_section_tile_errors(root, section, rel))
        errors.extend(_section_decor_errors(root, section, rel))
        errors.extend(_warden_drop_errors(root, section, rel, resolve))
    return errors


def _pack_catalog(root: Path) -> dict | None:
    """The item catalog the woven player will really get, or None for no catalog.

    `weave` reads the pack root's `world.json` straight off the disk and
    merges the unified shape over it before `cli._player_items` picks the
    catalog out (`cli.weave_player`), so the catalog the bag holds is the
    pack-level file's `items` block - in both shapes, since the unified
    `load_pack` reads that same file. Reading it off the `w` the caller
    handed the validator is a different question: `vefr.world.load_world`
    (what the tests and the web app validate) carries no `items` at all,
    and `load_pack` carries one only for an acts-shape pack. A chest read
    against either empty catalog is refused by name, so the pack's own
    file is where the answer actually lives.

    The two "no catalog" answers stay apart, because they mean opposite
    things. A `world.json` that cannot be read is None: the caller had no
    catalog to read the drops against, and every drop check is skipped.
    A file that reads and carries no `items` is `{}`: the pack declares no
    catalog, so it declares nothing, and a chest that drops from it opens
    on nothing.

    Every `drops` in the engine is read against this file and then
    through `library._declared_items`, which is the reader that keeps
    only the entries the item reader would really bake. One file, one
    read, one rule: the chest book, the region enemy, the Blueprint
    family and the Section family below all ask here.
    """
    config, problem = _pack_json(Path(root), 'world.json')
    if problem is not None:
        return None
    listed = config.get('items') if isinstance(config, dict) else None
    return listed if isinstance(listed, dict) else {}


def _section_tile_errors(root: Path, section: dict, rel: str) -> list[str]:
    """Every tileset a Section's `tiles` names that has no picture.

    A Section's `tiles` is what a play floor is drawn with (vefr#349), so a
    glyph naming a tileset nothing has is a floor that quietly falls back to
    that glyph's own colour - the author asked for a picture and got a
    rectangle. It is said here rather than in `shapes` for the reason
    `_warden_key_errors` is: `shapes` cannot see the files, and a picture is a
    file. The pack's own `tiles/` answers first, exactly as the weave reads it,
    then the engine set.

    The engine set is where `vefr art` and the bake find their pictures, and
    a wheel or a container may not carry it; a tile directory that is not there
    to read is a tile directory this check cannot have an opinion about, so it
    says nothing rather than refusing every Section.
    """
    from .cli import _pack_tile_paths, _template_candidates

    tiles = section.get('tiles')
    if not isinstance(tiles, dict) or not tiles:
        return []
    candidates = _template_candidates()
    web_dir = next((c.parent for c in candidates if c.exists()), None)
    if web_dir is None or not (web_dir / 'art' / 'tiles').is_dir():
        return []
    sid = section.get('id')
    sid = sid if isinstance(sid, str) and sid else 'this Section'
    problems = []
    for glyph in sorted(tiles, key=str):
        name = tiles[glyph]
        if not isinstance(name, str) or not name:
            continue                      # `shapes` speaks for a wrong value
        if _pack_tile_paths(root, root, name):
            continue
        if (web_dir / 'art' / 'tiles' / f'{name}.webp').is_file():
            continue
        problems.append(
            f'{rel}: /tiles/{glyph} Section {sid} draws {glyph!r} with '
            f'the tileset {name!r}, and no picture of that name is in this '
            f'pack\'s tiles/ or the engine\'s; the floor would fall back to '
            f'the glyph\'s own colour')
    return problems


def _section_decor_errors(root: Path, section: dict, rel: str) -> list[str]:
    """Every decor picture a Section names that the pack does not have (vefr#442).

    A decor `pic` is read the way a prop's is, from the pack's own `props/`,
    and one with no picture would be dressing nobody can see. `shapes` speaks
    for a wrong value; this speaks for a missing file, which only the pack
    directory can answer.
    """
    from .cli import _prop_picture_path

    decor = section.get('decor')
    if not isinstance(decor, list):
        return []
    sid = section.get('id')
    sid = sid if isinstance(sid, str) and sid else 'this Section'
    problems = []
    for i, entry in enumerate(decor):
        pic = entry.get('pic') if isinstance(entry, dict) else None
        if not isinstance(pic, str) or not pic:
            continue
        if pic in ('.', '..') or any(c in pic for c in '/\\\0'):
            problems.append(f'{rel}: /decor/{i}/pic Section {sid} decor {pic!r} must be '
                            f"a picture's file name with no folder")
            continue
        if _prop_picture_path(root, None, pic) is None:
            problems.append(f'{rel}: /decor/{i}/pic Section {sid} decor {pic!r} has no '
                            f"picture '{pic}.webp' or '{pic}.png' in this pack's props/")
    return problems


def _pack_declared(root: Path) -> set[str] | None:
    """The ids this pack really hands over, from its own `world.json`.

    `_pack_catalog` reads the file and `library._declared_items` says what
    the weave keeps of it, which is the pair every drop check in this
    module reads through. None (an unreadable `world.json`) is kept
    distinct from `{}` (a pack that declares no catalog, and so declares
    nothing) because they mean opposite things - see `_pack_catalog`.
    """
    catalog = _pack_catalog(root)
    return None if catalog is None else library._declared_items(catalog)


def _warden_key_errors(root: Path, section: dict, rel: str) -> list[str]:
    """ADR 0015 check 3 for the key a Section's warden `carries`.

    The key is a declared item that is `keep` (used, never used up) and has no
    `value` (so no shop buys or sells it), and no Blueprint family drops it:
    the only way to get it is to beat the warden. Without these a key could be
    sold, lost, or found elsewhere and open the vault early.

    An item the pack declares with no `name` is refused here too, and it is
    the same refusal the chest drops get: `weave` drops such an entry from the
    catalog it bakes (`cli._player_items`) and `bagAdd` refuses an id that
    catalog does not hold, so beating the warden would hand over a key the bag
    will not take - an empty chest with a monster standing next to it.
    """
    warden = section.get('warden')
    item = warden.get('carries') if isinstance(warden, dict) else None
    if not isinstance(item, str) or not item:
        return []
    world, problem = _pack_json(root, 'world.json')
    items = world.get('items') if isinstance(world, dict) else None
    spec = items.get(item) if isinstance(items, dict) else None
    where = f'{rel}: /warden/carries'
    if not isinstance(spec, dict):
        return [f'{where} {item!r} is not an item world.json declares']
    if not str(spec.get('name', '')).strip():
        return [f'{where} {item!r} is declared with no name, so it is not an '
                'item the bag can hold; give it a name']
    out = []
    if spec.get('keep') is not True:
        out.append(f'{where} {item!r} must be kept, not used up: give it "keep": true')
    value = spec.get('value')
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        out.append(f'{where} {item!r} must have no value, so no shop buys or sells it')
    from . import blueprint
    source, _ = (_pack_json(root, blueprint.BLUEPRINT_FILE)
                 if (root / blueprint.BLUEPRINT_FILE).is_file() else (None, None))
    families = source.get('families') if isinstance(source, dict) else None
    for fid, record in sorted(families.items()) if isinstance(families, dict) else ():
        defaults = record.get('defaults') if isinstance(record, dict) else None
        drops = defaults.get('drops') if isinstance(defaults, dict) else None
        if isinstance(drops, list) and item in drops:
            out.append(f'{where} {item!r} is dropped by family {fid!r}; '
                       'the warden must be the only way to get it')
    return out


def _warden_drop_errors(root: Path, section: dict, rel: str, resolve=None) -> list[str]:
    """Every sentence for a drop the warden's own family hands over.

    The last of the four drop surfaces the catalog reads. A chest book, a
    baked region's enemy and a rule's `give` are all checked against the
    items `weave` bakes; the warden's drops are drawn from its family's own
    `drops` (`delve._with_warden`, the draw every monster on the floor
    makes) and were the one that was not - so a pack could name a drop the
    bag will refuse, validate green, and lose it on the floor.

    Read the same way the chest drops are read: an id with no `name` under
    it is not an item the bag can hold (`library._declared_items`), a pack
    whose `world.json` cannot be read has no catalog to read against and is
    checked rather than refused, and a family the Blueprint does not have is
    the family's own sentence, not one of these.
    """
    from . import library

    warden = section.get('warden')
    family = warden.get('family') if isinstance(warden, dict) else warden
    if not (isinstance(family, str) and family):
        return []
    declared = library._declared_items(_pack_catalog(root))
    if declared is None:
        return []
    base = resolve(family) if resolve is not None else None
    drops = base.get('drops') if isinstance(base, dict) else None
    if not isinstance(drops, list):
        return []
    return [f'{rel}: /warden/family the warden drops {drop!r}, which is not '
            f'an item world.json declares - the bag will refuse it'
            for drop in drops
            if isinstance(drop, str) and drop and drop not in declared]


# The parts a skin may name (design/ui-skin.md). Anything else is a
# typo the author should read about, not a part the player silently
# ignores.
SKIN_PARTS = ('panel', 'button', 'tab', 'toggle', 'bar', 'slot', 'speech',
              'tooltip', 'gold-plate', 'divider', 'banner', 'corner', 'cursor')

# Every key of a part whose value is a picture file name. `slice` and
# `hotspot` are the only other keys the contract knows.
SKIN_PICTURE_KEYS = ('file', 'hover', 'pressed', 'disabled', 'selected',
                     'on', 'off', 'frame', 'fill', 'hand')

# The picture suffix a skin may use, and the per-picture size cap.
SKIN_SUFFIXES = ('.png', '.webp')
SKIN_PICTURE_BYTES = 300_000

# The one colour shape `ink` accepts.
_SKIN_INK_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

# The typefaces a skin may choose from: the families the engine bundles and
# ships inside the woven file (docs/plans/interface/PLAN.md, slice 3). A name
# outside this list would ask the browser for a font nobody has, so it is a
# plain sentence instead.
SKIN_FONTS = ('Cinzel', 'Atkinson Hyperlegible Next', 'Crimson Pro')

# The two roles a skin may set the type for.
SKIN_FONT_ROLES = ('display', 'body')


def _skin_picture_errors(kind: str, fname, skin_dir: str) -> tuple[list[str], str | None]:
    """Every problem with one picture a skin names; the path when it is good.

    `kind` names the thing to fix ("skin part 'panel' file", "skin backdrop"),
    so the sentence reads the way the author wrote the field. Returns the
    messages and the resolved path (None when the picture is not usable).
    """
    if not isinstance(fname, str) or not fname.strip():
        return ([f"{kind} must name a picture file"], None)
    from .cli import _inside

    target = _inside(skin_dir, fname)
    if target is None or not os.path.isfile(target):
        return ([f"{kind} names '{fname}', which does not exist in the skin folder"], None)
    if os.path.splitext(fname)[1].lower() not in SKIN_SUFFIXES:
        return ([f"{kind} names '{fname}', which is not a webp or png picture"], None)
    size = os.path.getsize(target)
    if size > SKIN_PICTURE_BYTES:
        return ([f"{kind} picture '{fname}' is too big ({size} bytes; "
                 f'the cap is {SKIN_PICTURE_BYTES})'], None)
    return [], target


def _font_errors(fonts) -> list[str]:
    """Every problem with a skin's optional `fonts` block (empty = good)."""
    if not isinstance(fonts, dict):
        return ["skin.json 'fonts' must be an object naming a bundled family"]
    errors = []
    for role, family in fonts.items():
        if role not in SKIN_FONT_ROLES:
            errors.append(
                f"skin.json fonts '{role}' is not a role; expected "
                f"{' or '.join(SKIN_FONT_ROLES)}")
        elif not isinstance(family, str) or not family.strip():
            errors.append(f"skin.json fonts '{role}' must name a bundled family")
        elif family not in SKIN_FONTS:
            errors.append(
                f"skin.json fonts '{role}' names '{family}', which the engine "
                f'does not bundle ({", ".join(SKIN_FONTS)})')
    return errors


def _picture_size(path: str) -> tuple[int, int] | None:
    """(width, height) read from a png or webp header, or None.

    PNG dimensions come from the IHDR chunk. WebP is read on a
    best-effort basis (VP8X canvas, VP8 frame header); a picture whose
    header cannot be read returns None, so the caller skips the
    half-slice check rather than guess.
    """
    try:
        with open(path, 'rb') as f:
            head = f.read(32)
    except OSError:
        return None
    # PNG: signature (8) + length (4) + 'IHDR' (4) + width/height (8).
    if len(head) >= 24 and head[:8] == b'\x89PNG\r\n\x1a\n' and head[12:16] == b'IHDR':
        return int.from_bytes(head[16:20], 'big'), int.from_bytes(head[20:24], 'big')
    # WebP: RIFF....WEBP then a VP8X/VP8 chunk.
    if len(head) >= 30 and head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        chunk = head[12:16]
        if chunk == b'VP8X':
            w = int.from_bytes(head[24:27], 'little') + 1
            h = int.from_bytes(head[27:30], 'little') + 1
            return w, h
        if chunk == b'VP8 ' and head[23:26] == b'\x9d\x01\x2a':
            w = int.from_bytes(head[26:28], 'little') & 0x3fff
            h = int.from_bytes(head[28:30], 'little') & 0x3fff
            return w, h
    return None


def skin_errors(w: dict, pack_dir: Path | None = None) -> list[str]:
    """Every problem with a pack's optional `skin` (empty = good).

    A `"skin": "skins/<name>"` field names a folder inside the pack
    with a `skin.json` and its pictures (design/ui-skin.md, rules 1, 5,
    6). The field is optional and additive: a pack with none gets no
    output. The path must stay inside the pack; `skin.json` must be a
    JSON object with a non-empty `name` and `credit`; every part key
    must be a known part; every named picture must exist, end in .png
    or .webp, and stay under the size cap; `slice` must fit inside its
    picture; `ink` colours must be `#RRGGBB`; an optional `backdrop`
    names one more picture under the same rules, and an optional
    `fonts` names bundled families for the display and body roles.
    Every message is one plain sentence naming the thing to fix.
    """
    if 'skin' not in w:
        return []
    skin_rel = w.get('skin')
    if not isinstance(skin_rel, str) or not skin_rel.strip():
        return ["skin must name a folder inside the pack"]
    # The path stays inside the pack: no absolute path, no '..'.
    if os.path.isabs(skin_rel) or '..' in Path(skin_rel).parts:
        return [f"skin '{skin_rel}' must stay inside the pack"]
    # Everything past here needs the pack on disk (in-memory drafts have
    # no folder to read).
    if pack_dir is None:
        return []
    from .cli import _inside

    base = os.path.realpath(str(pack_dir))
    skin_dir = _inside(base, skin_rel)
    if skin_dir is None or not os.path.isdir(skin_dir):
        return [f"skin folder '{skin_rel}' does not exist inside the pack"]

    skin_json = os.path.join(skin_dir, 'skin.json')
    if not os.path.isfile(skin_json):
        return [f"skin folder '{skin_rel}' has no skin.json"]
    try:
        data = json.loads(Path(skin_json).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return [f"skin.json in '{skin_rel}' is not valid JSON"]
    if not isinstance(data, dict):
        return [f"skin.json in '{skin_rel}' must be a JSON object"]

    errors: list[str] = []
    for field in ('name', 'credit'):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"skin.json needs a non-empty string '{field}'")

    parts = data.get('parts')
    if not isinstance(parts, dict):
        errors.append("skin.json 'parts' must be an object of named parts")
        parts = {}
    for pname, spec in parts.items():
        if pname not in SKIN_PARTS:
            errors.append(f"skin.json part '{pname}' is not a known part")
            continue
        if not isinstance(spec, dict):
            errors.append(f"skin part '{pname}' must be an object")
            continue
        # Every picture a part names: real, webp/png, small enough. The
        # backdrop is checked by the same sentence, one key further out.
        found: dict[str, str] = {}
        for key in SKIN_PICTURE_KEYS:
            fname = spec.get(key)
            if fname is None:
                continue
            problems, target = _skin_picture_errors(
                f"skin part '{pname}' {key}", fname, skin_dir)
            errors.extend(problems)
            if target is not None:
                found[key] = target
        # `slice` fits inside the part's main picture: a whole number of
        # at least 1, at most half the smaller side.
        if 'slice' in spec:
            sl = spec['slice']
            # The main picture for the fit check: `file`, else `frame`,
            # else the first picture the part names.
            main = None
            for key in ('file', 'frame', *SKIN_PICTURE_KEYS):
                if key in found:
                    main = found[key]
                    break
            if not _is_whole(sl) or sl < 1:
                errors.append(
                    f"skin part '{pname}' slice must be a whole number "
                    'of at least 1')
            elif main is not None:
                size = _picture_size(main)
                if size is not None and sl * 2 > min(size):
                    errors.append(
                        f"skin part '{pname}' slice {sl} is more than half "
                        f'the smaller side of its picture ({min(size)} px)')
        # `hotspot` is carried through untouched; only its presence has
        # a home in the player.

    ink = data.get('ink')
    if ink is not None:
        if not isinstance(ink, dict):
            errors.append("skin.json 'ink' must be an object of #RRGGBB colours")
        else:
            for name, colour in ink.items():
                if not isinstance(colour, str) or not _SKIN_INK_RE.match(colour):
                    errors.append(
                        f"skin.json ink '{name}' must be a #RRGGBB colour")

    # The optional backdrop: one seamless picture for the ground the map does
    # not cover. Checked exactly like a part's picture, and named in one
    # sentence so an author knows which file to look at.
    if 'backdrop' in data:
        problems, _ = _skin_picture_errors("skin backdrop", data['backdrop'], skin_dir)
        errors.extend(problems)

    # The optional type: a family per role, from the ones the engine bundles.
    if 'fonts' in data:
        errors.extend(_font_errors(data['fonts']))
    return errors


# Walk sheets (design/pack-art-proposal.md, phase B): the directions a
# sheet may name, the frame size and fps bounds, and the frame lists.
SHEET_DIRECTIONS = ('down', 'up', 'left', 'right')
SHEET_FRAME_MIN, SHEET_FRAME_MAX = 8, 512
SHEET_FPS_MIN, SHEET_FPS_MAX = 1, 30
SHEET_WALK_MIN, SHEET_WALK_MAX = 2, 16
SHEET_IDLE_MIN, SHEET_IDLE_MAX = 1, 16
SHEET_STATES = ('act', 'attack', 'hurt', 'talk')
SHEET_STATE_MIN, SHEET_STATE_MAX = 1, 16


def _sheet_frames(v, lo: int, hi: int) -> bool:
    return (isinstance(v, list) and lo <= len(v) <= hi
            and all(_is_whole(i) for i in v))


def _sprite_sheet_files(pack_dir: Path) -> list[tuple[Path, Path]]:
    """Every `*.sheet.json` under a pack's `sprites/` dirs: (path, rel).

    The pack root's own `sprites/` and each act region's
    `acts/<act>/<region>/sprites/`, the same two places the loader
    reads sprites from. `rel` is relative to the pack, so a message can
    name the file the author sees.
    """
    from .cli import _inside

    base = os.path.realpath(str(pack_dir))
    roots: list[Path] = []
    own = _inside(base, 'sprites')
    if own is not None and os.path.isdir(own):
        roots.append(Path(own))
    acts = _inside(base, 'acts')
    if acts is not None and os.path.isdir(acts):
        for act_name in sorted(os.listdir(acts)):
            act_dir = _inside(acts, act_name)
            if act_dir is None or not os.path.isdir(act_dir):
                continue
            for region_name in sorted(os.listdir(act_dir)):
                region = _inside(act_dir, region_name)
                if region is None or not os.path.isdir(region):
                    continue
                sprites = _inside(region, 'sprites')
                if sprites is not None and os.path.isdir(sprites):
                    roots.append(Path(sprites))
    out: list[tuple[Path, Path]] = []
    for root in roots:
        for f in sorted(root.rglob('*.sheet.json')):
            if f.is_file():
                out.append((f, f.relative_to(base)))
    return out


def sprite_sheet_errors(pack_dir: Path | None) -> list[str]:
    """Every problem with a pack's optional walk sheets (empty = good).

    A `sprites/<key>.sheet.json` beside a sprite describes the frames a
    character walks through (design/pack-art-proposal.md, phase B). The
    check is shape-only: the JSON must be an object; `image` must name
    a real picture beside the sheet and inside the pack; `frame` two
    whole numbers from 8 to 512; `fps` a whole number from 1 to 30;
    every direction an object with an `idle` of 1 to 16 frames, a `walk`
    of 2 to 16, and optional `act`, `attack`, `hurt` and `talk` lists of
    1 to 16; and every frame inside the sheet's grid. `down`
    is required. Each message names the sheet file, plainly. A pack
    that ships no sheet gets nothing here at all.
    """
    if pack_dir is None:
        return []
    from .cli import _ART_TYPES, _inside

    errors: list[str] = []
    for sheet_path, rel in _sprite_sheet_files(pack_dir):
        label = rel.as_posix()
        try:
            data = json.loads(sheet_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            errors.append(f'{label} is not valid JSON')
            continue
        if not isinstance(data, dict):
            errors.append(f'{label} must be a JSON object')
            continue

        image_path = None
        image = data.get('image')
        if not isinstance(image, str) or not image:
            errors.append(f"{label} needs a non-empty string 'image'")
        else:
            sheet_dir = os.path.realpath(sheet_path.parent)
            target = _inside(sheet_dir, image)
            if target is None or not os.path.isfile(target):
                errors.append(f"{label} names image '{image}', which does "
                              'not exist beside the sheet')
            else:
                image_path = Path(target)
                if image_path.suffix.lower() not in _ART_TYPES:
                    errors.append(f"{label} image '{image}' is not a known "
                                  'picture type')
                    image_path = None

        frame = data.get('frame')
        fw = fh = None
        if (not isinstance(frame, list) or len(frame) != 2
                or not all(_is_whole(v) and SHEET_FRAME_MIN <= v <= SHEET_FRAME_MAX
                           for v in frame)):
            errors.append(f"{label} 'frame' must be two whole numbers "
                          f'from {SHEET_FRAME_MIN} to {SHEET_FRAME_MAX}')
        else:
            fw, fh = frame

        fps = data.get('fps')
        if not (_is_whole(fps) and SHEET_FPS_MIN <= fps <= SHEET_FPS_MAX):
            errors.append(f"{label} 'fps' must be a whole number "
                          f'from {SHEET_FPS_MIN} to {SHEET_FPS_MAX}')

        indices: list[int] = []
        directions = data.get('directions')
        if not isinstance(directions, dict):
            errors.append(f"{label} needs a 'directions' object")
        else:
            for dname in directions:
                if dname not in SHEET_DIRECTIONS:
                    errors.append(f"{label} names an unknown direction "
                                  f"'{dname}'")
            if 'down' not in directions:
                errors.append(f"{label} needs a 'down' direction")
            for dname, frames in directions.items():
                if dname not in SHEET_DIRECTIONS:
                    continue
                if not isinstance(frames, dict):
                    errors.append(f"{label} direction '{dname}' must be an "
                                  'object with idle and walk lists')
                    continue
                idle = frames.get('idle')
                if not _sheet_frames(idle, SHEET_IDLE_MIN, SHEET_IDLE_MAX):
                    errors.append(f"{label} direction '{dname}' needs an "
                                  f"'idle' list of {SHEET_IDLE_MIN} to "
                                  f'{SHEET_IDLE_MAX} frames')
                else:
                    indices.extend(idle)
                walk = frames.get('walk')
                if walk is None:
                    pass   # a character that never walks (a resident at their post) needs no walk frames
                elif not _sheet_frames(walk, SHEET_WALK_MIN, SHEET_WALK_MAX):
                    errors.append(f"{label} direction '{dname}' needs a "
                                  f"'walk' list of {SHEET_WALK_MIN} to "
                                  f'{SHEET_WALK_MAX} frames')
                else:
                    indices.extend(walk)
                for state in SHEET_STATES:
                    if state not in frames:
                        continue
                    if not _sheet_frames(frames[state], SHEET_STATE_MIN, SHEET_STATE_MAX):
                        errors.append(f"{label} direction '{dname}' has an "
                                      f"'{state}' that is not a list of "
                                      f'{SHEET_STATE_MIN} to {SHEET_STATE_MAX} frames')
                    else:
                        indices.extend(frames[state])

        # The grid: image size / frame size, read from the picture's own
        # header. An unreadable header (None) skips only this check.
        if image_path is not None and fw and fh:
            size = _picture_size(str(image_path))
            if size is not None:
                cols, rows = size[0] // fw, size[1] // fh
                for idx in indices:
                    if cols < 1 or rows < 1:
                        inside = False
                    else:
                        # Both the column and the row must be in range; floor
                        # division sends a negative index to a negative row,
                        # which the old row-only check let through.
                        inside = (0 <= idx % cols < cols
                                  and 0 <= idx // cols < rows)
                    if not inside:
                        errors.append(f'{label} frame {idx} is outside the '
                                      "sheet's grid "
                                      f'({cols} columns by {rows} rows)')
    return errors


def rules_errors(w: dict, pack_dir: Path | None = None) -> list[str]:
    """Every problem with a pack's optional flags/claims/people/rules.

    The four keys are optional and additive: a pack that declares
    none of them gets no output at all, exactly as before. A pack
    that declares any of them gets every rule checked here, at
    authoring time, rather than by surprise in play. Messages are
    plain sentences; rule-level ones name the rule id.
    """
    if not any(k in w for k in ('flags', 'claims', 'people', 'rules')):
        return []
    errors: list[str] = []
    if 'flags' in w and not isinstance(w['flags'], dict):
        errors.append('flags must be an object mapping a flag name to one line of text')
    if 'claims' in w:
        if not isinstance(w['claims'], dict):
            errors.append('claims must be an object mapping a claim name to meaning and truth')
        else:
            for cname, spec in w['claims'].items():
                if not isinstance(spec, dict):
                    errors.append(f"claim '{cname}' must be an object with 'meaning' and 'true'")
                    continue
                meaning = spec.get('meaning')
                if not isinstance(meaning, str) or not meaning.strip():
                    errors.append(f"claim '{cname}' needs a non-empty string 'meaning'")
                if not isinstance(spec.get('true'), bool):
                    errors.append(f"claim '{cname}' needs 'true' set to true or false")
    speakers = w.get('speakers') if isinstance(w.get('speakers'), dict) else {}
    if 'people' in w:
        if not isinstance(w['people'], dict):
            errors.append('people must be an object mapping a person id to beliefs')
        else:
            for pid, spec in w['people'].items():
                if pid not in speakers:
                    # A person must be someone the hero can meet.
                    errors.append(f"person '{pid}' in people is not a speaker in this pack")
                if not isinstance(spec, dict):
                    errors.append(f"person '{pid}' in people must be an object with 'believes'")
                    continue
                believes = spec.get('believes')
                if not isinstance(believes, list) or not all(
                        isinstance(c, str) for c in believes):
                    errors.append(f"person '{pid}' in people needs a 'believes' "
                                  'list of claim names')
    if 'rules' in w and not isinstance(w['rules'], list):
        errors.append('rules must be a list')
        return errors
    rules = w.get('rules') or []
    if len(rules) > RULE_LIMIT:
        errors.append(f'this pack declares {len(rules)} rules - the limit is {RULE_LIMIT}')
    known = _rule_known_ids(w, pack_dir)
    seen: set = set()
    fireable: list = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f'the rule at position {index} must be an object')
            continue
        rid = rule.get('id')
        if not isinstance(rid, str) or not rid.strip():
            errors.append(f'the rule at position {index} needs a non-empty string id')
            continue
        label = f"rule '{rid}'"
        if rid in seen:
            errors.append(f"two rules share the id '{rid}' - rule ids must be unique")
            continue
        seen.add(rid)
        # `once` absent means true: a rule runs once unless the pack
        # asks otherwise, so only a non-boolean value is an error.
        if 'once' in rule and not isinstance(rule['once'], bool):
            errors.append(f"{label} 'once' must be true or false")
        if 'when' not in rule:
            errors.append(f"{label} needs a 'when' event")
        else:
            errors.extend(_rule_event_errors(rid, rule['when'], known))
        if 'if' in rule and not isinstance(rule['if'], list):
            errors.append(f"{label} 'if' must be a list of conditions")
        elif isinstance(rule.get('if'), list):
            for cond in rule['if']:
                errors.extend(_rule_condition_errors(rid, cond, known))
        then = rule.get('then')
        if not isinstance(then, list) or not then:
            errors.append(f"{label} 'then' must be a non-empty list of actions")
        else:
            for action in then:
                errors.extend(_rule_action_errors(rid, action, known))
        if 'on' in rule:
            on = rule['on']
            if not isinstance(on, str):
                errors.append(f"{label} 'on' must name a thing")
            elif on not in known['things']:
                errors.append(f"{label} 'on' names unknown thing '{on}'")
        fireable.append((rid, rule))
    # CONFLICT: two rules that fire on the same event and can both
    # pass it - same `when`, same `on`, same `if` - may disagree in
    # what they do. Rules with different `if` lists are not compared:
    # the validator cannot honestly decide whether two different
    # conditions overlap in play.
    for i, (aid, arule) in enumerate(fireable):
        for bid, brule in fireable[i + 1:]:
            if not isinstance(arule.get('when'), dict):
                continue
            if arule.get('when') != brule.get('when'):
                continue
            if arule.get('on') != brule.get('on'):
                continue
            if (arule.get('if') or []) != (brule.get('if') or []):
                continue
            message = _rule_conflict_message(aid, bid, arule.get('then'),
                                             brule.get('then'))
            if message:
                errors.append(message)
    return errors


# The three sticker kinds (design/album.md): `open` shows its name from
# the start, `riddle` hides behind its riddle until earned, `secret`
# shows only ever as a count. The shine levels are looks only.
ALBUM_KINDS = ('open', 'riddle', 'secret')
ALBUM_SHINES = ('paper', 'foil', 'holo')
ALBUM_NAME_LIMIT = 60


def _album_name_errors(sid: str, where: str, val, known_set, noun: str) -> list[str]:
    """One named thing inside a sticker's `when`, against the pack's ids."""
    if not isinstance(val, str):
        return [f"sticker '{sid}' {where} must be a {noun}"]
    if val not in known_set:
        return [f"sticker '{sid}' {where} names unknown {noun} '{val}'"]
    return []


_KNOWN_FOR_REF = {
    'item': 'items', 'place': 'places', 'thing': 'things',
    'book': 'books', 'enemy': 'enemies', 'phase': 'phases',
    'verb': 'verbs',
    'recipe': 'recipes',
}


def _known_ids(known: dict, ref: str) -> set:
    """The pack's ids of one ref kind, as `_rule_known_ids` names them.

    The one thing the table does not say: where a kind's ids are filed.
    Spelled out rather than guessed at from the kind's name, because
    not every plural is the name plus an `s`. A ref kind with no entry
    raises here, on its first sticker, rather than resolving to nothing.
    """
    return known[_KNOWN_FOR_REF[ref]]


def _album_when_errors(sid: str, when, known: dict) -> list[str]:
    """The `when` of one sticker: exactly one rules event, right payload.

    The same vocabulary and identity model as a rule's `when` - both
    read `shapes.EVENTS`, and a sticker may name only what the pack
    declares (`_rule_known_ids`) - but the wording is the sticker
    author's, never the rule validator's, because an album is not a
    rule and the author has no rule to look at. Each problem is one
    plain sentence naming the sticker id, and the unknown thing when
    there is one.
    """
    if not isinstance(when, dict):
        return [f"sticker '{sid}' when must name one event"]
    if len(when) != 1:
        return [f"sticker '{sid}' when must name exactly one event"]
    event = next(iter(when))
    if event not in RULE_EVENTS:
        return [f"sticker '{sid}' when names unknown event '{event}'"]
    payload = when[event]
    if not isinstance(payload, dict):
        return [f"sticker '{sid}' when '{event}' carries an object payload"]
    fields = shapes.EVENTS[event]
    want = RULE_EVENT_KEYS[event]
    errors: list[str] = []
    for key in payload:
        if key not in want:
            errors.append(f"sticker '{sid}' when '{event}' has unknown key '{key}'")
    for key in want:
        if key not in payload:
            errors.append(f"sticker '{sid}' when '{event}' needs key '{key}'")
    if errors:
        return errors
    # Each field's named thing is checked against the pack's own ids -
    # the exact model a rule uses, so the two never drift.
    for field in fields:
        where = _event_where(event, fields, field.name)
        if field.ref is not None:
            errors.extend(_album_name_errors(sid, where, payload[field.name],
                                             _known_ids(known, field.ref), field.ref))
            continue
        distance = payload[field.name]
        if isinstance(distance, bool) or not isinstance(distance, int) \
                or not field.lo <= distance <= field.hi:
            errors.append(f"sticker '{sid}' {where} must be an integer 0 to 9")
    return errors


def album_errors(w: dict, pack_dir: Path | None = None) -> list[str]:
    """Every problem with a pack's optional sticker album (empty = good).

    A pack that declares no `album` gets nothing here at all - exactly
    as before, which is the load-bearing compatibility promise. A pack
    that declares one gets every sticker checked at authoring time, one
    plain sentence per problem, each naming the sticker id (or the
    unknown thing). The `when` vocabulary and identity model are the
    rules': `_rule_known_ids` is the one place that decides what a
    sticker may name.
    """
    if 'album' not in w:
        return []
    album = w.get('album')
    if not isinstance(album, list):
        return ['album must be a list of stickers']
    errors: list[str] = []
    known = _rule_known_ids(w, pack_dir)
    seen: set = set()
    for index, entry in enumerate(album):
        if not isinstance(entry, dict):
            errors.append(f'the album entry at position {index} must be an object')
            continue
        sid = entry.get('id')
        if not isinstance(sid, str) or not sid.strip():
            errors.append(f'the album entry at position {index} '
                          'needs a non-empty string id')
            continue
        if sid in seen:
            errors.append(f"two stickers share the id '{sid}' - "
                          'sticker ids must be unique')
            continue
        seen.add(sid)
        name = entry.get('name')
        if not isinstance(name, str) or not 1 <= len(name) <= ALBUM_NAME_LIMIT:
            errors.append(f"sticker '{sid}' needs a name of 1 to "
                          f'{ALBUM_NAME_LIMIT} characters')
        kind = entry.get('kind')
        if kind not in ALBUM_KINDS:
            errors.append(f"sticker '{sid}' kind must be 'open', "
                          "'riddle' or 'secret'")
        riddle = entry.get('riddle')
        if kind == 'riddle':
            if not isinstance(riddle, str) or not riddle.strip():
                errors.append(f"sticker '{sid}' is a riddle and needs "
                              "a non-empty 'riddle'")
        elif 'riddle' in entry:
            errors.append(f"sticker '{sid}' has a riddle but is not "
                          'a riddle sticker')
        if 'shine' in entry and entry.get('shine') not in ALBUM_SHINES:
            errors.append(f"sticker '{sid}' shine must be 'paper', "
                          "'foil' or 'holo'")
        if 'when' not in entry:
            errors.append(f"sticker '{sid}' needs a 'when' event")
        else:
            errors.extend(_album_when_errors(sid, entry['when'], known))
    return errors


def _iter_conditions(node):
    """Yield every condition inside a rule's `if`, through `not` and `all-of`."""
    if isinstance(node, list):
        for sub in node:
            yield from _iter_conditions(sub)
    elif isinstance(node, dict):
        yield node
        if len(node) == 1 and 'not' in node:
            yield from _iter_conditions(node['not'])
        if len(node) == 1 and 'all-of' in node:
            yield from _iter_conditions(node['all-of'])


def rules_notes(w: dict, pack_dir: Path | None = None) -> list[str]:
    """Two warnings a pack can carry WITHOUT failing validation.

    Deliberately NOT called from validate() or cmd_validate: these
    are notes for a pack author, not errors. A pack with neither
    passes `norns validate` untouched.

    - a claim someone believes that no rule ever makes true or false
      in play: the belief starts and can never move;
    - a belief nothing can ever read: no rule's conditions test it.

    A belief is tracked as the (person, claim) pair. Deciding whether
    two *different* condition lists might overlap in play is not
    attempted here - only what the rules literally say.
    """
    if not any(k in w for k in ('flags', 'claims', 'people', 'rules')):
        return []
    notes: list[str] = []
    rules = w.get('rules') if isinstance(w.get('rules'), list) else []
    people = w.get('people') if isinstance(w.get('people'), dict) else {}
    changed_claims: set = set()   # claims some rule action touches
    born: set = set()             # (person, claim) pairs some rule creates
    read: set = set()             # (person, claim) pairs some condition tests
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if isinstance(rule.get('if'), list):
            for cond in _iter_conditions(rule['if']):
                if not isinstance(cond, dict):
                    continue
                for verb in ('believes', 'not-believes'):
                    payload = cond.get(verb)
                    if isinstance(payload, dict):
                        who, claim = payload.get('who'), payload.get('claim')
                        if isinstance(who, str) and isinstance(claim, str):
                            read.add((who, claim))
        then = rule.get('then')
        if not isinstance(then, list):
            continue
        for action in then:
            if not isinstance(action, dict) or len(action) != 1:
                continue
            key = next(iter(action))
            payload = action[key]
            if not isinstance(payload, dict):
                continue
            claim = payload.get('claim')
            if not isinstance(claim, str):
                continue
            if key in ('believes', 'stops-believing'):
                changed_claims.add(claim)
                if key == 'believes' and isinstance(payload.get('who'), str):
                    born.add((payload['who'], claim))
            elif key == 'tells':
                changed_claims.add(claim)
                if isinstance(payload.get('to'), str):
                    born.add((payload['to'], claim))
    declared: set = set()
    for pid, spec in people.items():
        if isinstance(spec, dict) and isinstance(spec.get('believes'), list):
            for claim in spec['believes']:
                if isinstance(claim, str):
                    declared.add((pid, claim))
    for pid, claim in sorted(declared):
        if claim not in changed_claims:
            notes.append(f"claim '{claim}', believed by '{pid}', is never made "
                         'true or false by any rule in play')
        if (pid, claim) not in read:
            notes.append(f"'{pid}' believes '{claim}' but no rule's conditions "
                         'ever read that belief')
    for pid, claim in sorted(born - declared):
        if (pid, claim) not in read:
            notes.append(f"a rule sets '{pid}' to believe '{claim}' but no rule's "
                         'conditions ever read that belief')
    return notes


def _engine_tiles_dir() -> Path | None:
    """The engine's own ground pictures, found the way the woven
    player finds web/packaged.html: the first candidate whose sibling
    `art/tiles/` directory exists. None when the engine's own web tree
    cannot be resolved at all."""
    from .cli import _template_candidates

    for candidate in _template_candidates():
        tiles = candidate.parent / 'art' / 'tiles'
        if tiles.is_dir():
            return tiles
    # NOTE: an engine tile directory that cannot be found is not a pack
    # error; the caller skips the engine-set half of the check rather
    # than failing every pack.
    return None


def _region_dirs(pack: Path, w: dict, region_geo: dict) -> dict:
    """Map each region name to its on-disk directory.

    Mirrors the loader: the flat shape is the pack root (one implicit
    region); the acts shape is <pack>/acts/<act-dir>/<region>, with
    the act directory resolved by its declared `id` through
    cli._act_dir_for, so an act whose id differs from its directory
    name still resolves. A region whose act directory cannot be
    resolved maps to None - it is read as having no tiles/, never a
    crash.
    """
    from .cli import _act_dir_for, _has_subdir, _inside

    names = list(region_geo)
    if not _has_subdir(pack, 'acts'):
        # NOTE: a flat pack keeps its ground at the pack root; that is
        # the flat-shape equivalent of a region's tiles/ directory.
        return {r: pack for r in names}
    acts = w.get('acts')
    if isinstance(acts, list) and acts and isinstance(acts[0], dict):
        act_id = acts[0].get('id')
    else:
        # The unified load_pack shape carries the act directory name;
        # _act_dir_for accepts it as its own id.
        act_id = w.get('_act_id')
    act_dir = _act_dir_for(pack, act_id)
    # NOTE: region_geo covers the first act's regions (the only ones
    # maplab reads), so one act directory is enough.
    out: dict = {}
    for r in names:
        region = None
        if act_dir is not None and isinstance(r, str) and r and '\0' not in r:
            # the region name comes from pack data: resolve it inside the act directory or not at all
            found = _inside(os.path.realpath(act_dir), r)
            region = Path(found) if found is not None else None
        out[r] = region
    return out


def _tile_errors(pack: Path, w: dict, region_geo: dict) -> list[str]:
    """Every tile-picture problem for a pack on disk (empty = good).

    A region that brings a `tiles/` directory opts into strict checks:
    every explicit legend `tile` must resolve to the region's own
    pictures or the engine set, every numbered variant must sit in an
    unbroken sequence, and every non-dot file must be .webp or .png.
    A region with no `tiles/` keeps the silent engine fallback, so
    existing packs validate green.
    """
    from .cli import _inside
    from .world import (_TILE_GRID_RE, _TILE_SUFFIXES, _TILE_VARIANT_RE,
                        TILE_GRID_MAX, _discover_tiles, tile_grid)

    engine_tiles = _engine_tiles_dir()
    engine_real = os.path.realpath(engine_tiles) if engine_tiles is not None else None
    pack_real = os.path.realpath(pack)
    dirs = _region_dirs(pack, w, region_geo)
    errors: list[str] = []
    for rname, geo in region_geo.items():
        if not isinstance(geo, dict):
            continue
        region_dir = dirs.get(rname)
        if region_dir is None:
            # NOTE: no resolvable act directory means no tiles/ to read;
            # skip the region rather than infer one.
            continue
        region_real = os.path.realpath(region_dir)
        if region_real != pack_real and not region_real.startswith(pack_real + os.sep):
            continue  # a region that resolves outside the pack is never read
        tiles_real = _inside(region_real, 'tiles')
        if tiles_real is None or not os.path.isdir(tiles_real):
            # Compatibility: a region with no tiles/ is unchanged.
            continue
        tiles_dir = Path(tiles_real)
        legend = geo.get('legend')
        legend = legend if isinstance(legend, dict) else {}
        known = set(_discover_tiles(tiles_dir))
        for ch, spec in legend.items():
            if not isinstance(spec, dict):
                continue
            name = spec.get('tile')
            if not (isinstance(name, str) and name):
                continue
            if name in known:
                continue
            if engine_real is None:
                # NOTE: no engine set to consult; the unknown-name check
                # is skipped, never failed (see _engine_tiles_dir).
                continue
            # the tile name comes from pack data: only a plain name inside the engine set can match
            engine_pic = None if '\0' in name else _inside(engine_real, f'{name}.webp')
            if engine_pic is not None and os.path.isfile(engine_pic):
                continue
            errors.append(
                f"region '{rname}': symbol '{ch}' names tile '{name}', which "
                f"is in neither the region's tiles/ nor the engine's art")
        # NOTE: a file the loader cannot read is a pack-authoring error
        # (the more restrictive reading). Dotfiles stay ignored exactly
        # as the loader ignores them.
        variants: dict[str, set[int]] = {}
        grids: set[str] = set()
        for f in sorted(tiles_dir.rglob('*')):
            if not f.is_file():
                continue
            rel = f.relative_to(tiles_dir)
            if any(part.startswith('.') for part in rel.parts):
                continue
            if f.suffix.lower() not in _TILE_SUFFIXES:
                errors.append(
                    f"region '{rname}': tiles/{rel.as_posix()} is not a tile "
                    f"picture (.webp or .png only)")
                continue
            stem = f.name[: -len(f.suffix)]
            if _TILE_GRID_RE.match(stem):
                grid = tile_grid(stem)
                if grid is None:
                    errors.append(
                        f"region '{rname}': tiles/{rel.as_posix()} is not a valid grid picture "
                        f"(each side 1..{TILE_GRID_MAX}, at least 2 cells; e.g. wood.grid3x3.webp)")
                else:
                    grids.add(grid[0])
                continue
            m = _TILE_VARIANT_RE.match(stem)
            if m:
                base, num = m.group('base'), int(m.group('num'))
            else:
                # NOTE: the unnumbered picture is variant 1; a stray
                # `name.1` names the same slot, so neither is a gap.
                base, num = stem, 1
            variants.setdefault(base, set()).add(num)
        for base in sorted(grids & set(variants)):
            errors.append(
                f"region '{rname}': tile '{base}' has a grid picture AND other pictures; "
                f"the grid is the one drawn and the others are ignored - remove one")
        for base, nums in variants.items():
            # NOTE: variant 1 is the unnumbered file and is optional, so
            # the numbered sequence the player walks begins at 2. Only a
            # hole in 2, 3, ... is a gap; a name that simply starts at 2
            # is whole, and the absence of 1 is never a gap.
            missing = sorted(n for n in range(2, max(nums) + 1)
                             if n not in nums)
            if missing:
                # NOTE: one error per tile name, naming the first hole in
                # the numbered sequence (variant 1 is optional).
                errors.append(
                    f"region '{rname}': tile '{base}' has a variant gap - "
                    f"variant {missing[0]} is missing")
    return errors


def _edge_errors(pack: Path | None, w: dict, region_geo: dict) -> list[str]:
    """Every bad legend `edges` (empty = good, or no legend names any).

    `"edges": "<name>"` asks the player to blend a ground into its
    neighbours with ONE 4 x 4 picture in the region's own `tiles/`
    (`cli._edges_for_legend`). The value must be a plain picture name;
    with the pack on disk it must also be exactly one plain picture there
    (not variants, not a grid) - the engine set has no edges, so nothing
    else could be drawn. Each sentence names the region and the symbol.
    """
    from .cli import _inside
    from .world import _discover_tiles, tile_grid

    dirs = _region_dirs(pack, w, region_geo) if pack is not None else {}
    pack_real = os.path.realpath(pack) if pack is not None else None
    errors: list[str] = []
    for rname, geo in region_geo.items():
        legend = geo.get('legend') if isinstance(geo, dict) else None
        if not isinstance(legend, dict):
            continue
        found = None
        for ch, spec in legend.items():
            if not isinstance(spec, dict) or 'edges' not in spec:
                continue
            name = spec['edges']
            if not isinstance(name, str) or not name.strip() or '\0' in name or '/' in name:
                errors.append(
                    f"region '{rname}': symbol '{ch}' has edges {json.dumps(name)}, which is not a "
                    f"picture name; write \"edges\": \"<name>\" for a 4 x 4 sheet <name>.webp in "
                    f"the region's tiles/")
                continue
            if pack is None:
                continue
            if found is None:
                found = {}
                region_dir = dirs.get(rname)
                if region_dir is not None:
                    region_real = os.path.realpath(region_dir)
                    if region_real == pack_real or region_real.startswith(pack_real + os.sep):
                        tiles_real = _inside(region_real, 'tiles')
                        if tiles_real is not None and os.path.isdir(tiles_real):
                            found = _discover_tiles(Path(tiles_real))
            pictures = found.get(name, [])
            if not pictures:
                errors.append(
                    f"region '{rname}': symbol '{ch}' names edges '{name}', which is not a "
                    f"picture in the region's tiles/ (edges come from the pack only: "
                    f"tiles/{name}.webp, one 4 x 4 sheet)")
            elif len(pictures) > 1 or tile_grid(Path(pictures[0]).name.rsplit('.', 1)[0]):
                errors.append(
                    f"region '{rname}': symbol '{ch}' names edges '{name}', which must be ONE "
                    f"picture (tiles/{name}.webp, a 4 x 4 sheet), not variants or a grid")
    return errors


def _people_block_errors(w: dict) -> list[str]:
    """`player.people_block`, when present, is true or false (empty = good or absent)."""
    player = w.get('player')
    if isinstance(player, dict) and 'people_block' in player and not isinstance(player['people_block'], bool):
        return ['player.people_block must be true or false']
    return []


def _sprite_scale_errors(w: dict, pack_dir) -> list[str]:
    """Plain problems with `player.sprite_scale` (empty = good or absent). Reads the block load_pack already holds; a key is a
    picture when `player.sprites` lists it or the same resolution finds
    its file by name (ADR 0010 B0), so a key naming nothing at all is
    refused as one plain sentence."""
    import math

    player = w.get('_player')
    if not isinstance(player, dict) or 'sprite_scale' not in player:
        return []
    scales = player['sprite_scale']
    if not isinstance(scales, dict):
        return ["player.sprite_scale must be an object like {\"hearth-cat\": 0.5}"]
    from .cli import resolve_sprites

    known = resolve_sprites(Path(pack_dir), w)
    errors: list[str] = []
    for name, v in scales.items():
        if name not in known:
            errors.append(f"player.sprite_scale names '{name}', which has no picture in player.sprites")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0.2 <= v <= 2.0:
            errors.append(f"player.sprite_scale for '{name}' must be a number from 0.2 to 2 (1 is the standard size)")
    return errors


def _transition_lock_errors(index: int, t: dict, known: dict) -> list[str]:
    """One plain sentence per problem with a transition's optional
    `requires` / `locked_text` (design/gates-and-guardians.md, step 1).

    `requires` names exactly one key, `item` or `flag`, and must point
    at something the pack declares; any other shape is one sentence
    naming `requires`. `locked_text` is one plain sentence of 1 to
    200 characters. A transition with neither key gets nothing.
    """
    errors: list[str] = []
    if 'requires' in t:
        req = t['requires']
        if not isinstance(req, dict):
            errors.append(
                f'transition {index} requires must be an object such as '
                '{"item": "brass-ring"}')
        else:
            held = [k for k in ('item', 'flag') if k in req]
            unknown = [k for k in req if k not in ('item', 'flag')]
            if len(held) != 1:
                errors.append(
                    f'transition {index} requires must hold exactly one '
                    'of item or flag')
            elif unknown:
                errors.append(
                    f"transition {index} requires has an unknown key "
                    f"'{unknown[0]}'; use item or flag")
            else:
                key = held[0]
                val = req[key]
                if not isinstance(val, str) or not val:
                    noun = 'an item id' if key == 'item' else 'a flag name'
                    errors.append(
                        f'transition {index} requires.{key} must be {noun}')
                elif key == 'item' and val not in known['items']:
                    errors.append(
                        f"transition {index} requires names unknown "
                        f"item '{val}'")
                elif key == 'flag' and val not in (known['flags'] or set()):
                    errors.append(
                        f"transition {index} requires names unknown "
                        f"flag '{val}'")
    if 'locked_text' in t:
        text = t['locked_text']
        if not isinstance(text, str) or not 1 <= len(text) <= 200:
            errors.append(
                f'transition {index} locked_text must be one plain '
                'sentence of 1 to 200 characters')
    return errors


def _door_tile_problem(field: str, rname: str, at,
                       rows: list, legend: dict) -> str | None:
    """One plain sentence for a door tile that is not a walkable tile,
    or None when the tile is a fine [x, y].

    Shared by the first act's transition check (which prefixes
    `transition N`) and the per-act checks (which prefix the act's id),
    so both act 1 and act 2 read the same way.
    """
    if (not isinstance(at, (list, tuple)) or len(at) != 2
            or not all(isinstance(v, (int, float)) for v in at)):
        return f"{field} in region '{rname}' must be a tile [x, y]"
    x, y = int(at[0]), int(at[1])
    ok = _map_tile_walkable(rows, legend, x, y)
    if ok is None:
        return f"{field} ({x},{y}) is off the map of region '{rname}'"
    if not ok:
        return f"{field} ({x},{y}) is on a solid tile in region '{rname}'"
    return None


def _enemy_drop_errors(where: str, drops, declared) -> list[str]:
    """Why a killed enemy hands the player none of what it wrote (empty = fine).

    The enemy face of the one rule: a `drops` line the bake cannot pay is
    a fight the player wins and walks away from with nothing, because the
    weave drops every id that is not a catalog item and the bag refuses
    one twice over (`placeDrops` and `bagAdd`), so the floor never even
    shows the marker.

    What a real item is, what a legal pack looks like and the exact words
    of the refusal are all `library._drop_payout_errors`'s, shared with
    the chest (`library._chest_drop_errors`) and the Blueprint and Section
    families, so the three surfaces cannot drift into three opinions. This
    function is only the door for the enemy: `declared` is the catalog the
    player will really get, read by the caller off the pack's own
    `world.json` through the same `library._declared_items` the chest
    check uses, and an enemy that writes no `drops` at all carries nothing,
    which is a legitimate monster.
    """
    return library._drop_payout_errors(where, "the kill", drops, declared)


def _speaker_specs(w: dict) -> dict:
    """The speakers the weave places: the first act's, else the pack's."""
    acts = w.get('acts')
    first = acts[0] if isinstance(acts, list) and acts and isinstance(acts[0], dict) else {}
    specs = first.get('speakers') if isinstance(first.get('speakers'), dict) else w.get('speakers')
    return specs if isinstance(specs, dict) else {}


def _region_prop_errors(w: dict, rname: str, geo: dict, pack_dir: Path,
                        region_dir: Path | None, transitions: list,
                        first_region: str | None) -> list[str]:
    """Each prop of one region: a real picture, a footprint on the map, a
    well-formed block, a frame count the picture divides into, and no
    speaker, start, wake point or door standing on a blocked cell."""
    from .cli import _prop_picture_path

    props = geo.get('props', [])
    if not isinstance(props, list):
        return [f"region '{rname}' props must be a list"]
    errors: list[str] = []
    rows = geo.get('map') or []
    height, width = len(rows), (len(rows[0]) if rows else 0)
    for i, p in enumerate(props):
        if not isinstance(p, dict):
            errors.append(f"region '{rname}' prop {i} must be an object with pic and at")
            continue
        pic = p.get('pic')
        tag = f"region '{rname}' prop {i} '{pic}'"
        pic_path = None
        if not isinstance(pic, str) or not pic or pic in ('.', '..') \
                or any(c in pic for c in '/\\\0'):
            errors.append(f"{tag}: pic must be a picture's file name with no folder")
        else:
            pic_path = _prop_picture_path(pack_dir, region_dir, pic)
            if pic_path is None:
                errors.append(f"{tag}: no picture '{pic}.webp' or '{pic}.png' "
                              f"in props/ here or at the pack root")
        at = p.get('at')
        if not _whole_pair(at):
            errors.append(f'{tag}: at must be [x, y] whole numbers')
            at = None
        size = p.get('size', [1, 1])
        if not _whole_pair(size, 1):
            errors.append(f'{tag}: size must be [width, height] whole numbers of at least 1')
            size = None
        frames = p.get('frames', 1)
        if not (_is_whole(frames) and PROP_FRAMES_MIN <= frames <= PROP_FRAMES_MAX):
            errors.append(f'{tag}: frames must be a whole number from '
                          f'{PROP_FRAMES_MIN} to {PROP_FRAMES_MAX}')
            frames = 1
        if p.get('layer', 'stand') not in ('stand', 'ground'):
            errors.append(f'{tag}: layer must be "stand" (the default) or "ground"')
        fps = p.get('fps', PROP_FPS_DEFAULT)
        if not (_is_whole(fps) and PROP_FPS_MIN <= fps <= PROP_FPS_MAX):
            errors.append(f'{tag}: fps must be a whole number from '
                          f'{PROP_FPS_MIN} to {PROP_FPS_MAX}')
        if at is not None and size is not None and rows:
            if at[0] + size[0] > width or at[1] + size[1] > height:
                errors.append(f'{tag}: its {size[0]}x{size[1]} footprint at {at[0]},{at[1]} '
                              f'leaves the map ({width}x{height})')
        block = p.get('block')
        if block is not None and size is not None:
            shaped = (isinstance(block, list) and len(block) == size[1]
                      and all(isinstance(r, str) and len(r) == size[0]
                              and set(r) <= {'#', '.'} for r in block))
            if not shaped:
                errors.append(f"{tag}: block must be {size[1]} rows of {size[0]} "
                              f"characters, '#' blocked and '.' open")
        if pic_path is not None:
            dims = _picture_size(str(pic_path))
            if dims is not None and dims[0] % frames:
                errors.append(f'{tag}: the picture is {dims[0]} px wide, which is not '
                              f'a whole number of {frames} frames')

    def _placed(where, what):
        if not _whole_pair(where):
            return
        i = prop_at(props, where[0], where[1])
        if i is not None:
            errors.append(f"region '{rname}' prop {i} '{props[i].get('pic')}' covers "
                          f"{what} at {where[0]},{where[1]}")

    for key, spec in _speaker_specs(w).items():
        if isinstance(spec, dict) and spec.get('region', first_region) == rname:
            _placed(spec.get('at'), f"speaker '{key}'")
    if rname == first_region:
        _placed(w['town'].get('hero_start'), "the hero's start")
    player = w.get('_player') or w.get('player')
    wake = player.get('wake') if isinstance(player, dict) else None
    if isinstance(wake, dict) and wake.get('region') == rname:
        _placed(wake.get('at'), 'the wake point')
    for ti, t in enumerate(transitions):
        if not isinstance(t, dict):
            continue
        if t.get('from') == rname:
            _placed(t.get('at'), f'the door of transition {ti}')
        if t.get('to') == rname:
            _placed(t.get('to_at'), f'the arrival of transition {ti}')
    return errors


def _book_prop_errors(books: list, region_geo: dict) -> list[str]:
    """Each map book whose tile a region's prop blocks."""
    errors: list[str] = []
    for b in books:
        if not isinstance(b, dict) or b.get('found') != 'map':
            continue
        region = b.get('region') or 'town'
        geo = region_geo.get(region)
        if not isinstance(geo, dict) or not _whole_pair(b.get('at')):
            continue
        props = geo.get('props') or []
        i = prop_at(props, b['at'][0], b['at'][1])
        if i is not None:
            errors.append(f"region '{region}' prop {i} '{props[i].get('pic')}' covers "
                          f"the book '{b.get('title') or b.get('id')}' at "
                          f"{b['at'][0]},{b['at'][1]}")
    return errors


def _region_enemy_errors(rname: str, geo: dict, levels_mode: bool,
                         act_id: str | None = None,
                         declared: set[str] | None = None) -> list[str]:
    """Every problem with one region's `enemies` (empty = good).

    Shared by the first act's region check and the per-act checks. With
    `act_id` None the sentences are exactly the first act's (each names
    the enemy's display name); with an act id every sentence carries
    `act '<id>'` and names the enemy by its id, so a hazard in act 2 is
    findable. The checks are the same either way: a walkable tile, real
    numbers, ids unique within the region, `xp` only in levels mode, and a
    `drops` line that hands the player something (`declared` is the
    catalog it is read against, and None means there was none to read
    against, so the check is skipped rather than wrong - see
    `_enemy_drop_errors`).
    """
    errors: list[str] = []
    rows = geo.get('map') or []
    legend = geo.get('legend') or {}
    listed = geo.get('enemies')
    if listed is None:
        return errors
    prefix = f"act '{act_id}' " if act_id is not None else ''
    if not isinstance(listed, list):
        errors.append(f"{prefix}region '{rname}' enemies must be a list")
        return errors
    seen_ids: set = set()
    for i, e in enumerate(listed):
        if not isinstance(e, dict):
            errors.append(f"{prefix}region '{rname}' enemy {i} must be an object")
            continue
        eid = e.get('id')
        if act_id is not None:
            who = str(eid or e.get('name') or f'#{i}')
        else:
            who = str(e.get('name') or eid or f'#{i}')
        if not str(eid or '').strip():
            errors.append(f"{prefix}enemy '{who}' in region '{rname}' needs an id")
        elif eid in seen_ids:
            errors.append(
                f"{prefix}enemy '{who}' in region '{rname}' repeats the id '{eid}'")
        else:
            seen_ids.add(eid)
        if not str(e.get('name', '')).strip():
            errors.append(f"{prefix}enemy '{who}' in region '{rname}' needs a name")
        at = e.get('at')
        if (not isinstance(at, (list, tuple)) or len(at) != 2
                or not all(isinstance(v, (int, float))
                           and not isinstance(v, bool) for v in at)):
            errors.append(
                f"{prefix}enemy '{who}' in region '{rname}' needs a tile [x, y]")
        else:
            x, y = int(at[0]), int(at[1])
            ok = _map_tile_walkable(rows, legend, x, y)
            if ok is None:
                errors.append(
                    f"{prefix}enemy '{who}' in region '{rname}' at ({x},{y}) "
                    f"is off the map")
            elif not ok:
                errors.append(
                    f"{prefix}enemy '{who}' in region '{rname}' at ({x},{y}) "
                    f"stands on a solid tile")
        for stat in ('hp', 'atk'):
            v = e.get(stat)
            if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                errors.append(
                    f"{prefix}enemy '{who}' in region '{rname}' needs a "
                    f"positive {stat}")
        # `xp` names the enemy id (not the display name), so the
        # author can find the exact contract entry to fix.
        xp = e.get('xp')
        if xp is not None:
            if not levels_mode:
                errors.append(
                    f"{prefix}enemy '{eid}' in region '{rname}' may only carry "
                    "'xp' in levels mode")
            elif not _is_whole(xp) or xp < 0:
                errors.append(
                    f"{prefix}enemy '{eid}' in region '{rname}' needs a whole "
                    "'xp' of 0 or more")
        # A `drops` line the kill cannot pay out is named by the enemy's
        # display name, like every other sentence here: an author reads
        # "a cellar rat", not an id, when they go looking for it.
        errors.extend(_enemy_drop_errors(
            f"{prefix}enemy '{who}' in region '{rname}'",
            e.get('drops', library.NO_DROPS), declared))
        # What the blow IS and what it leaves behind (vefr#497): a
        # `dmg_type` the hero's resistances may turn aside, and a
        # `burns` block that leaves the hero burning for a count of
        # turns. Both are optional and named the same way.
        errors.extend(enemy_element_errors(
            f"{prefix}enemy '{who}' in region '{rname}'", e))
    return errors


def validate(w: dict, pack_dir: Path | None = None) -> list[str]:
    """Every geometry check. Returns a list of problems (empty = good).

    Accepts both shapes:

      Flat shape: w['town'] is the town block directly.
      Acts shape: w['acts'][0]['_town_legacy'] holds the town block
        (preserved for backward compat) and the act's speakers live
        at w['acts'][0]['speakers']. The unified shape produced by
        load_pack() sets w['town'] and w['speakers'] explicitly.
    """
    errors: list[str] = []
    # The optional Blueprint (`docs/adr/0008-blueprint-format.md`): when
    # the pack is on disk, its source/stale check runs beside the rest.
    # Lazy so a pack with neither `blueprint.json` nor its lock reads
    # nothing new (the module's two existence checks), and so importing
    # maplab never reaches back into blueprint at import time.
    if pack_dir is not None:
        from . import blueprint
        errors.extend(blueprint.check_errors(pack_dir))
    if 'town' not in w and 'acts' in w and w['acts']:
        # Acts shape: synthesize the flat keys the rest of the
        # validator reads, so the same code path works for both.
        act = w['acts'][0]
        w = {
            **w,
            'town': act.get('_town_legacy', {}),
            'speakers': act.get('speakers', w.get('speakers', {})),
        }
    # The pack's grammars (optional): checked first so a broken
    # grammar is reported even when the map is wrong too.
    errors.extend(grammar_errors(w.get('grammars', {})))
    # The item catalog's optional `light` and `slot`/`mods` fields
    # (design/equipment.md, step 1): checked here so a broken torch or a
    # bad slot is a pack-authoring error, not a silent no-op in play.
    # `rarity`/`traits`/`roll` (ADR 0017) are checked beside them, for the
    # same reason: a roll the pack cannot draw from is a silent no-op.
    items = w.get('items')
    if isinstance(items, dict):
        key_ids = _door_key_items(w)
        spell_ids = spell_ids_of(w)
        # A granted verb is a verb of this pack's own, so the `uses-verb`
        # rules are checked against the set the catalog itself hands over.
        verb_ids = pack_verbs(w)
        for iid, spec in items.items():
            if isinstance(spec, dict):
                errors.extend(item_light_errors(iid, spec))
                errors.extend(item_slot_errors(iid, spec, key_ids))
                errors.extend(item_roll_errors(iid, spec))
                errors.extend(item_spell_errors(iid, spec, spell_ids))
                errors.extend(item_grants_errors(iid, spec, verb_ids))
    # The pack's optional identify service (ADR 0017, T3 slice 2): the
    # speaker that reads things, checked beside the other optional
    # fields so a service that names no place to stand is an authoring
    # error rather than a silence in play. A pack that declares none
    # gets nothing here and plays exactly as it did.
    errors.extend(identify_errors(w))
    # The catalog every `drops` is paid from: what the player will really
    # get, read off the pack's own `world.json` and through
    # `library._declared_items` - the same file, the same read and the
    # same shape the chest check above already uses, so an `items` entry
    # with no `name` is not an id a drop can hand over. A pack directory
    # that cannot be read is None, and every drop check below is then
    # skipped rather than wrong.
    declared_items = _pack_declared(pack_dir) if pack_dir is not None else None
    # The pack's optional rules/flags/claims/people catalog: checked
    # beside the other optional catalogs so a broken rule is a
    # pack-authoring error, not a surprise in play. A pack that
    # declares none of the four keys gets nothing here.
    errors.extend(rules_errors(w, pack_dir))
    # The pack's optional sticker album (design/album.md), checked
    # beside the rules it names events from. A pack that declares no
    # album gets nothing here.
    errors.extend(album_errors(w, pack_dir))
    # The pack's optional story status (vefr #339): the one place a
    # pack says which of its words are still drafts. A `status` written
    # as anything but `draft`/`approved` is a pack-authoring error, read
    # off the pack's own files because the key lives on five different
    # surfaces. A pack that writes no `status` says nothing here.
    if pack_dir is not None:
        from . import story_status
        errors.extend(story_status.errors(pack_dir))
    # The pack's optional skin (design/ui-skin.md), checked beside the
    # other optional catalogs. A pack that declares none gets nothing.
    errors.extend(skin_errors(w, pack_dir))
    # The pack's optional walk sheets (design/pack-art-proposal.md,
    # phase B), checked beside the other optional catalogs. A pack that
    # ships no `*.sheet.json` gets nothing here.
    errors.extend(sprite_sheet_errors(pack_dir))
    # The pack's optional growth block (design/growth.md), checked
    # beside the other optional catalogs. A pack that declares none
    # gets nothing here.
    errors.extend(growth_errors(w))
    # The pack's optional spells block (ADR 0018): the schools it teaches,
    # the spells in them, and the level each is learned at. Checked beside
    # the other optional blocks. A pack that declares none gets nothing
    # here and plays exactly as it always did.
    errors.extend(spells_errors(w))
    # The pack's optional saves block (docs/adr/0009-rule-saves.md),
    # checked beside the other optional catalogs. A pack that declares
    # none gets nothing here.
    errors.extend(saves_errors(w))
    # The pack's optional sound block (docs/guides/rulesets.md),
    # checked beside the other optional catalogs. A pack that declares
    # none gets nothing here.
    errors.extend(sound_errors(w))
    # The pack's optional time block: the Rest action, the rail lock and
    # the phase save. A pack that declares none gets nothing here and
    # keeps the free phase rail and a phase in memory only, as before.
    errors.extend(time_errors(w))
    # The pack's optional music block (vefr #502), checked beside the
    # other optional catalogs. A pack that declares none gets nothing
    # here, and a pack that does changes nothing about its sound.
    errors.extend(music_errors(w))
    errors.extend(display_errors(w))
    errors.extend(bag_errors(w))
    # The pack's optional recipes (E2, mending): two carried things that
    # become one. A pack that declares none gets nothing here and its
    # bag plays exactly as it always did.
    errors.extend(recipes_errors(w, pack_dir))
    errors.extend(stakes_errors(w, pack_dir))
    # The pack's optional player words (vefr #259): the pack's own
    # wording for the action-critical lines the engine speaks. A pack
    # that declares none gets nothing here and says nothing else about
    # it - the engine's own words are its own business.
    errors.extend(player_words_errors(w))
    # The pack's optional resistances (vefr#497, slice 1): the hero's
    # own `resist`/`immune`, checked beside the other optional player
    # words. A pack that declares neither bakes nothing and fights
    # every blow untyped, exactly as before.
    errors.extend(element_errors(w))
    # The pack's optional display block (pixel art): a pack that declares
    # none is drawn exactly as before.
    errors.extend(display_errors(w))
    # The pack's optional descent block (slice E1): the run seed, the
    # tile the descent starts from and its Sections. A pack that declares
    # none gets nothing here.
    errors.extend(descent_errors(w, pack_dir))
    # The pack's optional town-states block (ADR 0015, E8c): the regions
    # whose look follows a story flag. A pack that declares none gets
    # nothing here and plays every region as it always did.
    errors.extend(town_states_errors(w))
    # The pack's optional affix list and Section packs (ADR 0014), read
    # off the disk beside the blocks above: one `affixes.json` at the
    # root and one `sections/<id>.json` per Section. `shapes` speaks for
    # both, and this is the door that runs it. A pack that ships neither
    # gets nothing here.
    if pack_dir is not None:
        errors.extend(section_errors(pack_dir))
    # The pack's optional scenarios (ADR 0016, slice P2): one
    # `scenarios/<name>.json` per named game state, checked against this
    # pack's regions, descent and items. A pack that ships none gets
    # nothing here.
    if pack_dir is not None:
        from . import scenarios
        errors.extend(scenarios.errors(w, pack_dir))
    town = w['town']
    m = town['map']
    legend = town['legend']

    widths = {len(r) for r in m}
    if len(widths) != 1:
        errors.append(f'map rows are not rectangular: widths {sorted(widths)}')
        return errors

    used = set(''.join(m))
    missing_legend = sorted(used - set(legend))
    if missing_legend:
        errors.append(f'map chars missing from legend: {missing_legend}')

    start = tuple(town['hero_start'])
    if not walkable(w, *start):
        errors.append(f'hero_start {start} is not walkable')

    seen = reach(w, start)

    def near_open(x: int, y: int) -> bool:
        """A poi is usable if a walkable tile sits within the renderer's
        poiAt radius (2.4) of the label."""
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if (dx * dx + dy * dy) ** 0.5 <= 2.4 and walkable(w, x + dx, y + dy):
                    return True
        return False

    for key in town.get('pois', {}):
        try:
            x, y = (int(v) for v in str(key).split(','))
        except ValueError:
            # A name-keyed poi ({"the shed": [3, 1]}) used to crash the whole check with a traceback.
            errors.append(f'poi key {key!r} must be "x,y" with the label as its value, '
                          f'such as {{"3,1": "the shed"}}')
            continue
        if not near_open(x, y):
            errors.append(f'poi {key} ({town["pois"][key]}) has no reachable tile nearby')

    for x in range(len(m[0])):
        for y in range(len(m)):
            if m[y][x] in ('d', 'D') and (x, y) not in seen:
                errors.append(f'door at ({x},{y}) is unreachable')

    first_region = w.get('_region')
    for s in w.get('speakers', {}).values():
        if first_region and s.get('region', first_region) != first_region:
            continue   # a speaker of another region is checked on that map
        at = tuple(s['at'])
        if not walkable(w, *at):
            errors.append(f'speaker {s["name"]} stands on solid ground at {at}')
        elif at not in seen:
            errors.append(f'speaker {s["name"]} at {at} is unreachable')
        if set(s.get('seeds', {})) != set(w['phases']):
            errors.append(f'speaker {s["name"]} seeds do not cover every phase')

    if not town.get('sanctuary_tiles'):
        errors.append('no sanctuary tiles - the world needs one safe place')

    water = town.get('water_by_phase', {})
    if set(water) != set(w['phases']):
        errors.append('water_by_phase does not cover every phase')
    for x, y in town.get('flood_tiles', []):
        if not (0 <= y < len(m) and 0 <= x < len(m[0])):
            errors.append(f'flood tile ({x},{y}) is out of bounds')
        elif m[y][x] == '~':
            errors.append(f'flood tile ({x},{y}) is already deep water')

    voices = w.get('voices', {})
    stefna_voice = w.get('stefna_voice')
    if stefna_voice is not None:
        if stefna_voice not in voices:
            errors.append(f"stefna_voice '{stefna_voice}' does not resolve to a declared voice")

    for vkey, voice in voices.items():
        if not isinstance(voice, dict) or not str(voice.get('strike', '')).strip():
            errors.append(f"voice '{vkey}' is missing required non-empty 'strike' prompt")

    if pack_dir is not None:
        p = Path(pack_dir)
        # Helper to check if a voice file exists in acts or flat layout
        def find_voice_file(fname: str) -> bool:
            if not fname:
                return False
            basename = Path(fname).name
            acts_dir = p / 'acts'
            if acts_dir.is_dir():
                for act_dir in acts_dir.iterdir():
                    if not act_dir.is_dir():
                        continue
                    for region_dir in act_dir.iterdir():
                        if (region_dir / 'voices' / basename).exists():
                            return True
            if (p / fname).exists() or (p / 'voices' / basename).exists():
                return True
            return False

        for vkey, voice in voices.items():
            # In flat packs or acts packs, check if voice file exists on disk
            vfile = voice.get('file', f'voices/{vkey}.md') if isinstance(voice, dict) else f'voices/{vkey}.md'
            if not find_voice_file(vfile):
                errors.append(f"missing voice file for voice '{vkey}': {vfile}")

        for spec in w.get('speakers', {}).values():
            sfile = spec.get('voice_file', '')
            if not find_voice_file(sfile):
                errors.append(f'missing speaker voice file: {sfile}')

    # Pack law: each act declares how it plays (world.py contract).
    # Shape-checked here; the mechanics land with the ruleset
    # modules. A bad value is a pack authoring error, so it fails
    # validation loudly instead of silently defaulting.
    for act in w.get('acts', []):
        aid = act.get('id', '?')
        floor = act.get('floor', 'costume')
        if floor not in VALID_FLOORS:
            errors.append(f"act '{aid}' floor '{floor}' not in {list(VALID_FLOORS)}")
        tone = act.get('tone', '')
        if tone and tone not in VALID_TONES:
            errors.append(f"act '{aid}' tone '{tone}' not in {list(VALID_TONES)}")
        ruleset = act.get('ruleset', 'ambient')
        if not isinstance(ruleset, str) or not ruleset.strip():
            errors.append(f"act '{aid}' ruleset must be a non-empty string")
        for fname in ('verbs', 'enemies', 'bosses'):
            val = act.get(fname, [])
            if not isinstance(val, list):
                errors.append(f"act '{aid}' {fname} must be a list")
            elif not all(isinstance(x, str) for x in val):
                errors.append(f"act '{aid}' {fname} must be a list of strings")
        # `transitions` is the act's doors now, not a string list; the
        # shape and tiles are checked below.
        if not isinstance(act.get('transitions', []), list):
            errors.append(f"act '{aid}' transitions must be a list")

    # Cooking ruleset content (the act-1 loop): the morning is pack-
    # authored; the engine only resolves it. Orders must reference
    # real pantry ids so a served order can be checked
    # deterministically, and every ticket needs a note - the
    # customer's voice IS the order (reading them is the game).
    for act in w.get('acts', []):
        if act.get('ruleset') != 'cooking':
            continue
        aid = act.get('id', '?')
        block = act.get('cooking') or {}
        if not isinstance(block, dict):
            errors.append(f"act '{aid}' cooking block must be an object")
            continue
        pantry = block.get('pantry', [])
        pids = set()
        if not isinstance(pantry, list) or not pantry:
            errors.append(f"act '{aid}' cooking pantry must be a non-empty list")
        for item in pantry:
            if not isinstance(item, dict) or not str(item.get('id', '')).strip():
                errors.append(f"act '{aid}' pantry entries need an id")
                continue
            pids.add(item['id'])
            if not str(item.get('label', '')).strip():
                errors.append(f"act '{aid}' pantry entry '{item.get('id')}' needs a label")
        tickets = block.get('tickets', [])
        tlist = tickets if isinstance(tickets, list) else []
        if not isinstance(tickets, list) or not tickets:
            errors.append(f"act '{aid}' cooking tickets must be a non-empty list")
        for t in tlist:
            if not isinstance(t, dict) or not str(t.get('id', '')).strip():
                errors.append(f"act '{aid}' tickets need an id")
                continue
            order = t.get('order', [])
            if not isinstance(order, list) or not order:
                errors.append(f"act '{aid}' ticket '{t.get('id')}' needs a non-empty order")
            elif not all(o in pids for o in order):
                errors.append(
                    f"act '{aid}' ticket '{t.get('id')}' order references unknown pantry ids")
            if not str(t.get('note', '')).strip():
                errors.append(f"act '{aid}' ticket '{t.get('id')}' needs a note (the customer's voice)")
        length = block.get('morning_length', len(tlist))
        if not isinstance(length, int) or length < 1 or length > len(tlist):
            errors.append(f"act '{aid}' morning_length must be 1..len(tickets)")
        heads = block.get('headlines', [])
        if (not isinstance(heads, list) or len(heads) < 2
                or not all(isinstance(h, str) and h.strip() for h in heads)):
            errors.append(f"act '{aid}' cooking headlines must be at least two non-empty strings")
        if act.get('ruleset') == 'desk':
            dblock = act.get('desk') or {}
            if not isinstance(dblock, dict):
                errors.append(f"act '{aid}' desk block must be an object")
            else:
                dheads = dblock.get('headlines', [])
                if (not isinstance(dheads, list) or len(dheads) < 2
                        or not all(isinstance(h, str) and h.strip() for h in dheads)):
                    errors.append(
                        f"act '{aid}' desk headlines must be at least two non-empty strings")

    # Transitions: the act's doors between regions. A door is a tile
    # you step on in `from` that lands the hero at `to_at` in `to`.
    # Shape and door tiles are checked here; every region's *full*
    # geometry (reachability, pois, water) is still a follow-on -
    # only the first region's town is validated above.
    transitions = w.get('transitions')
    if transitions is None and w.get('acts'):
        transitions = w['acts'][0].get('transitions', [])
    transitions = transitions or []
    region_geo = region_geometry(w)

    # A pack may bring its own ground pictures under each region's
    # tiles/. That is on-disk data, so it is only checked when the pack
    # directory is known. Regions without a tiles/ directory keep the
    # silent engine fallback (the compatibility rule).
    if pack_dir is not None:
        errors.extend(_tile_errors(Path(pack_dir), w, region_geo))
        errors.extend(_sprite_scale_errors(w, Path(pack_dir)))
    errors.extend(_edge_errors(Path(pack_dir) if pack_dir is not None else None,
                               w, region_geo))
    errors.extend(_people_block_errors(w))

    def _door_tile_errors(index, field, rname, at):
        geo = region_geo.get(rname, {})
        problem = _door_tile_problem(field, rname, at,
                                     geo.get('map') or [],
                                     geo.get('legend') or {})
        if problem:
            errors.append(f'transition {index} {problem}')

    # The ids a transition's optional `requires` may name: the same
    # declared item catalog and flags the rules use.
    known = (_rule_known_ids(w, pack_dir)
             if any(isinstance(t, dict) and 'requires' in t for t in transitions)
             else {})
    for i, t in enumerate(transitions):
        if not isinstance(t, dict):
            errors.append(
                f'transition {i} must be an object with from, to, at, to_at')
            continue
        missing = [k for k in ('from', 'to', 'at', 'to_at') if k not in t]
        if missing:
            errors.append(f'transition {i} is missing {missing}')
            continue
        from_name, to_name = t['from'], t['to']
        if from_name not in region_geo:
            errors.append(
                f"transition {i} leaves region '{from_name}', which is "
                f"not a declared region")
        else:
            _door_tile_errors(i, 'at', from_name, t['at'])
        if to_name not in region_geo:
            errors.append(
                f"transition {i} enters region '{to_name}', which is "
                f"not a declared region")
        else:
            _door_tile_errors(i, 'to_at', to_name, t['to_at'])
        # The optional lock (design/gates-and-guardians.md, step 1):
        # checked after the base shape so a broken door still reports
        # its own missing/invalid fields first.
        errors.extend(_transition_lock_errors(i, t, known))

    # The region contracts' enemies: each is a named hazard with a
    # walkable tile and real numbers. Every declared region is checked
    # (not just the first); a broken one is named in plain words. An
    # optional `xp` (design/growth.md) is a whole number of at least 0
    # and belongs to `levels` mode only.
    _growth = w.get('growth')
    levels_mode = isinstance(_growth, dict) and _growth.get('mode') == 'levels'
    for rname, geo in region_geo.items():
        if isinstance(geo, dict):
            errors.extend(_region_enemy_errors(rname, geo, levels_mode,
                                               declared=declared_items))

    # The region contracts' props: pictures on the ground that block
    # walking. Only the first act's regions are baked, so only they are
    # checked here.
    if pack_dir is not None:
        prop_dirs = _region_dirs(Path(pack_dir), w, region_geo)
        first_region = next(iter(region_geo), None)
        for rname, geo in region_geo.items():
            if isinstance(geo, dict):
                errors.extend(_region_prop_errors(w, rname, geo, Path(pack_dir),
                                                  prop_dirs.get(rname), transitions,
                                                  first_region))

    # Every act after the first is checked against its OWN regions: its
    # doors must stay inside the act, land on walkable tiles, name
    # declared locks, and its enemies must be real hazards. The first
    # act is already covered by the flat checks above (its regions,
    # doors and enemies are w['regions'] / w['transitions']); running
    # the per-act checks on it too would report every first-act error
    # twice.
    acts_list = w.get('acts')
    if isinstance(acts_list, list) and len(acts_list) > 1:
        act_known = _rule_known_ids(w, pack_dir)
        # Region name -> the act that declares it, so a door that
        # crosses into another act reads as one that leaves its act.
        region_owner: dict[str, str] = {}
        for act in acts_list:
            if not isinstance(act, dict):
                continue
            for rname in (act.get('region_geo') or {}):
                region_owner.setdefault(rname, str(act.get('id', '?')))
        for act in acts_list[1:]:
            if not isinstance(act, dict):
                continue
            geo = act.get('region_geo')
            if not isinstance(geo, dict):
                continue
            aid = str(act.get('id', '?'))
            own = set(geo)
            for ti, t in enumerate(act.get('transitions', []) or []):
                if not isinstance(t, dict):
                    continue
                for field in ('from', 'to'):
                    if field not in t:
                        continue
                    rname = t[field]
                    if rname in own:
                        continue
                    if rname in region_owner:
                        errors.append(
                            f"act '{aid}' door {ti} {field} region '{rname}' "
                            f"is inside act '{region_owner[rname]}'")
                    else:
                        errors.append(
                            f"act '{aid}' door {ti} {field} region '{rname}' "
                            f"is not declared")
                for field, rkey in (('at', 'from'), ('to_at', 'to')):
                    rname = t.get(rkey)
                    if rname not in own:
                        continue
                    problem = _door_tile_problem(
                        field, rname, t.get(field),
                        geo[rname].get('map') or [],
                        geo[rname].get('legend') or {})
                    if problem:
                        errors.append(f"act '{aid}' transition {ti} {problem}")
                errors.extend(f"act '{aid}' {e}"
                              for e in _transition_lock_errors(ti, t, act_known))
            for rname, rdata in geo.items():
                if isinstance(rdata, dict):
                    errors.extend(
                        _region_enemy_errors(rname, rdata, levels_mode,
                                             act_id=aid,
                                             declared=declared_items))

    # The Library: authored books this pack keeps (library/*.md). Needs the
    # pack on disk; in-memory validation (chat drafts) has no books yet.
    if pack_dir is not None:
        from .library import load_library, validate_books
        declared = set(region_geo)
        for act in (w.get('acts') or []):
            declared |= set((act.get('region_geo') or act.get('regions') or {}) if isinstance(act, dict) else ())
        try:
            from . import delve
            descent = delve.descent_of(w, pack_dir) or None
        except ValueError:
            descent = None          # descent_errors() above has already said why
        # The pack's stamps ride in the descent the weave carries, so a
        # book pinned to a vault is checked against the floor the player
        # will actually draw (ADR 0013). The check reads the same descent
        # the weave writes; without the stamps it drew a floor with no
        # vault in it and refused every vault book there is.
        if descent:
            stamp_dir = Path(pack_dir) / 'stamps'
            if stamp_dir.is_dir():
                from . import stamps as stamps_mod
                descent = {**descent, 'stamps': stamps_mod.load(stamp_dir)}
        books = load_library(Path(pack_dir))
        errors.extend(validate_books(books, town=town,
                                     speakers=w.get('speakers'),
                                     regions=declared, descent=descent,
                                     items=_pack_catalog(pack_dir)))
        errors.extend(_book_prop_errors(books, region_geo))

    return errors


def _preserve_unknown(path: Path, known: dict) -> dict:
    """The previous file's keys, with `known` winning on conflict.

    A pack may carry fields the builder does not model: a game's title
    art and accent in `player`, a `stefna_voice`, a key from a future
    engine. A write must never silently drop them, so the file already
    on disk is the base and the writer overwrites only what it owns.
    """
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding='utf-8'))
        except ValueError:
            existing = {}
    if not isinstance(existing, dict):
        existing = {}
    return {**existing, **known}


def write_pack(pack_dir: Path, w: dict) -> None:
    """Atomic write - an interrupted build must never leave world.json
    truncated.

    Handles both shapes:

      Flat: writes a single world.json with all keys at the top.
      Acts: writes the pack-level world.json with phases/voices/bonds
        and the per-act world.json with the act's region, speakers,
        and town data.

    A unified shape from load_pack() (the path most callers use)
    has w['town'] synthesized; this function demuxes it back into
    the on-disk shape that matches the source pack.
    """
    pack = Path(pack_dir)
    tmp = pack / 'world.json.tmp'
    if 'acts' in w or (pack / 'acts').is_dir():
        # Acts shape: write pack-level + per-act JSONs, with the
        # town metadata in acts/<id>/town/contract.json (the
        # convention-driven home) and the map in acts/<id>/town/map.md.
        act_id = w.get('_act_id') or 'act-1'
        act_dir = pack / 'acts' / act_id
        act_dir.mkdir(parents=True, exist_ok=True)
        town = w.get('town', {})
        # The act contract: id, title, regions, speakers. Town
        # metadata lives in town/contract.json, not inline.
        # NOTE: this used to write 'regions': ['town'] and empty enemies/bosses every time, so a write on a
        # pack with several rooms (Cottage has six) silently threw the room list away. Only what this
        # function actually owns or was given is written; everything else on disk is kept.
        owned = {
            'id': act_id,
            'title': w.get('title', pack.name),
            'speakers': w.get('speakers', {}),
            'transitions': w.get('transitions', []),
        }
        loaded_regions = w.get('regions')
        if isinstance(loaded_regions, dict) and loaded_regions:
            owned['regions'] = list(loaded_regions)          # home room first, in the order loaded
        for key in ('enemies', 'bosses'):
            if key in w:                                      # absent means: keep what the file has
                owned[key] = w[key]
        act_contract = _preserve_unknown(act_dir / 'world.json', owned)
        act_contract.setdefault('regions', ['town'])          # a brand-new pack still gets its one room
        act_contract.setdefault('enemies', [])
        act_contract.setdefault('bosses', [])
        act_tmp = act_dir / 'world.json.tmp'
        act_tmp.write_text(json.dumps(act_contract, indent=2,
                                      ensure_ascii=False) + '\n', encoding='utf-8')
        act_tmp.replace(act_dir / 'world.json')
        # The town contract (every town-metadata field except map).
        town_dir = act_dir / 'town'
        town_dir.mkdir(parents=True, exist_ok=True)
        town_contract = _preserve_unknown(
            town_dir / 'contract.json',
            {k: v for k, v in town.items() if k != 'map'},
        )
        if town_contract:
            (town_dir / 'contract.json').write_text(
                json.dumps(town_contract, indent=2, ensure_ascii=False) + '\n',
                encoding='utf-8',
            )
        # The map moves to acts/<id>/town/map.md.
        if town.get('map'):
            (town_dir / 'map.md').write_text(
                '\n'.join(town['map']) + '\n', encoding='utf-8'
            )
        # The pack-level contract.
        pack_contract = _preserve_unknown(pack / 'world.json', {
            'name': pack.name,
            'title': w.get('title', pack.name),
            'description': w.get('description', ''),
            'creed': _creed_from(w),
            'phases': w.get('phases', {}),
            'surface': w.get('surface', 'combat'),
            'voices': w.get('voices', {}),
            'bonds': w.get('bonds', {}),
            'bond_draw': w.get('bond_draw', ''),
            'forge_texture': w.get('forge_texture', ''),
        })
        tmp.write_text(json.dumps(pack_contract, indent=2,
                                  ensure_ascii=False) + '\n', encoding='utf-8')
        tmp.replace(pack / 'world.json')
    else:
        # Flat shape: a single world.json with the legacy keys.
        legacy = _preserve_unknown(pack / 'world.json', {
            'name': pack.name,
            'title': w.get('title', pack.name),
            'description': w.get('description', ''),
            'creed': _creed_from(w),
            'phases': w.get('phases', {}),
            'surface': w.get('surface', 'combat'),
            'voices': w.get('voices', {}),
            'bonds': w.get('bonds', {}),
            'bond_draw': w.get('bond_draw', ''),
            'forge_texture': w.get('forge_texture', ''),
            'speakers': w.get('speakers', {}),
            'town': w.get('town', {}),
        })
        tmp.write_text(json.dumps(legacy, indent=2,
                                  ensure_ascii=False) + '\n', encoding='utf-8')
        tmp.replace(pack / 'world.json')


def build_map(segments: list) -> list[str]:
    rows = []
    for row_parts in segments:
        row = ''.join(ch * n for ch, n in row_parts)
        rows.append(row)
    widths = {len(r) for r in rows}
    if len(widths) != 1:
        raise SystemExit(f'segment rows are not rectangular: {sorted(widths)}')
    return rows


def cmd_validate(args) -> int:
    from .cli import pack_root
    pack_arg = Path(args.pack)
    if pack_arg.is_absolute():
        pack = pack_arg
    else:
        # Accept a bare name ("sample-world"), a worlds-relative path
        # ("worlds/foo"), or an absolute path. Matches the resolution
        # the other verbs (handbok, doctor, export) use.
        if (pack_arg / 'world.json').exists():
            pack = pack_arg
        elif (pack_root() / 'worlds' / pack_arg / 'world.json').exists():
            pack = pack_root() / 'worlds' / pack_arg
        else:
            print(
                f'pack not found: {pack_arg} '
                f'(looked at {pack_arg} and {pack_root() / "worlds" / pack_arg})'
            )
            return 1
    w = load_pack(pack)
    errors = validate(w, pack_dir=pack)
    if errors:
        for e in errors:
            print(f'FAIL: {e}')
        return 1
    print(f'ok: {pack} - geometry, reachability, voices all pass')
    return 0


def cmd_build(args) -> int:
    pack = Path(args.pack)
    w = load_pack(pack)
    spec = json.loads(Path(args.segments).read_text(encoding='utf-8'))
    w['town']['map'] = build_map(spec['rows'])
    errors = validate(w, pack_dir=pack)
    if errors and not args.force:
        for e in errors:
            print(f'FAIL: {e}')
        return 1
    write_pack(pack, w)
    print(f"built: {len(w['town']['map'])} x {len(w['town']['map'][0])} -> {pack / 'world.json'}")
    for e in errors:
        print(f'WARN: {e}')
    return 0


def cmd_verify(args) -> int:
    ok, errors = verify_live(args.url)
    if not ok:
        for e in errors:
            print(f'FAIL: {e}')
        return 1
    print(f'ok: {args.url} - the deployed world passes validation')
    return 0


def verify_live(url: str) -> tuple[bool, list[str]]:
    """Validate a live deployment's served /api/world payload.

    Used by both the maplab CLI ('verify') and the builder web UI
    ('/api/builder/verify'). Returns (ok, errors).

    Note: /api/world serves phases, speakers, and town geometry; pack-level
    voices are omitted from offline validation during live verification as
    they are internal prompt templates.
    """
    with urllib.request.urlopen(f'{url.rstrip("/")}/api/world', timeout=15) as r:
        served = json.loads(r.read().decode('utf-8'))
    town_keys = ('tile', 'map', 'legend', 'pois', 'watch', 'sanctuary_tiles',
                 'water_by_phase', 'flood_tiles', 'hero_start')
    w = {
        'phases': served['phases'],
        'speakers': {
            s['key']: {'name': s['name'], 'at': s['at'], 'near': s['near'],
                       'seeds': s.get('seeds', {})}
            for s in served['speakers']
        },
        'town': {k: served[k] for k in town_keys if k in served},
    }
    errors = validate(w)
    return (not errors), errors


def main(argv=None) -> int:
    default_pack = f'worlds/{_default_world_name()}'
    ap = argparse.ArgumentParser(prog='maplab', description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)

    v = sub.add_parser('validate', help='validate a world pack offline')
    v.add_argument('--pack', default=default_pack)
    v.set_defaults(fn=cmd_validate)

    b = sub.add_parser('build', help='rebuild the map from segment rows')
    b.add_argument('--segments', required=True)
    b.add_argument('--pack', default=default_pack)
    b.add_argument('--force', action='store_true', help='write even if validation fails')
    b.set_defaults(fn=cmd_build)

    r = sub.add_parser('verify', help='validate a live deployment')
    r.add_argument('--url', required=True)
    r.set_defaults(fn=cmd_verify)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
