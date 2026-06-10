"""Turn extracted lessons into draft Skill Markdown files for human review.

Skill candidates land under ``skills/_candidates/<slug>.md`` with YAML
frontmatter (`name`, `description`) so they slot directly into ECC's
existing /skill-create promotion flow. A companion JSON sidecar records
the source learning entries so reviewers can trace each claim back to a
concrete provenance record.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .lesson_extractor import Lesson


@dataclass
class SkillCandidate:
    slug: str
    path: Path
    sidecar_path: Path
    lesson: Lesson


class SkillEmitter:
    """Writes lesson candidates to disk under ``skills/_candidates/``."""

    def __init__(self, skills_root: Optional[Path] = None) -> None:
        if skills_root is None:
            repo_root = Path(os.environ.get("ECC_ROOT") or Path.cwd())
            skills_root = repo_root / "skills" / "_candidates"
        self.skills_root = Path(skills_root)
        self.skills_root.mkdir(parents=True, exist_ok=True)

    def emit_all(self, lessons: List[Lesson]) -> List[SkillCandidate]:
        return [self.emit(lesson) for lesson in lessons]

    def emit(self, lesson: Lesson) -> SkillCandidate:
        slug = lesson.slug
        path = self.skills_root / f"{slug}.md"
        sidecar = self.skills_root / f"{slug}.evidence.json"
        path.write_text(self._render_skill(lesson), encoding="utf-8")
        sidecar.write_text(self._render_sidecar(lesson), encoding="utf-8")
        return SkillCandidate(slug=slug, path=path, sidecar_path=sidecar, lesson=lesson)

    @staticmethod
    def _render_skill(lesson: Lesson) -> str:
        now = datetime.now(timezone.utc).isoformat()
        title = f"{lesson.track.title()} :: {lesson.stage} via {lesson.agent_role or 'agent'}"
        description = (
            f"Auto-distilled lesson from {lesson.occurrences} "
            f"successful runs of the {lesson.track} pipeline's {lesson.stage} stage."
        )
        findings_block = (
            "\n".join(f"- {f}" for f in lesson.distinct_findings)
            if lesson.distinct_findings
            else "- (no shared findings — confidence came from raw scores)"
        )
        samples_block = (
            "\n".join(f"- `{h}`" for h in lesson.sample_artifacts)
            if lesson.sample_artifacts
            else "- (no artifact hashes captured)"
        )
        return (
            "---\n"
            f"name: lesson-{lesson.slug}\n"
            f"description: {description}\n"
            f"status: candidate\n"
            f"emitted_at: {now}\n"
            "---\n\n"
            f"# {title}\n\n"
            "## Source\n"
            f"- Track: `{lesson.track}`\n"
            f"- Stage / phase: `{lesson.stage}`\n"
            f"- Agent role: `{lesson.agent_role or 'unknown'}`\n"
            f"- Occurrences observed: **{lesson.occurrences}**\n"
            f"- Average gate confidence: **{lesson.average_confidence}**\n\n"
            "## What worked\n"
            f"{findings_block}\n\n"
            "## Sample artifacts\n"
            f"{samples_block}\n\n"
            "## Suggested action\n"
            "- Review the listed findings and harden them into reusable guidance.\n"
            "- Run `/skill-create` to promote this candidate, or delete it if the pattern is too narrow.\n"
            "- Evidence sidecar with raw learning queue entries is committed next to this file.\n"
        )

    @staticmethod
    def _render_sidecar(lesson: Lesson) -> str:
        payload = {
            "slug": lesson.slug,
            "track": lesson.track,
            "stage": lesson.stage,
            "agent_role": lesson.agent_role,
            "occurrences": lesson.occurrences,
            "average_confidence": lesson.average_confidence,
            "sample_artifacts": lesson.sample_artifacts,
            "distinct_findings": lesson.distinct_findings,
            "source_entries": [entry.raw for entry in lesson.source_entries],
        }
        return json.dumps(payload, indent=2) + "\n"
