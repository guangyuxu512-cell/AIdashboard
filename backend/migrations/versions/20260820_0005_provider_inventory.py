"""add provider inventory and Yingdao discovery skill

Revision ID: 20260820_0005
Revises: 20260820_0004
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260820_0005"
down_revision: str | None = "20260820_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_provider_inventory",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column("provider_version", sa.String(length=64), nullable=True),
        sa.Column("account_display", sa.String(length=200), nullable=True),
        sa.Column("account_type", sa.String(length=64), nullable=True),
        sa.Column("enterprise_account", sa.Boolean(), nullable=True),
        sa.Column(
            "last_discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "inventory_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
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
            "jsonb_typeof(inventory_payload) = 'object'",
            name="ck_device_provider_inventory_inventory_payload_object",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_device_provider_inventory_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "device_id",
            "provider_code",
            name="pk_device_provider_inventory",
        ),
    )
    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        "skill_id IN ('system.echo', 'system.sleep', 'yingdao.test', "
        "'yingdao.discover')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        "skill_id IN ('system.echo', 'system.sleep', 'yingdao.test')",
    )
    op.drop_table("device_provider_inventory")
