from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, Uuid, text,
    false as sa_false,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class ProductSelectionStrategy(TimestampMixin, Base):
    __tablename__ = "product_selection_strategies"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("jsonb_typeof(conditions) = 'object'", name="conditions_object"),
        CheckConstraint("jsonb_typeof(schedule_config) = 'object'", name="schedule_object"),
        Index("ix_selection_strategy_team_updated", "team_id", "updated_at", "strategy_id"),
        Index("ix_selection_strategy_shop", "request_shop_id", "strategy_id"),
    )

    strategy_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    request_shop_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("shops.shop_id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    schedule_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProductSelectionCandidate(TimestampMixin, Base):
    """One Team-owned product identity, not a formal product-library record."""

    __tablename__ = "product_selection_candidates"
    __table_args__ = (
        CheckConstraint("discovery_tracking_version IS NULL OR discovery_tracking_version = 1", name="tracking_version"),
        CheckConstraint("(blocked_changed_at IS NULL) = (blocked_changed_by_user_id IS NULL)", name="block_actor_pair"),
        CheckConstraint("platform = 'douyin'", name="platform"),
        CheckConstraint(
            "length(trim(platform_product_id)) > 0", name="product_id_not_blank",
        ),
        UniqueConstraint(
            "team_id", "platform", "platform_product_id",
            name="uq_selection_candidate_team_product",
        ),
        UniqueConstraint(
            "candidate_id", "team_id",
            name="uq_selection_candidate_id_team",
        ),
        Index("ix_selection_candidate_team_id", "team_id", "candidate_id"),
    )

    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_false())
    blocked_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    blocked_changed_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.user_id", name="fk_selection_candidate_block_actor", ondelete="RESTRICT"))
    # NULL legacy cannot prove that absent discovery history means 'new'.
    discovery_tracking_version: Mapped[int | None] = mapped_column(Integer)


class ProductSelectionRun(TimestampMixin, Base):
    """One explicit manual intent, including empty success and no-fact failure."""

    __tablename__ = "product_selection_runs"
    __table_args__ = (
        CheckConstraint("operation_kind IN ('rank','basic_info')", name="operation_kind"),
        CheckConstraint("(operation_kind = 'rank' AND target_observation_id IS NULL) OR (operation_kind = 'basic_info' AND target_observation_id IS NOT NULL AND strategy_id IS NULL AND result_detail_version IS NULL)", name="operation_target"),
        CheckConstraint("result_detail_version IS NULL OR result_detail_version = 1", name="detail_version"),
        UniqueConstraint("team_id", "created_by_user_id", "submission_key", name="uq_selection_run_submission"),
        Index("uq_selection_run_active_request", "team_id", "request_shop_id", "request_fingerprint",
              unique=True, postgresql_where=text("status IN ('pending', 'running')")),
        Index("ix_selection_run_pending", "status", "created_at", "run_id"),
        Index("ix_selection_run_team_created", "team_id", "created_at", "run_id"),
        Index("ix_selection_run_strategy_created", "strategy_id", "created_at", "run_id"),
        Index("ix_selection_run_basic_target", "target_observation_id", "created_at", "run_id", postgresql_where=text("operation_kind = 'basic_info'")),
        Index("uq_selection_run_running_shop", "request_shop_id", unique=True,
              postgresql_where=text("status = 'running'")),
        Index("uq_selection_run_running_strategy", "strategy_id", unique=True,
              postgresql_where=text("status = 'running' AND strategy_id IS NOT NULL")),
        CheckConstraint("status IN ('pending','running','succeeded','partial','failed','interrupted','reused')", name="status"),
        CheckConstraint("(status = 'reused') = (reused_run_id IS NOT NULL)", name="reuse_state"),
        CheckConstraint("reused_run_id IS NULL OR reused_run_id <> run_id", name="reuse_not_self"),
        CheckConstraint("reused_run_id IS NULL OR (lease_id IS NULL AND lease_expires_at IS NULL AND started_at IS NULL AND finished_at IS NULL)", name="reuse_not_execution"),
        CheckConstraint("reused_run_id IS NULL OR (result_count IS NULL AND saved_count = 0 AND supplemented_count = 0 AND supplement_failed_count = 0 AND error_code IS NULL AND error_stage IS NULL AND platform_business_code IS NULL)", name="reuse_not_result"),
        CheckConstraint("stage IN ('queued','session','rank','persistence','basic_info','completed')", name="stage"),
        CheckConstraint("request_fingerprint ~ '^[a-f0-9]{64}$'", name="request_hash"),
        CheckConstraint("jsonb_typeof(request_conditions) = 'object'", name="request_object"),
        CheckConstraint("result_count IS NULL OR result_count >= 0", name="result_non_negative"),
        CheckConstraint("saved_count >= 0 AND supplemented_count >= 0 AND supplement_failed_count >= 0", name="counts_non_negative"),
        CheckConstraint("(operation_kind = 'rank' AND supplemented_count + supplement_failed_count <= saved_count) OR (operation_kind = 'basic_info' AND saved_count = 0 AND supplemented_count + supplement_failed_count <= 1)", name="supplement_counts"),
        CheckConstraint("platform_business_code IS NULL OR jsonb_typeof(platform_business_code) IN ('string','number')", name="business_code_scalar"),
    )

    run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    operation_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="rank", server_default="rank")
    target_observation_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_selection_observations.observation_id", name="fk_selection_run_basic_observation", ondelete="RESTRICT", use_alter=True))
    result_detail_version: Mapped[int | None] = mapped_column(Integer)
    team_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    request_shop_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("shops.shop_id", ondelete="RESTRICT"), nullable=False)
    submission_key: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    strategy_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_selection_strategies.strategy_id", name="fk_selection_run_strategy", ondelete="RESTRICT"),
    )
    reused_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_selection_runs.run_id", ondelete="RESTRICT"),
    )
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    request_conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer)
    saved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supplemented_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supplement_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(96))
    error_stage: Mapped[str | None] = mapped_column(String(32))
    platform_business_code: Mapped[str | int | None] = mapped_column(JSONB(none_as_null=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProductSelectionObservation(TimestampMixin, Base):
    """Current successful facts in one explicit, independently authorized scope.

    It cannot represent a failed/empty run and is intentionally not a queue.
    No raw response, session material or arbitrary request URL is stored.
    """

    __tablename__ = "product_selection_observations"
    __table_args__ = (
        CheckConstraint("basic_info_version >= 0", name="basic_version"),
        CheckConstraint("basic_info_status IS NULL OR jsonb_typeof(basic_info_status) = 'object'", name="basic_status_object"),
        CheckConstraint("period_begin <= period_end", name="period_order"),
        CheckConstraint(
            "source_scope_hash ~ '^[a-f0-9]{64}$'", name="source_hash",
        ),
        CheckConstraint("jsonb_typeof(source_context) = 'object'", name="source_object"),
        CheckConstraint(
            "jsonb_typeof(merchant_snapshot) = 'array'", name="merchants_array",
        ),
        CheckConstraint(
            "category_path IS NULL OR jsonb_typeof(category_path) = 'array'",
            name="category_array",
        ),
        CheckConstraint(
            "jsonb_typeof(video_metric_ranges) = 'object'", name="metrics_object",
        ),
        CheckConstraint("rank IS NULL OR rank >= 0", name="rank_non_negative"),
        CheckConstraint(
            "previous_rank IS NULL OR previous_rank >= 0", name="previous_rank_non_negative",
        ),
        CheckConstraint(
            "bad_comment_rate_raw IS NULL OR bad_comment_rate_raw >= 0",
            name="rate_non_negative",
        ),
        CheckConstraint(
            "bad_comment_rate_unit IS NULL OR "
            "jsonb_typeof(bad_comment_rate_unit) IN ('string', 'number', 'null')",
            name="rate_unit_scalar",
        ),
        UniqueConstraint(
            "candidate_id", "request_shop_id", "source_scope_hash",
            name="uq_selection_observation_source",
        ),
        Index(
            "ix_selection_observation_shop_checked",
            "request_shop_id", "checked_at", "observation_id",
        ),
        Index(
            "ix_selection_observation_candidate_checked",
            "candidate_id", "checked_at", "observation_id",
        ),
    )

    observation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_id,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_selection_candidates.candidate_id", ondelete="RESTRICT"),
        nullable=False,
    )
    request_shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        nullable=False,
    )
    last_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("product_selection_runs.run_id", ondelete="RESTRICT"),
    )
    source_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    period_begin: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    merchant_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    category_path: Mapped[list[str] | None] = mapped_column(JSONB(none_as_null=True))
    price_band: Mapped[str | None] = mapped_column(String(200))
    rank: Mapped[int | None] = mapped_column(Integer)
    previous_rank: Mapped[int | None] = mapped_column(Integer)
    previous_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    newly_on_ranking: Mapped[bool | None] = mapped_column(Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metrics_retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    video_metric_ranges: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    first_on_shelf_date: Mapped[date | None] = mapped_column(Date)
    bad_comment_rate_raw: Mapped[Decimal | None] = mapped_column(Numeric)
    bad_comment_rate_unit: Mapped[str | int | None] = mapped_column(JSONB(none_as_null=True))
    basic_info_retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_successful_request_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    last_error_code: Mapped[str | None] = mapped_column(String(96))
    last_error_stage: Mapped[str | None] = mapped_column(String(32))
    basic_info_status: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    basic_info_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ProductSelectionResultItem(Base):
    """Immutable observed membership and minimal rank snapshot, not product copies."""
    __tablename__ = "product_selection_result_items"
    __table_args__ = (
        UniqueConstraint("execution_run_id", "observation_id", name="uq_selection_result_run_observation"),
        CheckConstraint("discovery_state IN ('new','known','unknown')", name="discovery_state"),
        CheckConstraint("discovery_scope_hash ~ '^[a-f0-9]{64}$'", name="discovery_hash"),
        CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="snapshot_object"),
        Index("ix_selection_result_discovery", "discovery_scope_hash", "observation_id", "hit_at"),
        Index("ix_selection_result_hit", "hit_at", "observation_id"),
    )
    item_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    execution_run_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_selection_runs.run_id", ondelete="RESTRICT"), nullable=False)
    observation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_selection_observations.observation_id", ondelete="RESTRICT"), nullable=False)
    discovery_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    discovery_state: Mapped[str] = mapped_column(String(16), nullable=False)
    hit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
