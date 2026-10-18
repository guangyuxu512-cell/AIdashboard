from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.modules.sessions.auth_context import ShopSessionAuthContext, StoredSessionCookie
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.endpoints import COMPASS_PRODUCT_DATA_LIST_ENDPOINT
from app.platforms.douyin.product_data import CompassProductDataPage, parse_compass_product_data_page
from app.platforms.douyin.session_query import session_query_context
from app.platforms.exceptions import PlatformIdentityMismatchError


class FrozenProductDataRequest(Protocol):
    @property
    def shop_id(self) -> UUID: ...

    def business_query(self, page_no: int) -> dict[str, str]: ...


@dataclass(frozen=True)
class ProductDataFetchResult:
    page: CompassProductDataPage
    cookie_updates: tuple[StoredSessionCookie, ...]


class DouyinProductDataConnector:
    def __init__(self, api_client: DouyinApiClient | None = None):
        self.api_client = api_client or DouyinApiClient()

    def page(self, context: ShopSessionAuthContext, scope: FrozenProductDataRequest,
             platform_shop_id: str, page_no: int) -> ProductDataFetchResult:
        if context.platform != ShopPlatform.DOUYIN or context.shop_id != scope.shop_id:
            raise PlatformIdentityMismatchError()
        endpoint = COMPASS_PRODUCT_DATA_LIST_ENDPOINT
        response = self.api_client.request_json(
            endpoint, context,
            query=scope.business_query(page_no) | session_query_context(endpoint, context),
            precise_numbers=True,
        )
        page = parse_compass_product_data_page(response.payload, expected_platform_shop_id=platform_shop_id,
                                               expected_page_no=page_no, expected_page_size=10)
        return ProductDataFetchResult(page, response.cookie_updates)
