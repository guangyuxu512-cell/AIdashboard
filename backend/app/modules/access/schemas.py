from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.access.enums import DataScope
from app.modules.access.roles import DEFAULT_ROLE_CODE


class TeamCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    enabled: bool = True


class TeamUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "TeamUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name 不能为 null")
        if "enabled" in self.model_fields_set and self.enabled is None:
            raise ValueError("enabled 不能为 null")
        return self


class TeamMembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    team_id: UUID
    user_id: UUID
    role_code: str = Field(default=DEFAULT_ROLE_CODE, min_length=1, max_length=64)
    data_scope: DataScope = DataScope.TEAM
    enabled: bool = True


class TeamMembershipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    role_code: str | None = Field(default=None, min_length=1, max_length=64)
    data_scope: DataScope | None = None
    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "TeamMembershipUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class TeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: UUID
    name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class TeamMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    team_id: UUID
    user_id: UUID
    role_code: str
    data_scope: DataScope
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ActorContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    user_display_name: str
    team_id: UUID
    membership_id: UUID
    role_code: str
    data_scope: DataScope


class MyTeamMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    team_id: UUID
    team_name: str
    team_enabled: bool
    role_code: str
    data_scope: DataScope
    membership_enabled: bool
