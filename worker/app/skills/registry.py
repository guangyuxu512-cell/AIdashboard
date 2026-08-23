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


class SkillClassification(StrEnum):
    INTERNAL = "internal"
    BUSINESS = "business"


class SkillDescriptor(BaseModel):
    skill_id: str
    display_name: str
    runtime: SkillRuntime
    provider: SkillProvider | None
    version: str
    classification: SkillClassification


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    display_name: str
    version: str
    input_model: type[BaseModel]
    runtime: SkillRuntime
    timeout_seconds: float
    handler: SkillHandler | None = None
    provider: SkillProvider | None = None
    provider_app_id: str | None = None
    classification: SkillClassification = SkillClassification.BUSINESS

    def __post_init__(self) -> None:
        if not self.skill_id or not self.display_name or not self.version:
            raise ValueError("Skill descriptor fields cannot be blank")
        if self.runtime is SkillRuntime.PYTHON and self.handler is None:
            raise ValueError("Python Skill requires a local handler")
        if self.runtime is SkillRuntime.RPA and self.provider is None:
            raise ValueError("RPA Skill requires a provider")
        if self.runtime is SkillRuntime.DISCOVERY and self.provider is None:
            raise ValueError("Discovery Skill requires a provider")

    def descriptor(self) -> SkillDescriptor:
        return SkillDescriptor(
            skill_id=self.skill_id,
            display_name=self.display_name,
            runtime=self.runtime,
            provider=self.provider,
            version=self.version,
            classification=self.classification,
        )


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

    def descriptors(self) -> tuple[SkillDescriptor, ...]:
        return tuple(definition.descriptor() for definition in self._definitions.values())


registry = SkillRegistry()
