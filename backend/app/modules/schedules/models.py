from datetime import date, datetime, time
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "schedule_type IN ('once', 'daily', 'weekly')",
            name="schedule_type",
        ),
        CheckConstraint(
            "jsonb_typeof(weekdays) = 'array'",
            name="weekdays_array",
        ),
        CheckConstraint(
            "(schedule_type = 'once' AND local_date IS NOT NULL "
            "AND jsonb_array_length(weekdays) = 0) OR "
            "(schedule_type = 'daily' AND local_date IS NULL "
            "AND jsonb_array_length(weekdays) = 0) OR "
            "(schedule_type = 'weekly' AND local_date IS NULL "
            "AND jsonb_array_length(weekdays) > 0)",
            name="rule_fields",
        ),
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
        Index(
            "ix_schedules_team_created_schedule",
            "team_id",
            "created_at",
            "schedule_id",
        ),
        Index(
            "ix_schedules_team_creator_created_schedule",
            "team_id",
            "created_by_user_id",
            "created_at",
            "schedule_id",
        ),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
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
    shop_links: Mapped[list["ScheduleShop"]] = relationship(
        back_populates="schedule",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ScheduleShop.position",
    )
    skill_id: Mapped[str] = mapped_column(String(200), nullable=False)
    execution_display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    schedule_type: Mapped[str] = mapped_column(String(16), nullable=False)
    local_time: Mapped[time] = mapped_column(SQLTime(timezone=False), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    local_date: Mapped[date | None] = mapped_column(SQLDate, nullable=True)
    weekdays: Mapped[list[int]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    task_input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def shop_ids(self) -> list[UUID]:
        return [link.shop_id for link in self.shop_links]


class ScheduleShop(Base):
    __tablename__ = "schedule_shops"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        UniqueConstraint(
            "schedule_id",
            "position",
            name="uq_schedule_shops_schedule_position",
        ),
        Index("ix_schedule_shops_shop_schedule", "shop_id", "schedule_id"),
    )

    schedule_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("schedules.schedule_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    schedule: Mapped[Schedule] = relationship(back_populates="shop_links")


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
