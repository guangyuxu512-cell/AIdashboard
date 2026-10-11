"""Read-only Compass I/O; request selection remains the business resolver's job."""

from collections.abc import Mapping

import httpx

from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.api_client import DouyinApiClient
from app.platforms.douyin.endpoints import (
    COMPASS_CATEGORY_ENDPOINT, COMPASS_SELECTION_BASIC_INFO_ENDPOINT,
    COMPASS_SELECTION_RANK_ENDPOINT, DouyinEndpoint,
)
from app.platforms.douyin.product_selection import (
    CompassBasicInfo, CompassCategoryTree, CompassRankPage,
    parse_compass_basic_info, parse_compass_categories, parse_compass_rank_page,
)
from app.platforms.exceptions import PlatformRequestFailedError
from app.platforms.session_cookies import to_httpx_cookies


RANK_BUSINESS_KEYS = (
    "page_no", "page_size", "industry_id", "category_id", "brand_type",
    "price_bin", "search_info", "rank_data_type", "begin_date", "end_date",
    "date_type", "activity_id",
)


def _session_query_context(endpoint: DouyinEndpoint, context: ShopSessionAuthContext) -> dict[str, str]:
    # The successful server sample used its *selected* Session cookie for these
    # optional fields. Do not merge another domain/path's fingerprint or claim
    # that this rule is required for every Compass request.
    request = httpx.Request("GET", endpoint.url)
    to_httpx_cookies(context.cookies).set_cookie_header(request)
    values = {
        part.strip().partition("=")[2]
        for part in request.headers.get("cookie", "").split(";")
        if part.strip().partition("=")[0] == "s_v_web_id"
    }
    # Conflicting same-name fingerprints are not safe to choose by accident.
    return {"fp": next(iter(values)), "verifyFp": next(iter(values))} if len(values) == 1 and "" not in values else {}


class DouyinProductSelectionConnector:
    def __init__(self, api_client: DouyinApiClient | None = None):
        self.api_client = api_client or DouyinApiClient()

    def _request(self, endpoint: DouyinEndpoint, context: ShopSessionAuthContext, query: Mapping[str, str]):
        if context.platform != ShopPlatform.DOUYIN:
            raise PlatformRequestFailedError()
        # Credentials stay in the existing HTTP/signing boundary. No request
        # URL, response payload, callback or Session is logged/persisted here.
        return self.api_client.request_json(
            endpoint, context, query=dict(query) | _session_query_context(endpoint, context),
        ).payload

    def categories(self, context: ShopSessionAuthContext) -> CompassCategoryTree:
        return parse_compass_categories(self._request(COMPASS_CATEGORY_ENDPOINT, context, {
            "level": "4", "scene": "6", "default_cate_to_level": "2",
        }))

    def rank(self, context: ShopSessionAuthContext, query: Mapping[str, str]) -> CompassRankPage:
        if set(query) != set(RANK_BUSINESS_KEYS) or any(type(value) is not str for value in query.values()):
            raise ValueError("Rank I/O accepts only the frozen business query")
        # Preserve the observed business query order, including explicit empties.
        return parse_compass_rank_page(self._request(
            COMPASS_SELECTION_RANK_ENDPOINT, context,
            {key: query[key] for key in RANK_BUSINESS_KEYS},
        ))

    def basic_info(self, context: ShopSessionAuthContext, product_id: str) -> CompassBasicInfo:
        if not isinstance(product_id, str) or not product_id.isascii() or not product_id.isdigit():
            raise ValueError("Product identity must remain a decimal string")
        return parse_compass_basic_info(self._request(
            COMPASS_SELECTION_BASIC_INFO_ENDPOINT, context, {"product_id": product_id},
        ), expected_product_id=product_id)
