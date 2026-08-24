"""add business skill input contracts and dynamic task skill ids

Revision ID: 20260825_0017
Revises: 20260824_0016
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260825_0017"
down_revision: str | None = "20260824_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_STABLE_SKILL_ID_CHECK = (
    "skill_id ~ '^[a-z][a-z0-9_]*(\\.[a-z][a-z0-9_]*)+$'"
)
_INTERNAL_SKILL_ID_CHECK = (
    "skill_id IN ('system.echo', 'system.sleep', 'yingdao.test', "
    "'yingdao.discover', 'yingdao.app.run')"
)


def upgrade() -> None:
    op.add_column(
        "device_skill_capabilities",
        sa.Column(
            "input_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_device_skill_capabilities_input_schema_object",
        "device_skill_capabilities",
        "input_schema IS NULL OR jsonb_typeof(input_schema) = 'object'",
    )

    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.alter_column(
        "tasks",
        "skill_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        _STABLE_SKILL_ID_CHECK,
    )

    op.drop_constraint("ck_schedules_skill_id", "schedules", type_="check")
    op.alter_column(
        "schedules",
        "skill_id",
        existing_type=sa.String(length=64),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_schedules_skill_id",
        "schedules",
        _STABLE_SKILL_ID_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint("ck_schedules_skill_id", "schedules", type_="check")
    op.create_check_constraint(
        "ck_schedules_skill_id",
        "schedules",
        _INTERNAL_SKILL_ID_CHECK,
    )
    op.alter_column(
        "schedules",
        "skill_id",
        existing_type=sa.String(length=200),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.drop_constraint("ck_tasks_skill_id", "tasks", type_="check")
    op.create_check_constraint(
        "ck_tasks_skill_id",
        "tasks",
        _INTERNAL_SKILL_ID_CHECK,
    )
    op.alter_column(
        "tasks",
        "skill_id",
        existing_type=sa.String(length=200),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.drop_constraint(
        "ck_device_skill_capabilities_input_schema_object",
        "device_skill_capabilities",
        type_="check",
    )
    op.drop_column("device_skill_capabilities", "input_schema")
