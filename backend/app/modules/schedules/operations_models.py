"""Schedules for strategies owned by the independent operations service."""
from datetime import datetime, time
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Time, UniqueConstraint, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.identifiers import generate_id


class OperationsSchedule(Base):
    __tablename__ = 'operations_selection_schedules'
    __table_args__ = (
        UniqueConstraint('team_id', 'strategy_id', name='uq_ops_schedule_team_strategy'),
        CheckConstraint("kind IN ('daily', 'hourly')", name='kind'),
        CheckConstraint("(kind = 'daily' AND local_time IS NOT NULL AND interval_hours IS NULL) OR "
                        "(kind = 'hourly' AND local_time IS NULL AND interval_hours BETWEEN 1 AND 24)", name='rule'),
        Index('ix_ops_schedule_due', 'next_run_at', postgresql_where=text('enabled IS TRUE AND next_run_at IS NOT NULL')),
    )

    schedule_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('teams.team_id', ondelete='RESTRICT'), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.user_id', ondelete='RESTRICT'), nullable=False)
    strategy_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text('false'))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    local_time: Mapped[time | None] = mapped_column(Time(timezone=False))
    interval_hours: Mapped[int | None] = mapped_column(Integer)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OperationsScheduleRun(Base):
    __tablename__ = 'operations_selection_schedule_runs'
    __table_args__ = (
        UniqueConstraint('schedule_id', 'scheduled_for', name='uq_ops_schedule_occurrence'),
        UniqueConstraint('submission_key', name='uq_ops_schedule_submission'),
        CheckConstraint("state IN ('pending', 'sent', 'failed', 'cancelled')", name='state'),
        Index('ix_ops_schedule_pending', 'next_attempt_at', postgresql_where=text("state = 'pending'")),
    )

    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    schedule_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('operations_selection_schedules.schedule_id', ondelete='RESTRICT'), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submission_key: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default='pending')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operations_run_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
