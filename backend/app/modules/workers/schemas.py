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


class ProviderApplicationInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    app_id: str = Field(min_length=1, max_length=200)
    app_name: str = Field(min_length=1, max_length=500)
    package_version: str = Field(min_length=1, max_length=100)
    entrypoint: str = Field(min_length=1, max_length=200)


class YingdaoProviderInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: Literal["yingdao"]
    available: bool
    provider_version: str = Field(min_length=1, max_length=64)
    execution_available: bool = False
    execution_version: str | None = Field(default=None, max_length=64)
    execution_unavailable_reason: str | None = Field(default=None, max_length=500)
    logged_in: bool
    account_display: str = Field(min_length=1, max_length=200)
    account_type: str = Field(min_length=1, max_length=64)
    enterprise_account: bool
    user_id: str = Field(min_length=1, max_length=200)
    applications: list[ProviderApplicationInventory]
    discovered_at: datetime


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
