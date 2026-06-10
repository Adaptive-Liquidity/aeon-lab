---
description: Cursor /lab — autonomous lab work submission and status (ECC + Claw).
---

# /lab (Cursor)

Cursor's slash menu surfaces `/lab` from this file. Behavior is identical to the canonical `commands/lab.md`.

Resolution chain inside an agent run:

1. If the `ecc` Rust daemon is on PATH, call `ecc lab <args>`.
2. Otherwise call `python -m lab.api.cli <args>` from the repo root.
3. If the API gateway is offline, the CLI queues the submission to `~/.ecc/lab/submit-queue.jsonl`.

See `commands/lab.md` for full usage, routing cheatsheet, and exit states.
