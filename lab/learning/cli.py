"""CLI entrypoint that drains the learning queue and emits skill candidates.

Usage::

    python -m lab.learning.cli                # drain queue, emit candidates
    python -m lab.learning.cli --dry-run      # only report what would be emitted
    python -m lab.learning.cli --min-occ 5    # raise the threshold for promotion

This is the command the nightly self-improvement cron invokes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .lesson_extractor import LessonExtractor
from .queue import LearningQueue
from .skill_emitter import SkillEmitter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lab continuous-learning drainer")
    parser.add_argument("--dry-run", action="store_true", help="Only print, do not write")
    parser.add_argument(
        "--min-occ",
        type=int,
        default=3,
        help="Minimum number of recurrences before a lesson is promoted",
    )
    parser.add_argument(
        "--min-conf",
        type=float,
        default=0.7,
        help="Minimum average gate confidence required for promotion",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Override the candidate skills directory",
    )
    args = parser.parse_args(argv)

    queue = LearningQueue()
    entries = queue.read_all()
    if not entries:
        print(json.dumps({"status": "empty", "queue_path": str(queue.queue_path)}))
        return 0

    extractor = LessonExtractor(min_occurrences=args.min_occ, min_confidence=args.min_conf)
    lessons = extractor.extract(entries)

    if not lessons:
        print(
            json.dumps(
                {
                    "status": "no-lessons",
                    "entries": len(entries),
                    "thresholds": {
                        "min_occurrences": args.min_occ,
                        "min_confidence": args.min_conf,
                    },
                }
            )
        )
        if not args.dry_run:
            queue.mark_processed(entries)
        return 0

    if args.dry_run:
        report = [
            {
                "slug": lesson.slug,
                "occurrences": lesson.occurrences,
                "average_confidence": lesson.average_confidence,
                "track": lesson.track,
                "stage": lesson.stage,
            }
            for lesson in lessons
        ]
        print(json.dumps({"status": "dry-run", "candidates": report}, indent=2))
        return 0

    emitter = SkillEmitter(args.skills_root)
    written = emitter.emit_all(lessons)
    queue.mark_processed(entries)
    print(
        json.dumps(
            {
                "status": "ok",
                "candidates": [
                    {"slug": c.slug, "path": str(c.path)} for c in written
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
