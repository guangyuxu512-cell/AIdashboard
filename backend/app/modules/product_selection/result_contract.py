"""Immutable result projection; defaults retain the existing fact query."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.modules.product_selection.schemas import SelectionObservationRead, SelectionVideoMetricsRead
from app.modules.product_selection.run_contract import SelectionRunRead
from app.shared.pagination import Page

SelectionResultScope = Literal["all", "today", "today_new", "today_known"]
DiscoveryState = Literal["new", "known", "unknown"]


class SelectionRankSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    rank: int | None
    previous_rank: int | None
    previous_checked_at: datetime | None
    price_band: str | None
    newly_on_ranking: bool | None
    video_metric_ranges: SelectionVideoMetricsRead


class SelectionResultContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receipt_id: UUID | None = None
    execution_run_id: UUID | None = None
    detail_state: Literal["recorded", "not_recorded"] | None = None
    execution: SelectionRunRead | None = None
    unknown_discovery_count: int = 0


class SelectionCandidatePage(Page[SelectionObservationRead]):
    context: SelectionResultContext = Field(default_factory=SelectionResultContext)


class SelectionBatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    receipt_id: UUID
    execution_run_id: UUID
    submitted_at: datetime
    detail_state: Literal["recorded", "not_recorded"]
    execution: SelectionRunRead
    visible_item_count: int | None = None


class SelectionBlockCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    blocked: StrictBool
