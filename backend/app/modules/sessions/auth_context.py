"""Legacy parser types retained by the paused selection/operating modules.

These types do not load, save or decrypt a shop session on the server.
"""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool

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
    merchant_identity_check_required: StrictBool = Field(default=False, alias="merchantIdentityCheckRequired")


class ShopSessionAuthContext(BaseModel):
    model_config = ConfigDict(frozen=True)
    shop_id: UUID
    platform: ShopPlatform
    session_version: int
    cookies: tuple[StoredSessionCookie, ...]
    identity: StoredSessionIdentity | None = None
