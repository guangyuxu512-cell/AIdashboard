from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class WorkerTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    skill_id: str
    input: dict[str, Any]
    lease_until: datetime


class ProviderInventoryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_code: str
    inventory: dict[str, Any]


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ExecutionStatus
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    provider_inventory: ProviderInventoryReport | None = None


class SkillProcessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    skill_id: str
    params: dict[str, Any]


class RuntimeEventType(StrEnum):
    STATUS = "status"
    LOG = "log"
    PROGRESS = "progress"
    COMPLETED = "completed"
    FAILED = "failed"


class RuntimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seq: int = Field(gt=0)
    task_id: UUID
    event_type: RuntimeEventType
    level: str = Field(min_length=1, max_length=16)
    message: str = Field(max_length=10_000)
    event_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
