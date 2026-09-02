from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.modules.access.enums import DataScope
from app.modules.access.module_access import ModuleCode, module_codes_are_unique
from app.modules.access.roles import (
    ACCESS_ADMIN_ROLE_CODE,
    DEFAULT_ROLE_CODE,
    MANAGEABLE_ROLE_CODES,
)
from app.modules.human_auth.identifiers import normalize_login_name
from app.modules.human_auth.passwords import PASSWORD_MAX_LENGTH


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


class AccessMemberMembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: UUID
    role_code: str = DEFAULT_ROLE_CODE
    data_scope: DataScope = DataScope.TEAM
    enabled: bool = True
    module_codes: list[ModuleCode] = Field(default_factory=list)

    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, value: str) -> str:
        if value not in MANAGEABLE_ROLE_CODES:
            raise ValueError("role_code 不是当前可管理的角色")
        return value

    @field_validator("module_codes")
    @classmethod
    def validate_module_codes(cls, value: list[ModuleCode]) -> list[ModuleCode]:
        if not module_codes_are_unique(value):
            raise ValueError("module_codes 不能重复")
        return value


class AccessMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    display_name: str = Field(min_length=1, max_length=100)
    login_name: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    membership: AccessMemberMembershipCreate

    @field_validator("login_name")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return normalize_login_name(value)


class AccessMemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AccessMemberUpdate":
        if self.enabled is None:
            raise ValueError("至少提供一个需要更新的字段")
        return self


class AccessMemberPasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: SecretStr = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class AccessMembershipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: UUID
    role_code: str = DEFAULT_ROLE_CODE
    data_scope: DataScope = DataScope.TEAM
    enabled: bool = True
    module_codes: list[ModuleCode] = Field(default_factory=list)

    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, value: str) -> str:
        if value not in MANAGEABLE_ROLE_CODES:
            raise ValueError("role_code 不是当前可管理的角色")
        return value

    @field_validator("module_codes")
    @classmethod
    def validate_module_codes(cls, value: list[ModuleCode]) -> list[ModuleCode]:
        if not module_codes_are_unique(value):
            raise ValueError("module_codes 不能重复")
        return value


class AccessMembershipUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_code: str | None = None
    data_scope: DataScope | None = None
    enabled: bool | None = None
    module_codes: list[ModuleCode] | None = None

    @field_validator("role_code")
    @classmethod
    def validate_role_code(cls, value: str | None) -> str | None:
        if value is not None and value not in MANAGEABLE_ROLE_CODES:
            raise ValueError("role_code 不是当前可管理的角色")
        return value

    @field_validator("module_codes")
    @classmethod
    def validate_module_codes(
        cls,
        value: list[ModuleCode] | None,
    ) -> list[ModuleCode] | None:
        if value is not None and not module_codes_are_unique(value):
            raise ValueError("module_codes 不能重复")
        return value

    @model_validator(mode="after")
    def require_change(self) -> "AccessMembershipUpdate":
        if not self.model_fields_set:
            raise ValueError("至少提供一个需要更新的字段")
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} 不能为 null")
        return self


class AccessMembershipRead(BaseModel):
    membership_id: UUID
    team_id: UUID
    team_name: str
    team_enabled: bool
    role_code: str
    data_scope: DataScope
    enabled: bool
    module_codes: list[ModuleCode]


class AccessMemberRead(BaseModel):
    user_id: UUID
    display_name: str
    login_name: str | None
    enabled: bool
    memberships: list[AccessMembershipRead]
    created_at: datetime
    updated_at: datetime


class CurrentModuleAccessRead(BaseModel):
    module_codes: list[ModuleCode]
    is_access_administrator: bool


def is_access_administrator_role(role_code: str) -> bool:
    return role_code == ACCESS_ADMIN_ROLE_CODE
