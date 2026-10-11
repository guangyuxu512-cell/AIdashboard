from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy.orm import Session

from app.core.security import EncryptedPayloadError, SecretCipher
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionVersionConflictError,
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.shops.enums import ShopPlatform


class StoredSessionCookie(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str = Field(min_length=1)
    value: SecretStr
    domain: str | None = None
    path: str = "/"
    secure: bool = False
    http_only: bool = Field(default=False, alias="httpOnly")
    same_site: str | None = Field(default=None, alias="sameSite")
    expiration_date: float | None = Field(default=None, alias="expirationDate")


class StoredSessionIdentity(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    platform: ShopPlatform
    platform_shop_id: str = Field(alias="platformShopId", min_length=1)
    shop_display_name: str = Field(alias="shopDisplayName", min_length=1)


class StoredManagementSessionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    schema_name: Literal["management-login.session.v1"] = Field(alias="schema")
    platform: ShopPlatform
    identity: StoredSessionIdentity | None = None
    cookies: list[StoredSessionCookie] = Field(min_length=1)


class ShopSessionAuthContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    shop_id: UUID
    platform: ShopPlatform
    session_version: int
    cookies: tuple[StoredSessionCookie, ...]


class ShopSessionAccessor:
    """The only server-side boundary that decrypts stored ShopSession payloads."""

    def __init__(
        self,
        session: Session,
        cipher: SecretCipher,
        repository: ShopSessionRepository | None = None,
    ) -> None:
        self.session = session
        self.cipher = cipher
        self.repository = repository or ShopSessionRepository(session)

    def get_auth_context(
        self,
        shop_id: UUID,
        expected_platform: ShopPlatform,
    ) -> ShopSessionAuthContext:
        stored = self.repository.get_by_shop(shop_id)
        if stored is None or stored.status is ShopSessionStatus.NOT_CONFIGURED:
            raise ShopSessionNotConfiguredError()
        if stored.status not in {
            ShopSessionStatus.CAPTURED,
            ShopSessionStatus.VALID,
        }:
            raise ShopSessionAuthenticationInvalidError()
        try:
            plaintext = self.cipher.decrypt_bytes(stored.payload_encrypted)
            payload = StoredManagementSessionPayload.model_validate(
                json.loads(plaintext),
            )
        except (
            EncryptedPayloadError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
        ) as error:
            raise ShopSessionPayloadInvalidError() from error
        return self.context_from_payload(shop_id, expected_platform, stored.version, payload)

    @staticmethod
    def context_from_payload(
        shop_id: UUID,
        expected_platform: ShopPlatform,
        version: int,
        payload: StoredManagementSessionPayload,
    ) -> ShopSessionAuthContext:
        """Validate a captured candidate in memory; never replace the stored Session."""
        if payload.platform is not expected_platform:
            raise ShopSessionPayloadInvalidError()
        return ShopSessionAuthContext(
            shop_id=shop_id,
            platform=payload.platform,
            session_version=version,
            cookies=tuple(payload.cookies),
        )

    def merge_response_cookies(
        self,
        shop_id: UUID,
        updates: tuple[StoredSessionCookie, ...],
    ) -> tuple[bytes, int]:
        """Merge explicit Set-Cookie updates without exposing decrypted payloads."""
        stored = self.repository.get_by_shop(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        try:
            plaintext = self.cipher.decrypt_bytes(stored.payload_encrypted)
            return self.merge_payload_cookies(plaintext, updates)
        except (
            EncryptedPayloadError,
        ) as error:
            raise ShopSessionPayloadInvalidError() from error

    @staticmethod
    def merge_payload_cookies(
        plaintext: bytes,
        updates: tuple[StoredSessionCookie, ...],
    ) -> tuple[bytes, int]:
        """Shared Set-Cookie merge for stored and not-yet-persisted candidates."""
        try:
            raw_payload = json.loads(plaintext)
            StoredManagementSessionPayload.model_validate(raw_payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as error:
            raise ShopSessionPayloadInvalidError() from error
        if not isinstance(raw_payload, dict) or not isinstance(
            raw_payload.get("cookies"),
            list,
        ):
            raise ShopSessionPayloadInvalidError()

        cookies = [item for item in raw_payload["cookies"] if isinstance(item, dict)]
        now_timestamp = datetime.now(UTC).timestamp()
        applied = 0
        for update in updates:
            key = _cookie_key(update.name, update.domain, update.path)
            existing_index = next(
                (
                    index
                    for index, item in enumerate(cookies)
                    if _cookie_key(
                        str(item.get("name") or ""),
                        _optional_string(item.get("domain")),
                        str(item.get("path") or "/"),
                    )
                    == key
                ),
                None,
            )
            if update.expiration_date is not None and update.expiration_date <= now_timestamp:
                if existing_index is not None:
                    cookies.pop(existing_index)
                    applied += 1
                continue
            replacement = {
                "name": update.name,
                "value": update.value.get_secret_value(),
                "domain": update.domain,
                "path": update.path,
                "secure": update.secure,
                "httpOnly": update.http_only,
                "sameSite": update.same_site,
                "expirationDate": update.expiration_date,
            }
            replacement = {key: value for key, value in replacement.items() if value is not None}
            if existing_index is None:
                cookies.append(replacement)
            else:
                cookies[existing_index] = {**cookies[existing_index], **replacement}
            applied += 1
        raw_payload["cookies"] = cookies
        return json.dumps(raw_payload, separators=(",", ":")).encode(), applied

    def mark_validation_status(
        self,
        shop_id: UUID,
        expected_version: int,
        status: Literal[ShopSessionStatus.VALID, ShopSessionStatus.INVALID],
    ) -> None:
        stored = self.repository.get_by_shop(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        if not self.repository.set_validation_status(
            shop_id=shop_id,
            expected_version=expected_version,
            status=status,
            validated_at=datetime.now(UTC),
        ):
            self.session.rollback()
            raise SessionVersionConflictError()
        self.session.commit()


def _cookie_key(name: str, domain: str | None, path: str) -> tuple[str, str, str]:
    return (name, (domain or "").lstrip(".").lower(), path or "/")


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
