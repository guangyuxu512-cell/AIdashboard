from uuid import UUID

from pydantic import BaseModel

from app.modules.sessions.auth_context import StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform


class PlatformShopIdentity(BaseModel):
    platform_shop_id: str
    shop_display_name: str
    cookie_updates: tuple[StoredSessionCookie, ...] = ()


class PlatformShopIdentityRead(BaseModel):
    shop_id: UUID
    platform: ShopPlatform
    platform_shop_id: str
    shop_display_name: str
    session_status: ShopSessionStatus
