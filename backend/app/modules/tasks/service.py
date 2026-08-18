from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.exceptions import (
    TaskInputInvalidError,
    TaskNotFoundError,
    TaskStateConflictError,
    TaskTargetDeviceInvalidError,
)
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import TaskComplete, TaskCreate, TaskFail
from app.modules.tasks.skill_contracts import validate_skill_input
from app.modules.workers.service import WorkerPrincipal


class TaskService:
    def __init__(
        self,
        session: Session,
        repository: TaskRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or TaskRepository(session)
        self.settings = settings or get_settings()

    def create(self, data: TaskCreate) -> Task:
        if self.repository.get_enabled_device(data.target_device_id) is None:
            raise TaskTargetDeviceInvalidError()
        try:
            input_json = validate_skill_input(data.skill_id, data.input)
        except ValidationError as error:
            raise TaskInputInvalidError(
                details=error.errors(include_input=False),
            ) from error
        task = Task(
            target_device_id=data.target_device_id,
            skill_id=data.skill_id.value,
            status=TaskStatus.PENDING.value,
            input_json=input_json,
        )
        self.repository.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def get(self, task_id: UUID) -> Task:
        task = self.repository.get(task_id)
        if task is None:
            raise TaskNotFoundError()
        return task

    def claim(
        self,
        principal: WorkerPrincipal,
        *,
        now: datetime | None = None,
    ) -> Task | None:
        claimed_at = now or datetime.now(UTC)
        lease_until = claimed_at + timedelta(
            seconds=self.settings.worker_task_lease_seconds,
        )
        task = self.repository.claim_next(
            device_id=principal.device_id,
            now=claimed_at,
            lease_until=lease_until,
        )
        self.session.commit()
        return task

    def renew(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        *,
        now: datetime | None = None,
    ) -> Task:
        renewed_at = now or datetime.now(UTC)
        task = self.repository.renew(
            task_id=task_id,
            device_id=principal.device_id,
            now=renewed_at,
            lease_until=renewed_at
            + timedelta(seconds=self.settings.worker_task_lease_seconds),
        )
        if task is None:
            self.session.rollback()
            raise TaskStateConflictError()
        self.session.commit()
        return task

    def complete(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        data: TaskComplete,
        *,
        now: datetime | None = None,
    ) -> Task:
        return self._finish(
            principal,
            task_id,
            status=TaskStatus.SUCCESS,
            result=data.result,
            error_code=None,
            error_message=None,
            now=now,
        )

    def fail(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        data: TaskFail,
        *,
        now: datetime | None = None,
    ) -> Task:
        return self._finish(
            principal,
            task_id,
            status=TaskStatus.FAILED,
            result=None,
            error_code=data.error_code,
            error_message=data.error_message,
            now=now,
        )

    def _finish(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        *,
        status: TaskStatus,
        result: dict[str, object] | None,
        error_code: str | None,
        error_message: str | None,
        now: datetime | None,
    ) -> Task:
        finished_at = now or datetime.now(UTC)
        task = self.repository.complete(
            task_id=task_id,
            device_id=principal.device_id,
            now=finished_at,
            result=result,
            error_code=error_code,
            error_message=error_message,
            status=status,
        )
        if task is None:
            self.session.rollback()
            raise TaskStateConflictError()
        self.session.commit()
        return task

    def reconcile_expired(self, *, now: datetime | None = None) -> int:
        count = self.repository.mark_expired_lost(now=now or datetime.now(UTC))
        self.session.commit()
        return count
