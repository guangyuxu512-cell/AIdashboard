import asyncio
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.modules.tasks.service import TaskService


logger = logging.getLogger(__name__)


async def reconcile_lost_tasks_forever() -> None:
    interval = get_settings().worker_reconcile_interval_seconds
    while True:
        try:
            await asyncio.to_thread(reconcile_lost_tasks_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Task lease reconcile failed")
        await asyncio.sleep(interval)


def reconcile_lost_tasks_once() -> int:
    with Session(get_database_engine()) as session:
        return TaskService(session).reconcile_expired()
