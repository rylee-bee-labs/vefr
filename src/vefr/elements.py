"""Damage types, resistances and the one status effect this slice builds.

The pack contract is three optional words, all of them opt-in:

    "player": {"resist": {"fire": 2}, "immune": ["cold"]}

and, on a hazard in a region contract:

    {"id": "ember-hound", ..., "dmg_type": "fire",
     "burns": {"turns": 3, "tick": 1}}

A pack that declares none of them is not affected: the weave bakes no
resistance, no damage type and no status, and every number a fight
reaches is the number it reached before (vefr#497, slice 1 of the
campaign in `design/elemental-and-status-effects.md`).

The vocabulary is `design/elemental-and-status-effects.md`'s: **damage
type** is what the damage is, **status effect** is the state left on a
combatant, and **resistance/immunity** is the relationship between
them. Only `burning` is in the status vocabulary, because only
`burning` has something that can apply it; the rest of the doc's list
is deliberately not here yet, so an author cannot write a status that
does nothing.

The resolver is `after_resist()`, and it is the ONLY place a number is
changed by a resistance - both damage paths call it, so fire resists
and necrotic does not become an accident of which side struck first
(the asymmetry the design note calls out). It is deterministic like
the rest of the engine: no randomness, no model call, no clock.

Resistance is a divisor, not a percentage: `"fire": 2` means fire
does half. `immune` beats `resist` when a type is named in both, and
the resolver says which of the three things happened so the player can
be told in words rather than shown by colour alone.
"""

from __future__ import annotations

# What a damage type is *called* in a pack and in a sentence. Closed on
# purpose: an open vocabulary here would let a pack write "fiery" and
# "fire" for two different mechanics, which is the confusion the design
# note was written to end.
DAMAGE_TYPES = (
    "physical", "fire", "cold", "lightning", "poison", "necrotic",
    "acid", "radiant", "psychic", "thunder",
)

# The states a combatant can be left in. One entry: `burning` is the
# whole of the status vocabulary in this slice, and it is here because
# the pack can write it on a hazard.
STATUS_EFFECTS = ("burning",)

# The two words a resistance can answer with, plus the plain one. They
# are the same strings the player speaks, so a sentence and this
# function cannot drift apart.
HOW_HIT = "hit"
HOW_RESISTED = "resisted"
HOW_IMMUNE = "immune"

# The upper bound on a resistance divisor, matching the whole-number
# range gear `mods` uses (0 to 9): ten is "a tenth of the damage", and
# a larger number would be a spelling of immunity the pack should say.
MAX_RESIST = 9


def is_damage_type(value) -> bool:
    """True when `value` is one of the closed damage-type words."""
    return isinstance(value, str) and value.strip().lower() in DAMAGE_TYPES


def normal_type(value) -> str | None:
    """`value` as a damage-type word, or None when it names none."""
    return value.strip().lower() if is_damage_type(value) else None


def _whole_at_least(value, least: int) -> bool:
    return (isinstance(value, int) and not isinstance(value, bool)
            and value >= least)


def resist_of(player) -> dict:
    """`{type: divisor}` from `player.resist`, dropping anything unusable.

    The validator (`maplab.element_errors`) is what refuses a bad word
    to the author; this is the reader the bake uses, and it must never
    raise on a malformed pack - it reads what is sound and stops.
    """
    if not isinstance(player, dict):
        return {}
    raw = player.get('resist')
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        name = normal_type(key)
        if name and _whole_at_least(value, 1) and value <= MAX_RESIST:
            out[name] = value
    return out


def immune_of(player) -> list:
    """The damage types `player.immune` names, in the pack's own order."""
    if not isinstance(player, dict):
        return []
    raw = player.get('immune')
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for value in raw:
        name = normal_type(value)
        if name and name not in out:
            out.append(name)
    return out


def after_resist(amount: int, dtype: str | None = None,
                 resist=None, immune=None) -> dict:
    """The damage a blow actually lands, and which of the three it was.

    `amount` is the raw number a combatant would lose. `dtype` is the
    damage type, or None for the untyped blow every pack that has not
    opted in still deals. `resist` is `{type: divisor}` and `immune` is
    a list of type words; both may be None (no resistance at all).

    The untyped path is the identity: an amount that is not a whole
    number is passed through untouched, so a caller that hands in
    something it did not mean to convert never has its number changed
    behind its back. An untyped blow is never resisted either - there
    is no type to resist it *as*.
    """
    try:
        raw = int(amount)
    except (TypeError, ValueError):
        return {"damage": amount, "how": HOW_HIT, "type": dtype or ""}
    if raw < 0:
        raw = 0
    name = normal_type(dtype)
    if not name:
        return {"damage": raw, "how": HOW_HIT, "type": ""}
    if isinstance(immune, (list, tuple, set, frozenset)) and name in {
            normal_type(t) for t in immune}:
        return {"damage": 0, "how": HOW_IMMUNE, "type": name}
    divisor = None
    if isinstance(resist, dict):
        divisor = resist.get(name)
    if not _whole_at_least(divisor, 1):
        return {"damage": raw, "how": HOW_HIT, "type": name}
    return {"damage": raw // divisor, "how": HOW_RESISTED, "type": name}


def burning_of(enemy) -> dict | None:
    """The `burns` block of one hazard, normalised - or None.

    `{"turns": 3, "tick": 1}` is the whole data shape the design note
    asks for: a duration in turns and a tick (how much, how often).
    There is no stacking and no refresh rule here: the player keeps the
    longer of the two durations and one tick, because a second copy of
    the same burning is not a thing this slice decides.
    """
    if not isinstance(enemy, dict):
        return None
    raw = enemy.get('burns')
    if not isinstance(raw, dict):
        return None
    turns, tick = raw.get('turns'), raw.get('tick')
    if not _whole_at_least(turns, 1) or not _whole_at_least(tick, 1):
        return None
    return {"effect": "burning", "type": "fire",
            "turns": int(turns), "tick": int(tick)}