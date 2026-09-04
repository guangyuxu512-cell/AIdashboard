"""add logging audit V1

Revision ID: 20260904_0028
Revises: 20260903_0027
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260904_0028"
down_revision: str | None = "20260903_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("audit_log_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(trim(request_id)) > 0",
            name="request_id_not_blank",
        ),
        sa.CheckConstraint("length(trim(action)) > 0", name="action_not_blank"),
        sa.CheckConstraint(
            "length(trim(target_type)) > 0",
            name="target_type_not_blank",
        ),
        sa.CheckConstraint(
            "details IS NULL OR jsonb_typeof(details) = 'object'",
            name="details_object",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.user_id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_audit_logs_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("audit_log_id", name="pk_audit_logs"),
    )
    op.create_index(
        "ix_audit_logs_created_log",
        "audit_logs",
        ["created_at", "audit_log_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_actor_created_log",
        "audit_logs",
        ["actor_user_id", "created_at", "audit_log_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_action_created_log",
        "audit_logs",
        ["action", "created_at", "audit_log_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action_created_log", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_created_log", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_log", table_name="audit_logs")
    op.drop_table("audit_logs")
