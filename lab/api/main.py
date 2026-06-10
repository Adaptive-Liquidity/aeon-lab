"""FastAPI gateway for the lab.

Endpoints:
  POST /api/lab/submit          -> classify and start a workflow
  GET  /api/lab/workflows       -> list active workflows (Temporal visibility)
  GET  /api/lab/workflows/{id}  -> describe one workflow
  POST /api/lab/workflows/{id}/cancel
  WS   /ws/events               -> live stream of stage events
  GET  /api/lab/cost            -> rollup of cost ledger
  GET  /api/lab/provenance/{project_id} -> ledger entries
  GET  /api/lab/policy          -> MCP broker policy snapshot
  GET  /api/lab/health          -> liveness/readiness
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from lab import lab_data_home

log = logging.getLogger("lab.api")

try:
    from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    WebSocket = object  # type: ignore[assignment]
    WebSocketDisconnect = Exception  # type: ignore[assignment]

    class BaseModel:  # type: ignore[no-redef]
        pass


def create_app() -> "FastAPI":
    if FastAPI is None:
        raise RuntimeError("fastapi not installed; pip install -e lab")

    from lab.observability.tracing import init_tracing
    from lab.orchestrator.router import classify
    from lab.orchestrator.state import ProjectBrief
    from lab.observability.cost_ledger import CostLedger
    from lab.provenance.ledger import ProvenanceLedger
    from lab.mcp_broker.policy import default_policy

    init_tracing(service_name="ecc-lab-api")

    app = FastAPI(title="ECC Lab", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class SubmitRequest(BaseModel):
        title: str
        description: str
        track: str | None = None
        budget_usd: float = 50.0
        max_wall_clock_sec: int = 86400

    class SubmitResponse(BaseModel):
        project_id: str
        workflow_id: str
        track: str
        confidence: float
        rationale: str

    @app.get("/api/lab/health")
    async def health() -> dict:
        return {"ok": True, "version": "0.1.0"}

    @app.post("/api/lab/submit", response_model=SubmitResponse)
    async def submit(req: SubmitRequest) -> SubmitResponse:
        import uuid

        project_id = f"proj-{uuid.uuid4().hex[:12]}"
        decision = classify(
            ProjectBrief(
                project_id=project_id,
                title=req.title,
                description=req.description,
                track=req.track or "",
                budget_usd=req.budget_usd,
                max_wall_clock_sec=req.max_wall_clock_sec,
            ),
            hint=req.track,
        )
        workflow_id = await _start_workflow(
            project_id=project_id,
            track=decision.track,
            title=req.title,
            description=req.description,
            budget_usd=req.budget_usd,
            max_wall_clock_sec=req.max_wall_clock_sec,
        )
        return SubmitResponse(
            project_id=project_id,
            workflow_id=workflow_id,
            track=decision.track,
            confidence=decision.confidence,
            rationale=decision.rationale,
        )

    @app.get("/api/lab/workflows")
    async def list_workflows() -> dict:
        return await _list_workflows()

    @app.get("/api/lab/workflows/{workflow_id}")
    async def describe_workflow(workflow_id: str) -> dict:
        return await _describe_workflow(workflow_id)

    @app.post("/api/lab/workflows/{workflow_id}/cancel")
    async def cancel_workflow(workflow_id: str) -> dict:
        return await _cancel_workflow(workflow_id)

    @app.get("/api/lab/cost")
    async def cost(project_id: str | None = None) -> dict:
        return CostLedger.shared().rollup(project_id=project_id)

    @app.get("/api/lab/provenance/{project_id}")
    async def provenance(project_id: str) -> dict:
        ledger = ProvenanceLedger(project_id)
        return {"project_id": project_id, "entries": [asdict(e) for e in ledger.entries()]}

    @app.get("/api/lab/policy")
    async def policy_snapshot() -> dict:
        p = default_policy()
        return {
            "roles": {
                name: {
                    "servers": list(role.servers),
                    "tools": {k: list(v) for k, v in role.tools.items()},
                    "can_egress": role.can_egress,
                    "egress_allowlist": list(role.egress_allowlist),
                    "can_write_filesystem": role.can_write_filesystem,
                }
                for name, role in p.roles.items()
            }
        }

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket) -> None:
        await ws.accept()
        path = lab_data_home() / "events.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        try:
            with path.open("r", encoding="utf-8") as fh:
                fh.seek(0, 2)  # tail
                while True:
                    line = fh.readline()
                    if not line:
                        await asyncio.sleep(0.4)
                        continue
                    try:
                        await ws.send_text(line.strip())
                    except WebSocketDisconnect:
                        return
        except WebSocketDisconnect:
            return

    return app


async def _start_workflow(
    *,
    project_id: str,
    track: str,
    title: str,
    description: str,
    budget_usd: float,
    max_wall_clock_sec: int,
) -> str:
    try:
        from temporalio.client import Client

        from lab.orchestrator.state import ProjectBrief
        from lab.orchestrator.workflows import (
            EngineeringWorkflow,
            ResearchWorkflow,
        )
    except Exception:
        log.warning("temporalio not installed; persisting submit to local queue")
        _enqueue_local(
            project_id=project_id,
            track=track,
            title=title,
            description=description,
        )
        return f"local-{project_id}"

    client = await Client.connect(
        os.environ.get("TEMPORAL_HOST", "localhost:7233"),
        namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
    )
    brief = ProjectBrief(
        project_id=project_id,
        title=title,
        description=description,
        track=track,
        budget_usd=budget_usd,
        max_wall_clock_sec=max_wall_clock_sec,
    )
    handle = await client.start_workflow(
        ResearchWorkflow.run if track == "research" else EngineeringWorkflow.run,
        brief,
        id=f"ecc-lab-{project_id}",
        task_queue=os.environ.get("ECC_LAB_TASK_QUEUE", "ecc-lab"),
    )
    return handle.id


async def _list_workflows() -> dict:
    try:
        from temporalio.client import Client

        client = await Client.connect(
            os.environ.get("TEMPORAL_HOST", "localhost:7233"),
            namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        )
        results = []
        async for w in client.list_workflows("WorkflowType = 'ResearchWorkflow' OR WorkflowType = 'EngineeringWorkflow'"):
            results.append({"workflow_id": w.id, "type": w.workflow_type, "status": str(w.status)})
        return {"workflows": results}
    except Exception as exc:
        return {"workflows": [], "error": str(exc)}


async def _describe_workflow(workflow_id: str) -> dict:
    try:
        from temporalio.client import Client

        client = await Client.connect(
            os.environ.get("TEMPORAL_HOST", "localhost:7233"),
            namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        )
        handle = client.get_workflow_handle(workflow_id)
        desc = await handle.describe()
        return {
            "workflow_id": workflow_id,
            "type": desc.workflow_type,
            "status": str(desc.status),
            "task_queue": desc.task_queue,
            "start_time": desc.start_time.isoformat() if desc.start_time else None,
            "close_time": desc.close_time.isoformat() if desc.close_time else None,
        }
    except Exception as exc:
        return {"workflow_id": workflow_id, "error": str(exc)}


async def _cancel_workflow(workflow_id: str) -> dict:
    try:
        from temporalio.client import Client

        client = await Client.connect(
            os.environ.get("TEMPORAL_HOST", "localhost:7233"),
            namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        )
        handle = client.get_workflow_handle(workflow_id)
        await handle.cancel()
        return {"workflow_id": workflow_id, "cancelled": True}
    except Exception as exc:
        return {"workflow_id": workflow_id, "cancelled": False, "error": str(exc)}


def _enqueue_local(*, project_id: str, track: str, title: str, description: str) -> None:
    queue = lab_data_home() / "submit-queue.jsonl"
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "project_id": project_id,
                    "track": track,
                    "title": title,
                    "description": description,
                }
            )
            + "\n"
        )


app = None
try:
    app = create_app()
except Exception as exc:
    log.debug("FastAPI app not constructed at import time: %s", exc)
