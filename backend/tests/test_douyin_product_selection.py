from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from app.platforms.douyin.product_selection import (
    CompassSelectionBusinessError,
    CompassSelectionIdentityError,
    parse_compass_basic_info,
    parse_compass_categories,
    parse_compass_rank_page,
)
from app.platforms.exceptions import PlatformResponseInvalidError


PRODUCT_ID = "3769776708757094595"


def rank_payload() -> dict:
    # Minimal manually reviewed, non-sensitive response shape. Public facts
    # come from 819ca33 server evidence; it is not a new live request result.
    return {
        "st": 0,
        "data": {
            "page_result": {"page_no": 2, "page_size": 10, "total": 200},
            "data_result": [{
                "product_info": {
                    "id": PRODUCT_ID,
                    "name": "多规格不锈钢带滤网猪油罐",
                    "rank": 11,
                    "price_bin": "¥9-¥23",
                    "leaf_category_id": 1000010085,
                    "newly_on_ranking": False,
                    "shop_list": [{"shop_id": "239490763", "shop_name": "画晚好物优选"}],
                },
                "pay_amt": {"value_range": [
                    {"value": 10000000, "unit": "price"},
                    {"value": 25000000, "unit": "price"},
                ]},
                "pay_combo_cnt": {"value_range": [
                    {"value": 10000, "unit": "number"},
                    {"value": 25000, "unit": "number"},
                ]},
            }],
        },
    }


def basic_payload() -> dict:
    return {"st": "0", "data": {
        "product_id": PRODUCT_ID,
        "cid_info": ["餐饮厨具", "厨房小工具", "厨房储物器具"],
        "first_on_shelf_time": "2025年08月17日",
        "bad_comment_rate": {"value": {"value": 0.00205018686599039, "unit": 4}},
    }}


def test_rank_ids_ranks_ranges_and_merchant_are_not_inferred() -> None:
    page = parse_compass_rank_page(rank_payload())
    assert (page.page_no, page.page_size, page.total) == (2, 10, 200)
    product = page.products[0]
    assert product.product_id == PRODUCT_ID
    assert product.rank == 11  # Not this fixture's local row number 1.
    assert product.leaf_category_id == "1000010085"
    assert product.merchants[0].platform_shop_id == "239490763"
    assert product.newly_on_ranking is False
    assert product.pay_amt.value is not None
    assert [entry.value for entry in product.pay_amt.value.endpoints] == [
        Decimal(10000000), Decimal(25000000),
    ]
    assert all(entry.unit == "price" for entry in product.pay_amt.value.endpoints)
    assert product.product_click_cnt.state == "missing"


@pytest.mark.parametrize("status", [621000704, "621000704"])
def test_business_rejection_preserves_code_type_without_guessing_authentication(status) -> None:
    with pytest.raises(CompassSelectionBusinessError) as failure:
        parse_compass_rank_page({"st": status, "msg": "untrusted platform message"})
    assert failure.value.details == {"failure_stage": "platform_business", "platform_code": status}
    assert "untrusted" not in str(failure.value)


def test_string_business_code_is_not_limited_to_digits_or_allowed_to_leak_context() -> None:
    with pytest.raises(CompassSelectionBusinessError) as failure:
        parse_compass_rank_page({"st": "OTHER_STATUS"})
    assert failure.value.details["platform_code"] == "OTHER_STATUS"
    with pytest.raises(CompassSelectionBusinessError) as failure:
        parse_compass_rank_page({"st": "https://example.test/?token=synthetic-private"})
    assert "synthetic-private" not in str(failure.value.details)


@pytest.mark.parametrize("status", [None, False, {}, [], 0.0])
def test_missing_or_malformed_business_status_is_not_success(status) -> None:
    with pytest.raises(PlatformResponseInvalidError):
        parse_compass_rank_page({"st": status, "data": {}})


def test_successful_empty_page_is_distinct_from_absent_or_malformed_data() -> None:
    result = parse_compass_rank_page({"st": "0", "data": {
        "data_result": [], "page_result": {"page_no": 1, "page_size": 10, "total": 0},
    }})
    assert result.products == () and result.total == 0
    for data in [None, {}, {"data_result": []}]:
        with pytest.raises(PlatformResponseInvalidError):
            parse_compass_rank_page({"st": 0, "data": data})


@pytest.mark.parametrize("payload", [[], None, "not an object"])
def test_non_object_payload_has_a_safe_parse_error(payload) -> None:
    with pytest.raises(PlatformResponseInvalidError) as failure:
        parse_compass_rank_page(payload)
    assert failure.value.details["field_path"] == "response"


@pytest.mark.parametrize("value", [3769776708757094595, 3.7697767087570946e18, None, ""])
def test_product_id_is_a_required_string_never_a_float_or_fallback(value) -> None:
    payload = rank_payload()
    payload["data"]["data_result"][0]["product_info"]["id"] = value
    with pytest.raises(PlatformResponseInvalidError):
        parse_compass_rank_page(payload)


def test_optional_metric_null_invalid_and_zero_remain_independent() -> None:
    payload = rank_payload()
    row = payload["data"]["data_result"][0]
    row["pay_combo_cnt"] = None
    row["product_click_cnt"] = {"value_range": []}
    row["video_cnt"] = {"value_range": [{"value": 0, "unit": "number"}] * 2}
    result = parse_compass_rank_page(payload).products[0]
    assert result.pay_amt.state == "available"
    assert result.pay_combo_cnt.state == "null"
    assert result.product_click_cnt.state == "invalid"
    assert result.video_cnt.value is not None
    assert result.video_cnt.value.endpoints[0].value == Decimal(0)


@pytest.mark.parametrize("value", ["0", False, float("nan"), float("inf")])
def test_unverified_numeric_types_are_not_coerced_to_valid_zero(value) -> None:
    payload = rank_payload()
    payload["data"]["data_result"][0]["pay_amt"]["value_range"][0]["value"] = value
    assert parse_compass_rank_page(payload).products[0].pay_amt.state == "invalid"


def test_all_four_range_fields_use_their_exact_paths_and_retain_original_units() -> None:
    payload = rank_payload()
    row = payload["data"]["data_result"][0]
    row["product_click_cnt"] = {"value_range": [
        {"value": 100000, "unit": "number"}, {"value": 250000, "unit": "number"},
    ]}
    row["video_cnt"] = {"value_range": [
        {"value": 250, "unit": "number"}, {"value": 500, "unit": "number"},
    ]}
    result = parse_compass_rank_page(payload).products[0]
    assert result.pay_combo_cnt.value.endpoints[0].value == Decimal(10000)
    assert result.product_click_cnt.value.endpoints[0].value == Decimal(100000)
    assert result.video_cnt.value.endpoints[0].value == Decimal(250)
    assert result.video_cnt.value.endpoints[1].unit == "number"


@pytest.mark.parametrize("key,value", [("page_no", "2"), ("page_size", False), ("total", None)])
def test_pagination_metadata_cannot_be_silently_invented(key: str, value) -> None:
    payload = rank_payload()
    payload["data"]["page_result"][key] = value
    with pytest.raises(PlatformResponseInvalidError):
        parse_compass_rank_page(payload)


def test_basic_info_retains_day_precision_and_raw_nonzero_rate_with_unit() -> None:
    result = parse_compass_basic_info(basic_payload(), expected_product_id=PRODUCT_ID)
    assert result.category_path.value == ("餐饮厨具", "厨房小工具", "厨房储物器具")
    assert result.first_on_shelf_date.value == date(2025, 8, 17)
    assert result.bad_comment_rate.value is not None
    assert result.bad_comment_rate.value.value == Decimal("0.00205018686599039")
    assert result.bad_comment_rate.value.unit == 4


def test_partial_basic_info_does_not_fabricate_or_clear_confirmed_fields() -> None:
    payload = basic_payload()
    del payload["data"]["cid_info"]
    payload["data"]["bad_comment_rate"]["value"]["value"] = None
    result = parse_compass_basic_info(payload, expected_product_id=PRODUCT_ID)
    assert result.category_path.state == "missing"
    assert result.bad_comment_rate.state == "null"
    assert result.first_on_shelf_date.state == "available"
    payload["data"]["bad_comment_rate"]["value"]["value"] = 0
    zero = parse_compass_basic_info(payload, expected_product_id=PRODUCT_ID)
    assert zero.bad_comment_rate.value is not None
    assert zero.bad_comment_rate.value.value == 0


def test_wrong_basic_product_identity_is_not_accepted() -> None:
    payload = basic_payload()
    payload["data"]["product_id"] = "different-product"
    with pytest.raises(CompassSelectionIdentityError):
        parse_compass_basic_info(payload, expected_product_id=PRODUCT_ID)


def test_malformed_optional_basic_field_does_not_hide_other_valid_fields() -> None:
    payload = basic_payload()
    payload["data"]["first_on_shelf_time"] = "unverified epoch format"
    payload["data"]["bad_comment_rate"] = {"value": {"value": False, "unit": 4}}
    result = parse_compass_basic_info(payload, expected_product_id=PRODUCT_ID)
    assert result.first_on_shelf_date.state == "invalid"
    assert result.bad_comment_rate.state == "invalid"
    assert result.category_path.state == "available"


def test_categories_only_traverse_children_and_do_not_merge_repeated_all_nodes() -> None:
    all_node = {"cate_id": "0", "cate_name": "全部", "children": []}
    result = parse_compass_categories({"st": 0, "data": {
        "industry_id": "7", "industry_name": "智能家居", "cate_id": "1000009142",
        "cate_list": [{"cate_id": "7", "cate_name": "智能家居", "children": [
            deepcopy(all_node), {"cate_id": "1000009092", "cate_name": "餐饮厨具", "children": [
                deepcopy(all_node), {"cate_id": "1000009142", "cate_name": "厨房小工具", "children": []},
            ]},
        ]}],
    }})
    assert result.industry_id == "7"
    assert result.nodes[0].children[0].category_id == "0"
    assert result.nodes[0].children[1].children[0].category_id == "0"
    with pytest.raises(PlatformResponseInvalidError):
        parse_compass_categories({"st": 0, "data": {"other": {"cate_list": []}}})


def test_category_children_structure_is_not_fabricated_when_missing() -> None:
    with pytest.raises(PlatformResponseInvalidError):
        parse_compass_categories({"st": 0, "data": {
            "cate_list": [{"cate_id": "7", "cate_name": "智能家居"}],
        }})


@pytest.mark.parametrize("url", [
    "https://user:secret@example.test/image.jpg",
    "https://example.test/image.jpg?msToken=sensitive",
    "javascript:alert(1)",
])
def test_unusable_or_credential_bearing_product_image_is_not_propagated(url: str) -> None:
    payload = rank_payload()
    payload["data"]["data_result"][0]["product_info"]["image_url"] = url
    assert parse_compass_rank_page(payload).products[0].image_url is None


def test_public_product_image_remains_independent_of_authenticated_asset_http() -> None:
    payload = rank_payload()
    image_url = "https://public.example.test/photo.jpg"
    payload["data"]["data_result"][0]["product_info"]["image_url"] = image_url
    assert parse_compass_rank_page(payload).products[0].image_url == image_url
