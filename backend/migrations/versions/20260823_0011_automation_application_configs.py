"""add automation application configs and generic Yingdao app skill

Revision ID: 20260823_0011
Revises: 20260822_0010
Create Date: 2026-08-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260823_0011"
down_revision: str | None = "20260822_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_application_configs",
        sa.Column("config_id", sa.Uuid(), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("app_id", sa.String(length=200), nullable=False),
        sa.Column("schema_source", sa.String(length=16), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("default_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(provider_code)) > 0", name="ck_automation_application_configs_provider_code_not_blank"),
        sa.CheckConstraint("length(trim(app_id)) > 0", name="ck_automation_application_configs_app_id_not_blank"),
        sa.CheckConstraint("schema_source IN ('manual', 'provider')", name="ck_automation_application_configs_schema_source"),
        sa.CheckConstraint("jsonb_typeof(input_schema) = 'object'", name="ck_automation_application_configs_input_schema_object"),
        sa.CheckConstraint("jsonb_typeof(default_values) = 'object'", name="ck_automation_application_configs_default_values_object"),
        sa.CheckConstraint("version > 0", name="ck_automation_application_configs_positive_version"),
        sa.PrimaryKeyConstraint("config_id", name="pk_automation_application_configs"),
        sa.UniqueConstraint("provider_code", "app_id", name="uq_automation_app_provider_app"),
    )
    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        "skill_id IN ('system.echo', 'system.sleep', 'yingdao.test', "
        "'yingdao.discover', 'yingdao.app.run')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        "skill_id IN ('system.echo', 'system.sleep', 'yingdao.test', 'yingdao.discover')",
    )
    op.drop_table("automation_application_configs")
