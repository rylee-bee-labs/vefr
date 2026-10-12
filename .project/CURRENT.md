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
| durable architecture decisions | `docs/adr/` + `.project/DECISIONS.md` |
| engine/game boundary | `README.md` + relevant ADRs |
| release/validation truth | current CI/gates and runtime evidence |
| historical experiments/handoffs | dated docs + Git history |

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
