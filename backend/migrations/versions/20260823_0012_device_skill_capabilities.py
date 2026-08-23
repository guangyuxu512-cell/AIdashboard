"""add device skill capability snapshots

Revision ID: 20260823_0012
Revises: 20260823_0011
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260823_0012"
down_revision: str | None = "20260823_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_skill_capabilities",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.String(length=200), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("runtime", sa.String(length=32), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=True),
        sa.Column("skill_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "runtime IN ('python', 'rpa', 'discovery')",
            name="ck_device_skill_capabilities_runtime",
        ),
        sa.CheckConstraint(
            "length(trim(skill_id)) > 0",
            name="ck_device_skill_capabilities_skill_id_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(display_name)) > 0",
            name="ck_device_skill_capabilities_display_name_not_blank",
        ),
        sa.CheckConstraint(
            "length(trim(skill_version)) > 0",
            name="ck_device_skill_capabilities_skill_version_not_blank",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_device_skill_capabilities_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "device_id",
            "skill_id",
            name="pk_device_skill_capabilities",
        ),
    )


def downgrade() -> None:
    op.drop_table("device_skill_capabilities")
