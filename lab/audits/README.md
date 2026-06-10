# Lab Audits

Scheduled checks that protect the autonomous workgroup from drift.

| Audit | Cadence | Module | Output |
|---|---|---|---|
| `agent-architecture-audit` | Nightly @ 02:30 | `lab.audits.architecture_audit` | `~/.ecc/lab/audits/agent-architecture-audit/<date>/` |
| `skill-comply` | Weekly Mon @ 03:15 | `lab.audits.skill_comply_audit` | `~/.ecc/lab/audits/skill-comply/<date>/` |
| `learning-drain` | Nightly @ 04:00 | `lab.learning.cli` | `skills/_candidates/*.md` |

## Install

```bash
node lab/scripts/install-cron.js
```

- macOS/Linux: rewrites the user crontab (idempotent — entries are tagged with `# ECC-LAB-CRON`).
- Windows: writes `lab/scripts/install-cron.bat` for the user to run in an elevated prompt.

## Manual execution

```bash
python -m lab.audits.architecture_audit
python -m lab.audits.skill_comply_audit
python -m lab.learning.cli
```

Each run writes `report.json` and `summary.md` plus appends a one-line summary to
`audits/<audit-name>.history.jsonl`. The `lab.audit_event` hook records every run
to `~/.ecc/lab/audit-events.jsonl` so the dashboard's status panel can show
"last audit" badges next to each subsystem.

## Output schema

```json
{
  "audit": "agent-architecture-audit",
  "started_at": "2026-06-10T02:30:00Z",
  "finished_at": "2026-06-10T02:31:14Z",
  "status": "ok",
  "findings": [
    {"severity": "info|low|medium|high|critical", "title": "...", "detail": "..."}
  ]
}
```
