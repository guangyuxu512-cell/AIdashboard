import asyncio
import logging
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.security import get_secret_cipher
from app.modules.credentials.service import CredentialService
from app.modules.schedules.service import ScheduleService
from app.modules.schedules.selection_service import SelectionScheduleService
from app.modules.tasks.service import TaskService


logger = logging.getLogger(__name__)


def trigger_due_schedules_once(*, now: datetime | None = None) -> int:
    settings = get_settings()
    session_factory = get_session_factory()
    triggered = 0
    server_enabled = getattr(settings, "product_selection_schedule_enabled", False) and getattr(settings, "product_selection_execution_enabled", False)
    while triggered < settings.schedule_trigger_batch_size:
        progressed = False
        # One existing coordinator alternates targets. A disabled/busy server
        # row cannot hide or block the PC query; no second scanner is created.
        for target in (("server_selection", "pc") if server_enabled else ("pc",)):
            if triggered >= settings.schedule_trigger_batch_size: break
            with session_factory() as session:
                if target == 'server_selection':
                    result = SelectionScheduleService(session, settings=settings).trigger_next_due(now=now)
                else:
                    result = ScheduleService(session, task_service=TaskService(session,
                        credential_service=CredentialService(session, get_secret_cipher()),
                    )).trigger_next_due(now=now)
            if result is None: continue
            logger.info("Schedule trigger processed", extra={
                "schedule_id":str(result.schedule_id),"scheduled_for":result.scheduled_for.isoformat(),
                "task_id":str(result.task_id) if result.task_id else None,
                "trigger_result":result.trigger_result.value,
            })
            triggered += 1
            progressed = True
        if not progressed: break
    return triggered


async def trigger_due_schedules_forever() -> None:
    settings = get_settings()
    while True:
        try:
            await asyncio.to_thread(
                trigger_due_schedules_once,
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("Schedule trigger scan failed", extra={"error_type":type(error).__name__})
        await asyncio.sleep(settings.schedule_scan_interval_seconds)
