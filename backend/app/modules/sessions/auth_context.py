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
    expiration_date: float | None = Field(default=None, alias="expirationDate")


class StoredManagementSessionPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    schema_name: Literal["management-login.session.v1"] = Field(alias="schema")
    platform: ShopPlatform
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
        if stored is None:
            raise ShopSessionNotConfiguredError()
        if stored.status not in {
            ShopSessionStatus.CAPTURED,
            ShopSessionStatus.VALID,
        }:
            raise ShopSessionAuthenticationInvalidError()
        now = datetime.now(UTC)
        if stored.expires_at is not None and stored.expires_at <= now:
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
        if payload.platform is not expected_platform:
            raise ShopSessionPayloadInvalidError()

        active_cookies = tuple(
            cookie
            for cookie in payload.cookies
            if cookie.expiration_date is None
            or cookie.expiration_date > now.timestamp()
        )
        if not active_cookies:
            raise ShopSessionAuthenticationInvalidError()
        return ShopSessionAuthContext(
            shop_id=shop_id,
            platform=payload.platform,
            session_version=stored.version,
            cookies=active_cookies,
        )

    def mark_validation_status(
        self,
        shop_id: UUID,
        status: Literal[ShopSessionStatus.VALID, ShopSessionStatus.INVALID],
    ) -> None:
        stored = self.repository.get_by_shop(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        if not self.repository.set_validation_status(
            shop_id=shop_id,
            status=status,
            validated_at=datetime.now(UTC),
        ):
            self.session.rollback()
            raise ShopSessionNotConfiguredError()
        self.session.commit()
