import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.automation_apps.repository import AutomationApplicationConfigRepository
from app.modules.automation_apps.schemas import AutomationInputSchema, normalize_parameters
from app.modules.tasks.enums import TaskSkillId, TaskStatus
from app.modules.tasks.exceptions import (
    TaskApplicationNotAvailableError,
    TaskDeviceDisabledError,
    TaskEventForbiddenError,
    TaskInputInvalidError,
    TaskNotFoundError,
    TaskProviderLoginRequiredError,
    TaskProviderNotReadyError,
    TaskProviderVersionUnsupportedError,
    TaskSkillNotAvailableError,
    TaskStateConflictError,
    TaskTargetDeviceInvalidError,
    TaskWorkerOfflineError,
)
from app.modules.tasks.models import Task
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.schemas import (
    ActiveTaskSummaryRead,
    TaskComplete,
    TaskCreate,
    TaskEventBatchResult,
    TaskEventBatchWrite,
    TaskEventListRead,
    TaskFail,
    task_event_to_read,
)
from app.modules.tasks.skill_contracts import validate_skill_input
from app.modules.workers.service import WorkerPrincipal
from app.modules.workers.models import DeviceSkillCapability
from app.modules.workers.schemas import YingdaoProviderInventory


class TaskService:
    def __init__(
        self,
        session: Session,
        repository: TaskRepository | None = None,
        settings: Settings | None = None,
        application_config_repository: (
            AutomationApplicationConfigRepository | None
        ) = None,
    ) -> None:
        self.session = session
        self.repository = repository or TaskRepository(session)
        self.settings = settings or get_settings()
        self.application_config_repository = (
            application_config_repository
            or AutomationApplicationConfigRepository(session)
        )

    def create(self, data: TaskCreate) -> Task:
        device = self.repository.get_task_target_device(data.target_device_id)
        if device is None:
            raise TaskTargetDeviceInvalidError()
        if not device.enabled:
            raise TaskDeviceDisabledError()
        runtime = self.repository.get_device_runtime(data.target_device_id)
        if runtime is None or runtime.connection_status != "online":
            raise TaskWorkerOfflineError()
        capability = self.repository.get_skill_capability(
            data.target_device_id,
            data.skill_id.value,
        )
        if capability is None:
            raise TaskSkillNotAvailableError(
                details={"skill_id": data.skill_id.value},
            )
        provider_inventory = self._validate_provider_dependency(
            data.target_device_id,
            capability,
        )
        try:
            input_json = validate_skill_input(data.skill_id, data.input)
        except ValidationError as error:
            raise TaskInputInvalidError(
                details=error.errors(include_input=False),
            ) from error
        execution_display_name = capability.display_name
        if data.skill_id is TaskSkillId.YINGDAO_APP_RUN:
            input_json, execution_display_name = self._validate_yingdao_application_run(
                input_json,
                provider_inventory,
            )
        task = Task(
            target_device_id=data.target_device_id,
            skill_id=data.skill_id.value,
            execution_display_name=execution_display_name,
            status=TaskStatus.PENDING.value,
            input_json=input_json,
        )
        self.repository.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def _validate_provider_dependency(
        self,
        device_id: UUID,
        capability: DeviceSkillCapability,
    ) -> YingdaoProviderInventory | None:
        if capability.provider_code is None or capability.runtime == "discovery":
            return None
        if capability.provider_code != "yingdao":
            raise TaskProviderNotReadyError(
                details={"provider": capability.provider_code},
            )
        record = self.repository.get_provider_inventory(
            device_id,
            capability.provider_code,
        )
        if record is None:
            raise TaskProviderNotReadyError(details={"provider": "yingdao"})
        try:
            inventory = YingdaoProviderInventory.model_validate(
                record.inventory_payload,
            )
        except ValidationError as error:
            raise TaskProviderNotReadyError(
                details={"provider": "yingdao", "reason": "invalid_inventory"},
            ) from error
        if inventory.status == "need_login" or not inventory.logged_in:
            raise TaskProviderLoginRequiredError()
        if (
            inventory.status == "version_unsupported"
            or inventory.provider_version != "6.3.6"
            or inventory.execution_version != "6.3.6"
        ):
            raise TaskProviderVersionUnsupportedError(
                details={"required_version": "6.3.6"},
            )
        if (
            inventory.status != "ready"
            or not record.available
            or not inventory.available
            or not inventory.execution_available
        ):
            raise TaskProviderNotReadyError(details={"provider": "yingdao"})
        return inventory

    def _validate_yingdao_application_run(
        self,
        input_json: dict[str, Any],
        inventory: YingdaoProviderInventory | None,
    ) -> tuple[dict[str, Any], str]:
        if inventory is None:
            raise TaskProviderNotReadyError(details={"provider": "yingdao"})
        app_id = str(input_json["app_id"])
        application = next(
            (
                application
                for application in inventory.applications
                if application.app_id == app_id
            ),
            None,
        )
        if application is None:
            raise TaskApplicationNotAvailableError(
                details={"app_id": app_id},
            )
        config = self.application_config_repository.get("yingdao", app_id)
        schema = AutomationInputSchema.model_validate(
            config.input_schema if config is not None else {"fields": []},
        )
        try:
            params = normalize_parameters(schema, input_json.get("params", {}))
        except ValueError as error:
            raise TaskInputInvalidError(str(error)) from error
        return {"app_id": app_id, "params": params}, application.app_name

    def get(self, task_id: UUID) -> Task:
        task = self.repository.get(task_id)
        if task is None:
            raise TaskNotFoundError()
        return task

    def get_active_summary(self, device_id: UUID) -> ActiveTaskSummaryRead | None:
        task = self.repository.get_active_for_device(device_id)
        if task is None:
            return None
        latest_event = self.repository.get_latest_event(task.task_id)
        return ActiveTaskSummaryRead(
            task_id=task.task_id,
            target_device_id=task.target_device_id,
            skill_id=task.skill_id,
            execution_display_name=task.execution_display_name,
            status=task.status,
            started_at=task.started_at,
            created_at=task.created_at,
            latest_event=(
                task_event_to_read(latest_event) if latest_event is not None else None
            ),
        )

    def list_events(
        self,
        task_id: UUID,
        *,
        after_seq: int,
        limit: int,
    ) -> TaskEventListRead:
        if self.repository.get(task_id) is None:
            raise TaskNotFoundError()
        events = self.repository.list_events(
            task_id=task_id,
            after_seq=after_seq,
            limit=limit,
        )
        items = [task_event_to_read(event) for event in events]
        return TaskEventListRead(
            task_id=task_id,
            after_seq=after_seq,
            next_after_seq=items[-1].seq if items else after_seq,
            items=items,
        )

    def append_events(
        self,
        principal: WorkerPrincipal,
        task_id: UUID,
        data: TaskEventBatchWrite,
        *,
        now: datetime | None = None,
    ) -> TaskEventBatchResult:
        task = self.repository.get(task_id)
        if task is None:
            raise TaskNotFoundError()
        current_time = now or datetime.now(UTC)
        owns_running_lease = (
            task.status == TaskStatus.RUNNING.value
            and task.lease_until is not None
            and task.lease_until >= current_time
        )
        owns_terminal_task = task.status in {
            TaskStatus.SUCCESS.value,
            TaskStatus.FAILED.value,
            TaskStatus.LOST.value,
        }
        if (
            task.target_device_id != principal.device_id
            or not (owns_running_lease or owns_terminal_task)
        ):
            raise TaskEventForbiddenError()

        payloads = [
            {
                "seq": event.seq,
                "event_type": event.event_type.value,
                "level": event.level,
                "message": _redact_message(event.message),
                "event_at": event.event_at,
                "metadata_json": _redact_metadata(event.metadata),
            }
            for event in data.events
        ]
        accepted_count = self.repository.insert_events(
            task_id=task_id,
            events=payloads,
        )
        self.session.commit()
        return TaskEventBatchResult(
            task_id=task_id,
            accepted_count=accepted_count,
            highest_seq=max(event.seq for event in data.events),
        )

    def claim(
        self,
        principal: WorkerPrincipal,
        *,
        now: datetime | None = None,
    ) -> Task | None:
        claimed_at = now or datetime.now(UTC)
        if self.repository.get_enabled_device(principal.device_id) is None:
            self.session.rollback()
            return None
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


_SENSITIVE_MESSAGE = re.compile(
    r"(?i)\b(password|token|authorization|cookie|secret)\b\s*[:=]\s*[^\s,;]+",
)
_SENSITIVE_KEYS = frozenset(
    {"password", "token", "authorization", "cookie", "cookies", "secret"},
)


def _redact_message(value: str) -> str:
    return _SENSITIVE_MESSAGE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def _redact_metadata(value: dict[str, Any]) -> dict[str, Any]:
    def redact(item: Any, key: str | None = None) -> Any:
        if key is not None and key.lower() in _SENSITIVE_KEYS:
            return "[REDACTED]"
        if isinstance(item, dict):
            return {
                str(child_key): redact(child, str(child_key))
                for child_key, child in item.items()
            }
        if isinstance(item, list):
            return [redact(child) for child in item]
        return item

    return redact(value)
