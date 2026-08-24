from datetime import datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time as SQLTime,
    UniqueConstraint,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("schedule_type IN ('daily')", name="schedule_type"),
        CheckConstraint(
            "skill_id ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'",
            name="skill_id",
        ),
        CheckConstraint(
            "jsonb_typeof(task_input_json) = 'object'",
            name="task_input_object",
        ),
        Index(
            "ix_schedules_due",
            "next_run_at",
            "schedule_id",
            postgresql_where=text(
                "enabled IS TRUE AND deleted_at IS NULL AND next_run_at IS NOT NULL"
            ),
        ),
        Index(
            "ix_schedules_device_created",
            "target_device_id",
            "created_at",
            "schedule_id",
        ),
        Index("ix_schedules_created_schedule", "created_at", "schedule_id"),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    target_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        nullable=False,
    )
    skill_id: Mapped[str] = mapped_column(String(200), nullable=False)
    execution_display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(16), nullable=False)
    local_time: Mapped[time] = mapped_column(SQLTime(timezone=False), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    task_input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ScheduleRun(Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger_result IN ('task_created', 'blocked')",
            name="trigger_result",
        ),
        UniqueConstraint(
            "schedule_id",
            "scheduled_for",
            name="uq_schedule_runs_schedule_occurrence",
        ),
        Index(
            "ix_schedule_runs_schedule_scheduled",
            "schedule_id",
            "scheduled_for",
            "run_id",
        ),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    schedule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("schedules.schedule_id", ondelete="RESTRICT"),
        nullable=False,
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=True,
    )
    trigger_result: Mapped[str] = mapped_column(String(16), nullable=False)
    trigger_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trigger_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
