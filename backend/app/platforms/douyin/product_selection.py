"""Fixed-path parsing of the observed Compass selection responses.

This module does not infer channel/date enums or issue requests.  A business
query must be frozen separately before the service can execute it.  Metric
ranges and ratio units are retained without unverified display conversions.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Generic, Literal, TypeVar
from urllib.parse import parse_qsl, urlsplit

from app.platforms.exceptions import (
    PlatformRequestFailedError,
    PlatformResponseInvalidError,
)


T = TypeVar("T")
ObservationState = Literal["available", "missing", "null", "invalid"]


class CompassSelectionBusinessError(PlatformRequestFailedError):
    code = "DOUYIN_SELECTION_BUSINESS_REJECTED"
    message = "罗盘选品请求被平台业务拒绝，原因未确定"


class CompassSelectionIdentityError(PlatformResponseInvalidError):
    code = "DOUYIN_SELECTION_PRODUCT_ID_MISMATCH"
    message = "罗盘补充信息返回的商品身份不一致"


@dataclass(frozen=True)
class FieldObservation(Generic[T]):
    state: ObservationState
    value: T | None = None


@dataclass(frozen=True)
class CompassCategoryNode:
    category_id: str
    name: str
    children: tuple[CompassCategoryNode, ...]


@dataclass(frozen=True)
class CompassCategoryTree:
    nodes: tuple[CompassCategoryNode, ...]
    industry_id: str | None
    industry_name: str | None
    selected_category_id: str | None


@dataclass(frozen=True)
class CompassRangeEndpoint:
    value: Decimal
    value_type: Literal["int", "float"]
    unit: str | int | None


@dataclass(frozen=True)
class CompassMetricRange:
    endpoints: tuple[CompassRangeEndpoint, CompassRangeEndpoint]


@dataclass(frozen=True)
class CompassMerchant:
    platform_shop_id: str
    name: str | None


@dataclass(frozen=True)
class CompassRankProduct:
    product_id: str
    title: str | None
    image_url: str | None
    rank: int | None
    price_band: str | None
    merchants: tuple[CompassMerchant, ...]
    leaf_category_id: str | None
    newly_on_ranking: bool | None
    # These four names are the observed platform fields, not converted units.
    pay_amt: FieldObservation[CompassMetricRange]
    pay_combo_cnt: FieldObservation[CompassMetricRange]
    product_click_cnt: FieldObservation[CompassMetricRange]
    video_cnt: FieldObservation[CompassMetricRange]


@dataclass(frozen=True)
class CompassRankPage:
    products: tuple[CompassRankProduct, ...]
    page_no: int
    page_size: int
    total: int


@dataclass(frozen=True)
class CompassBadCommentRate:
    value: Decimal
    value_type: Literal["int", "float"]
    unit: str | int | None


@dataclass(frozen=True)
class CompassBasicInfo:
    product_id: str
    category_path: FieldObservation[tuple[str, ...]]
    first_on_shelf_date: FieldObservation[date]
    bad_comment_rate: FieldObservation[CompassBadCommentRate]


def parse_compass_categories(payload: Mapping[str, Any]) -> CompassCategoryTree:
    data = _success_data(payload)
    rows = data.get("cate_list")
    if not isinstance(rows, list):
        raise _invalid("data.cate_list")

    def node(raw: Any, path: str, depth: int) -> CompassCategoryNode:
        # Only the documented children path is traversed.  Do not recursively
        # search arbitrary objects for similarly named fields.
        if depth > 8 or not isinstance(raw, Mapping):
            raise _invalid(path)
        category_id = _identifier(raw.get("cate_id"))
        name = _text(raw.get("cate_name"))
        children = raw.get("children")
        if category_id is None or name is None or not isinstance(children, list):
            raise _invalid(path)
        return CompassCategoryNode(
            category_id=category_id,
            name=name,
            children=tuple(
                node(child, f"{path}.children", depth + 1) for child in children
            ),
        )

    return CompassCategoryTree(
        nodes=tuple(node(row, "data.cate_list[]", 0) for row in rows),
        industry_id=_identifier(data.get("industry_id")),
        industry_name=_text(data.get("industry_name")),
        selected_category_id=_identifier(data.get("cate_id")),
    )


def parse_compass_rank_page(payload: Mapping[str, Any]) -> CompassRankPage:
    data = _success_data(payload)
    rows = data.get("data_result")
    pagination = data.get("page_result")
    if not isinstance(rows, list) or not isinstance(pagination, Mapping):
        raise _invalid("data.data_result / data.page_result")
    page_no = _required_integer(pagination, "page_no", minimum=1)
    page_size = _required_integer(pagination, "page_size", minimum=1)
    total = _required_integer(pagination, "total", minimum=0)
    if len(rows) > page_size:
        raise _invalid("data.data_result")
    products: list[CompassRankProduct] = []
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("product_info"), Mapping):
            raise _invalid("data.data_result[].product_info")
        info = row["product_info"]
        # The observed product ID is a JSON string.  In particular, never
        # accept a float and stringify an already-rounded 19-digit ID.
        product_id = _text(info.get("id"))
        if product_id is None:
            raise _invalid("data.data_result[].product_info.id")
        merchants: list[CompassMerchant] = []
        shop_list = info.get("shop_list")
        if isinstance(shop_list, list):
            for shop in shop_list:
                if not isinstance(shop, Mapping):
                    continue
                shop_id = _identifier(shop.get("shop_id"))
                if shop_id is not None:
                    merchants.append(CompassMerchant(shop_id, _text(shop.get("shop_name"))))
        products.append(CompassRankProduct(
            product_id=product_id,
            title=_text(info.get("name")),
            image_url=_public_url(info.get("image_url")),
            rank=_optional_integer(info.get("rank")),
            price_band=_text(info.get("price_bin")),
            merchants=tuple(merchants),
            leaf_category_id=_identifier(info.get("leaf_category_id")),
            newly_on_ranking=(
                info["newly_on_ranking"]
                if type(info.get("newly_on_ranking")) is bool else None
            ),
            pay_amt=_range_observation(row, "pay_amt"),
            pay_combo_cnt=_range_observation(row, "pay_combo_cnt"),
            product_click_cnt=_range_observation(row, "product_click_cnt"),
            video_cnt=_range_observation(row, "video_cnt"),
        ))
    return CompassRankPage(tuple(products), page_no, page_size, total)


def parse_compass_basic_info(
    payload: Mapping[str, Any],
    *,
    expected_product_id: str,
) -> CompassBasicInfo:
    data = _success_data(payload)
    product_id = _text(data.get("product_id"))
    if product_id is None:
        raise _invalid("data.product_id")
    if product_id != expected_product_id:
        raise CompassSelectionIdentityError(details={"failure_stage": "response_parse"})
    return CompassBasicInfo(
        product_id=product_id,
        category_path=_category_path(data),
        first_on_shelf_date=_shelf_date(data),
        bad_comment_rate=_bad_comment_rate(data),
    )


def _success_data(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise _invalid("response")
    status = payload.get("st")
    # bool is an int subclass; False must not be accepted as business code 0.
    if type(status) not in {int, str}:
        raise _invalid("st")
    if status not in (0, "0"):
        # Raw messages may carry a URL or browser context.  Persist only the
        # typed business code, not arbitrary platform messages or payloads.
        raise CompassSelectionBusinessError(details={
            "failure_stage": "platform_business",
            "platform_code": (
                status if type(status) is int
                else status if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", status)
                else "unrecognized_string_code"
            ),
        })
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise _invalid("data")
    return data


def _invalid(path: str) -> PlatformResponseInvalidError:
    return PlatformResponseInvalidError(details={
        "failure_stage": "response_parse", "field_path": path,
    })


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _identifier(value: Any) -> str | None:
    if type(value) is int and value >= 0:
        return str(value)
    return _text(value)


def _optional_integer(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _required_integer(raw: Mapping[str, Any], key: str, *, minimum: int) -> int:
    value = raw.get(key)
    if type(value) is not int or value < minimum:
        raise _invalid(f"data.page_result.{key}")
    return value


def _absent(raw: Mapping[str, Any], key: str) -> FieldObservation[Any] | None:
    if key not in raw:
        return FieldObservation("missing")
    if raw[key] is None:
        return FieldObservation("null")
    return None


def _number(value: Any) -> tuple[Decimal, Literal["int", "float"]] | None:
    if type(value) not in {int, float}:
        return None
    try:
        numeric = Decimal(str(value))
    except InvalidOperation:
        return None
    if not numeric.is_finite() or numeric < 0:
        return None
    value_type: Literal["int", "float"] = "int" if type(value) is int else "float"
    return numeric, value_type


def _unit(value: Any) -> str | int | None:
    return value if type(value) in {str, int} else None


def _range_observation(
    raw: Mapping[str, Any], field: str,
) -> FieldObservation[CompassMetricRange]:
    absent = _absent(raw, field)
    if absent is not None:
        return absent
    metric = raw[field]
    if not isinstance(metric, Mapping):
        return FieldObservation("invalid")
    endpoints = metric.get("value_range")
    if not isinstance(endpoints, list) or len(endpoints) != 2:
        return FieldObservation("invalid")
    parsed: list[CompassRangeEndpoint] = []
    for endpoint in endpoints:
        if not isinstance(endpoint, Mapping):
            return FieldObservation("invalid")
        number = _number(endpoint.get("value"))
        if number is None:
            return FieldObservation("invalid")
        parsed.append(CompassRangeEndpoint(*number, _unit(endpoint.get("unit"))))
    # Preserve endpoint order and units; do not invent a midpoint or scale.
    return FieldObservation("available", CompassMetricRange((parsed[0], parsed[1])))


def _category_path(raw: Mapping[str, Any]) -> FieldObservation[tuple[str, ...]]:
    absent = _absent(raw, "cid_info")
    if absent is not None:
        return absent
    values = raw["cid_info"]
    if not isinstance(values, list) or not values or any(_text(value) is None for value in values):
        return FieldObservation("invalid")
    return FieldObservation("available", tuple(values))


def _shelf_date(raw: Mapping[str, Any]) -> FieldObservation[date]:
    absent = _absent(raw, "first_on_shelf_time")
    if absent is not None:
        return absent
    value = raw["first_on_shelf_time"]
    if not isinstance(value, str):
        return FieldObservation("invalid")
    try:
        result = datetime.strptime(value, "%Y年%m月%d日").date()
    except ValueError:
        return FieldObservation("invalid")
    return FieldObservation("available", result)


def _bad_comment_rate(raw: Mapping[str, Any]) -> FieldObservation[CompassBadCommentRate]:
    absent = _absent(raw, "bad_comment_rate")
    if absent is not None:
        return absent
    metric = raw["bad_comment_rate"]
    if not isinstance(metric, Mapping) or not isinstance(metric.get("value"), Mapping):
        return FieldObservation("invalid")
    value_container = metric["value"]
    absent = _absent(value_container, "value")
    if absent is not None:
        return absent
    number = _number(value_container["value"])
    if number is None:
        return FieldObservation("invalid")
    return FieldObservation(
        "available",
        CompassBadCommentRate(*number, _unit(value_container.get("unit"))),
    )


def _public_url(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    try:
        parsed = urlsplit(text)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
        ):
            return None
        sensitive_keys = {
            "cookie", "token", "mstoken", "a_bogus", "authorization",
            "sessionid", "verifyfp", "fp", "_lid",
        }
        if any(key.lower() in sensitive_keys for key, _ in parse_qsl(parsed.query)):
            return None
    except ValueError:
        return None
    return text
