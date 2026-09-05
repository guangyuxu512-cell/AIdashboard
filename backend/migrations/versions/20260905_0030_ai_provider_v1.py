"""add AI provider V1 execution reference

Revision ID: 20260905_0030
Revises: 20260905_0029
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260905_0030"
down_revision: str | None = "20260905_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "generation_provider_executions",
        sa.Column("generation_item_id", sa.Uuid(), nullable=False),
        sa.Column("provider_code", sa.String(length=32), nullable=False),
        sa.Column("external_task_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
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
            "provider_code = 'toapis'",
            name="provider_code",
        ),
        sa.CheckConstraint(
            "external_task_id IS NULL OR length(trim(external_task_id)) > 0",
            name="external_task_id_not_blank",
        ),
        sa.CheckConstraint(
            "attempt_count > 0",
            name="attempt_count_positive",
        ),
        sa.ForeignKeyConstraint(
            ["generation_item_id"],
            ["generation_items.generation_item_id"],
            name="fk_generation_provider_executions_generation_item",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "generation_item_id",
            name="pk_generation_provider_executions",
        ),
        sa.UniqueConstraint(
            "provider_code",
            "external_task_id",
            name="uq_generation_provider_executions_provider_task",
        ),
    )


def downgrade() -> None:
    op.drop_table("generation_provider_executions")
