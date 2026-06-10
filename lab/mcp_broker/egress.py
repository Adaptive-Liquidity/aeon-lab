"""Outbound HTTP filter for MCP tool calls.

Tool calls that hit external HTTP endpoints (e.g. via the firecrawl,
context7, exa, github MCP servers) are intercepted and checked against
the calling role's `egress_allowlist`. Anything outside the list is
denied. Wildcards (`*.context7.com`) are supported.
"""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass
from urllib.parse import urlparse

log = logging.getLogger("lab.mcp_broker.egress")


@dataclass
class EgressDecision:
    allowed: bool
    host: str
    reason: str = ""


class EgressFilter:
    def __init__(self, allowlist: tuple[str, ...]) -> None:
        self.allowlist = tuple(allowlist)

    def check(self, url: str) -> EgressDecision:
        try:
            parsed = urlparse(url)
        except ValueError:
            return EgressDecision(allowed=False, host="", reason="invalid url")
        host = parsed.netloc.lower()
        if not host:
            return EgressDecision(allowed=False, host="", reason="no host")
        for pattern in self.allowlist:
            if fnmatch.fnmatchcase(host, pattern.lower()):
                return EgressDecision(allowed=True, host=host)
        return EgressDecision(
            allowed=False,
            host=host,
            reason=f"host {host!r} not in allowlist {list(self.allowlist)!r}",
        )
