from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.workers.enums import WorkerConnectionStatus


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
