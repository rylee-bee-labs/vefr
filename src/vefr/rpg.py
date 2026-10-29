"""The RPG core (ADR 0021): fight rolls, guard, depth, spoils, stock,
traits, magic and trips.

Every key here is opt-in, and a pack that declares none of them weaves the
bytes it wove before and plays the fight it played before. The pack
contract, all of it optional:

    "fight":  {"miss": 10, "crit": 8, "crit_times": 2, "turns": true}
    "traits": {"keen": {"atk": 1}, "reckless": {"atk": 3, "sting": 1, "curse": true}}
    "player": {"guard": 1, "mana": 6}
    items:    "mods": {"guard": 1, "mana": 2}, "casts": "ember-bolt", "charges": 3
    spells:   "mana": 2, "harm": 4, "range": 6, "ward": {"guard": 2, "turns": 3}
    speakers: "stock": ["potion", {"item": "satchel", "flag": "cellar-done"}],
              "markup": 200
    families: "guard": 1, "drop_chance": 40, "gold": [1, 4]
    descent:  "resume": "deepest-landing", "fall": "home"
    time:     "rest_heals": true

and a Section's `curve`, which the schema has always accepted, is read at
last. The rules themselves - what a roll is, what guard takes away, how a
trait reacts - live in the woven player (`web/player/parts/427-the-rpg-core.js`
and the parts it hooks); this module is the half Python needs: the readers
the bake and the descent's Python twin share, and the validator's plain
sentences. It is deterministic like the rest of the engine: no randomness,
no model call, no clock.
"""

from __future__ import annotations

# ------------------------------------------------------------------ fight

FIGHT_PERCENT_MAX = 50       # a miss or a crit chance never passes half
CRIT_TIMES = (2, 3)          # what a critical blow is multiplied by
GUARD_MAX = 99
MOD_MAX = 9                  # the worn `mods` bound every stat shares

# ----------------------------------------------------------------- traits

TRAIT_STATS = ('hp', 'atk', 'guard', 'mana')
TRAIT_STAT_RANGE = (-9, 9)
TRAIT_CRIT_RANGE = (-50, 50)
# The closed set of reactions: each fires on one event, says one line, and
# never fires another reaction - so a turn's chain is bounded by its blows.
TRAIT_REACTIONS = {
    'kill_heal': (1, 9),     # a kill restores N health
    'opener': (2, 3),        # a blow on an unhurt foe is multiplied by N
    'thorns': (1, 9),        # a monster that hits you takes N
    'sting': (1, 9),         # each of your misses hurts you N (never below 1)
}
TRAIT_KEYS = TRAIT_STATS + ('crit',) + tuple(TRAIT_REACTIONS) + ('curse',)

# ------------------------------------------------------------------ magic

MANA_MAX = 999
SPELL_MANA_RANGE = (1, 99)
SPELL_HARM_RANGE = (1, 99)
SPELL_RANGE_RANGE = (1, 20)
DEFAULT_SPELL_RANGE = 6
WARD_GUARD_RANGE = (1, 9)
WARD_TURNS_RANGE = (1, 20)
CHARGES_RANGE = (1, 20)

# ----------------------------------------------------------- stock, trips

MARKUP_RANGE = (100, 500)
DROP_CHANCE_RANGE = (0, 100)
GOLD_RANGE = (0, 9999)
RESUME_CHOICES = ('deepest-landing',)
FALL_CHOICES = ('home',)


def _whole(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _in(value, bounds) -> bool:
    return _whole(value) and bounds[0] <= value <= bounds[1]


# --------------------------------------------------------------- readers


def fight_of(world) -> dict | None:
    """The pack's usable `fight` block, defaults filled, or None.

    None when the pack declares none: then no blow is ever rolled. A block
    with a value out of bounds is refused by `rpg_errors`; here a bad value
    reads as the default, so a pack the check refused still plays.
    """
    block = world.get('fight') if isinstance(world, dict) else None
    if not isinstance(block, dict):
        return None
    out = {'miss': 0, 'crit': 0, 'crit_times': CRIT_TIMES[0], 'turns': False}
    for key in ('miss', 'crit'):
        if _in(block.get(key), (0, FIGHT_PERCENT_MAX)):
            out[key] = block[key]
    if block.get('crit_times') in CRIT_TIMES:
        out['crit_times'] = block['crit_times']
    out['turns'] = block.get('turns') is True
    return out


def guard_of(record) -> int:
    """A record's own `guard` (the player block, a family, an enemy), or 0."""
    value = record.get('guard') if isinstance(record, dict) else None
    return value if _in(value, (0, GUARD_MAX)) else 0


def gold_of(record) -> tuple[int, int] | None:
    """A family's or enemy's `gold` as `(lo, hi)`, or None when it names none."""
    value = record.get('gold') if isinstance(record, dict) else None
    if (isinstance(value, list) and len(value) == 2
            and all(_in(v, GOLD_RANGE) for v in value) and value[0] <= value[1]):
        return value[0], value[1]
    return None


def drop_chance_of(record) -> int:
    """A family's `drop_chance` (0..100), or 100 - every kill drops, as before."""
    value = record.get('drop_chance') if isinstance(record, dict) else None
    return value if _in(value, DROP_CHANCE_RANGE) else 100


def curved(value: int, section, k: int, stat: str) -> int:
    """`value` scaled by `section`'s `curve` at floor `k` (ADR 0014, wired here).

    Through `vefr.mob_stats`, the one formula ADR 0014 wrote down: the
    curve's hundredths for this floor, an integer floor-divide, never below
    1. A Section with no `curve` is the neutral 100 and leaves `value` as it
    was, so a Section that never named one draws the numbers it always drew.
    No affix and cycle 0: elites and the endless ramp stay unwired.
    """
    from .mob_stats import mob_stats

    return mob_stats({stat: value}, None, section, k, 0)[stat]


def traits_of(world) -> dict:
    """The pack's usable `traits` table: each word to its clean effects."""
    table = world.get('traits') if isinstance(world, dict) else None
    if not isinstance(table, dict):
        return {}
    out: dict = {}
    for word, spec in table.items():
        if not isinstance(word, str) or not isinstance(spec, dict):
            continue
        clean: dict = {}
        for stat in TRAIT_STATS:
            if _in(spec.get(stat), TRAIT_STAT_RANGE):
                clean[stat] = spec[stat]
        if _in(spec.get('crit'), TRAIT_CRIT_RANGE):
            clean['crit'] = spec['crit']
        for reaction, bounds in TRAIT_REACTIONS.items():
            if _in(spec.get(reaction), bounds):
                clean[reaction] = spec[reaction]
        if spec.get('curse') is True:
            clean['curse'] = True
        out[word] = clean
    return out


def stock_of(spec) -> list[dict] | None:
    """A shopkeeper's `stock` as `[{item, flag?}]`, or None when it names none."""
    listed = spec.get('stock') if isinstance(spec, dict) else None
    if not isinstance(listed, list):
        return None
    out = []
    for entry in listed:
        if isinstance(entry, str) and entry:
            out.append({'item': entry})
        elif isinstance(entry, dict) and isinstance(entry.get('item'), str) and entry['item']:
            row = {'item': entry['item']}
            if isinstance(entry.get('flag'), str) and entry['flag']:
                row['flag'] = entry['flag']
            out.append(row)
    return out


def markup_of(spec) -> int | None:
    """A shopkeeper's `markup` percent, or None when it names none."""
    value = spec.get('markup') if isinstance(spec, dict) else None
    return value if _in(value, MARKUP_RANGE) else None


def verb_id(entry) -> str | None:
    """The verb an act's `verbs` entry names: a bare word, or the `verb` of a
    `{"verb", "label"}` entry (ADR 0021). None for anything else."""
    if isinstance(entry, str):
        return entry.strip() or None
    if isinstance(entry, dict) and isinstance(entry.get('verb'), str):
        return entry['verb'].strip() or None
    return None


def verb_ids(listed) -> list[str]:
    """Every verb id an act's `verbs` list names, in its order."""
    return [v for v in (verb_id(e) for e in (listed if isinstance(listed, list) else []))
            if v]


def verb_entry_ok(entry) -> bool:
    """A usable `verbs` entry: a word, or `{"verb": word, "label": 1-60 chars}`."""
    if isinstance(entry, str):
        return bool(entry.strip())
    return (isinstance(entry, dict) and set(entry) <= {'verb', 'label'}
            and isinstance(entry.get('verb'), str) and bool(entry['verb'].strip())
            and isinstance(entry.get('label'), str) and 1 <= len(entry['label']) <= 60)


# ------------------------------------------------------------ validation


def _player(w: dict) -> dict:
    player = w.get('_player') or w.get('player')
    return player if isinstance(player, dict) else {}


def fight_errors(w: dict) -> list[str]:
    """Every problem with the optional `fight` block (empty = good)."""
    if 'fight' not in w:
        return []
    block = w['fight']
    if not isinstance(block, dict):
        return ['world.json: fight must be an object, such as '
                '{"miss": 10, "crit": 8, "turns": true}']
    errors: list[str] = []
    allowed = ('miss', 'crit', 'crit_times', 'turns')
    for key in block:
        if key not in allowed:
            errors.append(f"world.json: fight may only hold {', '.join(allowed)}, "
                          f"not {key!r}")
    for key in ('miss', 'crit'):
        if key in block and not _in(block[key], (0, FIGHT_PERCENT_MAX)):
            errors.append(f'world.json: fight.{key} must be a whole number from 0 to '
                          f'{FIGHT_PERCENT_MAX}, the percent of blows that {key}')
    if 'crit_times' in block and block['crit_times'] not in CRIT_TIMES:
        errors.append('world.json: fight.crit_times must be 2 or 3, what a critical '
                      'blow is multiplied by')
    if 'turns' in block and not isinstance(block['turns'], bool):
        errors.append('world.json: fight.turns must be true or false')
    return errors


def player_errors(w: dict) -> list[str]:
    """Every problem with `player.guard` and `player.mana` (empty = good)."""
    player = _player(w)
    errors: list[str] = []
    if 'guard' in player and not _in(player['guard'], (0, GUARD_MAX)):
        errors.append(f'world.json: player.guard must be a whole number from 0 to '
                      f'{GUARD_MAX}, what every blow at the hero loses')
    if 'mana' in player and not _in(player['mana'], (0, MANA_MAX)):
        errors.append(f'world.json: player.mana must be a whole number from 0 to '
                      f'{MANA_MAX}')
    return errors


def traits_errors(w: dict) -> list[str]:
    """Every problem with the optional `traits` table (empty = good)."""
    if 'traits' not in w:
        return []
    table = w['traits']
    if not isinstance(table, dict):
        return ['world.json: traits must be an object of trait words to what each '
                'does, such as {"keen": {"atk": 1}}']
    errors: list[str] = []
    for word, spec in table.items():
        where = f'world.json: trait {word!r}'
        if not isinstance(spec, dict):
            errors.append(f'{where} must be an object, such as {{"atk": 1}}')
            continue
        for key, value in spec.items():
            if key not in TRAIT_KEYS:
                errors.append(f"{where} may only hold {', '.join(TRAIT_KEYS)}, "
                              f"not {key!r}")
            elif key in TRAIT_STATS and not _in(value, TRAIT_STAT_RANGE):
                errors.append(f'{where} {key} must be a whole number from '
                              f'{TRAIT_STAT_RANGE[0]} to {TRAIT_STAT_RANGE[1]}')
            elif key == 'crit' and not _in(value, TRAIT_CRIT_RANGE):
                errors.append(f'{where} crit must be a whole number from '
                              f'{TRAIT_CRIT_RANGE[0]} to {TRAIT_CRIT_RANGE[1]}')
            elif key in TRAIT_REACTIONS and not _in(value, TRAIT_REACTIONS[key]):
                lo, hi = TRAIT_REACTIONS[key]
                errors.append(f'{where} {key} must be a whole number from {lo} to {hi}')
            elif key == 'curse' and value is not True:
                errors.append(f'{where} curse must be true, or left out')
    return errors


def spell_errors(record: dict, where: str) -> list[str]:
    """Every problem with one spell's `mana`, `harm`, `range` and `ward`."""
    errors: list[str] = []
    if 'mana' in record and not _in(record['mana'], SPELL_MANA_RANGE):
        errors.append(f'{where} mana must be a whole number from 1 to 99')
    if 'harm' in record and not _in(record['harm'], SPELL_HARM_RANGE):
        errors.append(f'{where} harm must be a whole number from 1 to 99')
    if 'range' in record and not _in(record['range'], SPELL_RANGE_RANGE):
        errors.append(f'{where} range must be a whole number of tiles from 1 to 20')
    if 'range' in record and 'harm' not in record:
        errors.append(f'{where} range needs a harm: only a harmful spell reaches')
    if 'ward' in record:
        ward = record['ward']
        if not (isinstance(ward, dict) and set(ward) <= {'guard', 'turns'}
                and _in(ward.get('guard'), WARD_GUARD_RANGE)
                and _in(ward.get('turns'), WARD_TURNS_RANGE)):
            errors.append(f'{where} ward must be {{"guard": 1 to 9, "turns": 1 to 20}}')
    effects = [k for k in ('heal', 'harm', 'ward') if k in record]
    if len(effects) > 1:
        errors.append(f"{where} does one thing: {' and '.join(effects)} cannot "
                      f"sit together")
    return errors


def item_errors(item_id: str, spec: dict, spell_ids) -> list[str]:
    """Every problem with an item's `casts` and `charges` (empty = good)."""
    label = str(spec.get('name') or item_id)
    where = (f"item '{label}'" if label == item_id else f"item '{label}' ({item_id})")
    errors: list[str] = []
    if 'casts' in spec:
        if not isinstance(spec['casts'], str) or spec['casts'] not in spell_ids:
            errors.append(f'{where} casts {spec["casts"]!r}, which is not a spell '
                          f'this pack declares')
        if 'charges' not in spec:
            errors.append(f'{where} casts a spell, so it needs its charges, such as 3')
        if 'spell' in spec:
            errors.append(f'{where} cannot both teach a spell and cast one')
    if 'charges' in spec:
        if not _in(spec['charges'], CHARGES_RANGE):
            errors.append(f'{where} charges must be a whole number from 1 to 20')
        if 'casts' not in spec:
            errors.append(f'{where} charges need a casts: a charge is one cast')
    return errors


def stock_errors(key: str, spec: dict, item_ids) -> list[str]:
    """Every problem with a shopkeeper's `stock` and `markup` (empty = good)."""
    errors: list[str] = []
    where = f'speaker {key!r}'
    if 'stock' in spec:
        listed = spec['stock']
        if not isinstance(listed, list):
            errors.append(f'{where} stock must be a list of item ids, such as ["potion"]')
        else:
            for entry in listed:
                item = entry if isinstance(entry, str) else (
                    entry.get('item') if isinstance(entry, dict) else None)
                if isinstance(entry, dict) and not set(entry) <= {'item', 'flag'}:
                    errors.append(f'{where} stock entries may only hold item and flag')
                if not isinstance(item, str) or item not in item_ids:
                    errors.append(f'{where} stock names {item!r}, which is not an item '
                                  f'this pack declares')
    if 'markup' in spec and not _in(spec['markup'], MARKUP_RANGE):
        errors.append(f'{where} markup must be a whole number from 100 to 500, the buy '
                      f'price as a percent of value')
    return errors


def family_errors(name: str, defaults: dict) -> list[str]:
    """Every problem with a family's `guard`, `drop_chance` and `gold`."""
    errors: list[str] = []
    where = f"blueprint.json: family '{name}'"
    if 'guard' in defaults and not _in(defaults['guard'], (0, GUARD_MAX)):
        errors.append(f'{where} guard must be a whole number from 0 to {GUARD_MAX}')
    if 'drop_chance' in defaults and not _in(defaults['drop_chance'], DROP_CHANCE_RANGE):
        errors.append(f'{where} drop_chance must be a whole number from 0 to 100')
    if 'gold' in defaults and gold_of(defaults) is None:
        errors.append(f'{where} gold must be [lo, hi], whole numbers from 0 to 9999, '
                      f'such as [1, 4]')
    return errors
