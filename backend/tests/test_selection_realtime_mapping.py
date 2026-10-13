"""Confirmed realtime query, not a claim about availability at every hour."""

from datetime import UTC, datetime

import pytest

from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionResolvedRequest, SelectionDateOutcome
from tests.test_selection_request_mapping import _original


@pytest.mark.parametrize("at,day", [
    (datetime(2026, 10, 13, 0, 12, tzinfo=UTC), "2026/10/13 00:00:00"),
    (datetime(2026, 10, 31, 15, 59, tzinfo=UTC), "2026/10/31 00:00:00"),
    (datetime(2026, 10, 31, 16, tzinfo=UTC), "2026/11/01 00:00:00"),
    (datetime(2026, 12, 31, 16, tzinfo=UTC), "2027/01/01 00:00:00"),
])
def test_realtime_freezes_shanghai_today_without_backup(at, day):
    request = freeze_short_video_request(_original(period="realtime", rank_to=25), at)
    assert request.version == 4
    assert request.scope.begin_date == request.scope.end_date == day
    assert request.scope.date_type == "1" and request.scope.rank_data_type == "1"
    assert request.scope.brand_type == "-1" and request.scope.price_bin == "不限"
    assert request.page_numbers == (1, 2, 3)
    assert set(request.date_plan.model_dump()) == {"accepted_local_date"}
    chosen = request.model_copy(update={"date_outcome": SelectionDateOutcome(state="primary")})
    assert chosen.fingerprint() == request.fingerprint()
    assert chosen.provenance().policy == "shanghai_realtime_today"
    assert chosen.provenance().backup_begin is None
    with pytest.raises(ValueError): request.actual_scope()


@pytest.mark.parametrize("state", ["fallback_checking", "backup", "both_empty", "fallback_failed"])
def test_realtime_rejects_fallback_outcomes(state):
    request = freeze_short_video_request(_original(period="realtime"), datetime.now(UTC))
    with pytest.raises(ValueError):
        SelectionResolvedRequest.model_validate(request.model_dump(mode="json") | {"date_outcome": {"state": state}})


def test_realtime_does_not_accept_a_seven_day_scope_or_backup_plan():
    at = datetime.now(UTC)
    request = freeze_short_video_request(_original(period="realtime"), at)
    seven = freeze_short_video_request(_original(), at)
    for mutation in [{"scope": seven.scope.model_dump()}, {"date_plan": seven.date_plan.model_dump()}, {"version": 3}]:
        with pytest.raises(ValueError):
            SelectionResolvedRequest.model_validate(request.model_dump(mode="json") | mutation)
