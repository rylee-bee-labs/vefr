# 0020 - Game pack and file compatibility

Date: 2026-10-24

## Status

**Accepted.** This records Rylee's compatibility decision for the Player epic (her choice 5c, 2026-10-24: [#452 comment 6388092795](https://github.com/rylee-bee-labs/vefr/issues/452#issuecomment-6388092795), relayed as Sol #1581).

## Decision

1. Every existing game (Cottage, Lanternwake, Emberfield) and its standalone HTML keeps working, unchanged, on every engine update.
2. A `.vefr` file carries data only. Its pictures and sounds are data too; the shape is in [ADR 0019](0019-vefr-archive-format.md) (`manifest.json`, `content/`, `assets/`, `data/globals.json`).
3. Any pack-format change is versioned and needs Rylee's OK before a game is migrated.
4. Saves are never silently lost: checked before load, refused with a reason.
