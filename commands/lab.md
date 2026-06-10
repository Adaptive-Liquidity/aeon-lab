---
description: Submit work to the ECC + Claw autonomous lab and inspect running workflows from any harness.
---

# /lab

`/lab` is the harness-agnostic entry point to the unified ECC + Claw autonomous workgroup. It routes work items into either the 26-stage research pipeline or the 6-phase engineering pipeline, depending on the task, and shows live status from the Temporal-backed orchestrator.

## Usage

```text
/lab                                  # quick health snapshot + queue + recent gate decisions
/lab submit <title>                   # submit a work item, auto-routed (research vs engineering)
/lab submit <title> --research        # force research track
/lab submit <title> --engineering     # force engineering track
/lab submit <title> --budget 50       # cap USD spend
/lab status                           # JSON status of subsystems and recent workflows
/lab cost                             # cost rollup (today / 7d / 30d, by stage, project)
/lab verify <project-id|sha>          # verify provenance chain
/lab policy                           # MCP broker policy snapshot
/lab up                               # bring lab subsystems up (worker, api, mcp-broker)
/lab down                             # stop lab subsystems
```

## Operating Rules

1. Before calling, confirm the lab is running with `ecc lab status` (or `python -m lab.api.cli status`). If subsystems are down, run `ecc lab up` first.
2. When no track flag is given, the orchestrator's `WorkItemRouter` classifies the brief and prints the routing decision.
3. Every submission is durable: Temporal owns workflow state and retries crashed stages automatically.
4. Quality gates are automated — eval-harness, GAN-evaluator, Santa-method, Gateguard, and an ambiguity-only Council vote. No human approval is required for happy-path runs.
5. The MCP broker enforces per-role tool allowlists, scrubs secrets, and audits egress. `/lab policy` shows the current snapshot.
6. Costs are logged per-stage to `~/.ecc/lab/cost_ledger.jsonl`. The model router respects per-project budgets and refuses to spend past the cap.

## Routing Cheatsheet

| Brief signals | Track |
|---|---|
| literature, dataset, paper, hypothesis, experiment, ablation | research |
| feature, refactor, bugfix, endpoint, migration, deploy, schema | engineering |
| both signals | router picks the dominant; tie breaks to engineering |

## Implementation

This command resolves to a shell call. The preferred form (when the user is in the ECC repo and has the Rust daemon) is:

```bash
ecc lab submit "<title>" --description "<body>" --budget 50
```

Equivalent direct invocation without the daemon:

```bash
python -m lab.api.cli submit "<title>" --description "<body>" --budget 50
```

Both forward to `POST /api/lab/submit` against the local FastAPI gateway when it is reachable, and fall back to a local submit queue file at `~/.ecc/lab/submit-queue.jsonl` when offline (the worker drains the queue on start).

## Harness Notes

- **Claude Code** picks up this file from `commands/lab.md` directly.
- **Cursor** reads it through the workspace `commands/` surface and surfaces `/lab` in the slash menu.
- **Codex CLI** uses `.opencode/commands/lab.md` or `python -m lab.api.cli` directly.
- **OpenCode** uses `.opencode/commands/lab.md`, which is the same content as this file.

## Exit States

| Exit | Meaning |
|---|---|
| `accepted` | Workflow started, ID printed |
| `queued` | Lab gateway unreachable; submission queued locally |
| `budget_exhausted` | Project budget cap reached before stage could start |
| `policy_blocked` | MCP broker refused the request based on policy |
| `error` | Other failure; consult `ecc lab status` and the worker log |
