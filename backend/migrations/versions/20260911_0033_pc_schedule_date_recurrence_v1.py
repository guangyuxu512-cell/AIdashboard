"""add schedule date filter and recurrence rules

Revision ID: 20260911_0033
Revises: 20260906_0032
Create Date: 2026-09-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260911_0033"
down_revision: str | None = "20260906_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedules", sa.Column("local_date", sa.Date(), nullable=True))
    op.add_column(
        "schedules",
        sa.Column(
            "weekdays",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.drop_constraint("ck_schedules_schedule_type", "schedules", type_="check")
    op.create_check_constraint(
        "ck_schedules_schedule_type",
        "schedules",
        "schedule_type IN ('once', 'daily', 'weekly')",
    )
    op.create_check_constraint(
        "ck_schedules_weekdays_array",
        "schedules",
        "jsonb_typeof(weekdays) = 'array'",
    )
    op.create_check_constraint(
        "ck_schedules_rule_fields",
        "schedules",
        "(schedule_type = 'once' AND local_date IS NOT NULL "
        "AND jsonb_array_length(weekdays) = 0) OR "
        "(schedule_type = 'daily' AND local_date IS NULL "
        "AND jsonb_array_length(weekdays) = 0) OR "
        "(schedule_type = 'weekly' AND local_date IS NULL "
        "AND jsonb_array_length(weekdays) > 0)",
    )


def downgrade() -> None:
    non_daily_count = op.get_bind().execute(
        sa.text("SELECT count(*) FROM schedules WHERE schedule_type <> 'daily'"),
    ).scalar_one()
    if non_daily_count:
        raise RuntimeError(
            "Cannot downgrade schedule recurrence while once or weekly schedules exist",
        )
    op.drop_constraint("ck_schedules_rule_fields", "schedules", type_="check")
    op.drop_constraint("ck_schedules_weekdays_array", "schedules", type_="check")
    op.drop_constraint("ck_schedules_schedule_type", "schedules", type_="check")
    op.create_check_constraint(
        "ck_schedules_schedule_type",
        "schedules",
        "schedule_type IN ('daily')",
    )
    op.drop_column("schedules", "weekdays")
    op.drop_column("schedules", "local_date")
