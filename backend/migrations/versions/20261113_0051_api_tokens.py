"""Add individually scoped management API tokens.

Revision ID: 20261113_0051
Revises: 20261110_0050
"""

from alembic import op
import sqlalchemy as sa

revision = "20261113_0051"
down_revision = "20261110_0050"
branch_labels = None
depends_on = None

FEATURE_DATABASE = "control_center_feat_ai_token_management"


def upgrade():
    op.create_table(
        "api_tokens",
        sa.Column("token_id", sa.Uuid(), primary_key=True),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("team_ids", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(token_hash) = 64", name="api_tokens_hash_length"),
        sa.CheckConstraint("length(trim(name)) > 0", name="api_tokens_name_not_blank"),
    )
    op.create_table(
        "api_token_events",
        sa.Column("event_id", sa.Uuid(), primary_key=True),
        sa.Column("token_id", sa.Uuid(), sa.ForeignKey("api_tokens.token_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('create', 'update', 'revoke')", name="api_token_events_action"),
    )
    op.create_index("ix_api_token_events_token_id", "api_token_events", ["token_id"])


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("0051 downgrade requires an online Feature target check")
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT current_database()")) != FEATURE_DATABASE:
        raise RuntimeError("0051 downgrade permits only the registered Feature database")
    connection.execute(sa.text("LOCK TABLE api_token_events, api_tokens IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM api_tokens LIMIT 1) OR EXISTS (SELECT 1 FROM api_token_events LIMIT 1)")):
        raise RuntimeError("0051 contains credentials; retain schema and audit records")
    op.drop_index("ix_api_token_events_token_id", table_name="api_token_events")
    op.drop_table("api_token_events")
    op.drop_table("api_tokens")
