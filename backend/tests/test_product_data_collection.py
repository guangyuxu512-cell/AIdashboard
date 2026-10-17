from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.product_data.collection import collect_complete_snapshot
from app.modules.product_data.source import ProductDataSlice, REQUESTED_METRICS, freeze_native_slice
from app.platforms.douyin.product_data import (
    PRODUCT_METRICS, CompassProductDataPage, CompassProductDataRow,
    ProductMetricObservation, ProductTextObservation,
)
from app.platforms.exceptions import PlatformResponseInvalidError


def scope():
    return ProductDataSlice(shop_id=uuid4(), period="1d", start_date=date(2026, 1, 1), end_date=date(2026, 1, 1))


def page(number=1, total=12):
    rows = tuple(CompassProductDataRow(
        str(9000000000000000000 + i), "999999999",
        ProductTextObservation("missing"), ProductTextObservation("missing"),
        tuple(ProductMetricObservation(definition, "missing") for definition in PRODUCT_METRICS),
    ) for i in range((number - 1) * 10, min(number * 10, total)))
    return CompassProductDataPage(rows, number, 10, total)


@pytest.mark.parametrize("period,days,code", [("1d", 1, "20"), ("7d", 7, "21"), ("30d", 30, "23")])
def test_native_presets_freeze_shanghai_complete_dates_once(period, days, code):
    result = freeze_native_slice(uuid4(), period, datetime(2026, 1, 2, 16, 30, tzinfo=UTC))
    assert result.end_date == date(2026, 1, 2)
    assert result.start_date == result.end_date - timedelta(days=days - 1)
    assert result.date_type == code
    assert result.business_query(1)["end_date"].endswith("00:00:00")


def test_exact_74_fields_order_baseline_and_no_auth_or_current_page_in_source_key():
    result = scope()
    assert len(REQUESTED_METRICS) == len(set(REQUESTED_METRICS)) == 74
    assert set(item.code for item in PRODUCT_METRICS) <= set(REQUESTED_METRICS)
    query = result.business_query(2)
    assert len(query) == 22
    assert query["sale_type"] == query["content_type"] == "1"
    assert query["page_no"] == "2" and query["page_size"] == "10"
    assert not ({"a_bogus", "cookie", "fp", "verifyFp", "product_id"} & set(query))
    shifted = result.model_copy(update={"start_date": date(2026, 1, 2), "end_date": date(2026, 1, 2)})
    assert shifted.rolling_series_hash == result.rolling_series_hash
    assert shifted.source_scope_hash != result.source_scope_hash
    other_shop = result.model_copy(update={"shop_id": uuid4()})
    assert other_shop.rolling_series_hash != result.rolling_series_hash


@pytest.mark.parametrize("changes", [{"sale_type": "2"}, {"content_type": "3"}, {"period": "custom"},
                                   {"product_id": "123"}, {"end_date": "2026-01-02"}])
def test_unproved_slices_and_wrong_duration_rejected(changes):
    with pytest.raises(ValidationError):
        ProductDataSlice.model_validate(scope().model_dump() | changes)


def test_all_pages_once_unknown_metrics_not_zero_and_no_publication_side_effect():
    calls = []
    def fetch(number):
        calls.append(number)
        return page(number)
    result = collect_complete_snapshot(scope(), fetch, max_pages=2)
    assert calls == [1, 2]
    assert result.total == len(result.products) == 12 and result.page_count == 2
    assert result.raw_complete_rows == result.display_complete_rows == 0
    assert all(metric.raw_value is None for row in result.products for metric in row.metrics)


@pytest.mark.parametrize("fault", ["duplicate", "total", "page", "short", "shop", "metrics"])
def test_later_page_fault_never_yields_complete_snapshot(fault):
    first = page(1)
    second = page(2)
    if fault == "duplicate": second = replace(second, products=(first.products[0], second.products[1]))
    if fault == "total": second = replace(second, total=13)
    if fault == "page": second = replace(second, page_no=1)
    if fault == "short": second = replace(second, products=second.products[:1])
    if fault == "shop": second = replace(second, products=(replace(second.products[0], platform_shop_id="888888888"), second.products[1]))
    if fault == "metrics": second = replace(second, products=(replace(second.products[0], metrics=()), second.products[1]))
    with pytest.raises(PlatformResponseInvalidError):
        collect_complete_snapshot(scope(), lambda number: first if number == 1 else second, max_pages=2)


def test_budget_exceeded_stops_after_first_page_without_retry():
    calls = []
    def fetch(number):
        calls.append(number)
        return page(number, 146)
    with pytest.raises(PlatformResponseInvalidError) as error:
        collect_complete_snapshot(scope(), fetch, max_pages=1)
    assert calls == [1] and error.value.details["reason"] == "page_budget_exceeded"


def test_network_failure_propagates_once_without_fallback_or_result():
    calls = []
    def fetch(number):
        calls.append(number)
        if number == 2: raise TimeoutError("synthetic")
        return page(number)
    with pytest.raises(TimeoutError):
        collect_complete_snapshot(scope(), fetch, max_pages=2)
    assert calls == [1, 2]
