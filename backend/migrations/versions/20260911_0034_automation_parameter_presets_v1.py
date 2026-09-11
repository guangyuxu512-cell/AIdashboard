"""add automation parameter presets

Revision ID: 20260911_0034
Revises: 20260911_0033
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260911_0034"
down_revision: str | None = "20260911_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_parameter_presets",
        sa.Column("preset_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("app_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "common_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "shop_overrides",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
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
            "length(trim(name)) > 0",
            name=op.f("ck_automation_parameter_presets_name_not_blank"),
        ),
        sa.CheckConstraint(
            "length(trim(app_id)) > 0",
            name=op.f("ck_automation_parameter_presets_app_id_not_blank"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(common_parameters) = 'object'",
            name=op.f("ck_automation_parameter_presets_common_parameters_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(shop_overrides) = 'object'",
            name=op.f("ck_automation_parameter_presets_shop_overrides_object"),
        ),
        sa.CheckConstraint(
            "version > 0",
            name=op.f("ck_automation_parameter_presets_positive_version"),
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_automation_parameter_presets_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.user_id"],
            name="fk_automation_parameter_presets_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("preset_id", name="pk_automation_parameter_presets"),
        sa.UniqueConstraint(
            "team_id",
            "app_id",
            "name",
            name="uq_automation_preset_team_app_name",
        ),
    )
    op.create_index(
        "ix_automation_preset_team_app_created",
        "automation_parameter_presets",
        ["team_id", "app_id", "created_at", "preset_id"],
        unique=False,
    )
    op.create_index(
        "ix_automation_preset_team_creator_created",
        "automation_parameter_presets",
        ["team_id", "created_by_user_id", "created_at", "preset_id"],
        unique=False,
    )
    op.add_column(
        "schedules",
        sa.Column("parameter_preset_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_schedules_parameter_preset_id_automation_parameter_presets",
        "schedules",
        "automation_parameter_presets",
        ["parameter_preset_id"],
        ["preset_id"],
        ondelete="RESTRICT",
    )
    op.add_column("tasks", sa.Column("parameter_preset_id", sa.Uuid(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("parameter_preset_version", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_tasks_parameter_preset_id_automation_parameter_presets",
        "tasks",
        "automation_parameter_presets",
        ["parameter_preset_id"],
        ["preset_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_tasks_parameter_preset_snapshot",
        "tasks",
        "(parameter_preset_id IS NULL AND parameter_preset_version IS NULL) OR "
        "(parameter_preset_id IS NOT NULL AND parameter_preset_version > 0)",
    )


def downgrade() -> None:
    connection = op.get_bind()
    linked_task_count = connection.scalar(
        sa.text("SELECT count(*) FROM tasks WHERE parameter_preset_id IS NOT NULL"),
    )
    if linked_task_count:
        raise RuntimeError(
            "Cannot downgrade automation parameter presets while tasks reference a preset",
        )
    linked_schedule_count = connection.scalar(
        sa.text(
            "SELECT count(*) FROM schedules WHERE parameter_preset_id IS NOT NULL",
        ),
    )
    if linked_schedule_count:
        raise RuntimeError(
            "Cannot downgrade automation parameter presets while schedules reference a preset",
        )
    op.drop_constraint(
        "ck_tasks_parameter_preset_snapshot",
        "tasks",
        type_="check",
    )
    op.drop_constraint(
        "fk_tasks_parameter_preset_id_automation_parameter_presets",
        "tasks",
        type_="foreignkey",
    )
    op.drop_column("tasks", "parameter_preset_version")
    op.drop_column("tasks", "parameter_preset_id")
    op.drop_constraint(
        "fk_schedules_parameter_preset_id_automation_parameter_presets",
        "schedules",
        type_="foreignkey",
    )
    op.drop_column("schedules", "parameter_preset_id")
    op.drop_index(
        "ix_automation_preset_team_creator_created",
        table_name="automation_parameter_presets",
    )
    op.drop_index(
        "ix_automation_preset_team_app_created",
        table_name="automation_parameter_presets",
    )
    op.drop_table("automation_parameter_presets")
