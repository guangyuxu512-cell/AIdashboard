from datetime import UTC, date, datetime, time

import pytest

from app.modules.schedules.time_rules import (
    latest_schedule_occurrence,
    latest_daily_occurrence,
    latest_hourly_occurrence,
    next_schedule_occurrence,
    next_daily_occurrence,
    next_hourly_occurrence,
    next_weekly_occurrence,
    resolve_daily_local_time,
    view_date_utc_bounds,
)
from app.modules.schedules.enums import ScheduleType
from zoneinfo import ZoneInfo


def test_daily_occurrence_uses_explicit_iana_timezone() -> None:
    result = next_daily_occurrence(
        time(9, 30),
        "Asia/Shanghai",
        after=datetime(2026, 8, 24, 0, 0, tzinfo=UTC),
    )
    assert result == datetime(2026, 8, 24, 1, 30, tzinfo=UTC)


def test_daily_occurrence_rolls_to_the_next_local_day() -> None:
    result = next_daily_occurrence(
        time(9, 30),
        "Asia/Shanghai",
        after=datetime(2026, 8, 24, 2, 0, tzinfo=UTC),
    )
    assert result == datetime(2026, 8, 25, 1, 30, tzinfo=UTC)


def test_nonexistent_dst_time_moves_to_first_valid_minute() -> None:
    result = resolve_daily_local_time(
        datetime(2026, 3, 8).date(),
        time(2, 30),
        ZoneInfo("America/New_York"),
    )
    assert result == datetime(2026, 3, 8, 7, 0, tzinfo=UTC)


def test_repeated_dst_time_uses_first_occurrence() -> None:
    result = resolve_daily_local_time(
        datetime(2026, 11, 1).date(),
        time(1, 30),
        ZoneInfo("America/New_York"),
    )
    assert result == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_coalesce_uses_latest_missed_occurrence() -> None:
    result = latest_daily_occurrence(
        time(9, 30),
        "Asia/Shanghai",
        at_or_before=datetime(2026, 8, 24, 12, 0, tzinfo=UTC),
    )
    assert result == datetime(2026, 8, 24, 1, 30, tzinfo=UTC)


def test_naive_boundary_is_rejected() -> None:
    with pytest.raises(ValueError, match="aware datetime"):
        next_daily_occurrence(
            time(9, 30),
            "Asia/Shanghai",
            after=datetime(2026, 8, 24, 0, 0),
        )


def test_weekly_rule_uses_multiple_iso_weekdays() -> None:
    result = next_weekly_occurrence(
        time(9, 30),
        [1, 3, 5],
        "Asia/Shanghai",
        after=datetime(2026, 8, 24, 2, 0, tzinfo=UTC),
    )

    assert result == datetime(2026, 8, 26, 1, 30, tzinfo=UTC)


def test_one_time_rule_does_not_produce_a_second_occurrence() -> None:
    occurrence = datetime(2026, 8, 24, 1, 30, tzinfo=UTC)
    assert next_schedule_occurrence(
        ScheduleType.ONCE,
        local_date=date(2026, 8, 24),
        local_time=time(9, 30),
        weekdays=[],
        timezone_name="Asia/Shanghai",
        after=datetime(2026, 8, 24, 0, 0, tzinfo=UTC),
    ) == occurrence
    assert next_schedule_occurrence(
        ScheduleType.ONCE,
        local_date=date(2026, 8, 24),
        local_time=time(9, 30),
        weekdays=[],
        timezone_name="Asia/Shanghai",
        after=occurrence,
    ) is None
    assert latest_schedule_occurrence(
        ScheduleType.ONCE,
        local_date=date(2026, 8, 24),
        local_time=time(9, 30),
        weekdays=[],
        timezone_name="Asia/Shanghai",
        at_or_before=occurrence,
    ) == occurrence


def test_view_date_bounds_use_the_selected_iana_timezone() -> None:
    start, end = view_date_utc_bounds(date(2026, 8, 24), "Asia/Shanghai")
    assert start == datetime(2026, 8, 23, 16, 0, tzinfo=UTC)
    assert end == datetime(2026, 8, 24, 16, 0, tzinfo=UTC)


@pytest.mark.parametrize("accepted, next_hour, latest_hour", [
    (datetime(2026, 10, 13, 0, 59, 59, 999999, tzinfo=UTC), datetime(2026, 10, 13, 1, tzinfo=UTC), datetime(2026, 10, 13, 0, tzinfo=UTC)),
    (datetime(2026, 10, 13, 1, tzinfo=UTC), datetime(2026, 10, 13, 2, tzinfo=UTC), datetime(2026, 10, 13, 1, tzinfo=UTC)),
    (datetime(2026, 10, 13, 1, 0, 0, 1, tzinfo=UTC), datetime(2026, 10, 13, 2, tzinfo=UTC), datetime(2026, 10, 13, 1, tzinfo=UTC)),
    (datetime(2026, 12, 31, 15, 59, tzinfo=UTC), datetime(2026, 12, 31, 16, tzinfo=UTC), datetime(2026, 12, 31, 15, tzinfo=UTC)),
    (datetime(2026, 12, 31, 16, tzinfo=UTC), datetime(2026, 12, 31, 17, tzinfo=UTC), datetime(2026, 12, 31, 16, tzinfo=UTC)),
])
def test_server_hourly_whole_hour_acceptance_and_due_coalescing(accepted, next_hour, latest_hour):
    assert next_hourly_occurrence("Asia/Shanghai", after=accepted) == next_hour
    assert latest_hourly_occurrence("Asia/Shanghai", at_or_before=accepted) == latest_hour
    assert latest_hour <= accepted < next_hour


def test_hourly_restart_selects_only_latest_occurrence_and_next_future_hour():
    now = datetime(2026, 10, 13, 1, 24, tzinfo=UTC)
    # No historical-cycle iterator: the original due scanner can coalesce once.
    assert latest_hourly_occurrence("Asia/Shanghai", at_or_before=now) == datetime(2026, 10, 13, 1, tzinfo=UTC)
    assert next_hourly_occurrence("Asia/Shanghai", after=now) == datetime(2026, 10, 13, 2, tzinfo=UTC)
    assert next_hourly_occurrence("Asia/Shanghai", after=now.astimezone(ZoneInfo("Asia/Shanghai"))) == datetime(2026, 10, 13, 2, tzinfo=UTC)


@pytest.mark.parametrize("boundary", [datetime(2026, 10, 13, 1), datetime(2026, 10, 13, 1, tzinfo=UTC)])
def test_hourly_rejects_unknown_timezone_and_naive_acceptance(boundary):
    if boundary.tzinfo is None:
        with pytest.raises(ValueError, match="aware datetime"):
            next_hourly_occurrence("Asia/Shanghai", after=boundary)
        with pytest.raises(ValueError, match="aware datetime"):
            latest_hourly_occurrence("Asia/Shanghai", at_or_before=boundary)
    with pytest.raises(ValueError, match="requires Asia/Shanghai"):
        next_hourly_occurrence("Europe/London", after=boundary)


def test_hourly_preparation_does_not_open_pc_schedule_contract():
    from pydantic import ValidationError
    from app.modules.schedules.schemas import ScheduleCreate, ScheduleUpdate
    from uuid import uuid4
    assert "hourly" not in {item.value for item in ScheduleType}
    with pytest.raises(ValidationError):
        ScheduleCreate(name="PC不开放选品规则", target_device_id=uuid4(), application_id="synthetic", local_time="09:00", timezone="Asia/Shanghai", schedule_type="hourly")
    with pytest.raises(ValidationError):
        ScheduleUpdate(schedule_type="hourly")
