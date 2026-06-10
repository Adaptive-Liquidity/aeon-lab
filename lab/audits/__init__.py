"""Scheduled lab audits.

This package wires the existing ECC `agent-architecture-audit` and
`skill-comply` skills into the lab's cron surface. Each audit emits a
report under `~/.ecc/lab/audits/<audit-name>/<date>/` and posts a
`lab.audit_event` event the dashboard subscribes to.
"""

from .architecture_audit import run_architecture_audit
from .skill_comply_audit import run_skill_comply_audit

__all__ = ["run_architecture_audit", "run_skill_comply_audit"]
