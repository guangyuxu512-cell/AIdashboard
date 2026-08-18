"""create core domain v1

Revision ID: 20260818_0001
Revises:
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260818_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
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
            "length(trim(display_name)) > 0",
            name="display_name_not_blank",
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_users"),
    )

    op.create_table(
        "devices",
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
            "length(trim(display_name)) > 0",
            name="display_name_not_blank",
        ),
        sa.PrimaryKeyConstraint("device_id", name="pk_devices"),
    )

    op.create_table(
        "shops",
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("platform", sa.String(length=7), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
            "length(trim(display_name)) > 0",
            name="display_name_not_blank",
        ),
        sa.CheckConstraint(
            "platform IN ('douyin', 'pdd')",
            name="shop_platform",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.user_id"],
            name="fk_shops_owner_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("shop_id", name="pk_shops"),
    )
    op.create_index("ix_shops_owner_user_id", "shops", ["owner_user_id"], unique=False)

    op.create_table(
        "shop_device_bindings",
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("binding_role", sa.String(length=7), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
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
            "binding_role IN ('primary', 'backup')",
            name="binding_role",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_shop_device_bindings_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_shop_device_bindings_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "shop_id",
            "device_id",
            name="pk_shop_device_bindings",
        ),
    )
    op.create_index(
        "uq_shop_device_bindings_enabled_primary",
        "shop_device_bindings",
        ["shop_id"],
        unique=True,
        postgresql_where=sa.text("enabled AND binding_role = 'primary'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_shop_device_bindings_enabled_primary",
        table_name="shop_device_bindings",
    )
    op.drop_table("shop_device_bindings")
    op.drop_index("ix_shops_owner_user_id", table_name="shops")
    op.drop_table("shops")
    op.drop_table("devices")
    op.drop_table("users")
