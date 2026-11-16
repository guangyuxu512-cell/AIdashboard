"""Interpret a Worker's non-sensitive, snapshot-bound Session observation."""
from datetime import UTC, datetime, timedelta
from typing import Any, Literal


def worker_session_observation(
    shop: dict[str, Any], *, now: datetime | None = None,
) -> tuple[Literal["valid", "invalid"], datetime] | None:
    status = shop.get("sessionStatus")
    raw_time = shop.get("sessionCheckedAt")
    if (status not in ("valid", "invalid") or not isinstance(raw_time, str)
            or shop.get("sessionStored") is not True or not shop.get("sessionRevision")):
        return None
    try:
        checked_at = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        if checked_at.tzinfo is None:
            return None
        checked_at = checked_at.astimezone(UTC)
    except ValueError:
        return None
    current = now or datetime.now(UTC)
    if checked_at > current + timedelta(minutes=5):
        return None
    if status == "valid" and checked_at < current - timedelta(minutes=30):
        return None
    return status, checked_at


def merge_session_observations(known, reported):
    """A merchant identity check cannot undo an explicit category-auth failure."""
    if known and known[0] == "invalid" and reported and reported[0] == "valid":
        return known
    if reported and (known is None or reported[1] > known[1]):
        return reported
    return known
