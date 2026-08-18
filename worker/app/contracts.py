from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class WorkerTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    skill_id: str
    input: dict[str, Any]
    lease_until: datetime


class ExecutionResult(BaseModel):
    status: ExecutionStatus
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


class SkillProcessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    params: dict[str, Any]
