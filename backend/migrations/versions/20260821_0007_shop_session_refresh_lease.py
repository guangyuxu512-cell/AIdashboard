"""add expiring ShopSession refresh lease

Revision ID: 20260821_0007
Revises: 20260821_0006
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260821_0007"
down_revision: str | None = "20260821_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shop_sessions",
        sa.Column("refresh_lease_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "shop_sessions",
        sa.Column(
            "refresh_lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_shop_sessions_refresh_lease_pair",
        "shop_sessions",
        "(refresh_lease_id IS NULL) = (refresh_lease_expires_at IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_shop_sessions_refresh_lease_pair",
        "shop_sessions",
        type_="check",
    )
    op.drop_column("shop_sessions", "refresh_lease_expires_at")
    op.drop_column("shop_sessions", "refresh_lease_id")
