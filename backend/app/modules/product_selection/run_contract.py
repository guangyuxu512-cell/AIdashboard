"""Business-only manual run contract; external parameter mappings are separate."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, model_serializer

from app.modules.product_selection.source import SelectionSourceScope
from app.modules.product_selection.basic_contract import SelectionBasicRequest
from app.modules.product_selection.strategy_queue_key import SelectionStrategyQueueKey


CategoryId = Annotated[str, Field(pattern=r"^[0-9]{1,32}$")]
RunStatus = Literal["pending", "running", "succeeded", "partial", "failed", "interrupted"]
RunStage = Literal["queued", "session", "rank", "persistence", "basic_info", "completed"]
SelectionFallbackReason = Literal["primary_success_empty", "primary_business_rejection_probe"]
HISTORICAL_PERIOD_RULES = MappingProxyType({
    "1d": (1, "20", "shanghai_1d_yesterday"),
    "30d": (30, "23", "shanghai_30d_complete_days"),
})
BRAND_TYPES = MappingProxyType({"all": "-1", "known": "0", "unknown": "1"})


class SelectionRelativeConditions(BaseModel):
    """Original user intent. It does not claim a platform enum/date mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    channel: Literal["short-video", "baiying"]
    period: Literal["realtime", "1d", "7d", "30d"]
    industry_id: CategoryId
    category_ids: tuple[CategoryId, ...] = Field(min_length=1, max_length=3)
    brand: Literal["all", "known", "unknown"]
    price_mode: Literal["all", "custom"]
    # Confirmed two-sided yuan bounds remain plain, finite decimal strings.
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


def custom_price_bin(original: SelectionRelativeConditions) -> str:
    """Confirmed two-sided yuan query; no exponent, rounding or cent conversion."""
    values = (original.price_above, original.price_below)
    if any(type(value) is not str or re.fullmatch(r"[0-9]{1,10}(\.[0-9]{1,2})?", value) is None for value in values):
        raise ValueError("Two explicit finite nonnegative yuan bounds are required")
    lower, upper = (Decimal(value) for value in values)
    if lower > upper:
        raise ValueError("Minimum price cannot exceed maximum price")
    def plain(value: Decimal) -> str:
        number = format(value, "f")
        return number.rstrip("0").rstrip(".") if "." in number else number
    return f"{plain(lower)}-{plain(upper)}"


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
    """Existing single-window anchor; actual realtime/history dates live in scope."""

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


class SelectionHistoricalDateProvenance(SelectionRealtimeDateProvenance):
    policy: Literal["shanghai_1d_yesterday", "shanghai_30d_complete_days"]


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

    version: Literal[1, 2, 3, 4, 5, 6, 7, 8] = 1
    original: SelectionRunOriginal
    scope: SelectionSourceScope
    # V1 is deliberately bounded to at most two ten-item pages, not a crawler.
    page_numbers: tuple[Annotated[int, Field(ge=1, le=20)], ...] = Field(min_length=1, max_length=20)
    page_size: Literal[10] = 10
    date_plan: SelectionDatePlan | SelectionRealtimeDatePlan | None = None
    date_outcome: SelectionDateOutcome | None = None
    strategy: SelectionStrategySnapshot | None = None
    # Server-only conflict isolation; no HTTP command accepts this metadata.
    strategy_queue: SelectionStrategyQueueKey | None = None

    @model_serializer(mode="wrap")
    def retain_legacy_json_without_queue(self, handler):
        value = handler(self)
        if self.strategy_queue is None:
            value.pop("strategy_queue", None)
        return value

    @model_validator(mode="after")
    def validate_pages(self) -> "SelectionResolvedRequest":
        if len(set(self.page_numbers)) != len(self.page_numbers):
            raise ValueError("Repeated pages are not execution instructions")
        if self.version == 8:
            if self.page_numbers != self.target_pages():
                raise ValueError("Target pages must include one first-page date probe and only the selected rank pages")
            # Reuse date/brand/price checks, without rewriting old runs or
            # persisting/signing this legacy sequential-page projection.
            self.legacy_paging_request()
            return self
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
        elif self.version == 5:
            if not isinstance(self.date_plan, SelectionRealtimeDatePlan) or self.original.period not in HISTORICAL_PERIOD_RULES:
                raise ValueError("Historical execution freezes one supported window, without a backup")
            days, date_type, _ = HISTORICAL_PERIOD_RULES[self.original.period]
            day = self.date_plan.accepted_local_date
            if (
                self.original.channel != "short-video" or self.original.brand != "all" or self.original.price_mode != "all"
                or self.scope.date_type != date_type or self.scope.rank_data_type != "1"
                or self.scope.brand_type != "-1" or self.scope.price_bin != "不限"
                or self.scope.search_info != "" or self.scope.activity_id != ""
                or self.scope.industry_id != self.original.industry_id
                or self.scope.category_id != ",".join(self.original.category_ids)
                or self.scope.period_begin != day - timedelta(days=days)
                or self.scope.period_end != day - timedelta(days=1)
                or self.page_numbers != tuple(range(1, (self.original.rank_to + 9) // 10 + 1))
                or (self.date_outcome is not None and self.date_outcome.state != "primary")
            ):
                raise ValueError("Historical scope must match its frozen complete Shanghai days")
        elif self.version == 6:
            if self.original.price_mode != "custom" or self.original.brand != "all":
                raise ValueError("Custom price execution requires its confirmed default brand context")
            price = custom_price_bin(self.original)
            if self.date_outcome is not None and self.date_outcome.fallback_reason == "primary_business_rejection_probe":
                raise ValueError("Custom price cannot probe an unexplained business rejection")
            if (self.scope.price_bin != price or self.scope.brand_type != "-1"
                or self.scope.industry_id != self.original.industry_id
                or self.scope.category_id != ",".join(self.original.category_ids)
                or self.scope.rank_data_type != "1" or self.scope.search_info != "" or self.scope.activity_id != ""
                or (self.original.period == "7d" and self.scope.date_type != "21")):
                raise ValueError("Actual price query must match the explicit original bounds")
            raw = self.model_dump(mode="json")
            raw.pop("strategy_queue", None)
            raw["version"] = self._date_version()
            raw["original"] = raw["original"] | {"price_mode": "all", "price_above": None, "price_below": None}
            raw["scope"] = raw["scope"] | {"price_bin": "不限"}
            if isinstance(self.date_plan, SelectionDatePlan):
                if self.date_plan.backup_scope.price_bin != price:
                    raise ValueError("Backup cannot change custom price conditions")
                raw["date_plan"]["backup_scope"]["price_bin"] = "不限"
            # Reuse the versioned date validation without changing its old JSON
            # or hash semantics. This projection is never persisted or signed.
            SelectionResolvedRequest.model_validate(raw)
        elif self.version == 7:
            if self.original.brand not in {"known", "unknown"} or self.scope.brand_type != BRAND_TYPES[self.original.brand]:
                raise ValueError("Actual brand query must match the confirmed original label")
            price = custom_price_bin(self.original) if self.original.price_mode == "custom" else "不限"
            if (self.original.channel != "short-video" or self.scope.price_bin != price
                or self.scope.industry_id != self.original.industry_id
                or self.scope.category_id != ",".join(self.original.category_ids)
                or self.scope.rank_data_type != "1" or self.scope.search_info != "" or self.scope.activity_id != ""
                or (self.original.period == "7d" and self.scope.date_type != "21")):
                raise ValueError("Brand execution cannot replace the other submitted conditions")
            if self.date_outcome is not None and self.date_outcome.fallback_reason == "primary_business_rejection_probe":
                raise ValueError("Non-default brand cannot probe an unexplained business rejection")
            raw = self.model_dump(mode="json")
            raw.pop("strategy_queue", None)
            raw["version"] = 6 if self.original.price_mode == "custom" else self._date_version()
            raw["original"]["brand"] = "all"
            raw["scope"]["brand_type"] = "-1"
            if isinstance(self.date_plan, SelectionDatePlan):
                if self.date_plan.backup_scope.brand_type != BRAND_TYPES[self.original.brand]:
                    raise ValueError("Backup cannot change brand conditions")
                raw["date_plan"]["backup_scope"]["brand_type"] = "-1"
            # Validate the same date/price contract, never persist/sign this
            # default-brand projection or rewrite an already stored v1-v6 run.
            SelectionResolvedRequest.model_validate(raw)
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
        if self.strategy_queue is not None:
            if self.strategy is None or self.version < 3:
                raise ValueError("Queue isolation requires a saved strategy execution")
            self.strategy_queue.validate_binding(self, strategy_id=self.strategy.strategy_id)
        return self

    def _date_version(self) -> int:
        if self.version not in {6, 7, 8}:
            return self.version
        return 3 if self.original.period == "7d" else 4 if self.original.period == "realtime" else 5

    def target_pages(self) -> tuple[int, ...]:
        first = (self.original.rank_from - 1) // self.page_size + 1
        last = (self.original.rank_to - 1) // self.page_size + 1
        return tuple(dict.fromkeys((1, *range(first, last + 1))))

    def legacy_paging_request(self) -> "SelectionResolvedRequest":
        """Read/active-key compatibility only; historical instructions stay intact."""
        if self.version != 8:
            return self
        version = 7 if self.original.brand != "all" else 6 if self.original.price_mode == "custom" else self._date_version()
        raw = self.model_dump(mode="json") | {
            "version": version,
            "page_numbers": list(range(1, (self.original.rank_to + 9) // 10 + 1)),
        }
        raw.pop("strategy_queue", None)
        return SelectionResolvedRequest.model_validate(raw)

    def single_window(self) -> bool:
        return self._date_version() in {4, 5}

    def fingerprint(self) -> str:
        return self.strategy_queue.fingerprint() if self.strategy_queue is not None else self.base_fingerprint()

    def base_fingerprint(self) -> str:
        # Mutable execution outcome never changes the active-request key.
        # Preserve the exact v1 fingerprint for already-applied 0043 records.
        excluded = {"date_outcome", "strategy", "strategy_queue"}
        if self.version == 1:
            excluded.add("date_plan")
        return sha256(json.dumps(
            self.model_dump(mode="json", exclude=excluded), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode()).hexdigest()

    def actual_scope(self) -> SelectionSourceScope:
        if self.version == 1:
            return self.scope
        if self.single_window():
            if self.date_outcome is None or self.date_outcome.state != "primary":
                raise ValueError("Single-window execution must choose primary before writing facts")
            return self.scope
        if self.date_outcome is None or self.date_outcome.state not in {"primary", "backup", "backup_empty", "both_empty"}:
            raise ValueError("Choose the actual window before writing facts")
        if self.date_outcome.state in {"backup", "backup_empty"}:
            assert self.date_plan is not None
            return self.date_plan.backup_scope
        return self.scope

    def provenance(self) -> SelectionDateProvenance | SelectionRealtimeDateProvenance | SelectionHistoricalDateProvenance | None:
        if self.version == 1:
            return None
        self.actual_scope()
        assert self.date_plan is not None and self.date_outcome is not None
        if self._date_version() == 4:
            return SelectionRealtimeDateProvenance(
                accepted_local_date=self.date_plan.accepted_local_date,
                primary_begin=self.scope.period_begin, primary_end=self.scope.period_end,
                rank_from=self.original.rank_from, rank_to=self.original.rank_to,
            )
        if self._date_version() == 5:
            return SelectionHistoricalDateProvenance(
                policy=HISTORICAL_PERIOD_RULES[self.original.period][2],
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
    request: SelectionResolvedRequest | SelectionBasicRequest


class SelectionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    run_id: UUID
    operation_kind: Literal["rank", "basic_info"] = "rank"
    target_observation_id: UUID | None = None
    result_detail_version: Literal[1] | None = None
    team_id: UUID
    created_by_user_id: UUID
    request_shop_id: UUID
    strategy_id: UUID | None = None
    status: RunStatus
    stage: RunStage
    request_conditions: SelectionResolvedRequest | SelectionBasicRequest
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
    schedule_available: bool = True
    schedule_execution_enabled: bool = False
    material_collection_available: Literal[False] = False
    candidate_block_available: Literal[True] = True
    basic_info_available: bool = False
    supported_periods: tuple[Literal["realtime", "1d", "7d", "30d"], ...] = ("realtime", "1d", "7d", "30d")
    supported_brands: tuple[Literal["all", "known", "unknown"], ...] = ("all", "known", "unknown")
    custom_price_available: bool = True
    first_listed_filter_available: bool = True
    max_rank: int = 200
