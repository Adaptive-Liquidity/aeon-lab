"""Quality gate stack — replaces HITL approvals with automated review.

Each gate is a pure async function `(StageOutcome) -> GateResult`.
The orchestrator runs all enabled gates in parallel and combines verdicts
according to the decision policy in `policy.py`.
"""

from lab.quality_gates.orchestrator import run_quality_gate, QualityGateResult
from lab.quality_gates.policy import DecisionPolicy, default_policy

__all__ = [
    "run_quality_gate",
    "QualityGateResult",
    "DecisionPolicy",
    "default_policy",
]
