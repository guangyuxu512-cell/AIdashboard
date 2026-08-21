from uuid import UUID

from app.modules.sessions.health_service import ShopSessionHealthService
from app.platforms.schemas import PlatformShopIdentityRead


class ShopPlatformService:
    def __init__(
        self,
        health_service: ShopSessionHealthService,
    ) -> None:
        self.health_service = health_service

    def fetch_identity(self, shop_id: UUID) -> PlatformShopIdentityRead:
        health = self.health_service.check(shop_id, force=True)
        return PlatformShopIdentityRead(
            shop_id=health.shop_id,
            platform=health.platform,
            platform_shop_id=health.platform_shop_id,
            shop_display_name=health.shop_display_name,
            session_status=health.status,
        )
