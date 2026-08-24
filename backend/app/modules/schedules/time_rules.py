from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_schedule_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError(f"Unknown IANA timezone: {value}") from error


def resolve_daily_local_time(
    local_date: date,
    local_time: time,
    timezone: ZoneInfo,
) -> datetime:
    """Resolve a daily wall-clock occurrence to UTC.

    Repeated local times use the first occurrence. A nonexistent local time is
    shifted forward to the first valid minute on the same local day.
    """

    naive = datetime.combine(local_date, local_time.replace(tzinfo=None))
    for minute_offset in range(181):
        candidate = naive + timedelta(minutes=minute_offset)
        valid_instants: list[datetime] = []
        for fold in (0, 1):
            aware = candidate.replace(tzinfo=timezone, fold=fold)
            instant = aware.astimezone(UTC)
            round_trip = instant.astimezone(timezone).replace(tzinfo=None)
            if round_trip == candidate and instant not in valid_instants:
                valid_instants.append(instant)
        if valid_instants:
            return min(valid_instants)
    raise ValueError("Daily local time could not be resolved on the selected date")


def next_daily_occurrence(
    local_time: time,
    timezone_name: str,
    *,
    after: datetime,
) -> datetime:
    after_utc = _aware_utc(after)
    timezone = get_schedule_timezone(timezone_name)
    local_date = after_utc.astimezone(timezone).date()
    for day_offset in range(3):
        occurrence = resolve_daily_local_time(
            local_date + timedelta(days=day_offset),
            local_time,
            timezone,
        )
        if occurrence > after_utc:
            return occurrence
    raise ValueError("Unable to determine next daily occurrence")


def latest_daily_occurrence(
    local_time: time,
    timezone_name: str,
    *,
    at_or_before: datetime,
) -> datetime:
    boundary = _aware_utc(at_or_before)
    timezone = get_schedule_timezone(timezone_name)
    local_date = boundary.astimezone(timezone).date()
    for day_offset in range(3):
        occurrence = resolve_daily_local_time(
            local_date - timedelta(days=day_offset),
            local_time,
            timezone,
        )
        if occurrence <= boundary:
            return occurrence
    raise ValueError("Unable to determine latest daily occurrence")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    return value.astimezone(UTC)
