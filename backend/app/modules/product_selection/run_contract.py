"""Business-only manual run contract; external parameter mappings are separate."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.product_selection.source import SelectionSourceScope


CategoryId = Annotated[str, Field(pattern=r"^[0-9]{1,32}$")]
RunStatus = Literal["pending", "running", "succeeded", "partial", "failed", "interrupted"]
RunStage = Literal["queued", "session", "rank", "persistence", "basic_info", "completed"]
SelectionFallbackReason = Literal["primary_success_empty", "primary_business_rejection_probe"]


class SelectionRelativeConditions(BaseModel):
    """Original user intent. It does not claim a platform enum/date mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    channel: Literal["short-video", "baiying"]
    period: Literal["realtime", "1d", "7d", "30d"]
    industry_id: CategoryId
    category_ids: tuple[CategoryId, ...] = Field(min_length=1, max_length=3)
    brand: Literal["all", "known", "unknown"]
    price_mode: Literal["all", "custom"]
    # Unconfirmed price mapping cannot be enabled by accepting arbitrary text.
    price_above: Annotated[str, Field(pattern=r"^\d{1,10}(\.\d{1,2})?$")] | None = None
    price_below: Annotated[str, Field(pattern=r"^\d{1,10}(\.\d{1,2})?$")] | None = None
    first_listed_only: bool = Field(default=False, strict=True)
    rank_from: int = Field(ge=1, le=200)
    rank_to: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def validate_order(self) -> "SelectionRelativeConditions":
        if self.rank_from > self.rank_to:
            raise ValueError("Rank range must be ordered")
        if self.price_mode == "all" and (self.price_above is not None or self.price_below is not None):
            raise ValueError("Unlimited price has no custom bounds")
        return self


class SelectionRunOriginal(SelectionRelativeConditions):
    shop_id: UUID

    def fingerprint(self) -> str:
        return sha256(json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode()).hexdigest()


class SelectionRunCreate(SelectionRunOriginal):
    submission_key: UUID
    strategy_id: UUID | None = None
    strategy_version: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode="after")
    def validate_strategy_reference(self):
        if (self.strategy_id is None) != (self.strategy_version is None):
            raise ValueError("Strategy ID and saved version must be supplied together")
        return self

    def original(self) -> SelectionRunOriginal:
        return SelectionRunOriginal.model_validate(
            self.model_dump(exclude={"submission_key", "strategy_id", "strategy_version"}),
        )


class SelectionStrategySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: UUID
    version: int = Field(ge=1, strict=True)


class SelectionDatePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_local_date: date
    backup_scope: SelectionSourceScope


class SelectionRealtimeDatePlan(BaseModel):
    """One accepted Shanghai day, with no historical fallback window."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_local_date: date


class SelectionPrimaryBusinessError(BaseModel):
    """Only the explicitly approved first-page rejection, never a raw response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error_code: Literal["DOUYIN_SELECTION_BUSINESS_REJECTED"]
    error_stage: Literal["platform_business"]
    platform_business_code: Literal[621000704, "621000704"]

    @field_validator("platform_business_code", mode="before")
    @classmethod
    def exact_business_code(cls, value):
        if type(value) not in {int, str} or value not in {621000704, "621000704"}:
            raise ValueError("Only the exact observed int/string business code is eligible")
        return value


class SelectionDateOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Literal["primary", "fallback_checking", "backup", "backup_empty", "both_empty", "fallback_failed"]
    # Optional for already-stored v2 outcomes; they only supported empty-page fallback.
    fallback_reason: SelectionFallbackReason | None = None
    primary_error: SelectionPrimaryBusinessError | None = None

    @model_validator(mode="after")
    def validate_reason(self) -> "SelectionDateOutcome":
        probe = self.fallback_reason == "primary_business_rejection_probe"
        if (
            (self.state == "primary" and (self.fallback_reason is not None or self.primary_error is not None))
            or probe != (self.primary_error is not None)
            or (self.state == "both_empty" and probe)
            or (self.state == "backup_empty" and not probe)
        ):
            raise ValueError("The outcome must retain the actual first-page fallback reason")
        return self

    def effective_reason(self) -> SelectionFallbackReason | None:
        if self.state == "primary":
            return None
        return self.fallback_reason or "primary_success_empty"


class SelectionDateProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: Literal["shanghai_7d_once"] = "shanghai_7d_once"
    accepted_local_date: date
    primary_begin: date
    primary_end: date
    backup_begin: date
    backup_end: date
    actual_window: Literal["primary", "backup"]
    fallback_reason: SelectionFallbackReason | None
    primary_error: SelectionPrimaryBusinessError | None = None
    rank_from: int
    rank_to: int


class SelectionRealtimeDateProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    policy: Literal["shanghai_realtime_today"] = "shanghai_realtime_today"
    accepted_local_date: date
    primary_begin: date
    primary_end: date
    backup_begin: None = None
    backup_end: None = None
    actual_window: Literal["primary"] = "primary"
    fallback_reason: None = None
    primary_error: None = None
    rank_from: int
    rank_to: int


class SelectionRankQuery(BaseModel):
    """Projection for one chosen window, not a stored/accepted frozen plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    original: SelectionRunOriginal
    scope: SelectionSourceScope
    page_numbers: tuple[int, ...]
    page_size: Literal[10] = 10


class SelectionResolvedRequest(BaseModel):
    """A server-frozen request, never accepted directly from the public POST."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1, 2, 3, 4] = 1
    original: SelectionRunOriginal
    scope: SelectionSourceScope
    # V1 is deliberately bounded to at most two ten-item pages, not a crawler.
    page_numbers: tuple[Annotated[int, Field(ge=1, le=20)], ...] = Field(min_length=1, max_length=20)
    page_size: Literal[10] = 10
    date_plan: SelectionDatePlan | SelectionRealtimeDatePlan | None = None
    date_outcome: SelectionDateOutcome | None = None
    strategy: SelectionStrategySnapshot | None = None

    @model_validator(mode="after")
    def validate_pages(self) -> "SelectionResolvedRequest":
        if len(set(self.page_numbers)) != len(self.page_numbers):
            raise ValueError("Repeated pages are not execution instructions")
        if self.version == 1:
            if self.date_plan is not None or self.date_outcome is not None or self.strategy is not None or len(self.page_numbers) > 2:
                raise ValueError("Legacy executions have no fallback policy")
        elif self.version == 4:
            if not isinstance(self.date_plan, SelectionRealtimeDatePlan):
                raise ValueError("Realtime freezes one accepted day, without a backup")
            day = self.date_plan.accepted_local_date
            if (
                self.original.channel != "short-video" or self.original.period != "realtime"
                or self.original.brand != "all" or self.original.price_mode != "all"
                or self.scope.date_type != "1" or self.scope.rank_data_type != "1"
                or self.scope.brand_type != "-1" or self.scope.price_bin != "不限"
                or self.scope.search_info != "" or self.scope.activity_id != ""
                or self.scope.industry_id != self.original.industry_id
                or self.scope.category_id != ",".join(self.original.category_ids)
                or self.scope.period_begin != day or self.scope.period_end != day
                or self.page_numbers != tuple(range(1, (self.original.rank_to + 9) // 10 + 1))
                or (self.date_outcome is not None and self.date_outcome.state != "primary")
            ):
                raise ValueError("Realtime must match the single accepted Shanghai day")
        else:
            if not isinstance(self.date_plan, SelectionDatePlan):
                raise ValueError("A fallback execution must freeze both windows")
            day = self.date_plan.accepted_local_date
            backup = self.date_plan.backup_scope
            if (
                self.original.channel != "short-video" or self.original.period != "7d"
                or (self.version == 2 and (self.original.rank_to > 20 or self.strategy is not None
                    or self.page_numbers != ((1, 2) if self.original.rank_to > 10 else (1,))))
                or (self.version == 3 and self.page_numbers != tuple(range(1, (self.original.rank_to + 9) // 10 + 1)))
                or self.scope.period_begin != day - timedelta(days=7)
                or self.scope.period_end != day - timedelta(days=1)
                or backup.period_begin != day - timedelta(days=8)
                or backup.period_end != day - timedelta(days=2)
                or self.scope.model_dump(exclude={"begin_date", "end_date"})
                != backup.model_dump(exclude={"begin_date", "end_date"})
            ):
                raise ValueError("The bounded plan must match the accepted Shanghai date")
        return self

    def fingerprint(self) -> str:
        # Mutable execution outcome never changes the active-request key.
        # Preserve the exact v1 fingerprint for already-applied 0043 records.
        excluded = {"date_outcome", "strategy"}
        if self.version == 1:
            excluded.add("date_plan")
        return sha256(json.dumps(
            self.model_dump(mode="json", exclude=excluded), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode()).hexdigest()

    def actual_scope(self) -> SelectionSourceScope:
        if self.version == 1:
            return self.scope
        if self.version == 4:
            if self.date_outcome is None or self.date_outcome.state != "primary":
                raise ValueError("Realtime must choose its sole window before writing facts")
            return self.scope
        if self.date_outcome is None or self.date_outcome.state not in {"primary", "backup", "backup_empty", "both_empty"}:
            raise ValueError("Choose the actual window before writing facts")
        if self.date_outcome.state in {"backup", "backup_empty"}:
            assert self.date_plan is not None
            return self.date_plan.backup_scope
        return self.scope

    def provenance(self) -> SelectionDateProvenance | SelectionRealtimeDateProvenance | None:
        if self.version == 1:
            return None
        self.actual_scope()
        assert self.date_plan is not None and self.date_outcome is not None
        if self.version == 4:
            return SelectionRealtimeDateProvenance(
                accepted_local_date=self.date_plan.accepted_local_date,
                primary_begin=self.scope.period_begin, primary_end=self.scope.period_end,
                rank_from=self.original.rank_from, rank_to=self.original.rank_to,
            )
        assert isinstance(self.date_plan, SelectionDatePlan)
        return SelectionDateProvenance(
            accepted_local_date=self.date_plan.accepted_local_date,
            primary_begin=self.scope.period_begin, primary_end=self.scope.period_end,
            backup_begin=self.date_plan.backup_scope.period_begin,
            backup_end=self.date_plan.backup_scope.period_end,
            actual_window="backup" if self.date_outcome.state in {"backup", "backup_empty"} else "primary",
            fallback_reason=self.date_outcome.effective_reason(),
            primary_error=self.date_outcome.primary_error,
            rank_from=self.original.rank_from, rank_to=self.original.rank_to,
        )


@dataclass(frozen=True)
class SelectionRunClaim:
    run_id: UUID
    lease_id: UUID
    team_id: UUID
    user_id: UUID
    shop_id: UUID
    started_at: datetime
    request: SelectionResolvedRequest


class SelectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    run_id: UUID
    team_id: UUID
    created_by_user_id: UUID
    request_shop_id: UUID
    strategy_id: UUID | None = None
    status: RunStatus
    stage: RunStage
    request_conditions: SelectionResolvedRequest
    result_count: int | None
    saved_count: int
    supplemented_count: int
    supplement_failed_count: int
    error_code: str | None
    error_stage: str | None
    platform_business_code: str | int | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SelectionRunReceipt(BaseModel):
    """Accepted caller intent is separate from the canonical execution."""

    receipt_id: UUID
    submission_key: UUID
    execution_run_id: UUID
    reused: bool
    strategy: SelectionStrategySnapshot | None = None
    execution: SelectionRunRead


class SelectionCapabilitiesRead(BaseModel):
    candidate_query: Literal[True] = True
    execution_enabled: bool
    manual_execution_available: bool
    unavailable_reason: Literal["EXECUTION_DISABLED"] | None
    strategy_save_available: bool = True
    schedule_available: Literal[False] = False
    material_collection_available: Literal[False] = False
    supported_periods: tuple[Literal["realtime", "1d", "7d", "30d"], ...] = ("realtime", "7d")
    supported_brands: tuple[Literal["all", "known", "unknown"], ...] = ("all",)
    custom_price_available: bool = False
    first_listed_filter_available: bool = True
    max_rank: int = 200
