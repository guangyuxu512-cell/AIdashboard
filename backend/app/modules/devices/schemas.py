from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.workers.schemas import DeviceRuntimeRead


class DeviceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    location: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


class DeviceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    location: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_change(self) -> "DeviceUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field in ("display_name", "enabled"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} 不能为 null")
        return self


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: UUID
    display_name: str
    enabled: bool
    location: str | None
    note: str | None
    deleted_at: datetime | None
    worker_runtime: DeviceRuntimeRead | None = None
    created_at: datetime
    updated_at: datetime
