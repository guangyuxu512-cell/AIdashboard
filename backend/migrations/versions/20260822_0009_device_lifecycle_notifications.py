"""add Device lifecycle and notification channels

Revision ID: 20260822_0009
Revises: 20260822_0008
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260822_0009"
down_revision: str | None = "20260822_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_devices_deleted_at", "devices", ["deleted_at"])

    op.add_column(
        "device_runtime",
        sa.Column("connection_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "device_runtime",
        sa.Column("offline_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE device_runtime
        SET connection_status = CASE
                WHEN last_seen_at >= now() - interval '45 seconds' THEN 'online'
                ELSE 'offline'
            END,
            offline_since = CASE
                WHEN last_seen_at < now() - interval '45 seconds'
                    THEN last_seen_at + interval '45 seconds'
                ELSE NULL
            END
        """,
    )
    op.alter_column("device_runtime", "connection_status", nullable=False)
    op.create_check_constraint(
        "ck_device_runtime_connection_status",
        "device_runtime",
        "connection_status IN ('online', 'offline')",
    )

    op.create_table(
        "notification_channels",
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("channel_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("webhook_url_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column(
            "device_offline_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "device_recovered_enabled",
            sa.Boolean(),
            server_default=sa.true(),
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
            "channel_type IN ('feishu_webhook', 'wecom_webhook')",
            name="ck_notification_channels_channel_type",
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_notification_channels_name_not_blank",
        ),
        sa.PrimaryKeyConstraint("channel_id", name="pk_notification_channels"),
    )


def downgrade() -> None:
    op.drop_table("notification_channels")
    op.drop_constraint(
        "ck_device_runtime_connection_status",
        "device_runtime",
        type_="check",
    )
    op.drop_column("device_runtime", "offline_since")
    op.drop_column("device_runtime", "connection_status")
    op.drop_index("ix_devices_deleted_at", table_name="devices")
    op.drop_column("devices", "deleted_at")
