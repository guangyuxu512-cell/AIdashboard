from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr

from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform


class ShopSessionMetadataRead(BaseModel):
    session_id: UUID | None
    configured: bool
    status: ShopSessionStatus
    version: int
    source_device_id: UUID | None
    captured_at: datetime | None
    validated_at: datetime | None
    expires_at: datetime | None
    refresh_in_progress: bool = False
    refresh_lease_expires_at: datetime | None = None


class ShopSessionHealthRead(BaseModel):
    shop_id: UUID
    platform: ShopPlatform
    platform_shop_id: str
    shop_display_name: str
    status: ShopSessionStatus
    version: int
    validated_at: datetime
    used_cached_validation: bool
    cookie_updates_applied: int


class ShopSessionRefreshLeaseRead(BaseModel):
    shop_id: UUID
    lease_id: UUID
    expected_version: int
    expires_at: datetime


class CompleteShopSessionRefreshCommand(BaseModel):
    lease_id: UUID
    expected_version: int = Field(ge=1)
    session_payload_base64: SecretStr
    captured_at: datetime


class StoreShopSessionCommand(BaseModel):
    shop_id: UUID
    expected_version: int
    status: ShopSessionStatus
    source_device_id: UUID | None
    captured_at: datetime
    validated_at: datetime | None = None
    expires_at: datetime | None = None
