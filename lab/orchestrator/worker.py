"""Temporal worker entrypoint.

Starts a worker that hosts both research and engineering workflows plus
their activities. Binds the AgentDispatcher to a concrete invoker selected
via the `ECC_LAB_INVOKER` env var.

Usage:
  python -m lab.orchestrator.worker
  ECC_LAB_INVOKER=researchclaw_inproc python -m lab.orchestrator.worker
  ECC_LAB_INVOKER=claude_code_sdk python -m lab.orchestrator.worker
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

log = logging.getLogger("lab.orchestrator.worker")


def _load_invoker(name: str):
    from lab.invokers import load_invoker

    return load_invoker(name)


async def _run() -> int:
    invoker_name = os.environ.get("ECC_LAB_INVOKER", "researchclaw_inproc")
    invoker = _load_invoker(invoker_name)

    from lab.bridge.agent_dispatcher import AgentDispatcher
    from lab.orchestrator.activities import (
        engineering_phase_activity,
        quality_gate_activity_engineering,
        quality_gate_activity_research,
        research_stage_activity,
        rollback_activity_research,
        security_review_activity,
    )
    from lab.orchestrator.activities.research_activities import (
        set_dispatcher as set_research_dispatcher,
    )
    from lab.orchestrator.activities.engineering_activities import (
        set_dispatcher as set_engineering_dispatcher,
    )
    from lab.orchestrator.workflows import (
        EngineeringWorkflow,
        ResearchWorkflow,
    )

    dispatcher = AgentDispatcher(invoker=invoker)
    set_research_dispatcher(dispatcher)
    set_engineering_dispatcher(dispatcher)

    try:
        from temporalio.client import Client
        from temporalio.worker import Worker
    except ImportError:
        log.error(
            "temporalio not installed. pip install -e lab[dev] or install lab/pyproject.toml deps."
        )
        return 2

    host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = os.environ.get("ECC_LAB_TASK_QUEUE", "ecc-lab")

    client = await Client.connect(host, namespace=namespace)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[ResearchWorkflow, EngineeringWorkflow],
        activities=[
            research_stage_activity,
            engineering_phase_activity,
            quality_gate_activity_research,
            quality_gate_activity_engineering,
            rollback_activity_research,
            security_review_activity,
        ],
    )
    log.info("ecc-lab worker started: host=%s queue=%s invoker=%s", host, task_queue, invoker_name)
    await worker.run()
    return 0


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    try:
        sys.exit(asyncio.run(_run()))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
