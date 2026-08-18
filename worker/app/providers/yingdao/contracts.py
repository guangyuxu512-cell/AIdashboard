from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class YingdaoExecutionStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class YingdaoApplication(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    app_id: str = Field(min_length=1)
    app_name: str = Field(min_length=1)


class YingdaoDiscoveryResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider_available: bool
    account_display: str | None = None
    applications: list[YingdaoApplication] = Field(default_factory=list)


class YingdaoExecutionRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    task_id: UUID
    skill_id: str
    app_id: str
    params: dict[str, Any]
    runtime_directory: Path


class YingdaoExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: YingdaoExecutionStatus
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    step: str | None = None
    message: str | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> "YingdaoExecutionResult":
        if self.status is YingdaoExecutionStatus.FAILED and (
            not self.error_code or not self.error_message
        ):
            raise ValueError("FAILED Yingdao result requires error details")
        return self
