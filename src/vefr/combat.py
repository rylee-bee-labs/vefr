"""Surface-specific combat behavior.

The engine's surface field is a costume: packs declare
`surface: "combat" | "investigation" | "plain"` and the HUD
branches on it. This module is the small piece of server-side
behavior the costume needs:

  - HP values per phase, derived from the pack's own phase
    names. A pack with phases `dusk, dawn` gets HP=2 for dusk
    and HP=3 for dawn (later phases have more HP). The mapping
    is positional + simple; the costume is the point, not the
    formula.

  - The act's `verbs` list is the pack's own action vocabulary.
    When an act declares verbs, they ARE the allowed combat
    actions and the HUD's buttons; when it declares none, the
    engine's default costume verbs apply (back-compat).

  - POST /api/combat/action records a `combat_action` journal
    entry with the action's kind and an optional target. The
    engine doesn't have a turn system; the action just lives in
    the journal so the play log is complete.

How hard the numbers bite is the pack's law, not the engine's:
each act declares a `floor` (see world.py - "costume" by
default, where HP tracks as a number and the player never drops
to zero; "story" and "stakes" get their mechanics from rulesets
in future PRs). Under the default floor the old contract holds:
nothing the attack does can fail or end the game, and the
journal entry is honest.
"""

from .journal import log as _journal_log


# A simple per-phase HP scale. Index 0 is the first phase, 1 the
# second, etc. The numbers are intentionally small (single digit)
# - the costume is the point, not the math.
DEFAULT_HP_BY_INDEX = [3, 4, 5, 6]

# The engine's default action vocabulary - the costume verbs the
# HUD offers when the active act declares none of its own. A
# pack's act `verbs` list replaces this entirely.
DEFAULT_VERBS = ("attack", "console", "hurl", "strike", "observe")


def hp_for_pack(world: dict) -> dict:
    """Return the HUD's HP block: per-phase current/max.

    The `current` starts at the per-phase max. The `max` is the
    same value. The HUD shows the bar at full until something
    changes the current - which only happens in future PRs
    (encounter ticks, etc.). Today this is "the HP bar at full
    HP, the number on it."
    """
    phases = list(world.get("phases", {}).keys())
    if not phases:
        return {"current": 0, "max": 0, "per_phase": {}}
    per_phase: dict[str, int] = {}
    for i, phase in enumerate(phases):
        idx = min(i, len(DEFAULT_HP_BY_INDEX) - 1)
        per_phase[phase] = DEFAULT_HP_BY_INDEX[idx]
    return {
        "current": max(per_phase.values()),
        "max": max(per_phase.values()),
        "per_phase": per_phase,
    }


def verbs_for_pack(world: dict) -> tuple[str, ...]:
    """The active act's action vocabulary, or the engine default.

    An act that declares `verbs` owns its actions entirely - a
    cooking act can offer ["plate", "flip", "serve"] and the
    costume verbs stop being legal. An act with no `verbs` keeps
    the default costume so existing packs behave unchanged.
    """
    acts = world.get("acts") or []
    idx = world.get("_current_act", 0)
    act = acts[idx] if idx < len(acts) else {}
    # A verb may name its own label (ADR 0021); the vocabulary is its ids.
    from . import rpg
    verbs = rpg.verb_ids(act.get("verbs") or [])
    if verbs:
        return tuple(verbs)
    return DEFAULT_VERBS


def record_combat_action(
    *,
    kind: str,
    phase: str | None,
    target: str | None = None,
    session: str = "",
    allowed: tuple[str, ...] | None = None,
) -> dict:
    """Record a combat action in the journal. Returns the entry.

    The action is whatever the HUD sent, checked against the
    allowed vocabulary (the active act's verbs, or the engine
    default when the caller passes nothing). The journal shape
    is `combat_action` with the action, the phase, the target,
    and the timestamp. No HP change under the default floor -
    the surface is a costume, the costume is the point.
    """
    vocab = allowed if allowed is not None else DEFAULT_VERBS
    if kind not in set(vocab):
        raise ValueError(f"unknown combat action kind: {kind!r}")
    # The journal's first positional arg is the *kind of journal
    # entry* (rumor, npc_line, combat_action, etc.). The action's
    # own kind (attack, console, hurl) is stored under `verb` so
    # the journal entry has both: kind='combat_action' and
    # verb='attack'.
    entry = _journal_log(
        "combat_action",
        sid=session,
        verb=kind,
        phase=phase or "",
        target=target or "",
    )
    return entry
