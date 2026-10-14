"""Every-N-hours cadence is anchored, not a per-calendar-day modulo."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.schedules.time_rules import next_hourly_occurrence, latest_hourly_occurrence
from app.modules.product_selection.strategy_contract import SelectionStrategySchedule


@pytest.mark.parametrize("hours", [1, 2, 3, 5, 6, 12, 25, 48])
def test_start_next_hour_then_continuous_interval_across_midnight(hours):
    accepted = datetime(2026, 12, 31, 15, 47, tzinfo=UTC)
    first = next_hourly_occurrence("Asia/Shanghai", after=accepted, interval_hours=hours)
    assert first == datetime(2026, 12, 31, 16, tzinfo=UTC)
    for occurrence in range(4):
        at = first + timedelta(hours=hours * occurrence)
        assert latest_hourly_occurrence("Asia/Shanghai", at_or_before=at, interval_hours=hours, anchor=first) == at
        assert next_hourly_occurrence("Asia/Shanghai", after=at, interval_hours=hours, anchor=first) == at + timedelta(hours=hours)
    saved = SelectionStrategySchedule(interval_hours=hours, scheduled=True)
    assert SelectionStrategySchedule.model_validate_json(saved.model_dump_json()) == saved


def test_coalesced_restart_uses_latest_anchor_occurrence_not_completion_time():
    anchor = datetime(2026, 10, 13, 2, tzinfo=UTC)
    now = anchor + timedelta(days=4, hours=3, minutes=42)
    latest = latest_hourly_occurrence("Asia/Shanghai", at_or_before=now, interval_hours=5, anchor=anchor)
    assert latest == anchor + timedelta(hours=95)
    following = next_hourly_occurrence("Asia/Shanghai", after=now, interval_hours=5, anchor=anchor)
    assert following == anchor + timedelta(hours=100)
    # Persisted next_run_at itself is a sufficient advancing cadence anchor.
    assert next_hourly_occurrence("Asia/Shanghai", after=now, interval_hours=5, anchor=latest) == following
    assert following != now + timedelta(hours=5)


@pytest.mark.parametrize("value", [0, -1, 1.5, True, False, "3", None, 2147483648])
def test_invalid_intervals_are_not_silently_defaulted(value):
    with pytest.raises(ValueError):
        SelectionStrategySchedule(interval_hours=value)
    with pytest.raises(ValueError):
        next_hourly_occurrence("Asia/Shanghai", after=datetime(2026, 10, 14, tzinfo=UTC), interval_hours=value)


def test_legacy_json_defaults_one_and_unknown_anchor_is_not_invented():
    assert SelectionStrategySchedule.model_validate({"kind": "hourly", "scheduled": True}).interval_hours == 1
    with pytest.raises(ValueError, match="persisted"):
        latest_hourly_occurrence("Asia/Shanghai", at_or_before=datetime(2026, 10, 14, tzinfo=UTC), interval_hours=5)
    with pytest.raises(ValueError, match="not due"):
        latest_hourly_occurrence("Asia/Shanghai", at_or_before=datetime(2026, 10, 14, tzinfo=UTC), interval_hours=5, anchor=datetime(2026, 10, 14, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="whole-hour"):
        next_hourly_occurrence("Asia/Shanghai", after=datetime(2026, 10, 14, tzinfo=UTC), interval_hours=5, anchor=datetime(2026, 10, 14, 1, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match="date range"):
        next_hourly_occurrence("Asia/Shanghai", after=datetime(2026, 10, 14, tzinfo=UTC), interval_hours=2147483647)
