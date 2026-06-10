"""Append-only ledger with content-hash chain.

Each entry has:
  - id (auto)
  - timestamp
  - project_id
  - track/stage
  - agent_role
  - kind (artifact | decision | gate | rollback | budget)
  - payload (JSON)
  - artifact_sha256 (if kind == artifact)
  - previous_hash (sha256 of the prior entry, anchoring the chain)
  - signature (base64 ed25519, signed by the agent's key)

The ledger lives at `{lab_data_home}/ledger/{project_id}.jsonl`. Anyone
with the public keyring can verify the chain offline via the CLI.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lab import lab_data_home
from lab.provenance.sign import AgentKeyring

log = logging.getLogger("lab.provenance.ledger")


@dataclass
class LedgerEntry:
    id: str
    timestamp: float
    project_id: str
    track: str
    stage: str
    agent_role: str
    kind: str
    payload: dict[str, Any]
    artifact_sha256: str | None = None
    previous_hash: str = "0" * 64
    signature: str = ""

    def canonical_json(self) -> bytes:
        body = {k: v for k, v in asdict(self).items() if k != "signature"}
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def hash(self) -> str:
        return hashlib.sha256(self.canonical_json()).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class ProvenanceLedger:
    _lock = threading.Lock()

    def __init__(self, project_id: str, *, root: Path | None = None) -> None:
        self.project_id = project_id
        self.root = root or (lab_data_home() / "ledger")
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / f"{project_id}.jsonl"
        self.keyring = AgentKeyring()

    def append(
        self,
        *,
        kind: str,
        track: str,
        stage: str,
        agent_role: str,
        payload: dict[str, Any],
        artifact_path: Path | None = None,
    ) -> LedgerEntry:
        with self._lock:
            prev = self._last_hash()
            entry = LedgerEntry(
                id=f"{int(time.time()*1000):x}-{self._next_seq()}",
                timestamp=time.time(),
                project_id=self.project_id,
                track=track,
                stage=stage,
                agent_role=agent_role,
                kind=kind,
                payload=payload,
                artifact_sha256=sha256_file(artifact_path) if artifact_path else None,
                previous_hash=prev,
            )
            key = self.keyring.get(agent_role)
            entry.signature = key.sign(entry.canonical_json())
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(entry)) + "\n")
            return entry

    def entries(self) -> list[LedgerEntry]:
        if not self.path.exists():
            return []
        out: list[LedgerEntry] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                data = json.loads(line)
                out.append(LedgerEntry(**data))
        return out

    def _last_hash(self) -> str:
        entries = self.entries()
        return entries[-1].hash() if entries else "0" * 64

    def _next_seq(self) -> int:
        return len(self.entries()) + 1


# ---------------------------------------------------------------------------
# Convenience helpers used by activities + quality gates.
# ---------------------------------------------------------------------------


def record_artifact(
    project_id: str,
    *,
    track: str,
    stage: str,
    agent_role: str,
    artifact_path: Path,
    summary: dict[str, Any] | None = None,
) -> LedgerEntry:
    ledger = ProvenanceLedger(project_id)
    return ledger.append(
        kind="artifact",
        track=track,
        stage=stage,
        agent_role=agent_role,
        payload={"path": str(artifact_path), "summary": summary or {}},
        artifact_path=artifact_path,
    )


def record_decision(
    project_id: str,
    *,
    track: str,
    stage: str,
    agent_role: str,
    decision: str,
    rationale: dict[str, Any] | None = None,
) -> LedgerEntry:
    ledger = ProvenanceLedger(project_id)
    return ledger.append(
        kind="decision",
        track=track,
        stage=stage,
        agent_role=agent_role,
        payload={"decision": decision, "rationale": rationale or {}},
    )
