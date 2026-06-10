"""Chain verification CLI.

Verifies every entry's previous_hash and signature for a given project.
Returns a non-zero exit code if any tamper is detected.

Usage:
  python -m lab.provenance.verify <project_id>
  python -m lab.provenance.verify ./out/my-project/paper_final.md   # verify a file's lineage
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from lab import lab_data_home
from lab.provenance.ledger import LedgerEntry, ProvenanceLedger, sha256_file
from lab.provenance.sign import AgentKey, AgentKeyring

log = logging.getLogger("lab.provenance.verify")


def verify_chain(project_id: str) -> dict:
    ledger = ProvenanceLedger(project_id)
    entries = ledger.entries()
    if not entries:
        return {"project_id": project_id, "ok": True, "entries": 0, "issues": []}
    issues: list[str] = []
    keyring = AgentKeyring()
    prev = "0" * 64
    for idx, entry in enumerate(entries):
        if entry.previous_hash != prev:
            issues.append(
                f"entry {idx} ({entry.id}): previous_hash mismatch (have {entry.previous_hash[:12]}…, expected {prev[:12]}…)"
            )
        key = keyring.get(entry.agent_role)
        if not key.verify(entry.canonical_json(), entry.signature):
            issues.append(f"entry {idx} ({entry.id}): signature invalid for role {entry.agent_role!r}")
        prev = entry.hash()
    return {
        "project_id": project_id,
        "ok": not issues,
        "entries": len(entries),
        "issues": issues,
    }


def verify_artifact(path: Path) -> dict:
    """Locate the artifact entry by sha256 and verify the chain it belongs to."""
    if not path.exists():
        return {"ok": False, "issues": [f"file not found: {path}"]}
    digest = sha256_file(path)
    ledger_root = lab_data_home() / "ledger"
    for ledger_file in ledger_root.glob("*.jsonl"):
        project_id = ledger_file.stem
        ledger = ProvenanceLedger(project_id)
        for entry in ledger.entries():
            if entry.artifact_sha256 == digest:
                result = verify_chain(project_id)
                result["artifact"] = {
                    "path": str(path),
                    "sha256": digest,
                    "matched_entry": entry.id,
                    "stage": entry.stage,
                    "track": entry.track,
                    "agent_role": entry.agent_role,
                }
                return result
    return {"ok": False, "issues": [f"no ledger entry matches sha256={digest[:12]}…"]}


def main() -> int:
    logging.basicConfig(level="INFO", format="%(message)s")
    parser = argparse.ArgumentParser(prog="ecc-lab-verify", description="Verify lab provenance.")
    parser.add_argument("target", help="project_id OR path to an artifact file")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    target = args.target
    p = Path(target)
    result = verify_artifact(p) if p.exists() and p.is_file() else verify_chain(target)
    import json as _json

    print(_json.dumps(result, indent=2 if not args.json else None))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
