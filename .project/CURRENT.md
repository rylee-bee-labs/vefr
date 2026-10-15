# CURRENT — VEFR

This file is a **router, not a snapshot**.

VEFR is the engine/studio. Games remain separate projects and repositories
loaded through the world-pack contract.

## Current truth

| Question | Source |
| --- | --- |
| code, branches, PRs, issues | Git + GitHub |
| current work / owner attention | Project Home + GitHub Issues |
| product direction and horizons | `ROADMAP.md` |
| active implementation plans | `docs/plans/` + their owning GitHub epics/issues |
| **current game-release engine dependency** | [VEFR #489](https://github.com/rylee-bee-labs/vefr/issues/489) ↔ [Cottage 1.0 release #170](https://github.com/rylee-bee-labs/cottage-of-the-breeze/issues/170) (active owner-approved five-gate [release roadmap](https://github.com/rylee-bee-labs/cottage-of-the-breeze/blob/main/docs/plans/release-1-0/ROADMAP.md)) |
| durable architecture decisions | `docs/adr/` + `.project/DECISIONS.md` |
| engine/game boundary | `README.md` + relevant ADRs |
| release/validation truth | current CI/gates and runtime evidence |
| historical experiments/handoffs | dated docs + Git history |

## Current release-linked engine work (2026-10-14)

A four-Section browser-first game has an owner-approved 1.0 finish line; the pack's release epic is Cottage #170. VEFR's role is **limited, reusable engine work**, not a duplicate game plan or a new engine framework. [VEFR #489](https://github.com/rylee-bee-labs/vefr/issues/489) is the one linked dependency for checking existing loot/spell/omen/reaction/saving capabilities and proposing the smallest necessary gaps. Begin with a **Built / Partial / Missing / Unknown** source-grounded inventory; hand back tested PRs to the Cottage quality gates. Owner direction: **polish, not scope expansion**. Never mark a gameplay gate finished because a spec was written or code merged.

## Stable rules

- Game-specific story/content belongs in the game repository.
- Reusable engine capability belongs in VEFR when the evidence earns it.
- A merge is not proof of deployment or runtime behavior.
- Old handoffs and dated phase notes explain history; they do not define current work.

## Resume

Run `lab enter` or `now-block --print .`, then:

```sh
git fetch origin
git status --short
gh pr list --repo rylee-bee-labs/vefr --state open
gh issue list --repo rylee-bee-labs/vefr --state open
```

Read only the plan/ADR for the issue you are actually changing.

The previous rolling dated ledger in this file remains available in Git history.
Do not rebuild it here. If evidence is missing, say **UNKNOWN**.
