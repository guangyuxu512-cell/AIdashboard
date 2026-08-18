"""create Worker Core Lite runtime and task tables

Revision ID: 20260819_0003
Revises: 20260819_0002
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260819_0003"
down_revision: str | None = "20260819_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_device_credentials",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_worker_device_credentials_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "credential_id",
            name="pk_worker_device_credentials",
        ),
        sa.UniqueConstraint(
            "device_id",
            name="uq_worker_device_credentials_device_id",
        ),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_worker_device_credentials_token_hash",
        ),
    )
    op.create_index(
        "ix_worker_device_credentials_device_id",
        "worker_device_credentials",
        ["device_id"],
        unique=False,
    )

    op.create_table(
        "device_runtime",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("worker_version", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_device_runtime_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("device_id", name="pk_device_runtime"),
    )
    op.create_index(
        "ix_device_runtime_last_seen_at",
        "device_runtime",
        ["last_seen_at"],
        unique=False,
    )

    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("target_device_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column(
            "input_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "result_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'lost')",
            name="ck_tasks_status",
        ),
        sa.CheckConstraint(
            "skill_id IN ('system.echo', 'system.sleep')",
            name="ck_tasks_skill_id",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(input_json) = 'object'",
            name="ck_tasks_input_object",
        ),
        sa.CheckConstraint(
            "result_json IS NULL OR jsonb_typeof(result_json) = 'object'",
            name="ck_tasks_result_object",
        ),
        sa.ForeignKeyConstraint(
            ["target_device_id"],
            ["devices.device_id"],
            name="fk_tasks_target_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("task_id", name="pk_tasks"),
    )
    op.create_index("ix_tasks_status", "tasks", ["status"], unique=False)
    op.create_index(
        "ix_tasks_running_lease",
        "tasks",
        ["status", "lease_until"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_target_status_created",
        "tasks",
        ["target_device_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_target_status_created", table_name="tasks")
    op.drop_index("ix_tasks_running_lease", table_name="tasks")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_device_runtime_last_seen_at", table_name="device_runtime")
    op.drop_table("device_runtime")
    op.drop_index(
        "ix_worker_device_credentials_device_id",
        table_name="worker_device_credentials",
    )
    op.drop_table("worker_device_credentials")
