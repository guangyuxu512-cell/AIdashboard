"""add Shop soft-delete state

Revision ID: 20260822_0008
Revises: 20260821_0007
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_0008"
down_revision: str | None = "20260821_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_shops_deleted_at", "shops", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_shops_deleted_at", table_name="shops")
    op.drop_column("shops", "deleted_at")
