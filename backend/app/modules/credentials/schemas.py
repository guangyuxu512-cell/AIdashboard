from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.modules.credentials.enums import VerificationChannel
from app.modules.shops.enums import ShopPlatform


class CredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    shop_id: UUID
    login_identifier: str = Field(min_length=1, max_length=320)
    secret: SecretStr = Field(min_length=1, max_length=1000)
    preferred_verification_channel: VerificationChannel = VerificationChannel.MANUAL


class CredentialUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    login_identifier: str | None = Field(default=None, min_length=1, max_length=320)
    secret: SecretStr | None = Field(default=None, min_length=1, max_length=1000)
    preferred_verification_channel: VerificationChannel | None = None

    @field_validator("login_identifier", "secret", mode="before")
    @classmethod
    def blank_means_unchanged(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def require_change(self) -> "CredentialUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        return self


class CredentialStatusRead(BaseModel):
    credential_id: UUID | None
    platform: ShopPlatform
    masked_identifier: str | None
    configured: bool
    enabled: bool
    preferred_verification_channel: VerificationChannel | None
    updated_at: datetime | None
