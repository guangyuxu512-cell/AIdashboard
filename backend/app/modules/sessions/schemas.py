from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.sessions.enums import ShopSessionStatus


class ShopSessionMetadataRead(BaseModel):
    session_id: UUID | None
    configured: bool
    status: ShopSessionStatus
    version: int
    source_device_id: UUID | None
    captured_at: datetime | None
    validated_at: datetime | None
    expires_at: datetime | None


class StoreShopSessionCommand(BaseModel):
    shop_id: UUID
    expected_version: int
    status: ShopSessionStatus
    source_device_id: UUID | None
    captured_at: datetime
    validated_at: datetime | None = None
    expires_at: datetime | None = None
