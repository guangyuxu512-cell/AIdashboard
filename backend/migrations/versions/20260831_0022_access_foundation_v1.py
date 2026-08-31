"""add access foundation teams and memberships

Revision ID: 20260831_0022
Revises: 20260826_0021
Create Date: 2026-08-31
"""

from collections.abc import Iterable, Sequence
from uuid import UUID, uuid4

import sqlalchemy as sa
from alembic import op


revision: str = "20260831_0022"
down_revision: str | None = "20260826_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_TEAM_NAME = "默认团队"
DEFAULT_ROLE_CODE = "member"
DEFAULT_DATA_SCOPE = "team"


def _membership_rows(
    user_ids: Iterable[UUID],
    *,
    team_id: UUID,
) -> list[dict[str, object]]:
    return [
        {
            "membership_id": uuid4(),
            "team_id": team_id,
            "user_id": user_id,
            "role_code": DEFAULT_ROLE_CODE,
            "data_scope": DEFAULT_DATA_SCOPE,
            "enabled": True,
        }
        for user_id in user_ids
    ]


def _backfill_default_team() -> None:
    connection = op.get_bind()
    teams = sa.table(
        "teams",
        sa.column("team_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("enabled", sa.Boolean()),
    )
    users = sa.table("users", sa.column("user_id", sa.Uuid()))
    memberships = sa.table(
        "team_memberships",
        sa.column("membership_id", sa.Uuid()),
        sa.column("team_id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("role_code", sa.String()),
        sa.column("data_scope", sa.String()),
        sa.column("enabled", sa.Boolean()),
    )

    team_id = uuid4()
    connection.execute(
        teams.insert().values(
            team_id=team_id,
            name=DEFAULT_TEAM_NAME,
            enabled=True,
        ),
    )
    user_ids = connection.execute(sa.select(users.c.user_id)).scalars().all()
    rows = _membership_rows(user_ids, team_id=team_id)
    if rows:
        connection.execute(memberships.insert(), rows)


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
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
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.PrimaryKeyConstraint("team_id", name="pk_teams"),
    )
    op.create_table(
        "team_memberships",
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role_code",
            sa.String(length=64),
            server_default=sa.text("'member'"),
            nullable=False,
        ),
        sa.Column(
            "data_scope",
            sa.String(length=4),
            server_default=sa.text("'team'"),
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
            "length(trim(role_code)) > 0",
            name="role_code_not_blank",
        ),
        sa.CheckConstraint(
            "data_scope IN ('self', 'team', 'all')",
            name="data_scope",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_team_memberships_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_team_memberships_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "membership_id",
            name="pk_team_memberships",
        ),
        sa.UniqueConstraint(
            "team_id",
            "user_id",
            name="uq_team_memberships_team_user",
        ),
    )
    op.create_index(
        "ix_team_memberships_active_user",
        "team_memberships",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("enabled"),
    )
    op.create_index(
        "ix_team_memberships_active_team",
        "team_memberships",
        ["team_id"],
        unique=False,
        postgresql_where=sa.text("enabled"),
    )
    _backfill_default_team()


def downgrade() -> None:
    op.drop_index(
        "ix_team_memberships_active_team",
        table_name="team_memberships",
    )
    op.drop_index(
        "ix_team_memberships_active_user",
        table_name="team_memberships",
    )
    op.drop_table("team_memberships")
    op.drop_table("teams")
