from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, null, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task, TaskEvent
from app.modules.workers.models import DeviceProviderInventory
from app.shared.identifiers import generate_id


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
