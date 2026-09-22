from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    Date as SQLDate,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class ShopOperatingDailyMetric(TimestampMixin, Base):
    """One immutable business-date observation for one Shop.

    The table deliberately stores only metrics whose platform response paths
    and units are confirmed. Return quantity and merchant score have no
    persisted column until their platform contracts are separately verified.
    """

    __tablename__ = "shop_operating_daily_metrics"
    __table_args__ = (
        CheckConstraint("length(trim(source_code)) > 0", name="source_not_blank"),
        CheckConstraint("length(trim(metric_contract)) > 0", name="contract_not_blank"),
        CheckConstraint(
            "turnover_cents IS NULL OR turnover_cents >= 0",
            name="turnover_non_negative",
        ),
        CheckConstraint(
            "order_count IS NULL OR order_count >= 0",
            name="orders_non_negative",
        ),
        UniqueConstraint("shop_id", "business_date", name="uq_operating_metric_shop_date"),
        Index(
            "ix_operating_metric_shop_date",
            "shop_id",
            "business_date",
        ),
        Index("ix_operating_metric_date", "business_date"),
    )

    metric_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_id
    )
    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        nullable=False,
    )
    business_date: Mapped[date] = mapped_column(SQLDate, nullable=False)
    source_code: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_contract: Mapped[str] = mapped_column(String(64), nullable=False)
    turnover_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OperatingDataCollectionJob(TimestampMixin, Base):
    """A durable request group; item rows hold each shop/date outcome."""

    __tablename__ = "operating_data_collection_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('initial_backfill', 'reenable_backfill', 'manual_refresh', 'daily', 'retry')",
            name="kind",
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'partial_failed', 'failed')",
            name="status",
        ),
        CheckConstraint("requested_start_date <= requested_end_date", name="date_range"),
        UniqueConstraint("dedupe_key", name="uq_operating_collection_job_dedupe_key"),
        Index("ix_operating_collection_job_created", "created_at", "collection_job_id"),
    )

    collection_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_id
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_start_date: Mapped[date] = mapped_column(SQLDate, nullable=False)
    requested_end_date: Mapped[date] = mapped_column(SQLDate, nullable=False)
    requested_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    # A manually requested collection is re-authorized at execution time with
    # this original Team context.  System backfills and daily plans have no
    # human requester and deliberately leave it NULL.
    requested_team_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Daily scheduling uses one stable key per Shanghai business date.  Other
    # jobs leave this NULL so they do not become falsely idempotent forever.
    dedupe_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OperatingDataCollectionItem(TimestampMixin, Base):
    """One shop/date unit with database-enforced cross-process ownership."""

    __tablename__ = "operating_data_collection_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'skipped', 'paused_reauthorization')",
            name="status",
        ),
        CheckConstraint(
            "failure_stage IS NULL OR failure_stage IN ('queued', 'session_preparation', 'signing', 'platform_response', 'response_parse', 'session_persistence', 'execution')",
            name="failure_stage",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_non_negative"),
        CheckConstraint(
            "queue_wait_ms IS NULL OR queue_wait_ms >= 0",
            name="queue_wait_non_negative",
        ),
        CheckConstraint(
            "session_preparation_ms IS NULL OR session_preparation_ms >= 0",
            name="session_ms_non_negative",
        ),
        CheckConstraint(
            "signature_ms IS NULL OR signature_ms >= 0",
            name="signature_non_negative",
        ),
        CheckConstraint(
            "platform_response_ms IS NULL OR platform_response_ms >= 0",
            name="platform_ms_non_negative",
        ),
        CheckConstraint(
            "response_parse_ms IS NULL OR response_parse_ms >= 0",
            name="response_parse_non_negative",
        ),
        CheckConstraint("total_ms IS NULL OR total_ms >= 0", name="total_non_negative"),
        UniqueConstraint(
            "collection_job_id",
            "shop_id",
            "business_date",
            name="uq_operating_collection_item_job_shop_date",
        ),
        # An overlapping manual/daily/backfill request records a safe SKIPPED
        # item rather than allowing two processes to call one Shop/date.
        Index(
            "uq_operating_collection_active_shop_date",
            "shop_id",
            "business_date",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'running', 'paused_reauthorization')"
            ),
            sqlite_where=text(
                "status IN ('pending', 'running', 'paused_reauthorization')"
            ),
        ),
        # A Shop can have several dates queued but exactly one network request
        # running across all Backend processes.
        Index(
            "uq_operating_collection_running_shop",
            "shop_id",
            unique=True,
            postgresql_where=text("status = 'running'"),
            sqlite_where=text("status = 'running'"),
        ),
        Index(
            "ix_operating_collection_item_claim",
            "status",
            "retry_after",
            "priority",
            "created_at",
            "collection_item_id",
        ),
        Index(
            "ix_operating_collection_item_job", "collection_job_id", "created_at"),
        Index("ix_operating_collection_item_shop_date", "shop_id", "business_date"),
    )

    collection_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_id
    )
    collection_job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operating_data_collection_jobs.collection_job_id", ondelete="RESTRICT"),
        nullable=False,
    )
    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        nullable=False,
    )
    business_date: Mapped[date] = mapped_column(SQLDate, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(96))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    failure_stage: Mapped[str | None] = mapped_column(String(32))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Durations are operational facts for this collection attempt.  They are
    # nullable for pre-existing queued/skipped work and never store request
    # context, signed URLs, Cookie material, or platform response bodies.
    queue_wait_ms: Mapped[int | None] = mapped_column(Integer)
    session_preparation_ms: Mapped[int | None] = mapped_column(Integer)
    signature_ms: Mapped[int | None] = mapped_column(Integer)
    platform_response_ms: Mapped[int | None] = mapped_column(Integer)
    response_parse_ms: Mapped[int | None] = mapped_column(Integer)
    total_ms: Mapped[int | None] = mapped_column(Integer)
