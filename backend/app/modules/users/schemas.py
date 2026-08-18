from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=100)
    enabled: bool = True


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name 不能为 null")
        if "enabled" in self.model_fields_set and self.enabled is None:
            raise ValueError("enabled 不能为 null")
        return self


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    display_name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime
