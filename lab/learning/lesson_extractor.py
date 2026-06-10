"""Cluster `LearningEntry` rows into named lessons worth promoting to skills.

Heuristics:
- Group by (track, stage, agent_role).
- Require >= MIN_OCCURRENCES recurrences with average confidence >= MIN_CONF.
- Aggregate distinct findings into a deduped, ranked bullet list.
- A "lesson" is *only* surfaced when the evidence is strong; weak signals stay
  in the processed log and never produce a skill candidate.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from .queue import LearningEntry


MIN_OCCURRENCES = 3
MIN_CONFIDENCE = 0.7


@dataclass
class Lesson:
    track: str
    stage: str
    agent_role: str
    occurrences: int
    average_confidence: float
    sample_artifacts: List[str] = field(default_factory=list)
    distinct_findings: List[str] = field(default_factory=list)
    source_entries: List[LearningEntry] = field(default_factory=list)

    @property
    def slug(self) -> str:
        parts = [self.track, self.stage, self.agent_role or "agent"]
        slug = "-".join(p.lower().replace("_", "-") for p in parts if p)
        return slug.strip("-") or "lesson"


class LessonExtractor:
    """Pulls high-signal lessons out of a flat stream of learning entries."""

    def __init__(
        self,
        min_occurrences: int = MIN_OCCURRENCES,
        min_confidence: float = MIN_CONFIDENCE,
    ) -> None:
        self.min_occurrences = max(1, int(min_occurrences))
        self.min_confidence = float(min_confidence)

    def extract(self, entries: Iterable[LearningEntry]) -> List[Lesson]:
        grouped: Dict[Tuple[str, str, str], List[LearningEntry]] = defaultdict(list)
        for entry in entries:
            key = (entry.track, entry.stage, entry.agent_role)
            grouped[key].append(entry)

        lessons: List[Lesson] = []
        for (track, stage, role), bucket in grouped.items():
            if len(bucket) < self.min_occurrences:
                continue
            avg_conf = sum(e.confidence for e in bucket) / len(bucket)
            if avg_conf < self.min_confidence:
                continue
            findings = self._merge_findings(bucket)
            samples = [e.artifact_hash for e in bucket[:5] if e.artifact_hash]
            lessons.append(
                Lesson(
                    track=track,
                    stage=stage,
                    agent_role=role,
                    occurrences=len(bucket),
                    average_confidence=round(avg_conf, 3),
                    sample_artifacts=samples,
                    distinct_findings=findings,
                    source_entries=list(bucket),
                )
            )
        lessons.sort(
            key=lambda x: (x.occurrences, x.average_confidence),
            reverse=True,
        )
        return lessons

    @staticmethod
    def _merge_findings(entries: List[LearningEntry]) -> List[str]:
        counts: Dict[str, int] = defaultdict(int)
        for entry in entries:
            for finding in entry.findings:
                norm = finding.strip()
                if not norm:
                    continue
                counts[norm] += 1
        ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [f"{text} (x{count})" if count > 1 else text for text, count in ranked[:8]]
