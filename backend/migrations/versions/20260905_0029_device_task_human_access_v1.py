"""add ownership to devices schedules and tasks

Revision ID: 20260905_0029
Revises: 20260904_0028
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260905_0029"
down_revision: str | None = "20260904_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED_TABLES = ("devices", "schedules", "tasks")


def _backfill_single_team() -> None:
    """Assign legacy records only when exactly one Team is present."""

    connection = op.get_bind()
    teams = sa.table("teams", sa.column("team_id", sa.Uuid()))
    team_ids = connection.execute(sa.select(teams.c.team_id)).scalars().all()
    if len(team_ids) != 1:
        raise RuntimeError("0029迁移要求历史环境恰有一个Team")

    for table_name in OWNED_TABLES:
        table = sa.table(
            table_name,
            sa.column("team_id", sa.Uuid()),
        )
        connection.execute(
            table.update()
            .where(table.c.team_id.is_(None))
            .values(team_id=team_ids[0]),
        )
        remaining = connection.scalar(
            sa.select(sa.func.count())
            .select_from(table)
            .where(table.c.team_id.is_(None)),
        )
        if remaining:
            raise RuntimeError(f"0029迁移未完成{table_name}的Team回填")


def _add_ownership_columns(table_name: str) -> None:
    op.add_column(table_name, sa.Column("team_id", sa.Uuid(), nullable=True))
    op.add_column(
        table_name,
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
    )


def _add_ownership_constraints_and_indexes(
    table_name: str,
    primary_key: str,
) -> None:
    op.alter_column(
        table_name,
        "team_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_foreign_key(
        f"fk_{table_name}_team_id_teams",
        table_name,
        "teams",
        ["team_id"],
        ["team_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        f"fk_{table_name}_created_by_user_id_users",
        table_name,
        "users",
        ["created_by_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )
    singular = table_name.removesuffix("s")
    op.create_index(
        f"ix_{table_name}_team_created_{singular}",
        table_name,
        ["team_id", "created_at", primary_key],
        unique=False,
    )
    op.create_index(
        f"ix_{table_name}_team_creator_created_{singular}",
        table_name,
        ["team_id", "created_by_user_id", "created_at", primary_key],
        unique=False,
    )


def upgrade() -> None:
    for table_name in OWNED_TABLES:
        _add_ownership_columns(table_name)
    _backfill_single_team()
    _add_ownership_constraints_and_indexes("devices", "device_id")
    _add_ownership_constraints_and_indexes("schedules", "schedule_id")
    _add_ownership_constraints_and_indexes("tasks", "task_id")


def downgrade() -> None:
    for table_name, primary_key in reversed(
        (
            ("devices", "device_id"),
            ("schedules", "schedule_id"),
            ("tasks", "task_id"),
        ),
    ):
        singular = table_name.removesuffix("s")
        op.drop_index(
            f"ix_{table_name}_team_creator_created_{singular}",
            table_name=table_name,
        )
        op.drop_index(
            f"ix_{table_name}_team_created_{singular}",
            table_name=table_name,
        )
        op.drop_constraint(
            f"fk_{table_name}_created_by_user_id_users",
            table_name,
            type_="foreignkey",
        )
        op.drop_constraint(
            f"fk_{table_name}_team_id_teams",
            table_name,
            type_="foreignkey",
        )
        op.drop_column(table_name, "created_by_user_id")
        op.drop_column(table_name, "team_id")
