from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    String,
    and_,
    cast,
    delete,
    exists,
    func,
    null,
    or_,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.policy import DataScopePolicy
from app.modules.devices.models import Device
from app.modules.tasks.enums import TERMINAL_TASK_STATUS_VALUES, TaskStatus
from app.modules.tasks.models import Task, TaskEvent, TaskShop
from app.modules.tasks.precheck_contract import PRODUCT_PRECHECK_SKILL_ID
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


@dataclass(frozen=True)
class TaskEventPage:
    items: list[TaskEvent]
    has_more_before: bool


@dataclass(frozen=True)
class TaskEventPurgeBatch:
    tasks_purged: int
    events_deleted: int


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, task_id: UUID) -> Task | None:
        return self.session.get(Task, task_id)

    def get_running_for_device_for_session_read(
        self, *, task_id: UUID, device_id: UUID, now: datetime,
    ) -> Task | None:
        """Lock a live task belonging to this device before releasing task-scoped data."""
        return self.session.scalar(
            select(Task).where(
                Task.task_id == task_id,
                Task.target_device_id == device_id,
                Task.status == TaskStatus.RUNNING.value,
                Task.lease_until.is_not(None),
                Task.lease_until >= now,
            ).with_for_update(read=True, nowait=True)
            .execution_options(populate_existing=True),
        )

    def lock_shop_for_session_read(self, *, task_id: UUID, shop_id: UUID) -> bool:
        return self.session.scalar(
            select(TaskShop.shop_id)
            .where(TaskShop.task_id == task_id, TaskShop.shop_id == shop_id)
            .with_for_update(read=True, nowait=True),
        ) is not None

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        task_id: UUID,
    ) -> Task | None:
        statement = DataScopePolicy.apply(
            select(Task).where(Task.task_id == task_id),
            team_id_column=Task.team_id,
            created_by_user_id_column=Task.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement)

    def get_active_for_device(
        self,
        *,
        actor: ActorContext,
        device_id: UUID,
    ) -> Task | None:
        statement = DataScopePolicy.apply(
            select(Task)
            .where(
                Task.target_device_id == device_id,
                Task.status.in_(
                    [TaskStatus.PENDING.value, TaskStatus.RUNNING.value],
                ),
            ),
            team_id_column=Task.team_id,
            created_by_user_id_column=Task.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(
            statement
            .order_by(Task.created_at.asc(), Task.task_id.asc())
            .limit(1),
        )

    def list_management_tasks(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        status: TaskStatus | None,
        device_id: UUID | None,
        search: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> tuple[list[TaskListRecord], int]:
        filters = []
        if status is not None:
            filters.append(Task.status == status.value)
        if device_id is not None:
            filters.append(Task.target_device_id == device_id)
        if created_from is not None:
            filters.append(Task.created_at >= created_from)
        if created_to is not None:
            filters.append(Task.created_at < created_to)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    cast(Task.task_id, String).ilike(pattern),
                    Task.execution_display_name.ilike(pattern),
                    Task.skill_id.ilike(pattern),
                ),
            )

        total_statement = DataScopePolicy.apply(
            select(func.count()).select_from(Task).where(*filters),
            team_id_column=Task.team_id,
            created_by_user_id_column=Task.created_by_user_id,
            actor=actor,
        )
        total = int(self.session.scalar(total_statement) or 0)
        page_task_ids = (
            DataScopePolicy.apply(
                select(Task.task_id).where(*filters),
                team_id_column=Task.team_id,
                created_by_user_id_column=Task.created_by_user_id,
                actor=actor,
            )
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
        after_seq: int | None,
        before_seq: int | None,
        limit: int,
    ) -> TaskEventPage:
        if after_seq is not None:
            items = list(
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
            return TaskEventPage(items=items, has_more_before=False)

        filters = [TaskEvent.task_id == task_id]
        if before_seq is not None:
            filters.append(TaskEvent.seq < before_seq)
        descending = list(
            self.session.scalars(
                select(TaskEvent)
                .where(*filters)
                .order_by(TaskEvent.seq.desc())
                .limit(limit + 1),
            ),
        )
        has_more_before = len(descending) > limit
        return TaskEventPage(
            items=list(reversed(descending[:limit])),
            has_more_before=has_more_before,
        )

    def purge_expired_event_batch(
        self,
        *,
        cutoff: datetime,
        purged_at: datetime,
        batch_size: int,
        actor: ActorContext | None = None,
    ) -> TaskEventPurgeBatch:
        eligible_statement = select(Task.task_id).where(
            Task.status.in_(TERMINAL_TASK_STATUS_VALUES),
            Task.finished_at.is_not(None),
            Task.finished_at < cutoff,
            exists(
                select(TaskEvent.event_id).where(
                    TaskEvent.task_id == Task.task_id,
                ),
            ),
        )
        if actor is not None:
            eligible_statement = DataScopePolicy.apply(
                eligible_statement,
                team_id_column=Task.team_id,
                created_by_user_id_column=Task.created_by_user_id,
                actor=actor,
            )
        eligible_task_ids = list(
            self.session.scalars(
                eligible_statement
                .order_by(Task.finished_at.asc(), Task.task_id.asc())
                .with_for_update(skip_locked=True)
                .limit(batch_size),
            ),
        )
        if not eligible_task_ids:
            return TaskEventPurgeBatch(tasks_purged=0, events_deleted=0)

        delete_result = self.session.execute(
            delete(TaskEvent).where(TaskEvent.task_id.in_(eligible_task_ids)),
        )
        events_deleted = delete_result.rowcount
        if events_deleted:
            self.session.execute(
                update(Task)
                .where(Task.task_id.in_(eligible_task_ids))
                .values(runtime_events_purged_at=purged_at),
            )
        return TaskEventPurgeBatch(
            tasks_purged=len(eligible_task_ids) if events_deleted else 0,
            events_deleted=events_deleted,
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

    def get_enabled_device_for_session_read(self, device_id: UUID) -> Device | None:
        return self.session.scalar(
            select(Device)
            .where(
                Device.device_id == device_id,
                Device.enabled.is_(True),
                Device.deleted_at.is_(None),
            )
            .with_for_update(read=True, nowait=True)
            .execution_options(populate_existing=True),
        )

    def get_task_target_device(
        self,
        device_id: UUID,
    ) -> Device | None:
        filters = [
            Device.device_id == device_id,
            Device.deleted_at.is_(None),
        ]
        return self.session.scalar(
            select(Device)
            .where(*filters)
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
        allow_precheck: bool = False,
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
        )
        # Older Workers reject shop_ids and must never transition a queued
        # precheck to RUNNING. Skip it in the same atomic selection so it
        # cannot block unrelated ordinary tasks for this device.
        if not allow_precheck:
            candidate = candidate.where(Task.skill_id != PRODUCT_PRECHECK_SKILL_ID)
        candidate = (
            candidate
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
