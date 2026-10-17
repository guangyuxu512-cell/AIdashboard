"""Fixed-path Compass product-list observations, without I/O or persistence.

Only the verified 17 current metrics are read. Original Decimal/unit values stay
unchanged. Display scales follow the official product-list cell renderer chain.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Any, Literal

from app.platforms.exceptions import (
    PlatformIdentityMismatchError,
    PlatformRequestFailedError,
    PlatformResponseInvalidError,
)
from app.platforms.product_fields import public_product_image_url


ObservationState = Literal["available", "missing", "null", "invalid"]
MetricKind = Literal["count", "amount", "ratio"]
PRODUCT_METRIC_CONTRACT = "compass_product_list_core17_v1"


@dataclass(frozen=True)
class ProductMetricDefinition:
    code: str
    kind: MetricKind
    observed_unit: int

    @property
    def unit_verified(self) -> bool:
        # Restricted to this fixed product-list contract, not other endpoints.
        return self.observed_unit == {"count": 5, "amount": 3, "ratio": 4}.get(self.kind)


PRODUCT_METRICS = (
    ProductMetricDefinition("product_show_cnt", "count", 5),
    ProductMetricDefinition("product_click_cnt", "count", 5),
    ProductMetricDefinition("product_show_click_converse_uv_rate", "ratio", 4),
    ProductMetricDefinition("click_add_to_cart_uv", "count", 5),
    ProductMetricDefinition("product_add_show_converse_uv_ratio", "ratio", 4),
    ProductMetricDefinition("net_pay_cnt", "count", 5),
    ProductMetricDefinition("pay_cnt_exclude_refund", "count", 5),
    ProductMetricDefinition("product_click_pay_converse_uv_rate", "ratio", 4),
    ProductMetricDefinition("pay_refund_ratio", "ratio", 4),
    ProductMetricDefinition("pay_amt", "amount", 3),
    ProductMetricDefinition("pay_cnt", "count", 5),
    ProductMetricDefinition("pay_ucnt", "count", 5),
    ProductMetricDefinition("per_user_price", "amount", 3),
    ProductMetricDefinition("pay_refund_success_amt", "amount", 3),
    ProductMetricDefinition("pay_refund_success_order_cnt", "count", 5),
    ProductMetricDefinition("product_show_ucnt", "count", 5),
    ProductMetricDefinition("product_click_ucnt", "count", 5),
)


class CompassProductDataBusinessError(PlatformRequestFailedError):
    code = "DOUYIN_PRODUCT_DATA_REJECTED"
    message = "罗盘商品数据请求被平台业务拒绝，原因未确定"


class CompassProductDataEmptyUnconfirmedError(PlatformResponseInvalidError):
    code = "DOUYIN_PRODUCT_DATA_EMPTY_UNCONFIRMED"
    message = "商品数据空成功结构尚未核定，未发布空快照"


@dataclass(frozen=True)
class ProductTextObservation:
    state: ObservationState
    value: str | None = None


@dataclass(frozen=True)
class ProductMetricObservation:
    definition: ProductMetricDefinition
    state: ObservationState
    raw_value: Decimal | None = None
    raw_unit: int | None = None
    reason: str | None = None

    @property
    def unit_verified(self) -> bool:
        return self.definition.unit_verified and self.raw_unit == self.definition.observed_unit

    @property
    def display_value(self) -> Decimal | None:
        if self.state != "available" or not self.unit_verified or self.raw_value is None:
            return None
        if self.definition.kind == "amount":
            # Decimal multiplication/scaleb can round at the caller's context
            # precision. Moving the exponent preserves every original digit.
            value = self.raw_value.as_tuple()
            return Decimal((value.sign, value.digits, value.exponent - 2))
        # Ratio canonical values remain fractions; only presentation multiplies
        # by 100. Count values remain their original integers.
        return self.raw_value


@dataclass(frozen=True)
class CompassProductDataRow:
    product_id: str
    platform_shop_id: str
    title: ProductTextObservation
    image: ProductTextObservation
    metrics: tuple[ProductMetricObservation, ...]

    def metric(self, code: str) -> ProductMetricObservation:
        return next(item for item in self.metrics if item.definition.code == code)

    @property
    def raw_metrics_complete(self) -> bool:
        return all(item.state == "available" for item in self.metrics)

    @property
    def display_metrics_complete(self) -> bool:
        return all(item.display_value is not None for item in self.metrics)


@dataclass(frozen=True)
class CompassProductDataPage:
    products: tuple[CompassProductDataRow, ...]
    page_no: int
    page_size: int
    total: int


def parse_compass_product_data_page(
    payload: Mapping[str, Any],
    *,
    expected_platform_shop_id: str,
    expected_page_no: int,
    expected_page_size: int = 10,
) -> CompassProductDataPage:
    """Validate exactly one requested page; a page is never a published set."""
    if type(expected_page_no) is not int or expected_page_no < 1:
        raise ValueError("Expected page must be a positive integer")
    if type(expected_page_size) is not int or expected_page_size < 1:
        raise ValueError("Expected page size must be a positive integer")
    if not _decimal_id(expected_platform_shop_id):
        raise ValueError("Expected platform shop identity must remain a string")
    if not isinstance(payload, Mapping) or type(payload.get("st")) is not int:
        raise _invalid("st")
    if payload["st"] != 0:
        raise CompassProductDataBusinessError(details={"platform_code": payload["st"]})
    page = payload.get("page_result")
    if not isinstance(page, Mapping):
        raise _invalid("page_result")
    page_no = _integer(page, "page_no", minimum=1)
    page_size = _integer(page, "page_size", minimum=1)
    total = _integer(page, "total", minimum=0)
    if page_no != expected_page_no or page_size != expected_page_size:
        raise _invalid("page_result.requested_page")
    rows = payload.get("data")
    if not isinstance(rows, list) or not isinstance(payload.get("meta"), list):
        raise _invalid("data/meta")
    if total == 0 and not rows:
        # No controlled empty-success example exists. Do not silently turn
        # a new response shape into a zero-product published generation.
        raise CompassProductDataEmptyUnconfirmedError()
    offset = (page_no - 1) * page_size
    if total <= offset or len(rows) != min(page_size, total - offset):
        raise _invalid("data.page_coverage")
    products = tuple(_product(row, expected_platform_shop_id) for row in rows)
    if len({row.product_id for row in products}) != len(products):
        raise _invalid("data.duplicate_product")
    return CompassProductDataPage(products, page_no, page_size, total)


def _product(raw: Any, expected_shop: str) -> CompassProductDataRow:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("cell_info"), Mapping):
        raise _invalid("data[].cell_info")
    cell = raw["cell_info"]
    info = cell.get("product_info")
    product_state, product_id = _read(info, "product_id_value", "value", "value_str")
    shop_state, shop_id = _read(info, "shop_id_value", "value", "value_str")
    if product_state != "available" or not _decimal_id(product_id):
        raise _invalid("product_info.product_id_value.value.value_str")
    if shop_state != "available" or not _decimal_id(shop_id):
        raise _invalid("product_info.shop_id_value.value.value_str")
    if shop_id != expected_shop:
        raise PlatformIdentityMismatchError()
    return CompassProductDataRow(
        product_id=product_id,
        platform_shop_id=shop_id,
        title=_text(info, "product_name_value"),
        image=_text(info, "product_image_value", image=True),
        metrics=tuple(_metric(cell, definition) for definition in PRODUCT_METRICS),
    )


def _metric(cell: Mapping[str, Any], definition: ProductMetricDefinition) -> ProductMetricObservation:
    state, node = _read(cell, definition.code, definition.code + "_index_values", "index_values", "value")
    if state != "available":
        return ProductMetricObservation(definition, state, reason="current_node_" + state)
    if not isinstance(node, Mapping):
        return ProductMetricObservation(definition, "invalid", reason="current_node_type")
    unit = node.get("unit")
    raw_unit = unit if type(unit) is int else None
    if "value" not in node:
        return ProductMetricObservation(definition, "missing", raw_unit=raw_unit, reason="value_missing")
    value = node["value"]
    if value is None:
        return ProductMetricObservation(definition, "null", raw_unit=raw_unit, reason="value_null")
    if type(value) not in (int, Decimal):
        return ProductMetricObservation(definition, "invalid", raw_unit=raw_unit, reason="value_type")
    numeric = Decimal(value)
    if not numeric.is_finite():
        return ProductMetricObservation(definition, "invalid", raw_unit=raw_unit, reason="value_nonfinite")
    reason = None
    if numeric < 0:
        reason = "negative_semantics_unconfirmed"
    elif raw_unit != definition.observed_unit:
        reason = "unit_unconfirmed"
    elif definition.kind == "count" and numeric != numeric.to_integral_value():
        reason = "count_not_integer"
    return ProductMetricObservation(
        definition, "invalid" if reason else "available", numeric, raw_unit, reason,
    )


def _text(info: Any, key: str, *, image: bool = False) -> ProductTextObservation:
    state, value = _read(info, key, "value", "value_str")
    if state != "available":
        return ProductTextObservation(state)
    if not isinstance(value, str) or not value.strip():
        return ProductTextObservation("invalid")
    if image and public_product_image_url(value) is None:
        return ProductTextObservation("invalid")
    return ProductTextObservation("available", value)


def _read(raw: Any, *keys: str) -> tuple[ObservationState, Any]:
    node = raw
    for key in keys:
        if node is None:
            return "null", None
        if not isinstance(node, Mapping):
            return "invalid", None
        if key not in node:
            return "missing", None
        node = node[key]
    return ("null", None) if node is None else ("available", node)


def _decimal_id(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9]{1,32}", value) is not None


def _integer(raw: Mapping[str, Any], key: str, *, minimum: int) -> int:
    value = raw.get(key)
    if type(value) is not int or value < minimum:
        raise _invalid("page_result." + key)
    return value


def _invalid(path: str) -> PlatformResponseInvalidError:
    # Fixed local paths only: no platform message, URL, IDs or payload excerpt.
    return PlatformResponseInvalidError(details={
        "failure_stage": "response_parse", "field_path": path,
    })
