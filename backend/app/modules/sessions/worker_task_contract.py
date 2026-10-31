from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_serializer

from app.modules.sessions.auth_context import StoredSessionCookie
from app.modules.shops.enums import ShopPlatform


class WorkerTaskSessionCookie(StoredSessionCookie):
    """A cookie is revealed only when serializing this authenticated response."""

    @field_serializer("value", when_used="json")
    def serialize_value(self, value: SecretStr) -> str:
        return value.get_secret_value()


class WorkerTaskSessionRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shop_id: UUID
    platform: ShopPlatform
    session_version: int = Field(gt=0)
    task_lease_until: datetime
    cookies: tuple[WorkerTaskSessionCookie, ...] = Field(repr=False)
