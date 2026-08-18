"""allow the Yingdao adapter test skill

Revision ID: 20260820_0004
Revises: 20260819_0003
Create Date: 2026-08-20
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260820_0004"
down_revision: str | None = "20260819_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        "skill_id IN ('system.echo', 'system.sleep', 'yingdao.test')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        "skill_id IN ('system.echo', 'system.sleep')",
    )
