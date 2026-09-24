from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform


class ShopCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=100)
    platform: ShopPlatform
    platform_shop_id: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool = True
    owner_user_id: UUID | None = None
    note: str | None = Field(default=None, max_length=1000)


class ShopUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    platform: ShopPlatform | None = None
    enabled: bool | None = None
    owner_user_id: UUID | None = None
    note: str | None = Field(default=None, max_length=1000)
    # An explicit null clears a manager-confirmed coverage boundary.  Pydantic
    # preserves the difference between an omitted field and this explicit
    # clear through ``model_fields_set``.
    operating_start_date: date | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ShopUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field in ("display_name", "platform", "enabled"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null")
        return self


class ShopRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_id: UUID
    display_name: str
    platform: ShopPlatform
    platform_shop_id: str | None
    enabled: bool
    owner_user_id: UUID | None
    note: str | None
    # Defaults retain compatibility for existing service/mocking callers that
    # construct a ShopRead from the pre-0041 contract. SQLAlchemy-backed
    # responses still expose the database values once the migration is live.
    operating_start_date: date | None = None
    operating_start_date_source: Literal["manual"] | None = None
    operating_start_date_set_by_user_id: UUID | None = None
    operating_start_date_set_at: datetime | None = None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ShopListRead(ShopRead):
    session_status: ShopSessionStatus | None


class ShopDeviceBindingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: UUID
    enabled: bool = True


class ShopDeviceBindingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "ShopDeviceBindingUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field in ("enabled",):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null")
        return self


class ShopDeviceBindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    shop_id: UUID
    device_id: UUID
    enabled: bool
    created_at: datetime
    updated_at: datetime
