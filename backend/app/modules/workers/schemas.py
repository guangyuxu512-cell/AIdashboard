from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.workers.enums import ProviderCode, WorkerConnectionStatus


class WorkerHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    worker_version: str = Field(min_length=1, max_length=64)
    started_at: datetime


class DeviceRuntimeRead(BaseModel):
    device_id: UUID
    worker_version: str
    connection_status: WorkerConnectionStatus
    last_seen_at: datetime
    started_at: datetime
    updated_at: datetime


class WorkerCredentialRead(BaseModel):
    device_id: UUID
    status: Literal["issued", "revoked", "not_issued"]
    issued_at: datetime | None


class WorkerTokenIssuedRead(WorkerCredentialRead):
    token: str


class WorkerProvisioningRead(BaseModel):
    device_id: UUID
    device_display_name: str
    device_enabled: bool


class WorkerSkillDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    skill_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    runtime: Literal["python", "rpa", "discovery"]
    provider: str | None = Field(default=None, min_length=1, max_length=64)
    version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def require_provider_for_provider_runtimes(self) -> "WorkerSkillDescriptor":
        if self.runtime in {"rpa", "discovery"} and self.provider is None:
            raise ValueError("RPA and discovery Skills require a provider")
        return self


class SkillCapabilitySnapshotUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: list[WorkerSkillDescriptor] = Field(max_length=256)

    @model_validator(mode="after")
    def require_unique_skill_ids(self) -> "SkillCapabilitySnapshotUpsert":
        skill_ids = [skill.skill_id for skill in self.skills]
        if len(skill_ids) != len(set(skill_ids)):
            raise ValueError("Skill capability snapshot contains duplicate skill_id")
        return self


class DeviceSkillCapabilityRead(BaseModel):
    device_id: UUID
    skill_id: str
    display_name: str
    runtime: Literal["python", "rpa", "discovery"]
    provider: str | None
    version: str
    updated_at: datetime


class ProviderApplicationInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    app_id: str = Field(min_length=1, max_length=200)
    app_name: str = Field(min_length=1, max_length=500)
    version_id: str | None = Field(default=None, max_length=200)
    updated_at: str | None = Field(default=None, max_length=100)
    app_type: str | None = Field(default=None, max_length=100)
    group_id: str | None = Field(default=None, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_application_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        if "version_id" not in migrated and "package_version" in migrated:
            migrated["version_id"] = migrated["package_version"]
        migrated.pop("package_version", None)
        migrated.pop("entrypoint", None)
        return migrated


class YingdaoProviderInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Literal["yingdao"]
    available: bool
    status: Literal[
        "not_installed",
        "version_unsupported",
        "starting",
        "need_login",
        "interface_unreachable",
        "ready",
    ]
    status_reason_code: str | None = Field(default=None, max_length=100)
    status_reason: str | None = Field(default=None, max_length=500)
    provider_version: str | None = Field(default=None, max_length=64)
    execution_available: bool = False
    execution_version: str | None = Field(default=None, max_length=64)
    execution_unavailable_reason: str | None = Field(default=None, max_length=500)
    logged_in: bool
    account_display: str | None = Field(default=None, max_length=200)
    account_type: str | None = Field(default=None, min_length=1, max_length=64)
    enterprise_account: bool | None = None
    user_id: str | None = Field(default=None, max_length=200)
    applications: list[ProviderApplicationInventory]
    discovered_at: datetime

    @model_validator(mode="before")
    @classmethod
    def default_legacy_status(cls, value: object) -> object:
        if isinstance(value, dict) and "status" not in value:
            migrated = dict(value)
            if (
                migrated.get("available")
                and migrated.get("provider_version") == "6.3.6"
                and migrated.get("logged_in")
            ):
                migrated.setdefault("execution_available", True)
                migrated.setdefault("execution_version", "6.3.6")
                migrated["status"] = "ready"
            elif migrated.get("available"):
                migrated["available"] = False
                migrated["execution_available"] = False
                migrated["execution_version"] = None
                migrated["status"] = "version_unsupported"
                migrated.setdefault(
                    "status_reason",
                    "历史影刀版本不再受 Worker V1 支持",
                )
            else:
                migrated["status"] = "interface_unreachable"
            return migrated
        return value

    @model_validator(mode="after")
    def validate_ready_contract(self) -> "YingdaoProviderInventory":
        if self.status == "ready" and (
            not self.available
            or self.provider_version != "6.3.6"
            or not self.execution_available
            or self.execution_version != "6.3.6"
            or not self.logged_in
            or not self.user_id
        ):
            raise ValueError("ready Yingdao inventory requires an authenticated 6.3.6 runtime")
        return self


class ProviderInventoryUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_code: ProviderCode
    inventory: YingdaoProviderInventory

    @model_validator(mode="after")
    def require_matching_provider(self) -> "ProviderInventoryUpsert":
        if self.provider_code.value != self.inventory.provider:
            raise ValueError("provider_code does not match inventory provider")
        return self


class DeviceProviderInventoryRead(BaseModel):
    device_id: UUID
    provider_code: ProviderCode
    available: bool
    provider_version: str | None
    account_display: str | None
    account_type: str | None
    enterprise_account: bool | None
    last_discovered_at: datetime
    inventory: YingdaoProviderInventory
    updated_at: datetime
