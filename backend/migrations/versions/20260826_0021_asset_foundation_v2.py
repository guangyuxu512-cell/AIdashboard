"""generalize assets with media and source semantics

Revision ID: 20260826_0021
Revises: 20260826_0020
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260826_0021"
down_revision: str | None = "20260826_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assets",
        sa.Column(
            "media_type",
            sa.String(length=16),
            server_default=sa.text("'image'"),
            nullable=False,
        ),
    )
    op.add_column(
        "assets",
        sa.Column(
            "source_type",
            sa.String(length=32),
            server_default=sa.text("'upload'"),
            nullable=False,
        ),
    )
    op.drop_constraint(
        op.f("ck_assets_supported_content_type"),
        "assets",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_assets_media_type"),
        "assets",
        "media_type IN ('image', 'video')",
    )
    op.create_check_constraint(
        op.f("ck_assets_source_type"),
        "assets",
        "source_type IN ('upload', 'ai_generated', 'imported')",
    )
    op.create_check_constraint(
        op.f("ck_assets_content_type_not_blank"),
        "assets",
        "length(trim(content_type)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_assets_content_type_not_blank"),
        "assets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_assets_source_type"),
        "assets",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_assets_media_type"),
        "assets",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_assets_supported_content_type"),
        "assets",
        "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
    )
    op.drop_column("assets", "source_type")
    op.drop_column("assets", "media_type")
