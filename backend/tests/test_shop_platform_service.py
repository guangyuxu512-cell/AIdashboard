from uuid import UUID, uuid4

import pytest

from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.shops.platform_service import ShopPlatformService
from app.platforms.exceptions import PlatformAuthenticationInvalidError
from app.platforms.schemas import PlatformShopIdentity
from tests.support import FakeSession


class FakeShopRepository:
    def __init__(self, shop: Shop) -> None:
        self.shop = shop

    def get(self, shop_id: UUID) -> Shop | None:
        return self.shop if self.shop.shop_id == shop_id else None


class FakeSessionAccessor:
    def __init__(self) -> None:
        self.marked: list[ShopSessionStatus] = []

    def get_auth_context(self, shop_id: UUID, platform: ShopPlatform) -> object:
        return object()

    def mark_validation_status(
        self,
        shop_id: UUID,
        status: ShopSessionStatus,
    ) -> None:
        self.marked.append(status)


class FakeConnector:
    def __init__(self, *, auth_invalid: bool = False) -> None:
        self.auth_invalid = auth_invalid

    def fetch_shop_identity(self, shop_id: UUID, auth_context: object) -> PlatformShopIdentity:
        if self.auth_invalid:
            raise PlatformAuthenticationInvalidError()
        return PlatformShopIdentity(
            platform_shop_id="platform-shop-1",
            shop_display_name="HuanYu",
        )


def make_service(
    accessor: FakeSessionAccessor,
    connector: FakeConnector,
) -> tuple[ShopPlatformService, UUID]:
    shop_id = uuid4()
    shop = Shop(
        shop_id=shop_id,
        display_name="HuanYu",
        platform=ShopPlatform.DOUYIN,
        platform_shop_id="platform-shop-1",
        enabled=True,
    )
    service = ShopPlatformService(
        FakeSession(),  # type: ignore[arg-type]
        accessor,  # type: ignore[arg-type]
        {ShopPlatform.DOUYIN: connector},  # type: ignore[dict-item]
        FakeShopRepository(shop),  # type: ignore[arg-type]
    )
    return service, shop_id


def test_service_marks_session_valid_after_identity_match() -> None:
    accessor = FakeSessionAccessor()
    service, shop_id = make_service(accessor, FakeConnector())

    result = service.fetch_identity(shop_id)

    assert result.shop_display_name == "HuanYu"
    assert result.session_status is ShopSessionStatus.VALID
    assert accessor.marked == [ShopSessionStatus.VALID]


def test_service_marks_session_invalid_only_for_explicit_auth_failure() -> None:
    accessor = FakeSessionAccessor()
    service, shop_id = make_service(accessor, FakeConnector(auth_invalid=True))

    with pytest.raises(PlatformAuthenticationInvalidError):
        service.fetch_identity(shop_id)

    assert accessor.marked == [ShopSessionStatus.INVALID]
