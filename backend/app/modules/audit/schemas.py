from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from app.modules.audit.enums import AuditAction, AuditTargetType


class AuditLogCreatedRange(BaseModel):
    created_from: AwareDatetime | None = None
    created_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_order(self) -> "AuditLogCreatedRange":
        if (
            self.created_from is not None
            and self.created_to is not None
            and self.created_from >= self.created_to
        ):
            raise ValueError("created_from must be earlier than created_to")
        return self


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_log_id: UUID
    request_id: str
    actor_user_id: UUID
    actor_display_name: str
    team_id: UUID | None
    action: AuditAction
    target_type: AuditTargetType
    target_id: UUID
    details: dict[str, Any] | None
    created_at: datetime
