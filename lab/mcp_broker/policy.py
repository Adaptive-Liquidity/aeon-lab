"""Per-agent-role allow-lists.

Each agent role declares which MCP servers and which tools within those
servers it is allowed to invoke, plus optional argument-shape constraints.
Anything outside the allow-list is denied at the broker boundary.

Roles are derived from the agent file name (e.g. `planner`, `tdd-guide`,
`security-reviewer`). The default policy can be overridden by a
project-local `lab/mcp_broker/policy.yaml` (loaded at broker startup).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml  # type: ignore[import-untyped]

from lab import ECC_ROOT

log = logging.getLogger("lab.mcp_broker.policy")


@dataclass
class RolePolicy:
    role: str
    servers: tuple[str, ...]
    tools: dict[str, tuple[str, ...]] = field(default_factory=dict)
    can_write_filesystem: bool = False
    can_egress: bool = False
    egress_allowlist: tuple[str, ...] = ()


@dataclass
class McpPolicy:
    roles: dict[str, RolePolicy]
    default_role: str = "restricted"

    def for_role(self, role: str) -> RolePolicy:
        return self.roles.get(role) or self.roles[self.default_role]

    def allowed(self, role: str, server: str, tool: str) -> bool:
        rp = self.for_role(role)
        if server not in rp.servers and "*" not in rp.servers:
            return False
        tool_list = rp.tools.get(server) or rp.tools.get("*", ())
        if not tool_list:
            return True
        return tool in tool_list or "*" in tool_list


# ---------------------------------------------------------------------------
# Default policy — covers the agents shipped under ECC `agents/`.
# Read-only agents (planner, code-explorer, docs-lookup, *-reviewer) cannot
# write to filesystem or reach the network outside well-known doc lookup
# endpoints. tdd-guide, build-error-resolver, code-architect can write to
# the repo filesystem and run tests, but cannot reach uncontrolled HTTP.
# security-reviewer can call security MCPs but cannot egress publicly.
# ---------------------------------------------------------------------------

_DEFAULT_ROLES = {
    "restricted": RolePolicy(
        role="restricted",
        servers=("filesystem",),
        tools={"filesystem": ("read_file", "list_directory")},
        can_write_filesystem=False,
        can_egress=False,
    ),
    "planner": RolePolicy(
        role="planner",
        servers=("filesystem", "context7", "exa", "sequential-thinking", "memory"),
        tools={
            "filesystem": ("read_file", "list_directory", "search_files"),
            "context7": ("*",),
            "exa": ("*",),
            "sequential-thinking": ("*",),
            "memory": ("read_graph", "search_nodes"),
        },
        can_egress=True,
        egress_allowlist=("api.exa.ai", "context7.com", "*.context7.com"),
    ),
    "code-explorer": RolePolicy(
        role="code-explorer",
        servers=("filesystem", "github", "sourcegraph", "memory"),
        tools={"filesystem": ("read_file", "list_directory", "search_files")},
        can_egress=True,
        egress_allowlist=("api.github.com", "sourcegraph.com"),
    ),
    "docs-lookup": RolePolicy(
        role="docs-lookup",
        servers=("context7", "exa", "filesystem"),
        tools={"context7": ("*",), "exa": ("*",)},
        can_egress=True,
        egress_allowlist=("api.exa.ai", "context7.com", "*.context7.com"),
    ),
    "tdd-guide": RolePolicy(
        role="tdd-guide",
        servers=("filesystem", "github"),
        tools={"filesystem": ("*",), "github": ("get_pull_request", "list_files")},
        can_write_filesystem=True,
        can_egress=True,
        egress_allowlist=("api.github.com",),
    ),
    "build-error-resolver": RolePolicy(
        role="build-error-resolver",
        servers=("filesystem", "github"),
        tools={"filesystem": ("*",), "github": ("get_pull_request",)},
        can_write_filesystem=True,
        can_egress=False,
    ),
    "code-architect": RolePolicy(
        role="code-architect",
        servers=("filesystem", "context7", "github"),
        tools={"filesystem": ("*",)},
        can_write_filesystem=True,
        can_egress=True,
        egress_allowlist=("api.github.com", "context7.com"),
    ),
    "architect": RolePolicy(
        role="architect",
        servers=("filesystem", "context7", "exa", "sequential-thinking", "memory"),
        tools={
            "filesystem": ("read_file", "list_directory", "search_files"),
            "context7": ("*",),
            "exa": ("*",),
            "sequential-thinking": ("*",),
        },
        can_egress=True,
        egress_allowlist=("api.exa.ai", "context7.com"),
    ),
    "code-reviewer": RolePolicy(
        role="code-reviewer",
        servers=("filesystem", "github"),
        tools={
            "filesystem": ("read_file", "list_directory", "search_files"),
            "github": (
                "get_pull_request",
                "list_files",
                "list_review_comments",
                "create_review_comment",
            ),
        },
        can_egress=True,
        egress_allowlist=("api.github.com",),
    ),
    "security-reviewer": RolePolicy(
        role="security-reviewer",
        servers=("filesystem", "github"),
        tools={
            "filesystem": ("read_file", "list_directory", "search_files"),
            "github": ("get_pull_request", "list_files"),
        },
        can_egress=False,
    ),
    "mle-reviewer": RolePolicy(
        role="mle-reviewer",
        servers=("filesystem", "context7", "memory"),
        tools={"filesystem": ("read_file", "list_directory")},
        can_egress=False,
    ),
    "performance-optimizer": RolePolicy(
        role="performance-optimizer",
        servers=("filesystem", "datadog"),
        tools={"filesystem": ("read_file", "list_directory")},
        can_egress=True,
        egress_allowlist=("api.datadoghq.com",),
    ),
    "doc-updater": RolePolicy(
        role="doc-updater",
        servers=("filesystem", "github"),
        tools={"filesystem": ("*",)},
        can_write_filesystem=True,
        can_egress=False,
    ),
    "marketing-agent": RolePolicy(
        role="marketing-agent",
        servers=("filesystem", "exa"),
        tools={"filesystem": ("*",), "exa": ("*",)},
        can_write_filesystem=True,
        can_egress=True,
        egress_allowlist=("api.exa.ai",),
    ),
    "researchclaw_codegen": RolePolicy(
        role="researchclaw_codegen",
        servers=("filesystem",),
        tools={"filesystem": ("*",)},
        can_write_filesystem=True,
        can_egress=False,
    ),
    "researchclaw_literature": RolePolicy(
        role="researchclaw_literature",
        servers=("filesystem", "exa", "context7"),
        tools={"exa": ("*",), "context7": ("*",), "filesystem": ("read_file",)},
        can_egress=True,
        egress_allowlist=(
            "api.exa.ai",
            "context7.com",
            "*.context7.com",
            "api.semanticscholar.org",
            "api.openalex.org",
            "export.arxiv.org",
        ),
    ),
}


_DEFAULT_POLICY = McpPolicy(roles=_DEFAULT_ROLES)


def default_policy() -> McpPolicy:
    """Return the in-process default policy."""
    return _DEFAULT_POLICY


def load_policy(path: Path | str | None = None) -> McpPolicy:
    """Load a policy YAML; fall back to the default when missing."""
    if path is None:
        path = ECC_ROOT / "lab" / "mcp_broker" / "policy.yaml"
    p = Path(path)
    if not p.exists():
        return default_policy()
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        log.exception("invalid policy.yaml at %s; using default", p)
        return default_policy()
    roles: dict[str, RolePolicy] = {}
    for role_name, body in (data.get("roles") or {}).items():
        roles[role_name] = RolePolicy(
            role=role_name,
            servers=tuple(body.get("servers", ())),
            tools={k: tuple(v) for k, v in (body.get("tools") or {}).items()},
            can_write_filesystem=bool(body.get("can_write_filesystem", False)),
            can_egress=bool(body.get("can_egress", False)),
            egress_allowlist=tuple(body.get("egress_allowlist", ())),
        )
    if "restricted" not in roles:
        roles["restricted"] = _DEFAULT_ROLES["restricted"]
    return McpPolicy(roles=roles, default_role=data.get("default_role", "restricted"))
