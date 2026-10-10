"""Business-only manual run contract; external parameter mappings are separate."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.product_selection.source import SelectionSourceScope


CategoryId = Annotated[str, Field(pattern=r"^[0-9]{1,32}$")]
RunStatus = Literal["pending", "running", "succeeded", "partial", "failed", "interrupted"]
RunStage = Literal["queued", "session", "rank", "persistence", "basic_info", "completed"]


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


class SelectionResolvedRequest(BaseModel):
    """A server-frozen request, never accepted directly from the public POST."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    original: SelectionRunOriginal
    scope: SelectionSourceScope
    # V1 is deliberately bounded to at most two ten-item pages, not a crawler.
    page_numbers: tuple[Annotated[int, Field(ge=1, le=20)], ...] = Field(min_length=1, max_length=2)
    page_size: Literal[10] = 10

    @model_validator(mode="after")
    def validate_pages(self) -> "SelectionResolvedRequest":
        if len(set(self.page_numbers)) != len(self.page_numbers):
            raise ValueError("Repeated pages are not execution instructions")
        return self

    def fingerprint(self) -> str:
        return sha256(json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False,
        ).encode()).hexdigest()


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
    manual_execution_available: Literal[False] = False
    unavailable_reason: Literal["REQUEST_MAPPING_UNCONFIRMED"] = "REQUEST_MAPPING_UNCONFIRMED"
    strategy_save_available: Literal[False] = False
    schedule_available: Literal[False] = False
    material_collection_available: Literal[False] = False
