from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'lost')",
            name="status",
        ),
        CheckConstraint(
            "skill_id ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'",
            name="skill_id",
        ),
        CheckConstraint("jsonb_typeof(input_json) = 'object'", name="input_object"),
        CheckConstraint(
            "result_json IS NULL OR jsonb_typeof(result_json) = 'object'",
            name="result_object",
        ),
        Index(
            "ix_tasks_target_status_created",
            "target_device_id",
            "status",
            "created_at",
            "task_id",
        ),
        Index("ix_tasks_created_task", "created_at", "task_id"),
        Index(
            "ix_tasks_team_created_task",
            "team_id",
            "created_at",
            "task_id",
        ),
        Index(
            "ix_tasks_team_creator_created_task",
            "team_id",
            "created_by_user_id",
            "created_at",
            "task_id",
        ),
        Index(
            "ix_tasks_target_created_task",
            "target_device_id",
            "created_at",
            "task_id",
        ),
        Index(
            "ix_tasks_status_created_task",
            "status",
            "created_at",
            "task_id",
        ),
        Index(
            "ix_tasks_terminal_finished_task",
            "finished_at",
            "task_id",
            postgresql_where=text(
                "status IN ('success', 'failed', 'lost') "
                "AND finished_at IS NOT NULL"
            ),
        ),
        Index("ix_tasks_running_lease", "status", "lease_until"),
    )

    task_id: Mapped[UUID] = mapped_column(
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
    target_device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        nullable=False,
    )
    shop_links: Mapped[list["TaskShop"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TaskShop.position",
    )
    asset_links: Mapped[list["TaskAsset"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="TaskAsset.position",
    )
    skill_id: Mapped[str] = mapped_column(String(200), nullable=False)
    execution_display_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(8), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    runtime_events_purged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def shop_ids(self) -> list[UUID]:
        return [link.shop_id for link in self.shop_links]

    @property
    def asset_ids(self) -> list[UUID]:
        return [link.asset_id for link in self.asset_links]


class TaskShop(Base):
    __tablename__ = "task_shops"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        UniqueConstraint("task_id", "position", name="uq_task_shops_task_position"),
        Index("ix_task_shops_shop_task", "shop_id", "task_id"),
    )

    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    task: Mapped[Task] = relationship(back_populates="shop_links")


class TaskAsset(Base):
    __tablename__ = "task_assets"
    __table_args__ = (
        CheckConstraint("position >= 0", name="position_non_negative"),
        UniqueConstraint("task_id", "position", name="uq_task_assets_task_position"),
        Index("ix_task_assets_asset_task", "asset_id", "task_id"),
    )

    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("assets.asset_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    task: Mapped[Task] = relationship(back_populates="asset_links")


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('status', 'log', 'progress', 'completed', 'failed')",
            name="event_type",
        ),
        CheckConstraint("seq > 0", name="positive_seq"),
        CheckConstraint("jsonb_typeof(metadata_json) = 'object'", name="metadata_object"),
        UniqueConstraint("task_id", "seq", name="uq_task_events_task_seq"),
        Index("ix_task_events_task_type_seq", "task_id", "event_type", "seq"),
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.task_id", ondelete="RESTRICT"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
