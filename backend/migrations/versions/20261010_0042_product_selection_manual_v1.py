"""persist Team-owned selection candidates and source-scoped observations.

Revision ID: 20261010_0042
Revises: 20260924_0041
Create Date: 2026-10-10

No sessions, mock candidates or existing business facts are copied. Downgrade
deletes these new facts and is only for an explicitly rebuildable test DB;
an application rollback with real data must retain this schema.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261010_0042"
down_revision: str | None = "20260924_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "product_selection_candidates",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("platform_product_id", sa.String(128), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("candidate_id", name=op.f("pk_product_selection_candidates")),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("platform = 'douyin'", name="platform"),
        sa.CheckConstraint("length(trim(platform_product_id)) > 0", name="product_id_not_blank"),
        sa.UniqueConstraint(
            "team_id", "platform", "platform_product_id",
            name="uq_selection_candidate_team_product",
        ),
    )
    op.create_index("ix_selection_candidate_team_id", "product_selection_candidates", ["team_id", "candidate_id"])
    op.create_table(
        "product_selection_observations",
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("request_shop_id", sa.Uuid(), nullable=False),
        sa.Column("source_scope_hash", sa.String(64), nullable=False),
        sa.Column("source_context", postgresql.JSONB(), nullable=False),
        sa.Column("period_begin", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("image_url", sa.Text()),
        sa.Column("source_url", sa.Text()),
        sa.Column("merchant_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("category_path", postgresql.JSONB()),
        sa.Column("price_band", sa.String(200)),
        sa.Column("rank", sa.Integer()),
        sa.Column("previous_rank", sa.Integer()),
        sa.Column("previous_checked_at", sa.DateTime(timezone=True)),
        sa.Column("newly_on_ranking", sa.Boolean()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics_retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("video_metric_ranges", postgresql.JSONB(), nullable=False),
        sa.Column("first_on_shelf_date", sa.Date()),
        sa.Column("bad_comment_rate_raw", sa.Numeric()),
        sa.Column("bad_comment_rate_unit", postgresql.JSONB()),
        sa.Column("basic_info_retrieved_at", sa.DateTime(timezone=True)),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_successful_request_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error_code", sa.String(96)),
        sa.Column("last_error_stage", sa.String(32)),
        *_timestamps(),
        sa.PrimaryKeyConstraint("observation_id", name=op.f("pk_product_selection_observations")),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["product_selection_candidates.candidate_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["request_shop_id"], ["shops.shop_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("period_begin <= period_end", name="period_order"),
        sa.CheckConstraint("source_scope_hash ~ '^[a-f0-9]{64}$'", name="source_hash"),
        sa.CheckConstraint("jsonb_typeof(source_context) = 'object'", name="source_object"),
        sa.CheckConstraint("jsonb_typeof(merchant_snapshot) = 'array'", name="merchants_array"),
        sa.CheckConstraint(
            "category_path IS NULL OR jsonb_typeof(category_path) = 'array'",
            name="category_array",
        ),
        sa.CheckConstraint("jsonb_typeof(video_metric_ranges) = 'object'", name="metrics_object"),
        sa.CheckConstraint("rank IS NULL OR rank >= 0", name="rank_non_negative"),
        sa.CheckConstraint("previous_rank IS NULL OR previous_rank >= 0", name="previous_rank_non_negative"),
        sa.CheckConstraint("bad_comment_rate_raw IS NULL OR bad_comment_rate_raw >= 0", name="rate_non_negative"),
        sa.CheckConstraint(
            "bad_comment_rate_unit IS NULL OR "
            "jsonb_typeof(bad_comment_rate_unit) IN ('string', 'number', 'null')",
            name="rate_unit_scalar",
        ),
        sa.UniqueConstraint(
            "candidate_id", "request_shop_id", "source_scope_hash",
            name="uq_selection_observation_source",
        ),
    )
    op.create_index(
        "ix_selection_observation_shop_checked", "product_selection_observations",
        ["request_shop_id", "checked_at", "observation_id"],
    )
    op.create_index(
        "ix_selection_observation_candidate_checked", "product_selection_observations",
        ["candidate_id", "checked_at", "observation_id"],
    )


def downgrade() -> None:
    # Explicitly destructive for the new selection facts, never a recovery
    # procedure for shared/production data. Existing domain tables are kept.
    op.drop_index("ix_selection_observation_candidate_checked", table_name="product_selection_observations")
    op.drop_index("ix_selection_observation_shop_checked", table_name="product_selection_observations")
    op.drop_table("product_selection_observations")
    op.drop_index("ix_selection_candidate_team_id", table_name="product_selection_candidates")
    op.drop_table("product_selection_candidates")
