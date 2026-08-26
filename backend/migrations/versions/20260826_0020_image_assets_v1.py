"""add image assets and ordered task asset relation

Revision ID: 20260826_0020
Revises: 20260826_0019
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260826_0020"
down_revision: str | None = "20260826_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes > 0", name="positive_size"),
        sa.CheckConstraint("length(sha256) = 64", name="sha256_length"),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="supported_content_type",
        ),
        sa.PrimaryKeyConstraint("asset_id", name="pk_assets"),
        sa.UniqueConstraint("storage_key", name="uq_assets_storage_key"),
    )
    op.create_index(
        "ix_assets_created_asset",
        "assets",
        ["created_at", "asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_assets_original_filename",
        "assets",
        ["original_filename"],
        unique=False,
    )
    op.create_table(
        "task_assets",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 0", name="position_non_negative"),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.asset_id"],
            name="fk_task_assets_asset_id_assets",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name="fk_task_assets_task_id_tasks",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("task_id", "asset_id", name="pk_task_assets"),
        sa.UniqueConstraint(
            "task_id",
            "position",
            name="uq_task_assets_task_position",
        ),
    )
    op.create_index(
        "ix_task_assets_asset_task",
        "task_assets",
        ["asset_id", "task_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_task_assets_asset_task", table_name="task_assets")
    op.drop_table("task_assets")
    op.drop_index("ix_assets_original_filename", table_name="assets")
    op.drop_index("ix_assets_created_asset", table_name="assets")
    op.drop_table("assets")
