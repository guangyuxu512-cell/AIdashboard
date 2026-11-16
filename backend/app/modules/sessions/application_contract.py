"""Versioned contract for software clients receiving one authorized session."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_serializer

from app.modules.sessions.auth_context import StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform


class ApplicationShopRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shop_id: UUID
    display_name: str
    platform: ShopPlatform
    session_status: ShopSessionStatus | None


class ApplicationCookie(StoredSessionCookie):
    @field_serializer("value", when_used="json")
    def serialize_secret(self, value: SecretStr) -> str:
        return value.get_secret_value()


class ApplicationSessionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shop_id: UUID
    platform: ShopPlatform
    session_version: int = Field(gt=0)
    cookies: tuple[ApplicationCookie, ...] = Field(repr=False)
