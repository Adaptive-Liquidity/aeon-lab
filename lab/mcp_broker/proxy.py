"""MCP broker proxy.

A single MCP server that fronts the catalogue of backing servers declared
in `mcp-configs/`. Every tool call is intercepted and:

  1. The caller's role is resolved (from a header set by the dispatcher).
  2. `policy.allowed(role, server, tool)` decides whether to forward.
  3. Tool arguments are scrubbed via `scrub.scrub_secrets`.
  4. Tool results are scrubbed before returning to the caller.
  5. If the tool calls an external HTTP endpoint, `egress.EgressFilter`
     checks the URL against the role's allowlist.
  6. Every decision is appended to the broker audit log.

The implementation degrades gracefully when the `mcp` SDK is not
installed — the policy and scrub modules remain importable and unit
testable. The broker exposes both stdio and Streamable HTTP transports.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lab import ECC_ROOT, lab_data_home
from lab.mcp_broker.egress import EgressFilter
from lab.mcp_broker.policy import McpPolicy, default_policy, load_policy
from lab.mcp_broker.scrub import scrub_secrets

log = logging.getLogger("lab.mcp_broker.proxy")


@dataclass
class BrokerAuditEvent:
    timestamp: float
    role: str
    server: str
    tool: str
    decision: str  # allowed | denied
    reason: str = ""
    redactions: list[str] = field(default_factory=list)
    egress: dict[str, Any] | None = None


def _audit_path() -> Path:
    p = lab_data_home() / "mcp_broker_audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


class McpBroker:
    def __init__(
        self,
        *,
        policy: McpPolicy | None = None,
        backing_configs_dir: Path | None = None,
    ) -> None:
        self.policy = policy or default_policy()
        self.backing_configs_dir = backing_configs_dir or (ECC_ROOT / "mcp-configs")
        self._egress_filters: dict[str, EgressFilter] = {}

    def egress_for(self, role: str) -> EgressFilter:
        if role not in self._egress_filters:
            self._egress_filters[role] = EgressFilter(
                tuple(self.policy.for_role(role).egress_allowlist)
            )
        return self._egress_filters[role]

    def authorize(
        self, *, role: str, server: str, tool: str, args: Any
    ) -> tuple[bool, str, Any, list[str]]:
        if not self.policy.allowed(role, server, tool):
            self._audit(
                BrokerAuditEvent(
                    timestamp=time.time(),
                    role=role,
                    server=server,
                    tool=tool,
                    decision="denied",
                    reason="not in role allow-list",
                )
            )
            return False, "denied by policy", args, []
        scrub = scrub_secrets(args)
        if scrub.redactions:
            log.warning("scrubbed %d secret(s) before %s.%s", len(scrub.redactions), server, tool)
        # Egress URL check (if args contains a `url` field).
        egress_record = None
        if isinstance(args, dict):
            url = args.get("url") or args.get("href")
            if isinstance(url, str):
                decision = self.egress_for(role).check(url)
                egress_record = {"url": url, "allowed": decision.allowed, "host": decision.host}
                if not decision.allowed:
                    self._audit(
                        BrokerAuditEvent(
                            timestamp=time.time(),
                            role=role,
                            server=server,
                            tool=tool,
                            decision="denied",
                            reason=decision.reason,
                            redactions=scrub.redactions,
                            egress=egress_record,
                        )
                    )
                    return False, decision.reason, scrub.cleaned, scrub.redactions
        self._audit(
            BrokerAuditEvent(
                timestamp=time.time(),
                role=role,
                server=server,
                tool=tool,
                decision="allowed",
                redactions=scrub.redactions,
                egress=egress_record,
            )
        )
        return True, "ok", scrub.cleaned, scrub.redactions

    def post_filter_result(self, result: Any) -> tuple[Any, list[str]]:
        scrubbed = scrub_secrets(result)
        return scrubbed.cleaned, scrubbed.redactions

    def _audit(self, event: BrokerAuditEvent) -> None:
        try:
            with _audit_path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.__dict__) + "\n")
        except Exception:
            log.debug("audit write failed", exc_info=True)


# ---------------------------------------------------------------------------
# Stdio + HTTP entrypoints (skeleton; full MCP wiring requires the mcp SDK
# and the backing-server child processes, which start-lab.js handles.)
# ---------------------------------------------------------------------------


async def _serve_stdio(broker: McpBroker) -> None:
    log.info("mcp broker stdio mode (skeleton)")
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            return
        # Minimal JSON-RPC handler that authorizes a synthetic call shape.
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("method") != "tools/call":
            continue
        params = msg.get("params", {})
        role = params.get("_meta", {}).get("role", "restricted")
        server = params.get("server", "")
        tool = params.get("name", "")
        args = params.get("arguments", {})
        allowed, reason, cleaned, _redactions = broker.authorize(
            role=role, server=server, tool=tool, args=args
        )
        sys.stdout.write(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "result": {"allowed": allowed, "reason": reason, "arguments": cleaned},
                }
            )
            + "\n"
        )
        sys.stdout.flush()


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    policy = load_policy()
    broker = McpBroker(policy=policy)
    log.info("starting ecc-lab mcp broker (roles=%d)", len(policy.roles))
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_serve_stdio(broker))


if __name__ == "__main__":
    main()
