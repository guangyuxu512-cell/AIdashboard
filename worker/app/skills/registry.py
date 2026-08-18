from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


SkillHandler = Callable[[BaseModel], dict[str, Any]]


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    input_model: type[BaseModel]
    handler: SkillHandler
    timeout_seconds: float


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
