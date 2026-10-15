"""Closed single-product basic-info operation; no rank/date or HTTP input."""

from datetime import datetime
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StrictStr


class SelectionBasicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_id: UUID
    submission_key: UUID


class SelectionBasicExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    rank_started_at: AwareDatetime
    basic_version: int = Field(ge=1, strict=True)
    started_at: AwareDatetime


class SelectionBasicRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    operation: Literal["basic_info"] = "basic_info"
    observation_id: UUID
    candidate_id: UUID
    product_id: StrictStr = Field(pattern=r"^[0-9]{1,128}$")
    shop_id: UUID
    source_scope_hash: StrictStr = Field(pattern=r"^[a-f0-9]{64}$")
    execution: SelectionBasicExecution | None = None

    def fingerprint(self) -> str:
        # Execution fence/outcome never changes accepted idempotency identity.
        return sha256(json.dumps(self.model_dump(mode="json", exclude={"execution"}),
            ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class BasicFieldState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    last_attempt_state: Literal["available", "missing", "null", "invalid", "unknown"]
    last_success_at: datetime | None = None


class BasicInfoStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    attempted_at: datetime
    request_started_at: datetime
    state: Literal["succeeded", "partial", "failed"]
    category_path: BasicFieldState
    first_on_shelf_date: BasicFieldState
    bad_comment_rate: BasicFieldState
    error_code: str | None = None
    error_stage: str | None = None
    platform_business_code: StrictStr | StrictInt | None = None
