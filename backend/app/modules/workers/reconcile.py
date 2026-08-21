import asyncio
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.core.security import get_secret_cipher
from app.modules.notifications.service import NotificationService
from app.modules.workers.service import WorkerService


logger = logging.getLogger(__name__)


async def reconcile_offline_devices_forever() -> None:
    interval = get_settings().worker_reconcile_interval_seconds
    while True:
        try:
            await asyncio.to_thread(reconcile_offline_devices_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Device offline reconcile failed")
        await asyncio.sleep(interval)


def reconcile_offline_devices_once() -> int:
    with Session(get_database_engine()) as session:
        notification_service = NotificationService(session, get_secret_cipher())
        return WorkerService(
            session,
            notification_service=notification_service,
        ).reconcile_offline_devices()
