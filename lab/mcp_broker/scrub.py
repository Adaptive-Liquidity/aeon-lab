"""Secret detection + redaction for MCP traffic.

Scrubs known credential shapes from tool arguments (pre-call) and tool
results (post-call). On detection we replace the value with a placeholder
and emit an audit event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"xox[bopas]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+]{30,}"),
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"),
)

PLACEHOLDER = "[REDACTED::secret]"


@dataclass
class ScrubResult:
    cleaned: Any
    redactions: list[str]


def scrub_secrets(value: Any) -> ScrubResult:
    redactions: list[str] = []

    def _walk(v: Any) -> Any:
        if isinstance(v, str):
            for pattern in SECRET_PATTERNS:
                if pattern.search(v):
                    redactions.append(pattern.pattern)
                    v = pattern.sub(PLACEHOLDER, v)
            return v
        if isinstance(v, dict):
            return {k: _walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [_walk(x) for x in v]
        if isinstance(v, tuple):
            return tuple(_walk(x) for x in v)
        return v

    cleaned = _walk(value)
    return ScrubResult(cleaned=cleaned, redactions=redactions)
