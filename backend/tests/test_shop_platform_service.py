from datetime import UTC, datetime
from uuid import uuid4

from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.schemas import ShopSessionHealthRead
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.platform_service import ShopPlatformService


class FakeHealthService:
    def check(self, shop_id, *, force: bool) -> ShopSessionHealthRead:
        assert force is True
        return ShopSessionHealthRead(
            shop_id=shop_id,
            platform=ShopPlatform.DOUYIN,
            platform_shop_id="platform-shop-1",
            shop_display_name="HuanYu",
            status=ShopSessionStatus.VALID,
            version=2,
            validated_at=datetime.now(UTC),
            used_cached_validation=False,
            cookie_updates_applied=0,
        )


def test_platform_service_delegates_to_session_health_boundary() -> None:
    shop_id = uuid4()
    service = ShopPlatformService(FakeHealthService())  # type: ignore[arg-type]

    result = service.fetch_identity(shop_id)

    assert result.shop_display_name == "HuanYu"
    assert result.session_status is ShopSessionStatus.VALID
