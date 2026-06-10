"""Continuous-learning + lesson-to-skill emission loop for the lab.

Consumes the `~/.ecc/lab/learning-queue.jsonl` file populated by the
`lab-learning-emit.js` hook, extracts repeating patterns from
high-confidence stage outcomes, and emits skill candidates as Markdown
under `skills/_candidates/` for human review (or automated promotion via
the existing skill-create flow).

The pipeline is intentionally idempotent and crash-safe: the queue file
is the source of truth, and every processed entry is moved to
`learning-processed.jsonl` after a candidate is written.
"""

from .queue import LearningEntry, LearningQueue, drain_queue
from .lesson_extractor import LessonExtractor, Lesson
from .skill_emitter import SkillEmitter, SkillCandidate

__all__ = [
    "LearningEntry",
    "LearningQueue",
    "drain_queue",
    "LessonExtractor",
    "Lesson",
    "SkillEmitter",
    "SkillCandidate",
]
