from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.modules.human_auth.identifiers import normalize_login_name
from app.modules.human_auth.passwords import PASSWORD_MAX_LENGTH


class HumanLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_name: str = Field(min_length=1, max_length=100)
    password: SecretStr = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("login_name")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return normalize_login_name(value)


class CurrentHumanUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    display_name: str
