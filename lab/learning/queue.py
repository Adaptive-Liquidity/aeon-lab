"""Reads the learning queue produced by the `lab-learning-emit.js` hook."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, List, Optional


def _default_queue_path() -> Path:
    base = os.environ.get("ECC_LAB_DATA_HOME") or str(Path.home() / ".ecc" / "lab")
    return Path(base) / "learning-queue.jsonl"


def _default_processed_path() -> Path:
    return _default_queue_path().parent / "learning-processed.jsonl"


@dataclass
class LearningEntry:
    """One row from the learning queue. Mirrors hook payload shape."""

    project_id: str
    track: str
    stage: str
    agent_role: str
    artifact_hash: Optional[str]
    confidence: float
    findings: List[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, payload: dict) -> "LearningEntry":
        meta = payload.get("metadata") or {}
        return cls(
            project_id=str(payload.get("project_id") or meta.get("project_id") or ""),
            track=str(payload.get("track") or "unknown"),
            stage=str(payload.get("stage") or payload.get("phase") or "unknown"),
            agent_role=str(payload.get("agent_role") or meta.get("agent_role") or ""),
            artifact_hash=payload.get("artifact_hash") or meta.get("artifact_hash"),
            confidence=float(payload.get("confidence") or 0.0),
            findings=list(payload.get("findings") or []),
            raw=payload,
        )


@dataclass
class LearningQueue:
    """Reader for the learning-queue JSONL file."""

    queue_path: Path = field(default_factory=_default_queue_path)
    processed_path: Path = field(default_factory=_default_processed_path)

    def __post_init__(self) -> None:
        self.queue_path = Path(self.queue_path)
        self.processed_path = Path(self.processed_path)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)

    def read_all(self) -> List[LearningEntry]:
        if not self.queue_path.exists():
            return []
        out: List[LearningEntry] = []
        with self.queue_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out.append(LearningEntry.from_json(payload))
        return out

    def mark_processed(self, entries: List[LearningEntry]) -> None:
        if not entries:
            return
        with self.processed_path.open("a", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry.raw) + "\n")
        # truncate queue file once entries are processed
        self.queue_path.write_text("", encoding="utf-8")

    def stream(self) -> Iterator[LearningEntry]:
        for entry in self.read_all():
            yield entry


def drain_queue(queue_path: Optional[Path] = None) -> List[LearningEntry]:
    """Convenience function returning every queued lesson candidate."""

    queue = LearningQueue(queue_path or _default_queue_path())
    return queue.read_all()
