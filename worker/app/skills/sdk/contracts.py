from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Generic, Literal, Mapping, Protocol, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    model_validator,
)

from app.contracts import RuntimeEventType
from app.runtime_events import RuntimeEventBus
from app.skills.registry import SkillDescriptor


MAX_SKILL_RESULT_BYTES = 64 * 1024
MAX_SKILL_EVENT_METADATA_BYTES = 16 * 1024
_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
SkillLogLevel = Literal["debug", "info", "warning", "error"]


class BusinessSkillInput(BaseModel):
    """Base input model with a closed, explicit parameter surface."""

    model_config = ConfigDict(extra="forbid")


class SkillResult(BaseModel):
    """Small JSON result returned through the existing Task result contract."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=1_000)
    data: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def keep_result_small(self) -> SkillResult:
        encoded = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > MAX_SKILL_RESULT_BYTES:
            raise ValueError(
                f"Skill result exceeds {MAX_SKILL_RESULT_BYTES} bytes",
            )
        return self


class SkillExecutionError(Exception):
    """Expected, user-safe Business Skill failure."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, JsonValue] | None = None,
    ) -> None:
        if not _ERROR_CODE.fullmatch(code):
            raise ValueError("Skill error code must be stable upper snake case")
        safe_message = message.strip()
        if not safe_message or len(safe_message) > 1_000:
            raise ValueError("Skill error message must contain 1 to 1000 characters")
        super().__init__(safe_message)
        self.code = code
        self.message = safe_message
        self.retryable = retryable
        self.details = TypeAdapter(dict[str, JsonValue]).validate_python(
            dict(details or {}),
        )


@dataclass
class _CancellationState:
    requested: bool = False


@dataclass(frozen=True)
class SkillContextPaths:
    images: Path


@dataclass(frozen=True)
class SkillContext:
    task_id: UUID
    device_id: UUID
    skill_id: str
    timeout_seconds: float
    deadline: datetime
    _event_bus: RuntimeEventBus = field(repr=False)
    paths: SkillContextPaths
    accounts: list[Mapping[str, JsonValue]] = field(
        default_factory=list,
        repr=False,
    )
    _cancellation: _CancellationState = field(
        default_factory=_CancellationState,
        repr=False,
    )

    @property
    def is_cancelled(self) -> bool:
        """Local cooperative cancellation state; Backend Cancel is not supported."""

        return self._cancellation.requested

    def log(
        self,
        message: str,
        *,
        level: SkillLogLevel = "info",
        metadata: Mapping[str, JsonValue] | None = None,
    ) -> None:
        payload: dict[str, Any] = dict(metadata or {})
        payload["skill_id"] = self.skill_id
        encoded_metadata = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded_metadata) > MAX_SKILL_EVENT_METADATA_BYTES:
            raise ValueError("Skill log metadata is too large")
        self._event_bus.emit(
            self.task_id,
            RuntimeEventType.LOG,
            message,
            level=level,
            metadata=payload,
        )

    def progress(
        self,
        *,
        current: int,
        total: int | None = None,
        message: str | None = None,
    ) -> None:
        if current < 0:
            raise ValueError("Skill progress current cannot be negative")
        if total is not None and total <= 0:
            raise ValueError("Skill progress total must be greater than zero")
        if total is not None and current > total:
            raise ValueError("Skill progress current cannot exceed total")
        metadata: dict[str, Any] = {
            "skill_id": self.skill_id,
            "current": current,
        }
        if total is not None:
            metadata["total"] = total
        self._event_bus.emit(
            self.task_id,
            RuntimeEventType.PROGRESS,
            message or "执行进度已更新",
            level="info",
            metadata=metadata,
        )

    def _mark_cancelled(self) -> None:
        self._cancellation.requested = True


InputT = TypeVar("InputT", bound=BusinessSkillInput)


class BusinessSkill(Protocol, Generic[InputT]):
    descriptor: SkillDescriptor
    input_model: type[InputT]
    timeout_seconds: float

    async def run(self, ctx: SkillContext, input: InputT) -> SkillResult: ...
