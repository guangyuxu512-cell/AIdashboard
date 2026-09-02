"""add membership module access for access management v1

Revision ID: 20260902_0025
Revises: 20260901_0024
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260902_0025"
down_revision: str | None = "20260901_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# These are the current user-facing PC Module Registry codes. The development-
# only foundation module is intentionally excluded from employee access.
BACKFILL_MODULE_CODES = (
    "shop",
    "asset",
    "ai-workbench",
    "device",
    "task",
    "schedule",
    "settings",
)


def _backfill_existing_memberships() -> None:
    connection = op.get_bind()
    memberships = sa.table(
        "team_memberships",
        sa.column("membership_id", sa.Uuid()),
    )
    accesses = sa.table(
        "membership_module_accesses",
        sa.column("membership_id", sa.Uuid()),
        sa.column("module_code", sa.String()),
    )
    membership_ids = connection.execute(
        sa.select(memberships.c.membership_id),
    ).scalars()
    rows = [
        {"membership_id": membership_id, "module_code": module_code}
        for membership_id in membership_ids
        for module_code in BACKFILL_MODULE_CODES
    ]
    if rows:
        connection.execute(accesses.insert(), rows)


def upgrade() -> None:
    op.create_table(
        "membership_module_accesses",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"],
            ["team_memberships.membership_id"],
            name="fk_membership_module_accesses_membership_id_team_memberships",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "membership_id",
            "module_code",
            name="pk_membership_module_accesses",
        ),
    )
    _backfill_existing_memberships()


def downgrade() -> None:
    op.drop_table("membership_module_accesses")
