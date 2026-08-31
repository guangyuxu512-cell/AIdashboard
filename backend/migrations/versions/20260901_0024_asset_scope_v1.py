"""add team ownership and creator scope to assets

Revision ID: 20260901_0024
Revises: 20260831_0023
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260901_0024"
down_revision: str | None = "20260831_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TEAM_NAME = "默认团队"


def _backfill_asset_team() -> None:
    """历史系统是单组织共享环境，只能回填唯一的正式默认团队。"""

    connection = op.get_bind()
    teams = sa.table(
        "teams",
        sa.column("team_id", sa.Uuid()),
        sa.column("name", sa.String()),
    )
    assets = sa.table(
        "assets",
        sa.column("asset_id", sa.Uuid()),
        sa.column("team_id", sa.Uuid()),
    )
    default_team_ids = (
        connection.execute(
            sa.select(teams.c.team_id).where(teams.c.name == DEFAULT_TEAM_NAME),
        )
        .scalars()
        .all()
    )
    if len(default_team_ids) != 1:
        raise RuntimeError("Asset Scope迁移要求唯一的默认团队")

    connection.execute(
        assets.update()
        .where(assets.c.team_id.is_(None))
        .values(team_id=default_team_ids[0]),
    )
    remaining = connection.scalar(
        sa.select(sa.func.count())
        .select_from(assets)
        .where(assets.c.team_id.is_(None)),
    )
    if remaining:
        raise RuntimeError("Asset Scope历史数据回填不完整")


def upgrade() -> None:
    op.add_column("assets", sa.Column("team_id", sa.Uuid(), nullable=True))
    op.add_column(
        "assets",
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
    )
    _backfill_asset_team()
    op.alter_column(
        "assets",
        "team_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_assets_team_id_teams",
        "assets",
        "teams",
        ["team_id"],
        ["team_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_assets_created_by_user_id_users",
        "assets",
        "users",
        ["created_by_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_assets_team_created_asset",
        "assets",
        ["team_id", "created_at", "asset_id"],
        unique=False,
    )
    op.create_index(
        "ix_assets_team_creator_created_asset",
        "assets",
        ["team_id", "created_by_user_id", "created_at", "asset_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assets_team_creator_created_asset", table_name="assets")
    op.drop_index("ix_assets_team_created_asset", table_name="assets")
    op.drop_constraint(
        "fk_assets_created_by_user_id_users",
        "assets",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_assets_team_id_teams",
        "assets",
        type_="foreignkey",
    )
    op.drop_column("assets", "created_by_user_id")
    op.drop_column("assets", "team_id")
