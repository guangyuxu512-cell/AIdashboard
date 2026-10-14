"""Saved relative strategy configuration, not an execution or schedule result."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.product_selection.run_contract import SelectionRelativeConditions, SelectionRunOriginal, SelectionRunRead


class SelectionStrategySchedule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scheduled: bool = False
    kind: Literal["hourly", "daily"] = "hourly"
    interval_hours: int = Field(default=1, ge=1, le=2147483647, strict=True)
    daily_time: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"


class SelectionStrategyConditions(BaseModel):
    """The same relative conditions as manual runs; Shop lives in its FK."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    request: SelectionRelativeConditions

    def original(self, shop_id: UUID) -> SelectionRunOriginal:
        return SelectionRunOriginal.model_validate(self.request.model_dump() | {"shop_id": shop_id})


class SelectionStrategyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    shop_id: UUID
    conditions: SelectionStrategyConditions
    schedule: SelectionStrategySchedule = Field(default_factory=SelectionStrategySchedule)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Strategy name cannot be blank")
        return value.strip()


class SelectionStrategyUpdate(SelectionStrategyCreate):
    expected_version: int = Field(ge=1, strict=True)


class SelectionStrategyToggle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    expected_version: int = Field(ge=1, strict=True)


class SelectionStrategyRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: UUID
    team_id: UUID
    created_by_user_id: UUID
    name: str
    shop_id: UUID
    shop_name: str
    version: int
    enabled: bool
    conditions: SelectionStrategyConditions
    schedule: SelectionStrategySchedule
    # A persists the plan but does not pretend to schedule it.
    schedule_available: bool = False
    next_run_at: datetime | None = None
    latest_run: SelectionRunRead | None = None
    created_at: datetime
    updated_at: datetime
