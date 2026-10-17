from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.product_data.exceptions import ProductDataUnitUnconfirmedError
from app.modules.product_data.source import NativePeriod, PERIODS, ProductDataSlice
from app.platforms.douyin.product_data import PRODUCT_METRICS, ObservationState
from app.shared.pagination import Page


METRIC_BY_CODE = {metric.code: metric for metric in PRODUCT_METRICS}
RANGE_CODES = {
    "product_show_cnt", "product_click_cnt", "product_show_click_converse_uv_rate",
    "click_add_to_cart_uv", "product_add_show_converse_uv_ratio", "net_pay_cnt",
    "pay_cnt_exclude_refund", "product_click_pay_converse_uv_rate", "pay_refund_ratio",
}
SORT_FIELDS = {"shop_name", "product_id", "title", "retrieved_at", *METRIC_BY_CODE}


class ProductDataMetricRange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    min_value: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_value: Decimal | None = Field(default=None, ge=0, allow_inf_nan=False)

    @field_validator("min_value", "max_value", mode="before")
    @classmethod
    def exact_number(cls, value):
        if isinstance(value, (bool, float)):
            raise ValueError("Range boundaries must be exact decimal strings or integers")
        return value

    @model_validator(mode="after")
    def interval(self):
        if self.metric not in RANGE_CODES:
            raise ValueError("Unknown product metric range")
        if self.min_value is None and self.max_value is None:
            raise ValueError("A selected range needs at least one boundary")
        if self.min_value is not None and self.max_value is not None and self.min_value >= self.max_value:
            raise ValueError("A range uses min inclusive and max exclusive, with min below max")
        if METRIC_BY_CODE[self.metric].kind == "count":
            if any(value is not None and value != value.to_integral_value() for value in (self.min_value, self.max_value)):
                raise ValueError("Count ranges need integer boundaries")
        return self


class ProductDataQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    period: NativePeriod
    start_date: date
    end_date: date
    shop_id: UUID | None = None
    product_id: str = Field(default="", max_length=32, pattern=r"^[0-9]*$")
    product_name: str = Field(default="", max_length=200)
    sale_type: Literal["1"] = "1"
    content_type: Literal["1"] = "1"
    ranges: tuple[ProductDataMetricRange, ...] = ()
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_field: str | None = None
    sort_direction: Literal["asc", "desc"] | None = None

    @model_validator(mode="after")
    def valid_query(self):
        if (self.end_date - self.start_date).days != PERIODS[self.period][0] - 1:
            raise ValueError("Query must use an exact native preset window")
        if (self.sort_field is None) != (self.sort_direction is None):
            raise ValueError("Sort field and direction must be paired")
        if self.sort_field is not None and self.sort_field not in SORT_FIELDS:
            raise ValueError("Unknown product sort field")
        if len({interval.metric for interval in self.ranges}) != len(self.ranges):
            raise ValueError("Duplicate metric ranges")
        return self

    def require_verified_units(self) -> None:
        codes = {interval.metric for interval in self.ranges}
        if self.sort_field in METRIC_BY_CODE:
            codes.add(self.sort_field)
        if any(METRIC_BY_CODE[code].kind != "count" for code in codes):
            raise ProductDataUnitUnconfirmedError()

    def scope_for(self, shop_id: UUID) -> ProductDataSlice:
        return ProductDataSlice(shop_id=shop_id, period=self.period, start_date=self.start_date,
                                end_date=self.end_date, sale_type=self.sale_type, content_type=self.content_type)


class ProductDataCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    shop_id: UUID
    period: NativePeriod
    submission_key: UUID
    sale_type: Literal["1"] = "1"
    content_type: Literal["1"] = "1"


class ProductDataMetricRead(BaseModel):
    state: ObservationState
    raw_value: str | None
    raw_unit: int | None
    unit_verified: bool


class ProductDataRowRead(BaseModel):
    shop_product_id: UUID
    generation_id: UUID
    shop_id: UUID
    shop_name: str
    product_id: str
    title: str | None
    image_url: str | None
    metrics: dict[str, ProductDataMetricRead]
    scope: ProductDataSlice
    retrieved_at: datetime


class ProductDataCoverageRead(BaseModel):
    supported_shop_count: int
    collected_shop_count: int
    missing_shop_ids: list[UUID]
    # This is fact coverage, not another Team's run/progress metadata.
    collection_available: bool
    unit_unconfirmed_codes: list[str]


class ProductDataListRead(Page[ProductDataRowRead]):
    coverage: ProductDataCoverageRead


class ProductDataGenerationRead(BaseModel):
    generation_id: UUID
    scope: ProductDataSlice
    status: Literal["pending", "running", "succeeded", "failed"]
    stage: str
    received_pages: int
    expected_total: int | None
    received_total: int | None
    pages_complete: bool
    raw_complete_rows: int | None
    unit_complete_rows: int | None
    failure_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    published_at: datetime | None
    lease_expired: bool
