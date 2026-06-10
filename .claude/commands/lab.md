---
description: Claude Code entry to the ECC + Claw autonomous lab. Aliases /lab in commands/ for project-scoped use.
---

# /lab (Claude Code)

See `commands/lab.md` for the canonical command surface. This file makes `/lab` available when Claude Code is configured to load project-scoped commands from `.claude/commands/`.

## Behavior

- `/lab` — health snapshot
- `/lab submit "<title>" [--research|--engineering] [--budget N]` — submit a work item
- `/lab status` — JSON workflow snapshot
- `/lab cost` — cost rollup
- `/lab verify <project-id|sha>` — verify provenance
- `/lab policy` — MCP broker policy snapshot

Invocation resolves to:

```bash
ecc lab "$@"          # preferred (Rust daemon)
python -m lab.api.cli "$@"   # fallback when ecc binary is unavailable
```
