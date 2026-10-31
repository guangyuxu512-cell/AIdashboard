from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, SecretStr

from app.skills.registry import SkillDescriptor


class ExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class AccountPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shop_id: UUID
    shop_name: str | None = None
    platform_code: str
    login_identifier: str
    secret: str = Field(repr=False)
    preferred_verification_channel: str | None = None


class TaskAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    filename: str
    position: int = Field(ge=0)
    content_type: str
    size_bytes: int = Field(gt=0)
    sha256: str = Field(min_length=64, max_length=64)
    download_path: str


class WorkerTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    skill_id: str
    input: dict[str, Any]
    lease_until: datetime
    accounts: list[AccountPayload] = Field(default_factory=list, repr=False)
    assets: list[TaskAsset] = Field(default_factory=list)
    shop_ids: list[UUID] | None = None


class TaskShopSessionCookie(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

    name: str = Field(min_length=1)
    value: SecretStr
    domain: str | None = None
    path: str = "/"
    secure: bool = False
    http_only: bool = Field(default=False, alias="httpOnly")
    same_site: str | None = Field(default=None, alias="sameSite")
    expiration_date: float | None = Field(default=None, alias="expirationDate")


class TaskShopSession(BaseModel):
    """In-memory task-bound session; never serialize to runtime files or events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    shop_id: UUID
    platform: Literal["douyin"]
    session_version: int = Field(gt=0)
    task_lease_until: AwareDatetime
    cookies: tuple[TaskShopSessionCookie, ...] = Field(min_length=1, repr=False)


class ProviderInventoryReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_code: str
    inventory: dict[str, Any]


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
    provider_inventory: ProviderInventoryReport | None = None


class SkillProcessPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")

    images: Path


class SkillProcessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    skill_id: str
    params: dict[str, Any]
    paths: SkillProcessPaths
    accounts: list[AccountPayload] = Field(default_factory=list, repr=False)
    shop_ids: list[UUID] | None = None


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
