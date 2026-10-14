"""Confirmed two-sided yuan encoding; synthetic, not extra platform probes."""

from datetime import UTC, datetime

import pytest

from app.modules.product_selection.exceptions import SelectionPriceRangeInvalidError
from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionDateOutcome, SelectionResolvedRequest, custom_price_bin
from tests.test_selection_request_mapping import _original


def _custom(**changes):
    return _original(price_mode="custom", price_above="20.00", price_below="100.0", **changes)


@pytest.mark.parametrize("lower,upper,query", [
    ("20.00", "100.0", "20-100"), ("0", "0", "0-0"),
    ("0.00", "0.01", "0-0.01"), ("000020", "040.50", "20-40.5"),
    ("9999999999.98", "9999999999.99", "9999999999.98-9999999999.99"),
])
def test_plain_yuan_encoding_preserves_value_without_rounding(lower, upper, query):
    assert custom_price_bin(_original(price_mode="custom", price_above=lower, price_below=upper)) == query


@pytest.mark.parametrize("lower,upper", [(None, "100"), ("0", None), (None, None), ("100", "20")])
def test_custom_requires_both_explicit_ordered_bounds(lower, upper):
    with pytest.raises(SelectionPriceRangeInvalidError):
        freeze_short_video_request(_original(price_mode="custom", price_above=lower, price_below=upper), datetime.now(UTC))


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "1e2", "1.001", "10000000000", " 20", "20 ", "20-100"])
def test_api_decimal_contract_rejects_unknown_encoding(value):
    with pytest.raises(ValueError):
        _original(price_mode="custom", price_above=value, price_below="100")


@pytest.mark.parametrize("period,version,code", [("realtime", 4, "1"), ("1d", 5, "20"), ("7d", 3, "21"), ("30d", 5, "23")])
def test_v6_reuses_existing_date_policy_and_freezes_actual_price(period, version, code):
    at = datetime(2026, 12, 31, 16, tzinfo=UTC)
    price = freeze_short_video_request(_custom(period=period), at)
    default = freeze_short_video_request(_original(period=period), at)
    assert default.version == version and price.version == 6
    assert price.scope.price_bin == "20-100" and price.scope.date_type == code
    assert price.scope.begin_date == default.scope.begin_date and price.scope.end_date == default.scope.end_date
    assert price.date_plan.accepted_local_date == default.date_plan.accepted_local_date
    assert price.fingerprint() != default.fingerprint()
    assert price.scope.fingerprint() != default.scope.fingerprint()
    chosen = price.model_copy(update={"date_outcome": SelectionDateOutcome(state="primary")})
    assert chosen.fingerprint() == price.fingerprint()
    assert SelectionResolvedRequest.model_validate(chosen.model_dump(mode="json")) == chosen
    assert chosen.provenance().primary_begin == price.scope.period_begin
    if period == "7d":
        assert price.date_plan.backup_scope.price_bin == "20-100"
        assert price.date_plan.backup_scope.period_end == default.date_plan.backup_scope.period_end
    else:
        assert chosen.provenance().backup_begin is None
        with pytest.raises(ValueError):
            SelectionResolvedRequest.model_validate(price.model_dump(mode="json") | {"date_outcome": {"state": "both_empty"}})


def test_v6_cannot_store_price_mismatch_or_business_rejection_probe():
    request = freeze_short_video_request(_custom(), datetime.now(UTC))
    raw = request.model_dump(mode="json")
    with pytest.raises(ValueError):
        SelectionResolvedRequest.model_validate(raw | {"scope": raw["scope"] | {"price_bin": "不限"}})
    with pytest.raises(ValueError):
        SelectionResolvedRequest.model_validate(raw | {"date_plan": raw["date_plan"] | {"backup_scope": raw["date_plan"]["backup_scope"] | {"price_bin": "不限"}}})
    with pytest.raises(ValueError):
        SelectionResolvedRequest.model_validate(raw | {"date_outcome": {"state": "fallback_checking", "fallback_reason": "primary_business_rejection_probe", "primary_error": {"error_code": "DOUYIN_SELECTION_BUSINESS_REJECTED", "error_stage": "platform_business", "platform_business_code": 621000704}}})


def test_v6_legal_empty_fallback_keeps_both_frozen_price_windows():
    request = freeze_short_video_request(_custom(), datetime.now(UTC))
    raw = request.model_dump(mode="json") | {"date_outcome": {"state": "backup", "fallback_reason": "primary_success_empty"}}
    selected = SelectionResolvedRequest.model_validate(raw)
    assert selected.actual_scope().price_bin == "20-100"
    assert selected.provenance().actual_window == "backup"
