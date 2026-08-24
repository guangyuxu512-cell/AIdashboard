"""add task query indexes and Runtime Event retention marker

Revision ID: 20260824_0015
Revises: 20260824_0014
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260824_0015"
down_revision: str | None = "20260824_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "runtime_events_purged_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_target_status_created", table_name="tasks")
    op.create_index(
        "ix_tasks_target_status_created",
        "tasks",
        ["target_device_id", "status", "created_at", "task_id"],
    )
    op.create_index(
        "ix_tasks_created_task",
        "tasks",
        ["created_at", "task_id"],
    )
    op.create_index(
        "ix_tasks_target_created_task",
        "tasks",
        ["target_device_id", "created_at", "task_id"],
    )
    op.create_index(
        "ix_tasks_status_created_task",
        "tasks",
        ["status", "created_at", "task_id"],
    )
    op.create_index(
        "ix_tasks_terminal_finished_task",
        "tasks",
        ["finished_at", "task_id"],
        postgresql_where=sa.text(
            "status IN ('success', 'failed', 'lost') "
            "AND finished_at IS NOT NULL"
        ),
    )

    op.drop_index("ix_task_events_task_seq", table_name="task_events")
    op.create_index(
        "ix_task_events_task_type_seq",
        "task_events",
        ["task_id", "event_type", "seq"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_events_task_type_seq", table_name="task_events")
    op.create_index(
        "ix_task_events_task_seq",
        "task_events",
        ["task_id", "seq"],
    )

    op.drop_index("ix_tasks_terminal_finished_task", table_name="tasks")
    op.drop_index("ix_tasks_status_created_task", table_name="tasks")
    op.drop_index("ix_tasks_target_created_task", table_name="tasks")
    op.drop_index("ix_tasks_created_task", table_name="tasks")
    op.drop_index("ix_tasks_target_status_created", table_name="tasks")
    op.create_index(
        "ix_tasks_target_status_created",
        "tasks",
        ["target_device_id", "status", "created_at"],
    )
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.drop_column("tasks", "runtime_events_purged_at")
