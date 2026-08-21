from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.repository import ShopRepository
from app.platforms.base import PlatformConnector
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
    PlatformNotSupportedError,
)
from app.platforms.schemas import PlatformShopIdentityRead


class ShopPlatformService:
    def __init__(
        self,
        session: Session,
        session_accessor: ShopSessionAccessor,
        connectors: dict[ShopPlatform, PlatformConnector],
        shop_repository: ShopRepository | None = None,
    ) -> None:
        self.session_accessor = session_accessor
        self.connectors = connectors
        self.shop_repository = shop_repository or ShopRepository(session)

    def fetch_identity(self, shop_id: UUID) -> PlatformShopIdentityRead:
        shop = self.shop_repository.get(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        connector = self.connectors.get(shop.platform)
        if connector is None:
            raise PlatformNotSupportedError()
        auth_context = self.session_accessor.get_auth_context(
            shop_id,
            shop.platform,
        )
        try:
            identity = connector.fetch_shop_identity(shop_id, auth_context)
        except PlatformAuthenticationInvalidError:
            self.session_accessor.mark_validation_status(
                shop_id,
                ShopSessionStatus.INVALID,
            )
            raise
        if (
            shop.platform_shop_id is not None
            and identity.platform_shop_id != shop.platform_shop_id
        ):
            raise PlatformIdentityMismatchError()
        self.session_accessor.mark_validation_status(
            shop_id,
            ShopSessionStatus.VALID,
        )
        return PlatformShopIdentityRead(
            shop_id=shop.shop_id,
            platform=shop.platform,
            platform_shop_id=identity.platform_shop_id,
            shop_display_name=identity.shop_display_name,
            session_status=ShopSessionStatus.VALID,
        )
