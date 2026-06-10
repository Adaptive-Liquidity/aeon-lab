"""Policy-enforcing MCP proxy.

Wraps the 14 backing MCP servers configured in `mcp-configs/` (plus the
per-harness configs under `.cursor/`, `.claude/`, etc.) with:

  - per-agent-role allow-lists (`policy.py`)
  - secret detection + redaction (`scrub.py`)
  - outbound HTTP allow-listing (`egress.py`)
  - decision audit log
"""

from lab.mcp_broker.proxy import McpBroker
from lab.mcp_broker.policy import McpPolicy, default_policy
from lab.mcp_broker.scrub import scrub_secrets
from lab.mcp_broker.egress import EgressFilter

__all__ = ["McpBroker", "McpPolicy", "default_policy", "scrub_secrets", "EgressFilter"]
