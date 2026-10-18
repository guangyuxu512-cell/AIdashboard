from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.operating_dashboard.enums import (
    OperatingCollectionFailureStage,
    OperatingCollectionItemStatus,
    OperatingCollectionJobKind,
    OperatingCollectionJobStatus,
)
from app.modules.shops.enums import ShopPlatform


class OperatingDashboardDateRangeRead(BaseModel):
    start_date: date
    end_date: date


class OperatingDashboardComparisonRead(BaseModel):
    state: Literal["unavailable", "equal", "increase", "decrease"]
    percentage: float | None = None
    favorable: bool | None = None


class OperatingDashboardSummaryRead(BaseModel):
    turnover_cents: int | None
    order_count: int | None
    # `refund_order_cnt`: Compass “退款订单数（退款时间）”, unit: order.
    refund_order_count: int | None
    # Refund coverage is independent from core turnover/order coverage.  A
    # partial aggregate is useful but cannot support a misleading comparison.
    refund_order_coverage_complete: bool
    shop_count: int
    turnover_comparison: OperatingDashboardComparisonRead
    order_comparison: OperatingDashboardComparisonRead
    refund_order_comparison: OperatingDashboardComparisonRead
    shop_count_comparison: OperatingDashboardComparisonRead


class OperatingDashboardTrendPointRead(BaseModel):
    business_date: date
    turnover_cents: int | None
    order_count: int | None
    # A point can contain a useful partial aggregate when some supported
    # Shops have not yet supplied the selected business date.  The value is
    # never synthesized from a missing observation; consumers use this flag
    # to label the partial coverage without erasing the facts that do exist.
    coverage_complete: bool


class OperatingDashboardShopOptionRead(BaseModel):
    shop_id: UUID
    shop_name: str
    platform: ShopPlatform


class OperatingDashboardTableRowRead(BaseModel):
    shop_id: UUID
    shop_name: str
    platform: ShopPlatform
    turnover_cents: int | None
    order_count: int | None
    refund_order_count: int | None
    refund_order_coverage_complete: bool
    experience_score: None = None
    collected_at: datetime | None
    coverage_complete: bool
    # True only when the entire selected range ends before this Shop's
    # explicitly confirmed operating start date.  It is distinct from a
    # missing/failed observation and therefore must not render as a zero.
    not_operating_for_range: bool = False


class OperatingDashboardTablePageRead(BaseModel):
    items: list[OperatingDashboardTableRowRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class OperatingSessionRecoveryRead(BaseModel):
    collection_job_id: UUID
    collection_item_id: UUID
    session_version: int = Field(ge=1)
    # A read does not validate the Session or enqueue work. A stale validation
    # must pass the authoritative health check during explicit recovery.
    requires_validation: bool


class OperatingDashboardCoverageMissingRead(BaseModel):
    shop_id: UUID
    shop_name: str
    business_date: date
    # This is intentionally a presentation-safe state, not a raw platform
    # error or a collection item identifier.
    state: Literal[
        "missing",
        "collecting",
        "waiting_collection_time",
        "waiting_reauthorization",
        "failed",
        "unknown",
    ]
    # A locally mapped, presentation-safe failure reason.  Raw platform
    # messages and persisted failure details must never appear in coverage.
    failure_reason: str | None = None
    session_recovery: OperatingSessionRecoveryRead | None = None
    recovery_block_reason: str | None = None


class OperatingDashboardCoverageRead(BaseModel):
    # `unsupported` means the current authorized/filter scope has no enabled
    # platform that can collect operating data. A read/query failure remains a
    # normal API error and is never represented as fake empty coverage.
    state: Literal["available", "unsupported"]
    supported_shop_count: int = Field(ge=0)
    collected_shop_days: int = Field(ge=0)
    total_shop_days: int = Field(ge=0)
    missing_shop_days: int = Field(ge=0)
    missing_samples: list[OperatingDashboardCoverageMissingRead]
    missing_samples_truncated: bool
    # The selected range includes a missing Shop/date. Historical work is
    # explicitly requested on the dashboard, never created by ordinary reads.
    manual_backfill_required: bool
    # Calendar dates before a confirmed Shop operating-start boundary are not
    # expected collection work and therefore are excluded from the denominator.
    not_operating_shop_days: int = Field(default=0, ge=0)
    # Unknown remains deliberately conservative: those Shops retain the
    # complete selected calendar range rather than being guessed as unopened.
    shops_with_unknown_operating_start: int = Field(default=0, ge=0)
    # Lets the UI distinguish an all-pre-operation selection from an all-null
    # or failed collection range without manufacturing zeros.
    no_operating_scope: bool = False


class OperatingDashboardRead(BaseModel):
    date_range: OperatingDashboardDateRangeRead
    comparison_date_range: OperatingDashboardDateRangeRead
    trend_date_range: OperatingDashboardDateRangeRead
    all_available_shops: list[OperatingDashboardShopOptionRead]
    summary: OperatingDashboardSummaryRead
    trend: list[OperatingDashboardTrendPointRead]
    table: OperatingDashboardTablePageRead
    coverage: OperatingDashboardCoverageRead
    # Read access and collection execution are deliberately separate.  A
    # Feature/Integration Backend can truthfully show persisted data without
    # being allowed to call the platform on a user's button click.
    collection_available: bool


class OperatingDataCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date
    end_date: date
    platform: ShopPlatform | None = None
    shop_id: UUID | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "OperatingDataCollectionRequest":
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days + 1 > 60:
            raise ValueError("单次经营数据更新最多覆盖60个完整自然日")
        return self


class OperatingDataCollectionItemRead(BaseModel):
    collection_item_id: UUID
    shop_id: UUID
    business_date: date
    status: OperatingCollectionItemStatus
    retryable: bool
    failure_code: str | None
    failure_message: str | None
    failure_stage: OperatingCollectionFailureStage | None
    attempt_count: int
    started_at: datetime | None
    finished_at: datetime | None
    queue_wait_ms: int | None
    session_preparation_ms: int | None
    signature_ms: int | None
    platform_response_ms: int | None
    response_parse_ms: int | None
    total_ms: int | None


class OperatingDataCollectionCountsRead(BaseModel):
    pending: int = Field(ge=0)
    running: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    paused_reauthorization: int = Field(ge=0)


class OperatingDataCollectionJobRead(BaseModel):
    collection_job_id: UUID
    kind: OperatingCollectionJobKind
    status: OperatingCollectionJobStatus
    requested_start_date: date
    requested_end_date: date
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    counts: OperatingDataCollectionCountsRead
    items: list[OperatingDataCollectionItemRead]


class OperatingDataCollectionSubmissionRead(BaseModel):
    """Safe result of a dashboard update/recollection request.

    Ordinary dashboard updates may correctly have no durable Job: the
    selected confirmed metrics can already be complete.  Keeping that state
    explicit prevents the UI from fabricating an empty Job merely to display
    a success message.
    """

    state: Literal[
        "up_to_date",
        "collection_queued",
        "attention_required",
        "unsupported",
        "not_operating",
    ]
    message: str
    collection_job: OperatingDataCollectionJobRead | None
    missing_shop_days: int = Field(ge=0)
    queued_shop_days: int = Field(ge=0)
    active_shop_days: int = Field(ge=0)
    blocked_shop_days: int = Field(ge=0)
    # A yesterday item can be durably queued before the configured Shanghai
    # boundary, but must not be claimed for an upstream request until then.
    waiting_shop_days: int = Field(default=0, ge=0)
    # A successful core response can still report an optional refund field as
    # unavailable/not-ready/malformed. It is not a core failure and is not
    # automatically retried forever; this count keeps that result visible.
    refund_attention_shop_days: int = Field(ge=0)
    not_operating_shop_days: int = Field(default=0, ge=0)


class OperatingDataCollectionRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[UUID] = Field(default_factory=list, max_length=200)
    session_recovery_version: int | None = Field(default=None, ge=1)
    revalidate_current_session: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def validate_session_recovery(self) -> "OperatingDataCollectionRetryRequest":
        if self.session_recovery_version is not None and len(self.item_ids) != 1:
            raise ValueError("Session恢复必须明确选择一个原失败项")
        if self.revalidate_current_session and self.session_recovery_version is None:
            raise ValueError("会话复核必须用于明确的单项Session恢复")
        return self
