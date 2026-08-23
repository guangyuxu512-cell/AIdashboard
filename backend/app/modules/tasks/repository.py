from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, and_, cast, exists, func, null, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task, TaskEvent
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
)
from app.shared.identifiers import generate_id


@dataclass(frozen=True)
class TaskListRecord:
    task: Task
    device_display_name: str
    skill_display_name: str | None
    progress_message: str | None
    progress_metadata: dict[str, Any] | None
    status_message: str | None
    log_message: str | None


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, task_id: UUID) -> Task | None:
        return self.session.get(Task, task_id)

    def get_active_for_device(self, device_id: UUID) -> Task | None:
        return self.session.scalar(
            select(Task)
            .where(
                Task.target_device_id == device_id,
                Task.status.in_(
                    [TaskStatus.PENDING.value, TaskStatus.RUNNING.value],
                ),
            )
            .order_by(Task.created_at.asc(), Task.task_id.asc())
            .limit(1),
        )

    def list_management_tasks(
        self,
        *,
        offset: int,
        limit: int,
        status: TaskStatus | None,
        device_id: UUID | None,
        search: str | None,
    ) -> tuple[list[TaskListRecord], int]:
        filters = []
        if status is not None:
            filters.append(Task.status == status.value)
        if device_id is not None:
            filters.append(Task.target_device_id == device_id)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    cast(Task.task_id, String).ilike(pattern),
                    Task.execution_display_name.ilike(pattern),
                    Task.skill_id.ilike(pattern),
                ),
            )

        total = int(
            self.session.scalar(
                select(func.count()).select_from(Task).where(*filters),
            )
            or 0,
        )
        page_task_ids = (
            select(Task.task_id)
            .where(*filters)
            .order_by(Task.created_at.desc(), Task.task_id.desc())
            .offset(offset)
            .limit(limit)
            .subquery("task_management_page")
        )

        def latest_event_value(event_type: str, column: Any) -> Any:
            return (
                select(column)
                .where(
                    TaskEvent.task_id == Task.task_id,
                    TaskEvent.event_type == event_type,
                )
                .order_by(TaskEvent.seq.desc())
                .limit(1)
                .correlate(Task)
                .scalar_subquery()
            )

        statement = (
            select(
                Task,
                Device.display_name.label("device_display_name"),
                DeviceSkillCapability.display_name.label("skill_display_name"),
                latest_event_value("progress", TaskEvent.message).label(
                    "progress_message",
                ),
                latest_event_value("progress", TaskEvent.metadata_json).label(
                    "progress_metadata",
                ),
                latest_event_value("status", TaskEvent.message).label(
                    "status_message",
                ),
                latest_event_value("log", TaskEvent.message).label("log_message"),
            )
            .join(page_task_ids, page_task_ids.c.task_id == Task.task_id)
            .join(Device, Device.device_id == Task.target_device_id)
            .outerjoin(
                DeviceSkillCapability,
                and_(
                    DeviceSkillCapability.device_id == Task.target_device_id,
                    DeviceSkillCapability.skill_id == Task.skill_id,
                ),
            )
            .order_by(Task.created_at.desc(), Task.task_id.desc())
        )
        records = [
            TaskListRecord(
                task=row[0],
                device_display_name=row.device_display_name,
                skill_display_name=row.skill_display_name,
                progress_message=row.progress_message,
                progress_metadata=row.progress_metadata,
                status_message=row.status_message,
                log_message=row.log_message,
            )
            for row in self.session.execute(statement)
        ]
        return records, total

    def get_latest_event(self, task_id: UUID) -> TaskEvent | None:
        return self.session.scalar(
            select(TaskEvent)
            .where(TaskEvent.task_id == task_id)
            .order_by(TaskEvent.seq.desc())
            .limit(1),
        )

    def list_events(
        self,
        *,
        task_id: UUID,
        after_seq: int,
        limit: int,
    ) -> list[TaskEvent]:
        return list(
            self.session.scalars(
                select(TaskEvent)
                .where(
                    TaskEvent.task_id == task_id,
                    TaskEvent.seq > after_seq,
                )
                .order_by(TaskEvent.seq.asc())
                .limit(limit),
            ),
        )

    def insert_events(
        self,
        *,
        task_id: UUID,
        events: list[dict[str, Any]],
    ) -> int:
        if not events:
            return 0
        values = [
            {
                "event_id": generate_id(),
                "task_id": task_id,
                **event,
            }
            for event in events
        ]
        statement = (
            insert(TaskEvent)
            .values(values)
            .on_conflict_do_nothing(constraint="uq_task_events_task_seq")
            .returning(TaskEvent.seq)
        )
        result = self.session.execute(statement)
        return len(result.scalars().all())

    def get_enabled_device(self, device_id: UUID) -> Device | None:
        statement = (
            select(Device)
            .where(
                Device.device_id == device_id,
                Device.enabled.is_(True),
                Device.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return self.session.scalar(statement)

    def get_task_target_device(self, device_id: UUID) -> Device | None:
        return self.session.scalar(
            select(Device)
            .where(
                Device.device_id == device_id,
                Device.deleted_at.is_(None),
            )
            .with_for_update(),
        )

    def get_skill_capability(
        self,
        device_id: UUID,
        skill_id: str,
    ) -> DeviceSkillCapability | None:
        return self.session.get(DeviceSkillCapability, (device_id, skill_id))

    def get_device_runtime(self, device_id: UUID) -> DeviceRuntime | None:
        return self.session.get(DeviceRuntime, device_id)

    def get_provider_inventory(
        self,
        device_id: UUID,
        provider_code: str,
    ) -> DeviceProviderInventory | None:
        return self.session.get(DeviceProviderInventory, (device_id, provider_code))

    def has_active_for_device(self, device_id: UUID) -> bool:
        return bool(
            self.session.scalar(
                select(func.count())
                .select_from(Task)
                .where(
                    Task.target_device_id == device_id,
                    Task.status.in_(
                        [TaskStatus.PENDING.value, TaskStatus.RUNNING.value],
                    ),
                ),
            ),
        )

    def add(self, task: Task) -> None:
        self.session.add(task)

    def claim_next(
        self,
        *,
        device_id: UUID,
        now: datetime,
        lease_until: datetime,
    ) -> Task | None:
        candidate = (
            select(Task.task_id)
            .where(
                Task.target_device_id == device_id,
                Task.status == TaskStatus.PENDING.value,
                exists(
                    select(Device.device_id).where(
                        Device.device_id == device_id,
                        Device.enabled.is_(True),
                        Device.deleted_at.is_(None),
                    ),
                ),
            )
            .order_by(Task.created_at.asc(), Task.task_id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            update(Task)
            .where(
                Task.task_id == candidate,
                Task.status == TaskStatus.PENDING.value,
            )
            .values(
                status=TaskStatus.RUNNING.value,
                started_at=now,
                lease_until=lease_until,
                updated_at=now,
            )
            .returning(Task)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def renew(
        self,
        *,
        task_id: UUID,
        device_id: UUID,
        now: datetime,
        lease_until: datetime,
    ) -> Task | None:
        statement = (
            update(Task)
            .where(
                Task.task_id == task_id,
                Task.target_device_id == device_id,
                Task.status == TaskStatus.RUNNING.value,
                Task.lease_until >= now,
            )
            .values(lease_until=lease_until, updated_at=now)
            .returning(Task)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def complete(
        self,
        *,
        task_id: UUID,
        device_id: UUID,
        now: datetime,
        result: dict[str, Any] | None,
        error_code: str | None,
        error_message: str | None,
        status: TaskStatus,
    ) -> Task | None:
        statement = (
            update(Task)
            .where(
                Task.task_id == task_id,
                Task.target_device_id == device_id,
                Task.status == TaskStatus.RUNNING.value,
                Task.lease_until >= now,
            )
            .values(
                status=status.value,
                # JSONB(None) is JSON `null`, which violates the table's
                # object-or-SQL-NULL constraint used by failed Tasks.
                result_json=result if result is not None else null(),
                error_code=error_code,
                error_message=error_message,
                lease_until=None,
                finished_at=now,
                updated_at=now,
            )
            .returning(Task)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def mark_expired_lost(self, *, now: datetime) -> int:
        statement = (
            update(Task)
            .where(
                Task.status == TaskStatus.RUNNING.value,
                Task.lease_until < now,
            )
            .values(
                status=TaskStatus.LOST.value,
                error_code="WORKER_LEASE_EXPIRED",
                error_message="Worker lease expired before a result was received",
                lease_until=None,
                finished_at=now,
                updated_at=now,
            )
        )
        result = self.session.execute(statement)
        return result.rowcount or 0
