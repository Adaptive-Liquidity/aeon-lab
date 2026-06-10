---
description: OpenCode shim for /lab — forwards to the ECC + Claw autonomous lab gateway.
---

# /lab (OpenCode)

Forwards every invocation to `python -m lab.api.cli` in the repo root. See `commands/lab.md` for the canonical command surface and routing rules.

## Resolution

```bash
python -m lab.api.cli "$@"
```

If the API gateway is unreachable the CLI queues the submission to `~/.ecc/lab/submit-queue.jsonl` and the next worker boot drains it.
