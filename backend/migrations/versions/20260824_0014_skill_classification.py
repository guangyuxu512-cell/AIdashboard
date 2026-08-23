"""classify device skill capabilities

Revision ID: 20260824_0014
Revises: 20260823_0013
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260824_0014"
down_revision: str | None = "20260823_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "device_skill_capabilities",
        sa.Column("classification", sa.String(length=16), nullable=True),
    )
    op.execute(
        """
        UPDATE device_skill_capabilities
        SET classification = 'internal'
        WHERE skill_id IN (
            'system.echo',
            'system.sleep',
            'yingdao.app.run',
            'yingdao.test',
            'yingdao.discover'
        )
        """,
    )
    op.create_check_constraint(
        "ck_device_skill_capabilities_classification",
        "device_skill_capabilities",
        "classification IS NULL OR classification IN ('internal', 'business')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_device_skill_capabilities_classification",
        "device_skill_capabilities",
        type_="check",
    )
    op.drop_column("device_skill_capabilities", "classification")
