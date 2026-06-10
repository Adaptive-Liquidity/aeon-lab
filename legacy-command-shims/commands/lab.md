---
description: Codex CLI shim for /lab — forwards to the unified lab gateway.
---

# /lab (Codex CLI shim)

Codex CLI consumes legacy command shims as plain Markdown commands. The shim's only responsibility is to invoke the lab gateway in a Codex-friendly way:

```bash
python -m lab.api.cli "$@"
```

Behavior, exit states, and arguments are documented in the canonical `commands/lab.md`. This shim exists so Codex sessions can call `/lab submit "<title>"` without going through the Rust daemon.
