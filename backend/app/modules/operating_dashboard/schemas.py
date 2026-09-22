from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    return_quantity: int | None
    shop_count: int
    turnover_comparison: OperatingDashboardComparisonRead
    order_comparison: OperatingDashboardComparisonRead
    return_comparison: OperatingDashboardComparisonRead
    shop_count_comparison: OperatingDashboardComparisonRead


class OperatingDashboardTrendPointRead(BaseModel):
    business_date: date
    turnover_cents: int | None
    order_count: int | None


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
    # No backend source has established the refund/return-piece contract yet.
    return_quantity: int | None
    experience_score: None = None
    collected_at: datetime | None
    coverage_complete: bool


class OperatingDashboardTablePageRead(BaseModel):
    items: list[OperatingDashboardTableRowRead]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class OperatingDashboardRead(BaseModel):
    date_range: OperatingDashboardDateRangeRead
    comparison_date_range: OperatingDashboardDateRangeRead
    trend_date_range: OperatingDashboardDateRangeRead
    all_available_shops: list[OperatingDashboardShopOptionRead]
    summary: OperatingDashboardSummaryRead
    trend: list[OperatingDashboardTrendPointRead]
    table: OperatingDashboardTablePageRead
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
    status: str
    retryable: bool
    failure_code: str | None
    failure_message: str | None
    failure_stage: str | None
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
    kind: str
    status: str
    requested_start_date: date
    requested_end_date: date
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    counts: OperatingDataCollectionCountsRead
    items: list[OperatingDataCollectionItemRead]


class OperatingDataCollectionRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_ids: list[UUID] = Field(default_factory=list, max_length=200)
