from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.modules.schedules.enums import ScheduleType


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


def next_hourly_occurrence(timezone_name: str, *, after: datetime) -> datetime:
    """Server selection's Shanghai next whole hour, strictly after acceptance.

    This preparation helper does not expose hourly in the PC Schedule DTO,
    extend database enums, or activate a new due scanner.
    """
    boundary = _shanghai_hour_boundary(timezone_name, after)
    return (boundary + timedelta(hours=1)).astimezone(UTC)


def latest_hourly_occurrence(timezone_name: str, *, at_or_before: datetime) -> datetime:
    """COALESCE ONE: an already-due whole hour is included, not skipped."""
    return _shanghai_hour_boundary(timezone_name, at_or_before).astimezone(UTC)


def _shanghai_hour_boundary(timezone_name: str, value: datetime) -> datetime:
    if timezone_name != "Asia/Shanghai":
        raise ValueError("Server selection hourly requires Asia/Shanghai")
    return _aware_utc(value).astimezone(get_schedule_timezone(timezone_name)).replace(
        minute=0, second=0, microsecond=0,
    )


def normalize_weekdays(value: list[int]) -> list[int]:
    if any(isinstance(day, bool) or not isinstance(day, int) for day in value):
        raise ValueError("weekdays must contain integer ISO weekdays")
    if any(day < 1 or day > 7 for day in value):
        raise ValueError("weekdays must contain ISO weekdays from 1 through 7")
    if len(value) != len(set(value)):
        raise ValueError("weekdays must not contain duplicates")
    return sorted(value)


def validate_schedule_rule(
    schedule_type: ScheduleType,
    local_date: date | None,
    weekdays: list[int],
) -> tuple[date | None, list[int]]:
    normalized_weekdays = normalize_weekdays(weekdays)
    if schedule_type is ScheduleType.ONCE:
        if local_date is None or normalized_weekdays:
            raise ValueError("Once schedules require local_date and no weekdays")
        return local_date, []
    if schedule_type is ScheduleType.DAILY:
        if local_date is not None or normalized_weekdays:
            raise ValueError("Daily schedules cannot include local_date or weekdays")
        return None, []
    if schedule_type is ScheduleType.WEEKLY:
        if local_date is not None or not normalized_weekdays:
            raise ValueError("Weekly schedules require weekdays and no local_date")
        return None, normalized_weekdays
    raise ValueError("Unknown schedule type")


def next_weekly_occurrence(
    local_time: time,
    weekdays: list[int],
    timezone_name: str,
    *,
    after: datetime,
) -> datetime:
    after_utc = _aware_utc(after)
    timezone = get_schedule_timezone(timezone_name)
    local_day = after_utc.astimezone(timezone).date()
    selected_days = set(normalize_weekdays(weekdays))
    for day_offset in range(8):
        candidate_day = local_day + timedelta(days=day_offset)
        if candidate_day.isoweekday() not in selected_days:
            continue
        occurrence = resolve_daily_local_time(candidate_day, local_time, timezone)
        if occurrence > after_utc:
            return occurrence
    raise ValueError("Unable to determine next weekly occurrence")


def latest_weekly_occurrence(
    local_time: time,
    weekdays: list[int],
    timezone_name: str,
    *,
    at_or_before: datetime,
) -> datetime:
    boundary = _aware_utc(at_or_before)
    timezone = get_schedule_timezone(timezone_name)
    local_day = boundary.astimezone(timezone).date()
    selected_days = set(normalize_weekdays(weekdays))
    for day_offset in range(8):
        candidate_day = local_day - timedelta(days=day_offset)
        if candidate_day.isoweekday() not in selected_days:
            continue
        occurrence = resolve_daily_local_time(candidate_day, local_time, timezone)
        if occurrence <= boundary:
            return occurrence
    raise ValueError("Unable to determine latest weekly occurrence")


def next_schedule_occurrence(
    schedule_type: ScheduleType,
    *,
    local_date: date | None,
    local_time: time,
    weekdays: list[int],
    timezone_name: str,
    after: datetime,
) -> datetime | None:
    rule_date, rule_weekdays = validate_schedule_rule(
        schedule_type,
        local_date,
        weekdays,
    )
    if schedule_type is ScheduleType.DAILY:
        return next_daily_occurrence(local_time, timezone_name, after=after)
    if schedule_type is ScheduleType.WEEKLY:
        return next_weekly_occurrence(
            local_time,
            rule_weekdays,
            timezone_name,
            after=after,
        )
    assert rule_date is not None
    occurrence = resolve_daily_local_time(
        rule_date,
        local_time,
        get_schedule_timezone(timezone_name),
    )
    return occurrence if occurrence > _aware_utc(after) else None


def latest_schedule_occurrence(
    schedule_type: ScheduleType,
    *,
    local_date: date | None,
    local_time: time,
    weekdays: list[int],
    timezone_name: str,
    at_or_before: datetime,
) -> datetime:
    rule_date, rule_weekdays = validate_schedule_rule(
        schedule_type,
        local_date,
        weekdays,
    )
    if schedule_type is ScheduleType.DAILY:
        return latest_daily_occurrence(
            local_time,
            timezone_name,
            at_or_before=at_or_before,
        )
    if schedule_type is ScheduleType.WEEKLY:
        return latest_weekly_occurrence(
            local_time,
            rule_weekdays,
            timezone_name,
            at_or_before=at_or_before,
        )
    assert rule_date is not None
    occurrence = resolve_daily_local_time(
        rule_date,
        local_time,
        get_schedule_timezone(timezone_name),
    )
    if occurrence > _aware_utc(at_or_before):
        raise ValueError("One-time schedule is not due")
    return occurrence


def view_date_utc_bounds(value: date, timezone_name: str) -> tuple[datetime, datetime]:
    timezone = get_schedule_timezone(timezone_name)
    return (
        resolve_daily_local_time(value, time.min, timezone),
        resolve_daily_local_time(value + timedelta(days=1), time.min, timezone),
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An aware datetime is required")
    return value.astimezone(UTC)
