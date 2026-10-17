from copy import deepcopy
from decimal import Decimal

import pytest

from app.platforms.douyin.product_data import (
    PRODUCT_METRICS,
    CompassProductDataBusinessError,
    CompassProductDataEmptyUnconfirmedError,
    parse_compass_product_data_page,
)
from app.platforms.exceptions import PlatformIdentityMismatchError, PlatformResponseInvalidError


SHOP = "999999999"
PRODUCT = "9000000000000000001"


def payload():
    # Synthetic identities and text only; shape follows offline-reviewed
    # product_list evidence, not a saved credential or real product fixture.
    info = {
        "product_id_value": {"value": {"unit": 1, "value_str": PRODUCT}},
        "shop_id_value": {"value": {"unit": 1, "value_str": SHOP}},
        "product_name_value": {"value": {"unit": 1, "value_str": "Synthetic product"}},
        "product_image_value": {"value": {"unit": 1, "value_str": "https://example.test/product.png"}},
    }
    cell = {"product_info": info}
    for definition in PRODUCT_METRICS:
        cell[definition.code] = {definition.code + "_index_values": {"index_values": {
            "value": {"unit": definition.observed_unit, "value": 0},
        }}}
    return {"st": 0, "data": [{"cell_info": cell}], "meta": [],
            "page_result": {"page_no": 1, "page_size": 10, "total": 1}}


def parse(raw):
    return parse_compass_product_data_page(raw, expected_platform_shop_id=SHOP, expected_page_no=1)


def current(raw, code="pay_amt"):
    return raw["data"][0]["cell_info"][code][code + "_index_values"]["index_values"]["value"]


def test_exact_seventeen_metrics_and_zero_values_are_not_missing():
    page = parse(payload())
    assert len(PRODUCT_METRICS) == len({metric.code for metric in PRODUCT_METRICS}) == 17
    row = page.products[0]
    assert row.product_id == PRODUCT
    assert row.title.value == "Synthetic product"
    assert row.image.value == "https://example.test/product.png"
    assert row.raw_metrics_complete
    assert all(metric.raw_value == 0 and metric.state == "available" for metric in row.metrics)
    assert row.metric("pay_cnt").display_value == Decimal(0)
    assert not row.display_metrics_complete


def test_raw_precision_and_unit_not_guessed_or_recalculated():
    raw = payload()
    current(raw)["value"] = Decimal("12345678901234567890.1234567890123456789")
    current(raw, "pay_refund_ratio")["value"] = Decimal("0.12345678901234567890123456789")
    current(raw, "pay_cnt")["value"] = 900719925474099312345
    row = parse(raw).products[0]
    assert str(row.metric("pay_amt").raw_value) == "12345678901234567890.1234567890123456789"
    assert str(row.metric("pay_refund_ratio").raw_value) == "0.12345678901234567890123456789"
    assert row.metric("pay_amt").raw_unit == 3
    assert row.metric("pay_refund_ratio").raw_unit == 4
    assert row.metric("pay_amt").display_value is None
    assert row.metric("pay_refund_ratio").display_value is None
    assert row.metric("pay_cnt").display_value == Decimal(900719925474099312345)


@pytest.mark.parametrize("value", [True, False, "0", "private_untrusted_payload", [], {}, 0.1])
def test_wrong_value_types_are_unknown_not_zero(value):
    raw = payload()
    current(raw)["value"] = value
    metric = parse(raw).products[0].metric("pay_amt")
    assert metric.state == "invalid" and metric.raw_value is None
    assert metric.reason == "value_type"


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_nonfinite_values_not_stored(value):
    raw = payload()
    current(raw)["value"] = value
    assert parse(raw).products[0].metric("pay_amt").reason == "value_nonfinite"


def test_minus_one_retains_observation_without_guessing_semantics():
    raw = payload()
    current(raw)["value"] = -1
    metric = parse(raw).products[0].metric("pay_amt")
    assert metric.state == "invalid" and metric.raw_value == Decimal(-1)
    assert metric.reason == "negative_semantics_unconfirmed"
    assert metric.display_value is None


def test_missing_null_invalid_and_unit_only_are_distinct():
    raw = payload()
    cell = raw["data"][0]["cell_info"]
    del cell["product_show_cnt"]
    current(raw, "product_click_cnt")["value"] = None
    cell["net_pay_cnt"] = []
    refund = current(raw, "pay_refund_ratio")
    del refund["value"]
    refund["unit"] = 6
    refund["value_str"] = "0%"
    row = parse(raw).products[0]
    assert row.metric("product_show_cnt").state == "missing"
    assert row.metric("product_click_cnt").state == "null"
    assert row.metric("net_pay_cnt").state == "invalid"
    assert row.metric("pay_refund_ratio").state == "missing"
    assert row.metric("pay_refund_ratio").raw_unit == 6
    assert row.metric("pay_refund_ratio").raw_value is None
    assert not row.raw_metrics_complete


@pytest.mark.parametrize("unit", [None, True, "3", 6, 5])
def test_wrong_money_unit_does_not_get_normalized(unit):
    raw = payload()
    current(raw)["unit"] = unit
    metric = parse(raw).products[0].metric("pay_amt")
    assert metric.state == "invalid" and metric.reason == "unit_unconfirmed"
    assert metric.raw_value == 0 and metric.display_value is None


def test_fractional_count_is_invalid_and_other_metrics_are_independent():
    raw = payload()
    current(raw, "pay_cnt")["value"] = Decimal("1.5")
    current(raw, "net_pay_cnt")["value"] = 97
    current(raw, "pay_cnt_exclude_refund")["value"] = 95
    current(raw, "pay_refund_success_order_cnt")["value"] = 7
    row = parse(raw).products[0]
    assert row.metric("pay_cnt").reason == "count_not_integer"
    assert [row.metric(code).raw_value for code in (
        "net_pay_cnt", "pay_cnt_exclude_refund", "pay_refund_success_order_cnt",
    )] == [97, 95, 7]


def test_previous_value_and_other_duplicate_paths_never_fill_current():
    raw = payload()
    current(raw).pop("value")
    wrapper = raw["data"][0]["cell_info"]["pay_amt"]["pay_amt_index_values"]["index_values"]
    wrapper["last_value"] = {"value": 999, "unit": 3}
    raw["pay_amt"] = {"value": 888, "unit": 3}
    assert parse(raw).products[0].metric("pay_amt").raw_value is None


@pytest.mark.parametrize("value,state", [(None, "null"), ("", "invalid"), (42, "invalid")])
def test_optional_titles_do_not_invent_data(value, state):
    raw = payload()
    raw["data"][0]["cell_info"]["product_info"]["product_name_value"]["value"]["value_str"] = value
    row = parse(raw).products[0]
    assert row.title.state == state and row.title.value is None
    assert row.raw_metrics_complete


@pytest.mark.parametrize("uri", ["javascript:alert(1)", "file:///tmp/a.png", "https://user:pass@example.test/a",
                                 "https://example.test/a?token=synthetic", "https://example.test/a#fragment"])
def test_images_reuse_existing_public_product_url_policy(uri):
    raw = payload()
    raw["data"][0]["cell_info"]["product_info"]["product_image_value"]["value"]["value_str"] = uri
    assert parse(raw).products[0].image.state == "invalid"


@pytest.mark.parametrize("field,value", [("page_no", 2), ("page_size", 20), ("total", 2), ("total", True), ("total", -1)])
def test_page_shape_and_requested_pagination_must_match(field, value):
    raw = payload()
    raw["page_result"][field] = value
    with pytest.raises(PlatformResponseInvalidError):
        parse(raw)


def test_duplicate_products_and_wrong_shop_fail_page():
    raw = payload()
    raw["data"].append(deepcopy(raw["data"][0]))
    raw["page_result"]["total"] = 2
    with pytest.raises(PlatformResponseInvalidError):
        parse(raw)
    raw = payload()
    raw["data"][0]["cell_info"]["product_info"]["shop_id_value"]["value"]["value_str"] = "888888888"
    with pytest.raises(PlatformIdentityMismatchError):
        parse(raw)


@pytest.mark.parametrize("product_id", [int(PRODUCT), "", "9e18", "９００１"])
def test_product_identity_must_be_original_decimal_string(product_id):
    raw = payload()
    raw["data"][0]["cell_info"]["product_info"]["product_id_value"]["value"]["value_str"] = product_id
    with pytest.raises(PlatformResponseInvalidError):
        parse(raw)


def test_business_rejection_does_not_export_platform_message_or_mark_auth_invalid():
    with pytest.raises(CompassProductDataBusinessError) as error:
        parse({"st": 100008, "msg": "untrusted private platform text"})
    assert error.value.details == {"platform_code": 100008}
    assert "private" not in str(error.value)


@pytest.mark.parametrize("status", [True, "0", None])
def test_unobserved_success_types_fail_closed(status):
    raw = payload()
    raw["st"] = status
    with pytest.raises(PlatformResponseInvalidError):
        parse(raw)


def test_empty_success_is_explicitly_gated_until_evidence_exists():
    raw = payload()
    raw["data"] = []
    raw["page_result"]["total"] = 0
    with pytest.raises(CompassProductDataEmptyUnconfirmedError):
        parse(raw)
