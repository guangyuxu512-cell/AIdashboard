from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiTokenChange(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(min_length=1, max_length=300)
    team_ids: list[UUID] | None = Field(default=None, max_length=200)
    enabled: bool = True
    expires_at: datetime | None = None


class ApiTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token_id: UUID
    owner_user_id: UUID
    name: str
    permissions: list[str]
    team_ids: list[str] | None
    enabled: bool
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApiTokenEnabled(BaseModel):
    enabled: bool


class ApiTokenEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: UUID
    token_id: UUID
    actor_user_id: UUID
    request_id: str
    action: str
    name: str
    created_at: datetime


class ApiTokenIssued(BaseModel):
    token: ApiTokenRead
    value: str = Field(repr=False)


class PermissionRead(BaseModel):
    id: str
    module: str
    name: str
    team_scoped: bool
