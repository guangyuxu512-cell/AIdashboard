"""add task runtime events

Revision ID: 20260822_0010
Revises: 20260822_0009
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260822_0010"
down_revision: str | None = "20260822_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('status', 'log', 'progress', 'completed', 'failed')",
            name="ck_task_events_event_type",
        ),
        sa.CheckConstraint("seq > 0", name="ck_task_events_positive_seq"),
        sa.CheckConstraint(
            "jsonb_typeof(metadata_json) = 'object'",
            name="ck_task_events_metadata_object",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name="fk_task_events_task_id_tasks",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_task_events"),
        sa.UniqueConstraint(
            "task_id",
            "seq",
            name="uq_task_events_task_seq",
        ),
    )
    op.create_index(
        "ix_task_events_task_seq",
        "task_events",
        ["task_id", "seq"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_events_task_seq", table_name="task_events")
    op.drop_table("task_events")
