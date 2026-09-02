"""add human auth credentials and server sessions

Revision ID: 20260831_0023
Revises: 20260831_0022
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260831_0023"
down_revision: str | None = "20260831_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("login_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_login_name_normalized",
        "users",
        "login_name IS NULL OR (length(trim(login_name)) > 0 AND "
        "login_name = lower(trim(login_name)))",
    )
    op.create_unique_constraint(
        "uq_users_login_name",
        "users",
        ["login_name"],
    )
    op.create_table(
        "human_sessions",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(token_hash) = 64",
            name="ck_human_sessions_token_hash_length",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_human_sessions_expiry_after_creation",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
            name="fk_human_sessions_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("session_id", name="pk_human_sessions"),
    )
    op.create_index(
        "ix_human_sessions_token_hash",
        "human_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_human_sessions_user_id",
        "human_sessions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_human_sessions_user_id", table_name="human_sessions")
    op.drop_index("ix_human_sessions_token_hash", table_name="human_sessions")
    op.drop_table("human_sessions")
    op.drop_constraint("uq_users_login_name", "users", type_="unique")
    op.drop_constraint(
        "ck_users_login_name_normalized",
        "users",
        type_="check",
    )
    op.drop_column("users", "password_hash")
    op.drop_column("users", "login_name")
