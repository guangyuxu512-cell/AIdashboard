"""Database read contract, independent of unapproved platform execution inputs."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from app.modules.product_selection.source import SelectionSourceScope
from app.modules.product_selection.basic_contract import BasicInfoStatus
from app.modules.product_selection.run_contract import SelectionDateProvenance, SelectionRealtimeDateProvenance, SelectionHistoricalDateProvenance


SelectionSortField = Literal["checked_at", "first_on_shelf_date", "rank"]
SelectionSortDirection = Literal["asc", "desc"]


class SelectionCategoryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: StrictStr
    name: StrictStr
    children: list["SelectionCategoryRead"]


class SelectionCategoriesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shop_id: UUID
    nodes: list[SelectionCategoryRead]
    industry_id: StrictStr | None
    industry_name: StrictStr | None
    selected_category_id: StrictStr | None


class SelectionSourceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1, 2]
    platform: Literal["douyin"]
    endpoint: Literal["product_rank/video_bring_good"]
    business: SelectionSourceScope
    date_selection: SelectionDateProvenance | SelectionRealtimeDateProvenance | SelectionHistoricalDateProvenance | None = None
    first_listed_only: Literal[True] | None = None


class SelectionMerchantRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_shop_id: StrictStr
    name: StrictStr | None


class SelectionRangeEndpointRead(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    # JSON is a decimal string, not a JS number or a converted amount.
    value: Decimal = Field(ge=0)
    value_type: Literal["int", "float"]
    unit: StrictStr | StrictInt | None


class SelectionMetricRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["available", "missing", "null", "invalid"]
    retrieved_at: datetime
    value_range: tuple[SelectionRangeEndpointRead, SelectionRangeEndpointRead] | None = None

    @model_validator(mode="after")
    def validate_range_state(self) -> "SelectionMetricRead":
        if (self.state == "available") != (self.value_range is not None):
            raise ValueError("Only an available metric has a confirmed value range")
        return self


class SelectionVideoMetricsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pay_amt: SelectionMetricRead
    pay_combo_cnt: SelectionMetricRead
    product_click_cnt: SelectionMetricRead
    video_cnt: SelectionMetricRead


class SelectionObservationRead(BaseModel):
    """One visible source per list row; detail is pinned by observation_id.

    It represents persisted observations, never an empty/failed/running job.
    Nullable values remain unknown; no percentage/unit or period-label inference.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    observation_id: UUID
    last_run_id: UUID | None = None
    candidate_id: UUID
    blocked: bool = False
    blocked_changed_at: datetime | None = None
    discovery_state: Literal["new", "known", "unknown"] = "unknown"
    hit_at: datetime | None = None
    result_run_id: UUID | None = None
    basic_info_status: BasicInfoStatus | None = None
    product_id: StrictStr
    platform: Literal["douyin"]
    request_shop_id: UUID
    request_shop_name: StrictStr
    source_scope_hash: StrictStr
    source_context: SelectionSourceRead
    period_begin: date
    period_end: date
    title: StrictStr | None
    image_url: StrictStr | None
    source_url: StrictStr | None
    merchants: list[SelectionMerchantRead]
    category_path: list[StrictStr] | None
    price_band: StrictStr | None
    rank: int | None
    previous_rank: int | None
    previous_checked_at: datetime | None
    newly_on_ranking: bool | None
    first_seen_at: datetime
    checked_at: datetime
    metrics_retrieved_at: datetime
    video_metric_ranges: SelectionVideoMetricsRead
    first_on_shelf_date: date | None
    bad_comment_rate_raw: Decimal | None
    bad_comment_rate_unit: StrictStr | StrictInt | None
    basic_info_retrieved_at: datetime | None
    last_attempt_at: datetime
    last_error_code: StrictStr | None
    last_error_stage: StrictStr | None
