"""User-confirmed official label/query mapping, no captured dynamic context."""

from datetime import UTC, datetime

import pytest

from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionDateOutcome, SelectionResolvedRequest, BRAND_TYPES
from tests.test_selection_request_mapping import _original


@pytest.mark.parametrize("brand,code", [("known", "0"), ("unknown", "1")])
@pytest.mark.parametrize("period", ["realtime", "1d", "7d", "30d"])
@pytest.mark.parametrize("price", [False, True])
def test_confirmed_brand_freezes_and_roundtrips_actual_scope(brand, code, period, price):
    changes = {"price_mode": "custom", "price_above": "20", "price_below": "100"} if price else {}
    original = _original(brand=brand, period=period, **changes)
    at = datetime(2026, 12, 31, 16, tzinfo=UTC)
    request = freeze_short_video_request(original, at)
    default = freeze_short_video_request(original.model_copy(update={"brand": "all"}), at)
    assert request.version == 7 and request.scope.brand_type == code and type(request.scope.brand_type) is str
    assert request.scope.model_dump(exclude={"brand_type"}) == default.scope.model_dump(exclude={"brand_type"})
    assert request.scope.price_bin == ("20-100" if price else "不限")
    assert request.fingerprint() != default.fingerprint()
    assert request.scope.fingerprint() != default.scope.fingerprint()
    selected = request.model_copy(update={"date_outcome": SelectionDateOutcome(state="primary")})
    assert selected.actual_scope().brand_type == code and selected.fingerprint() == request.fingerprint()
    assert SelectionResolvedRequest.model_validate(selected.model_dump(mode="json")) == selected
    assert selected.provenance().primary_begin == request.scope.period_begin
    if period == "7d":
        assert request.date_plan.backup_scope.brand_type == code
        backup = SelectionResolvedRequest.model_validate(request.model_dump(mode="json") | {"date_outcome": {"state": "backup", "fallback_reason": "primary_success_empty"}})
        assert backup.actual_scope().brand_type == code and backup.provenance().actual_window == "backup"
    else:
        assert selected.provenance().backup_begin is None


@pytest.mark.parametrize("brand", [0, 1, "0", "1", "other", None, False])
def test_unknown_or_platform_code_as_user_label_is_rejected(brand):
    with pytest.raises(ValueError):
        _original(brand=brand)


@pytest.mark.parametrize("location", ["primary", "backup", "original", "business_probe", "price", "industry", "category", "date_type"])
def test_nondefault_brand_does_not_accept_changed_scope_or_business_error_probe(location):
    request = freeze_short_video_request(_original(brand="known"), datetime.now(UTC))
    raw = request.model_dump(mode="json")
    if location == "primary": raw["scope"]["brand_type"] = "-1"
    elif location == "backup": raw["date_plan"]["backup_scope"]["brand_type"] = "1"
    elif location == "original": raw["original"]["brand"] = "unknown"
    elif location == "price": raw["scope"]["price_bin"] = "20-100"
    elif location == "industry": raw["scope"]["industry_id"] = "5"
    elif location == "category": raw["scope"]["category_id"] = "5001"
    elif location == "date_type": raw["scope"]["date_type"] = "23"
    else: raw["date_outcome"] = {"state": "fallback_checking", "fallback_reason": "primary_business_rejection_probe", "primary_error": {"error_code": "DOUYIN_SELECTION_BUSINESS_REJECTED", "error_stage": "platform_business", "platform_business_code": 621000704}}
    with pytest.raises(ValueError): SelectionResolvedRequest.model_validate(raw)


def test_default_brand_and_old_price_date_versions_remain_unchanged():
    assert dict(BRAND_TYPES) == {"all": "-1", "known": "0", "unknown": "1"}
    for period, version in [("realtime", 4), ("1d", 5), ("7d", 3), ("30d", 5)]:
        plain = freeze_short_video_request(_original(period=period), datetime.now(UTC))
        assert plain.version == version and plain.scope.brand_type == "-1"
        priced = freeze_short_video_request(_original(period=period, price_mode="custom", price_above="20", price_below="100"), datetime.now(UTC))
        assert priced.version == 6 and priced.scope.brand_type == "-1"
