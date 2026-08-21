from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.modules.notifications.enums import NotificationChannelType


def _validate_webhook_url(value: SecretStr | None) -> SecretStr | None:
    if value is None:
        return None
    raw_value = value.get_secret_value().strip()
    parsed = urlsplit(raw_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Webhook URL 必须是有效的 HTTP(S) 地址")
    return SecretStr(raw_value)


class NotificationChannelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    channel_type: NotificationChannelType
    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    webhook_url: SecretStr = Field(min_length=1, max_length=2048)
    device_offline_enabled: bool = True
    device_recovered_enabled: bool = True

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: SecretStr) -> SecretStr:
        return _validate_webhook_url(value)  # type: ignore[return-value]


class NotificationChannelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    channel_type: NotificationChannelType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    webhook_url: SecretStr | None = Field(default=None, max_length=2048)
    device_offline_enabled: bool | None = None
    device_recovered_enabled: bool | None = None

    @field_validator("webhook_url", mode="before")
    @classmethod
    def blank_webhook_means_unchanged(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, value: SecretStr | None) -> SecretStr | None:
        return _validate_webhook_url(value)

    @model_validator(mode="after")
    def require_change(self) -> "NotificationChannelUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        return self


class NotificationChannelRead(BaseModel):
    channel_id: UUID
    channel_type: NotificationChannelType
    name: str
    enabled: bool
    webhook_configured: bool
    device_offline_enabled: bool
    device_recovered_enabled: bool
    created_at: datetime
    updated_at: datetime


class NotificationTestRead(BaseModel):
    delivered: bool
