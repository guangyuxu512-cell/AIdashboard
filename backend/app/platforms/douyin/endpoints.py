from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DouyinEndpoint:
    """A verified Douyin request contract owned by the Douyin platform layer."""

    host: str
    path: str
    method: Literal["GET", "POST"]
    sign_required: bool = False
    referer: str | None = None
    aid: int | None = None
    page_id: int | None = None
    headers: tuple[tuple[str, str], ...] = ()

    @property
    def url(self) -> str:
        return f"https://{self.host}{self.path}"


SHOP_INFO_V2_ENDPOINT = DouyinEndpoint(
    host="compass.jinritemai.com",
    path="/compass_api/shop/mall/common/shop_info_v2",
    method="GET",
    headers=(("accept", "application/json, text/plain, */*"),),
)


PRODUCT_LIST_ENDPOINT = DouyinEndpoint(
    host="fxg.jinritemai.com",
    path="/product/tproduct/list",
    method="GET",
    sign_required=True,
    referer="https://fxg.jinritemai.com/ffa/g/list",
    aid=6383,
    page_id=6241,
    headers=(
        ("accept", "application/json, text/plain, */*"),
        ("referer", "https://fxg.jinritemai.com/ffa/g/list"),
        (
            "user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36",
        ),
        ("x-tt-from-end", "PC"),
        ("x-tt-from-appid", "ffa-goods"),
        ("x-tt-from-page", "https://fxg.jinritemai.com/ffa/g/list"),
        ("x-tt-from-version", "1.0.1.7840"),
        ("x-wb-strategy", "swr"),
        (
            "x-wb-config",
            '{"key":"?page=0&pageSize=20&id_name_code=&sku_price=&goodsType=&sell_num='
            "&category=&draft_status=0&delivery_mode=&comment_percent=&group_id=&create_time="
            "&audit_time=&freight_id=&&return_policy_id=&sku_type=&category_property_artnumber="
            "&have_correct_ticket=&tab=onSale&business_type=4&is_online=1&not_for_sale_search_type=1"
            "&from_mng=1&check_status=3&status=0&supply_status=&offline_time="
            "&need_auto_rectify_info=true&need_pay_no_stock_skus=true&order_field=audit_time&sort=desc\"}",
        ),
        ("sec-ch-ua", '"Chromium";v="152", "Not?A_Brand";v="24", "Google Chrome";v="152"'),
        ("sec-ch-ua-mobile", "?0"),
        ("sec-ch-ua-platform", '"Windows"'),
    ),
)


# Verified from the Compass homepage request contract.  Keep dynamic browser
# context out of this definition: `_lid` is supplied per request and the
# signed request is built without `a_bogus`, which the API client injects only
# after the signer returns a fresh value.
COMPASS_CORE_INDEX_V3_ENDPOINT = DouyinEndpoint(
    host="compass.jinritemai.com",
    path="/compass_api/shop/common/homepage/core_index_v3",
    method="GET",
    sign_required=True,
    referer="https://compass.jinritemai.com/shop",
    headers=(
        ("accept", "application/json, text/plain, */*"),
        ("accept-language", "zh-CN"),
        ("agw-js-conv", "str"),
        ("cache-control", "no-cache"),
        ("pragma", "no-cache"),
        ("sec-ch-ua", '"Not?A_Brand";v="8", "Chromium";v="108"'),
        ("sec-ch-ua-mobile", "?0"),
        ("sec-ch-ua-platform", '"Windows"'),
        ("sec-fetch-dest", "empty"),
        ("sec-fetch-mode", "cors"),
        ("sec-fetch-site", "same-origin"),
        ("x-e2e-platform", "compass"),
        ("referer", "https://compass.jinritemai.com/shop"),
        (
            "user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) feige/1.1.11 "
            "Chrome/108.0.5359.215 Electron/22.3.18-tt.10.release.main.13 "
            "TTElectron/22.3.18-tt.10.release.main.13 Safari/537.36",
        ),
    ),
)
