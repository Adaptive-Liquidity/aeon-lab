"""Temporal workflows for the lab.

Two top-level workflows:
  - `ResearchWorkflow` — drives Claw's 26-stage pipeline
  - `EngineeringWorkflow` — drives ECC's 6-phase orch-pipeline
"""

from lab.orchestrator.workflows.research import ResearchWorkflow
from lab.orchestrator.workflows.engineering import EngineeringWorkflow

__all__ = ["ResearchWorkflow", "EngineeringWorkflow"]
