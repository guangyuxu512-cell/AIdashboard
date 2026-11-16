from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.skills.registry import SkillDescriptor


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class TaskAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    filename: str
    position: int = Field(ge=0)
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    download_path: str


class LocalShopContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_shop_id: str = Field(min_length=1, max_length=160)
    platform: str = Field(min_length=1, max_length=64)
    platform_shop_id: str | None = Field(default=None, max_length=160)


class WorkerTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    skill_id: str
    input: dict[str, Any]
    lease_until: datetime
    local_shops: list[LocalShopContext] = Field(default_factory=list)
    assets: list[TaskAsset] = Field(default_factory=list)
    result_delivery: Literal["central", "product"] = "central"


class SkillCapabilitySnapshot(BaseModel):
    """The complete set of Skills currently registered by this Worker."""

    model_config = ConfigDict(extra="forbid")

    skills: list[SkillDescriptor]


class ExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ExecutionStatus
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


class SkillProcessPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    images: Path


class SkillProcessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    skill_id: str
    params: dict[str, Any]
    paths: SkillProcessPaths
    local_shops: list[LocalShopContext] = Field(default_factory=list)


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
