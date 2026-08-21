from typing import Protocol
from uuid import UUID

from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.platforms.schemas import PlatformShopIdentity


class PlatformConnector(Protocol):
    def fetch_shop_identity(
        self,
        shop_id: UUID,
        auth_context: ShopSessionAuthContext,
    ) -> PlatformShopIdentity: ...
