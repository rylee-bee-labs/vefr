# 0020 - Game pack and file compatibility

Date: 2026-10-24

## Status

**Accepted.** This records Rylee's compatibility decision for the Player epic.

## Decision

1. Every existing game (Cottage, Lanternwake, Emberfield) and its standalone HTML keeps working, unchanged, on every engine update.
2. A `.vefr` file carries data only.
3. Any pack-format change is versioned and needs Rylee's OK before a game is migrated.
4. Saves are never silently lost: checked before load, refused with a reason.
