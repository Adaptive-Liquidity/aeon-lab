"""`ecc-lab` CLI entrypoint.

Subcommands:
  submit <title>           submit a work item (engineering by default)
  submit --research <...>  submit a research project
  list                     list workflows
  describe <id>            describe one workflow
  cancel <id>              cancel a workflow
  cost [--project P]       print cost rollup
  verify <project|file>    verify provenance
  serve [--port N]         run the FastAPI gateway
  worker                   run the Temporal worker
  policy                   print MCP broker policy
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path


def _cmd_submit(args: argparse.Namespace) -> int:
    payload = {
        "title": args.title,
        "description": args.description or args.title,
        "track": "research" if args.research else ("engineering" if args.engineering else None),
        "budget_usd": args.budget,
        "max_wall_clock_sec": args.max_seconds,
    }
    # Talk to the local API if available; fall back to direct invocation.
    import urllib.error
    import urllib.request

    url = f"{args.api}/api/lab/submit"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(resp.read().decode("utf-8"))
        return 0
    except urllib.error.URLError as exc:
        print(f"API unreachable ({exc}); writing to local submit queue", file=sys.stderr)
        from lab.api.main import _enqueue_local
        from lab.orchestrator.router import classify
        from lab.orchestrator.state import ProjectBrief
        import uuid

        project_id = f"proj-{uuid.uuid4().hex[:12]}"
        decision = classify(payload["description"] or payload["title"], hint=payload["track"])
        _enqueue_local(
            project_id=project_id,
            track=decision.track,
            title=payload["title"],
            description=payload["description"],
        )
        print(json.dumps({"project_id": project_id, "track": decision.track, "queued_locally": True}))
        return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    from lab.provenance.verify import main as verify_main

    sys.argv = ["ecc-lab-verify", args.target] + (["--json"] if args.json else [])
    return verify_main()


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("lab.api.main:app", host=args.host, port=args.port, reload=False)
    return 0


def _cmd_worker(args: argparse.Namespace) -> int:
    from lab.orchestrator.worker import main as worker_main

    worker_main()
    return 0


def _cmd_cost(args: argparse.Namespace) -> int:
    from lab.observability.cost_ledger import CostLedger

    print(json.dumps(CostLedger.shared().rollup(project_id=args.project), indent=2))
    return 0


def _cmd_policy(args: argparse.Namespace) -> int:
    from lab.mcp_broker.policy import default_policy

    p = default_policy()
    print(json.dumps({k: list(v.servers) for k, v in p.roles.items()}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="ecc-lab", description="ECC + Claw Autonomous Lab.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_submit = sub.add_parser("submit", help="Submit a work item")
    p_submit.add_argument("title", help="Short task title")
    p_submit.add_argument("--description", default=None)
    p_submit.add_argument("--research", action="store_true")
    p_submit.add_argument("--engineering", action="store_true")
    p_submit.add_argument("--budget", type=float, default=50.0)
    p_submit.add_argument("--max-seconds", type=int, default=86400)
    p_submit.add_argument("--api", default="http://localhost:8810")
    p_submit.set_defaults(func=_cmd_submit)

    p_verify = sub.add_parser("verify", help="Verify provenance (project id or artifact path)")
    p_verify.add_argument("target")
    p_verify.add_argument("--json", action="store_true")
    p_verify.set_defaults(func=_cmd_verify)

    p_serve = sub.add_parser("serve", help="Run the FastAPI gateway")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8810)
    p_serve.set_defaults(func=_cmd_serve)

    p_worker = sub.add_parser("worker", help="Run the Temporal worker")
    p_worker.set_defaults(func=_cmd_worker)

    p_cost = sub.add_parser("cost", help="Print cost rollup")
    p_cost.add_argument("--project", default=None)
    p_cost.set_defaults(func=_cmd_cost)

    p_policy = sub.add_parser("policy", help="Show MCP broker policy")
    p_policy.set_defaults(func=_cmd_policy)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
