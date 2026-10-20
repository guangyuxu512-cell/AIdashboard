"""Opaque, batch-scoped ingest credential helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import secrets
from uuid import UUID, uuid4


MIN_SECRET_BYTES = 32
SALT_BYTES = 16


@dataclass(frozen=True)
class CredentialBinding:
    attempt_id: UUID
    gateway_id: str
    device_id: str
    gateway_job_id: str
    capture_batch_id: str
    source_platform: str
    source_product_id: str

    def message(self, credential_id: UUID, version: int, salt_hex: str) -> bytes:
        fields = (
            "central_ingest_v1",
            str(credential_id),
            str(version),
            salt_hex,
            str(self.attempt_id),
            self.gateway_id,
            self.device_id,
            self.gateway_job_id,
            self.capture_batch_id,
            self.source_platform,
            self.source_product_id,
        )
        return "\x1f".join(fields).encode("utf-8")


@dataclass(frozen=True)
class IssuedCredential:
    credential_id: UUID
    version: int
    salt_hex: str
    token: str
    token_sha256: str


def issue_credential(
    *,
    secret: bytes,
    binding: CredentialBinding,
    version: int,
    credential_id: UUID | None = None,
    salt: bytes | None = None,
) -> IssuedCredential:
    if len(secret) < MIN_SECRET_BYTES:
        raise ValueError("Ingest credential secret must contain at least 256 bits")
    if version < 1:
        raise ValueError("Credential version must be positive")
    actual_id = credential_id or uuid4()
    actual_salt = salt or secrets.token_bytes(SALT_BYTES)
    if len(actual_salt) != SALT_BYTES:
        raise ValueError("Credential salt must contain exactly 128 bits")
    salt_hex = actual_salt.hex()
    digest = hmac.digest(secret, binding.message(actual_id, version, salt_hex), "sha256")
    token = f"pci_v1.{actual_id.hex}.{digest.hex()}"
    return IssuedCredential(
        credential_id=actual_id,
        version=version,
        salt_hex=salt_hex,
        token=token,
        token_sha256=sha256(token.encode("ascii")).hexdigest(),
    )


def verify_credential_hash(token: str, expected_sha256: str) -> bool:
    if len(expected_sha256) != 64:
        return False
    actual = sha256(token.encode("ascii")).hexdigest()
    return hmac.compare_digest(actual, expected_sha256)
