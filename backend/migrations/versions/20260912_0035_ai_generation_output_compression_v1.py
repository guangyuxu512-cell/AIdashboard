"""add immutable generation output compression snapshot

Revision ID: 20260912_0035
Revises: 20260911_0034
Create Date: 2026-09-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260912_0035"
down_revision: str | None = "20260911_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column(
            "compress_output_under_1000kb",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("generation_jobs", "compress_output_under_1000kb")
