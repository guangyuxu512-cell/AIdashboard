from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


SkillHandler = Callable[[BaseModel], dict[str, Any]]


class SkillRuntime(StrEnum):
    PYTHON = "python"
    RPA = "rpa"
    DISCOVERY = "discovery"


class SkillProvider(StrEnum):
    YINGDAO = "yingdao"


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    input_model: type[BaseModel]
    runtime: SkillRuntime
    timeout_seconds: float
    handler: SkillHandler | None = None
    provider: SkillProvider | None = None
    provider_app_id: str | None = None

    def __post_init__(self) -> None:
        if self.runtime is SkillRuntime.PYTHON and self.handler is None:
            raise ValueError("Python Skill requires a local handler")
        if self.runtime is SkillRuntime.RPA and self.provider is None:
            raise ValueError("RPA Skill requires a provider")
        if self.runtime is SkillRuntime.DISCOVERY and self.provider is None:
            raise ValueError("Discovery Skill requires a provider")


class SkillRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, SkillDefinition] = {}

    def register(self, definition: SkillDefinition) -> None:
        if definition.skill_id in self._definitions:
            raise ValueError(f"Skill already registered: {definition.skill_id}")
        self._definitions[definition.skill_id] = definition

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._definitions.get(skill_id)

    def require(self, skill_id: str) -> SkillDefinition:
        definition = self.get(skill_id)
        if definition is None:
            raise KeyError(skill_id)
        return definition


registry = SkillRegistry()
