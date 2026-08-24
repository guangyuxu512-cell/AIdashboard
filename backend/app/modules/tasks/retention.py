import asyncio
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.modules.tasks.schemas import TaskEventPurgeRead
from app.modules.tasks.service import TaskService


logger = logging.getLogger(__name__)


async def purge_expired_task_events_forever() -> None:
    interval = get_settings().task_event_retention_sweep_interval_seconds
    while True:
        try:
            result = await asyncio.to_thread(purge_expired_task_events_once)
            if result.events_deleted:
                logger.info(
                    "Purged %s Runtime Event(s) for %s terminal Task(s)",
                    result.events_deleted,
                    result.tasks_purged,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Task Runtime Event retention sweep failed")
        await asyncio.sleep(interval)


def purge_expired_task_events_once() -> TaskEventPurgeRead:
    with Session(get_database_engine()) as session:
        return TaskService(session).purge_expired_events()
