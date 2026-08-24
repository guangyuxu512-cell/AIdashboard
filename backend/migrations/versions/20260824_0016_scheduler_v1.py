"""add database-backed daily schedules

Revision ID: 20260824_0016
Revises: 20260824_0015
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260824_0016"
down_revision: str | None = "20260824_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("target_device_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=64), nullable=False),
        sa.Column("execution_display_name", sa.String(length=500), nullable=False),
        sa.Column("schedule_type", sa.String(length=16), nullable=False),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column(
            "task_input_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_schedules_name_not_blank",
        ),
        sa.CheckConstraint(
            "schedule_type IN ('daily')",
            name="ck_schedules_schedule_type",
        ),
        sa.CheckConstraint(
            "skill_id IN ('system.echo', 'system.sleep', 'yingdao.test', "
            "'yingdao.discover', 'yingdao.app.run')",
            name="ck_schedules_skill_id",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(task_input_json) = 'object'",
            name="ck_schedules_task_input_object",
        ),
        sa.ForeignKeyConstraint(
            ["target_device_id"],
            ["devices.device_id"],
            name="fk_schedules_target_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("schedule_id", name="pk_schedules"),
    )
    op.create_index(
        "ix_schedules_due",
        "schedules",
        ["next_run_at", "schedule_id"],
        unique=False,
        postgresql_where=sa.text(
            "enabled IS TRUE AND deleted_at IS NULL AND next_run_at IS NOT NULL"
        ),
    )
    op.create_index(
        "ix_schedules_device_created",
        "schedules",
        ["target_device_id", "created_at", "schedule_id"],
        unique=False,
    )
    op.create_index(
        "ix_schedules_created_schedule",
        "schedules",
        ["created_at", "schedule_id"],
        unique=False,
    )

    op.create_table(
        "schedule_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_result", sa.String(length=16), nullable=False),
        sa.Column("trigger_error_code", sa.String(length=64), nullable=True),
        sa.Column("trigger_error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "trigger_result IN ('task_created', 'blocked')",
            name="ck_schedule_runs_trigger_result",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["schedules.schedule_id"],
            name="fk_schedule_runs_schedule_id_schedules",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name="fk_schedule_runs_task_id_tasks",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_schedule_runs"),
        sa.UniqueConstraint(
            "schedule_id",
            "scheduled_for",
            name="uq_schedule_runs_schedule_occurrence",
        ),
    )
    op.create_index(
        "ix_schedule_runs_schedule_scheduled",
        "schedule_runs",
        ["schedule_id", "scheduled_for", "run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_schedule_runs_schedule_scheduled",
        table_name="schedule_runs",
    )
    op.drop_table("schedule_runs")
    op.drop_index("ix_schedules_created_schedule", table_name="schedules")
    op.drop_index("ix_schedules_device_created", table_name="schedules")
    op.drop_index("ix_schedules_due", table_name="schedules")
    op.drop_table("schedules")
