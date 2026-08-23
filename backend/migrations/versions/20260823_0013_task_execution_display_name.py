"""snapshot task execution display names

Revision ID: 20260823_0013
Revises: 20260823_0012
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260823_0013"
down_revision: str | None = "20260823_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("execution_display_name", sa.String(length=500), nullable=True),
    )
    op.execute("UPDATE tasks SET execution_display_name = skill_id")
    op.alter_column("tasks", "execution_display_name", nullable=False)


def downgrade() -> None:
    op.drop_column("tasks", "execution_display_name")
