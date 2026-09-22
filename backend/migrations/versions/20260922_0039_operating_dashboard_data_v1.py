"""persist verified Douyin operating metrics and durable collection progress.

Revision ID: 20260922_0039
Revises: 20260920_0038
Create Date: 2026-09-22

Only the Compass fields with a frozen response path are persisted. Refund
amount/order fields do not establish a return-piece metric, and the merchant
experience endpoint is unverified, so neither has a column in this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260922_0039"
down_revision: str | None = "20260920_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "shop_operating_daily_metrics",
        sa.Column("metric_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("metric_contract", sa.String(length=64), nullable=False),
        sa.Column("turnover_cents", sa.Integer(), nullable=True),
        sa.Column("order_count", sa.Integer(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("length(trim(source_code)) > 0", name="source_not_blank"),
        sa.CheckConstraint("length(trim(metric_contract)) > 0", name="contract_not_blank"),
        sa.CheckConstraint(
            "turnover_cents IS NULL OR turnover_cents >= 0",
            name="turnover_non_negative",
        ),
        sa.CheckConstraint(
            "order_count IS NULL OR order_count >= 0",
            name="orders_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_shop_operating_daily_metrics_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("metric_id"),
        sa.UniqueConstraint("shop_id", "business_date", name="uq_operating_metric_shop_date"),
    )
    op.create_index(
        "ix_operating_metric_shop_date",
        "shop_operating_daily_metrics",
        ["shop_id", "business_date"],
        unique=False,
    )
    op.create_index(
        "ix_operating_metric_date",
        "shop_operating_daily_metrics",
        ["business_date"],
        unique=False,
    )

    op.create_table(
        "operating_data_collection_jobs",
        sa.Column("collection_job_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_start_date", sa.Date(), nullable=False),
        sa.Column("requested_end_date", sa.Date(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("requested_team_id", sa.Uuid(), nullable=True),
        sa.Column("dedupe_key", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('initial_backfill', 'reenable_backfill', 'manual_refresh', 'daily', 'retry')",
            name="kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'partial_failed', 'failed')",
            name="status",
        ),
        sa.CheckConstraint("requested_start_date <= requested_end_date", name="date_range"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.user_id"],
            name="fk_operating_data_collection_jobs_requested_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_team_id"],
            ["teams.team_id"],
            name="fk_operating_data_collection_jobs_requested_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("collection_job_id"),
        sa.UniqueConstraint("dedupe_key", name="uq_operating_collection_job_dedupe_key"),
    )
    op.create_index(
        "ix_operating_collection_job_created",
        "operating_data_collection_jobs",
        ["created_at", "collection_job_id"],
        unique=False,
    )

    op.create_table(
        "operating_data_collection_items",
        sa.Column("collection_item_id", sa.Uuid(), nullable=False),
        sa.Column("collection_job_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=96), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("failure_stage", sa.String(length=32), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queue_wait_ms", sa.Integer(), nullable=True),
        sa.Column("session_preparation_ms", sa.Integer(), nullable=True),
        sa.Column("signature_ms", sa.Integer(), nullable=True),
        sa.Column("platform_response_ms", sa.Integer(), nullable=True),
        sa.Column("response_parse_ms", sa.Integer(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'paused_reauthorization')",
            name="status",
        ),
        sa.CheckConstraint(
            "failure_stage IS NULL OR failure_stage IN ('queued', 'session_preparation', 'signing', 'platform_response', 'response_parse', 'session_persistence', 'execution')",
            name="failure_stage",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="attempt_non_negative"),
        sa.CheckConstraint(
            "queue_wait_ms IS NULL OR queue_wait_ms >= 0",
            name="queue_wait_non_negative",
        ),
        sa.CheckConstraint(
            "session_preparation_ms IS NULL OR session_preparation_ms >= 0",
            name="session_ms_non_negative",
        ),
        sa.CheckConstraint(
            "signature_ms IS NULL OR signature_ms >= 0",
            name="signature_non_negative",
        ),
        sa.CheckConstraint(
            "platform_response_ms IS NULL OR platform_response_ms >= 0",
            name="platform_ms_non_negative",
        ),
        sa.CheckConstraint(
            "response_parse_ms IS NULL OR response_parse_ms >= 0",
            name="response_parse_non_negative",
        ),
        sa.CheckConstraint("total_ms IS NULL OR total_ms >= 0", name="total_non_negative"),
        sa.ForeignKeyConstraint(
            ["collection_job_id"],
            ["operating_data_collection_jobs.collection_job_id"],
            name="fk_operating_collection_items_job",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_operating_collection_items_shop",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("collection_item_id"),
        sa.UniqueConstraint(
            "collection_job_id",
            "shop_id",
            "business_date",
            name="uq_operating_collection_item_job_shop_date",
        ),
    )
    op.create_index(
        "uq_operating_collection_active_shop_date",
        "operating_data_collection_items",
        ["shop_id", "business_date"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'running', 'paused_reauthorization')",
        ),
    )
    op.create_index(
        "uq_operating_collection_running_shop",
        "operating_data_collection_items",
        ["shop_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "ix_operating_collection_item_claim",
        "operating_data_collection_items",
        ["status", "retry_after", "priority", "created_at", "collection_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_operating_collection_item_job",
        "operating_data_collection_items",
        ["collection_job_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_operating_collection_item_shop_date",
        "operating_data_collection_items",
        ["shop_id", "business_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("operating_data_collection_items")
    op.drop_table("operating_data_collection_jobs")
    op.drop_table("shop_operating_daily_metrics")
