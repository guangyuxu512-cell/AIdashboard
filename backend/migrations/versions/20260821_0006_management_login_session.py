"""add platform shop identity and captured session state

Revision ID: 20260821_0006
Revises: 20260820_0005
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260821_0006"
down_revision: str | None = "20260820_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("platform_shop_id", sa.String(length=128), nullable=True),
    )
    op.create_unique_constraint(
        "uq_shops_platform_identity",
        "shops",
        ["platform", "platform_shop_id"],
    )
    op.drop_constraint(
        "shop_session_status",
        "shop_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "shop_session_status",
        "shop_sessions",
        "status IN ('not_configured', 'captured', 'valid', 'invalid', 'refresh_required')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE shop_sessions SET status = 'refresh_required' WHERE status = 'captured'",
    )
    op.drop_constraint(
        "shop_session_status",
        "shop_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "shop_session_status",
        "shop_sessions",
        "status IN ('not_configured', 'valid', 'invalid', 'refresh_required')",
    )
    op.drop_constraint("uq_shops_platform_identity", "shops", type_="unique")
    op.drop_column("shops", "platform_shop_id")
