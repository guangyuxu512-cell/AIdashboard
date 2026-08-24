from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.modules.devices.models import Device
from app.modules.schedules.models import Schedule, ScheduleRun
from app.modules.tasks.models import Task


@dataclass(frozen=True)
class ScheduleListRecord:
    schedule: Schedule
    device_display_name: str
    latest_run: ScheduleRun | None
    latest_task_status: str | None


@dataclass(frozen=True)
class ScheduleRunRecord:
    run: ScheduleRun
    task_status: str | None


class ScheduleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, schedule: Schedule) -> None:
        self.session.add(schedule)

    def add_run(self, run: ScheduleRun) -> None:
        self.session.add(run)

    def get(self, schedule_id: UUID) -> Schedule | None:
        return self.session.scalar(
            select(Schedule).where(
                Schedule.schedule_id == schedule_id,
                Schedule.deleted_at.is_(None),
            ),
        )

    def get_including_deleted(self, schedule_id: UUID) -> Schedule | None:
        return self.session.get(Schedule, schedule_id)

    def get_for_update(self, schedule_id: UUID) -> Schedule | None:
        return self.session.scalar(
            select(Schedule)
            .where(
                Schedule.schedule_id == schedule_id,
                Schedule.deleted_at.is_(None),
            )
            .with_for_update(),
        )

    def get_next_due(self, *, now: datetime) -> Schedule | None:
        return self.session.scalar(
            select(Schedule)
            .where(
                Schedule.enabled.is_(True),
                Schedule.deleted_at.is_(None),
                Schedule.next_run_at.is_not(None),
                Schedule.next_run_at <= now,
            )
            .order_by(Schedule.next_run_at.asc(), Schedule.schedule_id.asc())
            .with_for_update(skip_locked=True)
            .limit(1),
        )

    def list_management(
        self,
        *,
        offset: int,
        limit: int,
        enabled: bool | None,
        device_id: UUID | None,
        search: str | None,
    ) -> tuple[list[ScheduleListRecord], int]:
        filters = [Schedule.deleted_at.is_(None)]
        if enabled is not None:
            filters.append(Schedule.enabled.is_(enabled))
        if device_id is not None:
            filters.append(Schedule.target_device_id == device_id)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    cast(Schedule.schedule_id, String).ilike(pattern),
                    Schedule.name.ilike(pattern),
                    Schedule.execution_display_name.ilike(pattern),
                ),
            )

        total = int(
            self.session.scalar(
                select(func.count()).select_from(Schedule).where(*filters),
            )
            or 0,
        )
        page_schedule_ids = (
            select(Schedule.schedule_id)
            .where(*filters)
            .order_by(Schedule.created_at.desc(), Schedule.schedule_id.desc())
            .offset(offset)
            .limit(limit)
            .subquery("schedule_management_page")
        )
        latest_run_id = (
            select(ScheduleRun.run_id)
            .where(ScheduleRun.schedule_id == Schedule.schedule_id)
            .order_by(ScheduleRun.scheduled_for.desc(), ScheduleRun.run_id.desc())
            .limit(1)
            .correlate(Schedule)
            .scalar_subquery()
        )
        statement = (
            select(
                Schedule,
                Device.display_name.label("device_display_name"),
                ScheduleRun,
                Task.status.label("task_status"),
            )
            .join(
                page_schedule_ids,
                page_schedule_ids.c.schedule_id == Schedule.schedule_id,
            )
            .join(Device, Device.device_id == Schedule.target_device_id)
            .outerjoin(ScheduleRun, ScheduleRun.run_id == latest_run_id)
            .outerjoin(Task, Task.task_id == ScheduleRun.task_id)
            .order_by(Schedule.created_at.desc(), Schedule.schedule_id.desc())
        )
        records = [
            ScheduleListRecord(
                schedule=row[0],
                device_display_name=row.device_display_name,
                latest_run=row[2],
                latest_task_status=row.task_status,
            )
            for row in self.session.execute(statement)
        ]
        return records, total

    def get_record(self, schedule_id: UUID) -> ScheduleListRecord | None:
        latest_run_id = (
            select(ScheduleRun.run_id)
            .where(ScheduleRun.schedule_id == Schedule.schedule_id)
            .order_by(ScheduleRun.scheduled_for.desc(), ScheduleRun.run_id.desc())
            .limit(1)
            .correlate(Schedule)
            .scalar_subquery()
        )
        statement = (
            select(
                Schedule,
                Device.display_name.label("device_display_name"),
                ScheduleRun,
                Task.status.label("task_status"),
            )
            .join(Device, Device.device_id == Schedule.target_device_id)
            .outerjoin(ScheduleRun, ScheduleRun.run_id == latest_run_id)
            .outerjoin(Task, Task.task_id == ScheduleRun.task_id)
            .where(
                Schedule.schedule_id == schedule_id,
                Schedule.deleted_at.is_(None),
            )
        )
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return ScheduleListRecord(
            schedule=row[0],
            device_display_name=row.device_display_name,
            latest_run=row[2],
            latest_task_status=row.task_status,
        )

    def list_runs(
        self,
        schedule_id: UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[ScheduleRunRecord], int]:
        total = int(
            self.session.scalar(
                select(func.count())
                .select_from(ScheduleRun)
                .where(ScheduleRun.schedule_id == schedule_id),
            )
            or 0,
        )
        statement = (
            select(ScheduleRun, Task.status.label("task_status"))
            .outerjoin(Task, Task.task_id == ScheduleRun.task_id)
            .where(ScheduleRun.schedule_id == schedule_id)
            .order_by(ScheduleRun.scheduled_for.desc(), ScheduleRun.run_id.desc())
            .offset(offset)
            .limit(limit)
        )
        return (
            [
                ScheduleRunRecord(run=row[0], task_status=row.task_status)
                for row in self.session.execute(statement)
            ],
            total,
        )
