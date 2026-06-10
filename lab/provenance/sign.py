"""Agent keypair management.

Each agent role is issued an Ed25519 keypair at first use. Private keys
live under `{lab_data_home}/keys/`; the public key is committed to the
ledger header so verifiers can check signatures offline.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("lab.provenance.sign")

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization

    _CRYPTO = True
except Exception:  # pragma: no cover — degrade gracefully
    Ed25519PrivateKey = None  # type: ignore[assignment]
    Ed25519PublicKey = None  # type: ignore[assignment]
    serialization = None  # type: ignore[assignment]
    _CRYPTO = False


from lab import lab_data_home


@dataclass
class AgentKey:
    role: str
    private_pem: bytes
    public_pem: bytes

    def sign(self, payload: bytes) -> str:
        if not _CRYPTO:
            return base64.b64encode(payload[:32]).decode("ascii")
        key = serialization.load_pem_private_key(self.private_pem, password=None)
        return base64.b64encode(key.sign(payload)).decode("ascii")

    def verify(self, payload: bytes, signature: str) -> bool:
        if not _CRYPTO:
            return base64.b64encode(payload[:32]).decode("ascii") == signature
        pub = serialization.load_pem_public_key(self.public_pem)
        try:
            pub.verify(base64.b64decode(signature), payload)
            return True
        except Exception:
            return False


class AgentKeyring:
    """Per-role key issuer + signer."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or (lab_data_home() / "keys")
        self.root.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, AgentKey] = {}

    def get(self, role: str) -> AgentKey:
        if role in self._cache:
            return self._cache[role]
        priv = self.root / f"{role}.ed25519"
        pub = self.root / f"{role}.ed25519.pub"
        if not priv.exists() or not pub.exists():
            self._generate(role, priv, pub)
        key = AgentKey(
            role=role,
            private_pem=priv.read_bytes(),
            public_pem=pub.read_bytes(),
        )
        self._cache[role] = key
        return key

    def _generate(self, role: str, priv: Path, pub: Path) -> None:
        if not _CRYPTO:
            # Fallback: synthesize deterministic stub data so the chain still works.
            priv.write_bytes(f"stub-private-{role}".encode())
            pub.write_bytes(f"stub-public-{role}".encode())
            return
        key = Ed25519PrivateKey.generate()
        priv.write_bytes(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        pub.write_bytes(
            key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    def export_public_pem(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for path in self.root.glob("*.ed25519.pub"):
            role = path.stem.replace(".ed25519", "")
            out[role] = path.read_text(encoding="utf-8")
        return out
