from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint, Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class ProductSelectionCandidate(TimestampMixin, Base):
    """One Team-owned product identity, not a formal product-library record."""

    __tablename__ = "product_selection_candidates"
    __table_args__ = (
        CheckConstraint("platform = 'douyin'", name="platform"),
        CheckConstraint(
            "length(trim(platform_product_id)) > 0", name="product_id_not_blank",
        ),
        UniqueConstraint(
            "team_id", "platform", "platform_product_id",
            name="uq_selection_candidate_team_product",
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


class ProductSelectionObservation(TimestampMixin, Base):
    """Current successful facts in one explicit, independently authorized scope.

    It cannot represent a failed/empty run and is intentionally not a queue.
    No raw response, session material or arbitrary request URL is stored.
    """

    __tablename__ = "product_selection_observations"
    __table_args__ = (
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
