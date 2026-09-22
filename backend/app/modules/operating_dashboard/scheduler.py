from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.modules.operating_dashboard.service import OperatingDashboardService


logger = logging.getLogger(__name__)
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")


def enqueue_due_daily_operating_collection_once(
    *,
    now: datetime | None = None,
) -> bool:
    """Persist at most one Shanghai-yesterday job after the configured time.

    The service-level dedupe key makes scans/restarts idempotent.  This does
    not enable platform I/O by itself: the separate executor switch controls
    consumption of persisted items.
    """

    settings = get_settings()
    if (
        not settings.operating_dashboard_daily_collection_enabled
        or settings.operating_dashboard_daily_collection_local_time is None
    ):
        return False
    resolved_now = now or datetime.now(UTC)
    local_now = resolved_now.astimezone(SHANGHAI_TIMEZONE)
    if local_now.timetz().replace(tzinfo=None) < settings.operating_dashboard_daily_collection_local_time:
        return False
    business_date = local_now.date() - timedelta(days=1)
    with get_session_factory()() as session:
        OperatingDashboardService(session, settings=settings).enqueue_daily_collection(
            business_date=business_date,
        )
    return True


async def enqueue_due_daily_operating_collections_forever() -> None:
    settings = get_settings()
    while True:
        try:
            await asyncio.to_thread(enqueue_due_daily_operating_collection_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Operating dashboard daily planning scan failed")
        await asyncio.sleep(settings.operating_dashboard_collection_scan_interval_seconds)
