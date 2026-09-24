"""persist verified Compass refund-order observations.

Revision ID: 20260924_0040
Revises: 20260922_0039
Create Date: 2026-09-24

`refund_order_cnt` is verified as Compass “退款订单数（退款时间）”, in
orders.  It is an optional observation relative to the established turnover
and paid-order facts.  The narrow status column lets pre-existing rows receive
one bounded backfill and records unavailable/not-ready/malformed responses
without turning them into zero or an endless automatic retry.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260924_0040"
down_revision: str | None = "20260922_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shop_operating_daily_metrics",
        sa.Column("refund_order_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "shop_operating_daily_metrics",
        sa.Column(
            "refund_order_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'unobserved'"),
        ),
    )
    op.create_check_constraint(
        "refund_orders_non_negative",
        "shop_operating_daily_metrics",
        "refund_order_count IS NULL OR refund_order_count >= 0",
    )
    op.create_check_constraint(
        "refund_order_status_valid",
        "shop_operating_daily_metrics",
        "refund_order_status IN ('unobserved', 'available', 'unavailable', 'not_ready', 'invalid')",
    )


def downgrade() -> None:
    # Core 0039 facts remain intact.  Only the separately added refund value
    # and observation state are removed, so this is valid solely for the
    # explicitly rebuildable Feature/Integration validation databases.
    op.drop_constraint(
        "refund_order_status_valid",
        "shop_operating_daily_metrics",
        type_="check",
    )
    op.drop_constraint(
        "refund_orders_non_negative",
        "shop_operating_daily_metrics",
        type_="check",
    )
    op.drop_column("shop_operating_daily_metrics", "refund_order_status")
    op.drop_column("shop_operating_daily_metrics", "refund_order_count")
