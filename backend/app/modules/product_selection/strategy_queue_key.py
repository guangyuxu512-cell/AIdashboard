"""Approved conflict-only Run key, not another queue or authority source.

The writer/reader bind metadata to frozen intent, strategy FK and authorized
Team/Shop. Only unsafe running associations use this namespace; normal intent
keeps its existing key. HTTP commands cannot supply this metadata.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Annotated, Literal, TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:
    from app.modules.product_selection.run_contract import SelectionResolvedRequest


class SelectionStrategyQueueKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    base_fingerprint: Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
    strategy_id: UUID

    @field_validator("version", mode="before")
    @classmethod
    def exact_key_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Queue key version must be the exact supported integer")
        return value

    @classmethod
    def from_request(cls, request: SelectionResolvedRequest, *, strategy_id: UUID) -> "SelectionStrategyQueueKey":
        if request.strategy is None or request.strategy.strategy_id != strategy_id:
            raise ValueError("Queue isolation needs its validated saved strategy snapshot")
        return cls(base_fingerprint=request.base_fingerprint(), strategy_id=strategy_id)

    def validate_binding(self, request: SelectionResolvedRequest, *, strategy_id: UUID) -> None:
        expected = self.from_request(request, strategy_id=strategy_id)
        if self != expected:
            raise ValueError("Queue metadata cannot replace the frozen basis or saved strategy")

    def fingerprint(self) -> str:
        payload = {"selection_strategy_queue": self.model_dump(mode="json")}
        return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
