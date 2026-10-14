"""Confirmed historical date enums and frozen Shanghai single windows."""

from datetime import UTC, datetime

import pytest

from app.modules.product_selection.request_mapping import freeze_short_video_request
from app.modules.product_selection.run_contract import SelectionDateOutcome, SelectionResolvedRequest
from tests.test_selection_request_mapping import _original


@pytest.mark.parametrize("period,code,policy", [
    ("1d", "20", "shanghai_1d_yesterday"),
    ("30d", "23", "shanghai_30d_complete_days"),
])
@pytest.mark.parametrize("at,end,begin30", [
    (datetime(2026, 10, 13, 1, tzinfo=UTC), "2026/10/12 00:00:00", "2026/09/13 00:00:00"),
    (datetime(2026, 10, 31, 16, tzinfo=UTC), "2026/10/31 00:00:00", "2026/10/02 00:00:00"),
    (datetime(2026, 12, 31, 16, tzinfo=UTC), "2026/12/31 00:00:00", "2026/12/02 00:00:00"),
])
def test_history_freezes_complete_relative_days_without_backup(period, code, policy, at, end, begin30):
    request = freeze_short_video_request(_original(period=period, rank_to=25), at)
    assert request.version == 5 and request.scope.date_type == code
    assert request.scope.end_date == end
    assert request.scope.begin_date == (end if period == "1d" else begin30)
    assert request.page_numbers == (1, 2, 3)
    assert set(request.date_plan.model_dump()) == {"accepted_local_date"}
    chosen = request.model_copy(update={"date_outcome": SelectionDateOutcome(state="primary")})
    assert chosen.fingerprint() == request.fingerprint()
    assert chosen.provenance().policy == policy and chosen.provenance().backup_begin is None
    assert SelectionResolvedRequest.model_validate(chosen.model_dump(mode="json")) == chosen


@pytest.mark.parametrize("period", ["1d", "30d"])
@pytest.mark.parametrize("state", ["fallback_checking", "backup", "both_empty", "fallback_failed"])
def test_history_rejects_fallback_and_changed_frozen_scope(period, state):
    request = freeze_short_video_request(_original(period=period), datetime(2026, 10, 13, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        SelectionResolvedRequest.model_validate(request.model_dump(mode="json") | {"date_outcome": {"state": state}})
    realtime = freeze_short_video_request(_original(period="realtime"), datetime(2026, 10, 13, 1, tzinfo=UTC))
    with pytest.raises(ValueError):
        SelectionResolvedRequest.model_validate(request.model_dump(mode="json") | {"scope": realtime.scope.model_dump()})
