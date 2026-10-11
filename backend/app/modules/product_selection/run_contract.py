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


class SelectionRunOriginal(BaseModel):
    """Original user intent. It does not claim a platform enum/date mapping."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    shop_id: UUID
    channel: Literal["short-video", "baiying"]
    period: Literal["realtime", "1d", "7d", "30d"]
    industry_id: CategoryId
    category_ids: tuple[CategoryId, ...] = Field(min_length=1, max_length=3)
    brand: Literal["all", "known", "unknown"]
    price_mode: Literal["all", "custom"]
    # Unconfirmed price mapping cannot be enabled by accepting arbitrary text.
    price_above: Annotated[str, Field(pattern=r"^\d{1,10}(\.\d{1,2})?$")] | None = None
    price_below: Annotated[str, Field(pattern=r"^\d{1,10}(\.\d{1,2})?$")] | None = None
    first_listed_only: bool = False
    rank_from: int = Field(ge=1, le=200)
    rank_to: int = Field(ge=1, le=200)

    @model_validator(mode="after")
    def validate_order(self) -> "SelectionRunOriginal":
        if self.rank_from > self.rank_to:
            raise ValueError("Rank range must be ordered")
        if self.price_mode == "all" and (self.price_above is not None or self.price_below is not None):
            raise ValueError("Unlimited price has no custom bounds")
        return self

    def fingerprint(self) -> str:
        return sha256(json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode()).hexdigest()


class SelectionRunCreate(SelectionRunOriginal):
    submission_key: UUID

    def original(self) -> SelectionRunOriginal:
        return SelectionRunOriginal.model_validate(
            self.model_dump(exclude={"submission_key"}),
        )


class SelectionDatePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted_local_date: date
    backup_scope: SelectionSourceScope


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


class SelectionResolvedRequest(BaseModel):
    """A server-frozen request, never accepted directly from the public POST."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1, 2] = 1
    original: SelectionRunOriginal
    scope: SelectionSourceScope
    # V1 is deliberately bounded to at most two ten-item pages, not a crawler.
    page_numbers: tuple[Annotated[int, Field(ge=1, le=20)], ...] = Field(min_length=1, max_length=2)
    page_size: Literal[10] = 10
    date_plan: SelectionDatePlan | None = None
    date_outcome: SelectionDateOutcome | None = None

    @model_validator(mode="after")
    def validate_pages(self) -> "SelectionResolvedRequest":
        if len(set(self.page_numbers)) != len(self.page_numbers):
            raise ValueError("Repeated pages are not execution instructions")
        if self.version == 1:
            if self.date_plan is not None or self.date_outcome is not None:
                raise ValueError("Legacy executions have no fallback policy")
        else:
            if self.date_plan is None:
                raise ValueError("A fallback execution must freeze both windows")
            day = self.date_plan.accepted_local_date
            backup = self.date_plan.backup_scope
            if (
                self.original.channel != "short-video" or self.original.period != "7d"
                or self.original.rank_to > 20
                or self.page_numbers != ((1, 2) if self.original.rank_to > 10 else (1,))
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
        excluded = {"date_outcome"}
        if self.version == 1:
            excluded.add("date_plan")
        return sha256(json.dumps(
            self.model_dump(mode="json", exclude=excluded), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode()).hexdigest()

    def actual_scope(self) -> SelectionSourceScope:
        if self.version == 1:
            return self.scope
        if self.date_outcome is None or self.date_outcome.state not in {"primary", "backup", "backup_empty", "both_empty"}:
            raise ValueError("Choose the actual window before writing facts")
        if self.date_outcome.state in {"backup", "backup_empty"}:
            assert self.date_plan is not None
            return self.date_plan.backup_scope
        return self.scope

    def provenance(self) -> SelectionDateProvenance | None:
        if self.version == 1:
            return None
        self.actual_scope()
        assert self.date_plan is not None and self.date_outcome is not None
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
    execution: SelectionRunRead


class SelectionCapabilitiesRead(BaseModel):
    candidate_query: Literal[True] = True
    execution_enabled: bool
    manual_execution_available: bool
    unavailable_reason: Literal["EXECUTION_DISABLED"] | None
    strategy_save_available: Literal[False] = False
    schedule_available: Literal[False] = False
    material_collection_available: Literal[False] = False
