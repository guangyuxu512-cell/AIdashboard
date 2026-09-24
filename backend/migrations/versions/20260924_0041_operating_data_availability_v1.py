"""record explicit operating-data coverage boundaries on shops.

Revision ID: 20260924_0041
Revises: 20260924_0040
Create Date: 2026-09-24

An operating start date is deliberately optional.  It is never inferred from
Control Center onboarding, first collected fact, or first order: only an
authorized manager may set it, and its source plus audit actor/time travel
with the Shop.  Collection and coverage use it only to exclude confirmed
pre-operation calendar dates; it does not alter or delete existing facts.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260924_0041"
down_revision: str | None = "20260924_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("operating_start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "shops",
        sa.Column("operating_start_date_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "shops",
        sa.Column("operating_start_date_set_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "shops",
        sa.Column(
            "operating_start_date_set_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_shops_operating_start_date_set_by_user",
        "shops",
        "users",
        ["operating_start_date_set_by_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "operating_start_date_audit_complete",
        "shops",
        "(operating_start_date IS NULL "
        "AND operating_start_date_source IS NULL "
        "AND operating_start_date_set_by_user_id IS NULL "
        "AND operating_start_date_set_at IS NULL) "
        "OR (operating_start_date IS NOT NULL "
        "AND operating_start_date_source IS NOT NULL "
        "AND operating_start_date_set_by_user_id IS NOT NULL "
        "AND operating_start_date_set_at IS NOT NULL)",
    )


def downgrade() -> None:
    # Existing facts and collection history are intentionally retained.  This
    # downgrade only removes the optional coverage-boundary metadata from a
    # rebuildable Feature/Integration database.
    op.drop_constraint(
        "operating_start_date_audit_complete",
        "shops",
        type_="check",
    )
    op.drop_constraint(
        "fk_shops_operating_start_date_set_by_user",
        "shops",
        type_="foreignkey",
    )
    op.drop_column("shops", "operating_start_date_set_at")
    op.drop_column("shops", "operating_start_date_set_by_user_id")
    op.drop_column("shops", "operating_start_date_source")
    op.drop_column("shops", "operating_start_date")
