"""Authentication of independent backend applications, not Worker devices."""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator

from app.core.exceptions import AppError


class ApplicationSessionUnavailableError(AppError):
    code = "APPLICATION_SESSION_UNAVAILABLE"
    message = "软件 Session 接口未启用或授权配置不可用"
    status_code = 503


class ApplicationAuthenticationError(AppError):
    code = "APPLICATION_AUTHENTICATION_FAILED"
    message = "软件凭据无效或已撤销"
    status_code = 401


class ApplicationTransportError(AppError):
    code = "APPLICATION_TLS_REQUIRED"
    message = "软件 Session 接口需要 HTTPS 连接"
    status_code = 403


class ApplicationShopNotFoundError(AppError):
    code = "APPLICATION_SHOP_NOT_FOUND"
    message = "店铺不存在或未授权"
    status_code = 404


class ApplicationSessionBusyError(AppError):
    code = "APPLICATION_SESSION_BUSY"
    message = "店铺或授权正在更新，请稍后重试"
    status_code = 409


class ClientGrant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    client_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    token_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", repr=False)
    authorized_by_user_id: UUID
    enabled: StrictBool
    shop_ids: tuple[UUID, ...] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_shop_ids(self) -> ClientGrant:
        if len(set(self.shop_ids)) != len(self.shop_ids):
            raise ValueError("duplicate shop grants")
        return self


class ClientConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = Field(ge=1, le=1, strict=True)
    clients: tuple[ClientGrant, ...] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_clients(self) -> ClientConfiguration:
        ids = [entry.client_id for entry in self.clients]
        hashes = [entry.token_sha256 for entry in self.clients]
        if len(set(ids)) != len(ids) or len(set(hashes)) != len(hashes):
            raise ValueError("duplicate client ids or token hashes")
        return self


@dataclass(frozen=True, slots=True)
class ApplicationPrincipal:
    grant: ClientGrant
    # Needed only for an in-flight authorization recheck; never logged or repr'd.
    token: str = field(repr=False)


class ApplicationAuthenticator:
    """Re-read the protected configuration for every authorization decision."""

    def __init__(self, *, enabled: bool, path: Path | None) -> None:
        self.enabled = enabled
        self.path = path

    def authenticate(self, client_id: str, token: str) -> ApplicationPrincipal:
        if not self.enabled or self.path is None:
            raise ApplicationSessionUnavailableError()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", client_id):
            raise ApplicationAuthenticationError()
        if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
            raise ApplicationAuthenticationError()
        try:
            with self.path.open("rb") as config_file:
                content = config_file.read(1024 * 1024 + 1)
            if len(content) > 1024 * 1024:
                raise ValueError("configuration too large")
            config = ClientConfiguration.model_validate_json(content)
        except (OSError, ValueError, ValidationError):
            raise ApplicationSessionUnavailableError() from None
        presented_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
        grant = next((item for item in config.clients if item.client_id == client_id), None)
        if grant is None or not grant.enabled or not hmac.compare_digest(
            presented_hash, grant.token_sha256,
        ):
            raise ApplicationAuthenticationError()
        return ApplicationPrincipal(grant=grant, token=token)

    def reauthorize(self, principal: ApplicationPrincipal, shop_id: UUID) -> ClientGrant:
        current = self.authenticate(principal.grant.client_id, principal.token).grant
        if current.authorized_by_user_id != principal.grant.authorized_by_user_id:
            raise ApplicationAuthenticationError()
        if shop_id not in current.shop_ids:
            raise ApplicationShopNotFoundError()
        return current
