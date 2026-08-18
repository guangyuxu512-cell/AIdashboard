"""create credential and session domain foundation

Revision ID: 20260819_0002
Revises: 20260818_0001
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260819_0002"
down_revision: str | None = "20260818_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_credentials",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("platform_code", sa.String(length=7), nullable=False),
        sa.Column("login_identifier", sa.String(length=320), nullable=False),
        sa.Column("secret_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "preferred_verification_channel",
            sa.String(length=12),
            server_default="manual",
            nullable=False,
        ),
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
            "platform_code IN ('douyin', 'pdd')",
            name="credential_platform_code",
        ),
        sa.CheckConstraint(
            "preferred_verification_channel IN ('manual', 'email', 'sms_hardware')",
            name="verification_channel",
        ),
        sa.CheckConstraint(
            "length(trim(login_identifier)) > 0",
            name="login_identifier_not_blank",
        ),
        sa.PrimaryKeyConstraint("credential_id", name="pk_platform_credentials"),
    )

    op.create_table(
        "shop_credential_bindings",
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["platform_credentials.credential_id"],
            name="fk_shop_credential_bindings_credential_id_platform_credentials",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_shop_credential_bindings_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "shop_id",
            "credential_id",
            name="pk_shop_credential_bindings",
        ),
    )
    op.create_index(
        "ix_shop_credential_bindings_credential_id",
        "shop_credential_bindings",
        ["credential_id"],
        unique=False,
    )
    op.create_index(
        "uq_shop_credential_bindings_enabled_shop",
        "shop_credential_bindings",
        ["shop_id"],
        unique=True,
        postgresql_where=sa.text("enabled"),
    )

    op.create_table(
        "shop_sessions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_device_id", sa.Uuid(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_encrypted", sa.LargeBinary(), nullable=False),
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
            "status IN ('not_configured', 'valid', 'invalid', 'refresh_required')",
            name="shop_session_status",
        ),
        sa.CheckConstraint("version > 0", name="version_positive"),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_shop_sessions_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_device_id"],
            ["devices.device_id"],
            name="fk_shop_sessions_source_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("session_id", name="pk_shop_sessions"),
        sa.UniqueConstraint("shop_id", name="uq_shop_sessions_shop_id"),
    )


def downgrade() -> None:
    op.drop_table("shop_sessions")
    op.drop_index(
        "uq_shop_credential_bindings_enabled_shop",
        table_name="shop_credential_bindings",
    )
    op.drop_index(
        "ix_shop_credential_bindings_credential_id",
        table_name="shop_credential_bindings",
    )
    op.drop_table("shop_credential_bindings")
    op.drop_table("platform_credentials")
