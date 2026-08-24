import asyncio
import logging
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.modules.schedules.service import ScheduleService


logger = logging.getLogger(__name__)


def trigger_due_schedules_once(*, now: datetime | None = None) -> int:
    settings = get_settings()
    session_factory = get_session_factory()
    triggered = 0
    for _ in range(settings.schedule_trigger_batch_size):
        with session_factory() as session:
            result = ScheduleService(session).trigger_next_due(now=now)
        if result is None:
            break
        logger.info(
            "Schedule trigger processed",
            extra={
                "schedule_id": str(result.schedule_id),
                "scheduled_for": result.scheduled_for.isoformat(),
                "task_id": str(result.task_id) if result.task_id else None,
                "trigger_result": result.trigger_result.value,
            },
        )
        triggered += 1
    return triggered


async def trigger_due_schedules_forever() -> None:
    settings = get_settings()
    while True:
        try:
            await asyncio.to_thread(
                trigger_due_schedules_once,
                now=datetime.now(UTC),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Schedule trigger scan failed")
        await asyncio.sleep(settings.schedule_scan_interval_seconds)
