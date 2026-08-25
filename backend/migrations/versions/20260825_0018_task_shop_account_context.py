"""add explicit shop context to tasks and schedules

Revision ID: 20260825_0018
Revises: 20260825_0017
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260825_0018"
down_revision: str | None = "20260825_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("shop_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_shop_id_shops",
        "tasks",
        "shops",
        ["shop_id"],
        ["shop_id"],
        ondelete="RESTRICT",
    )
    op.add_column("schedules", sa.Column("shop_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_schedules_shop_id_shops",
        "schedules",
        "shops",
        ["shop_id"],
        ["shop_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_schedules_shop_id_shops",
        "schedules",
        type_="foreignkey",
    )
    op.drop_column("schedules", "shop_id")
    op.drop_constraint(
        "fk_tasks_shop_id_shops",
        "tasks",
        type_="foreignkey",
    )
    op.drop_column("tasks", "shop_id")
