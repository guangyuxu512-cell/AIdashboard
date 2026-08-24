from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.skills.sdk import BusinessSkill


SkillHandler = Callable[[BaseModel], dict[str, Any]]


BUSINESS_SKILL_INPUT_SCHEMA_MAX_BYTES = 32 * 1024


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
    classification: SkillClassification = SkillClassification.BUSINESS
    input_schema: dict[str, Any] | None = None


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
    business_skill: BusinessSkill[Any] | None = None

    def __post_init__(self) -> None:
        if not self.skill_id or not self.display_name or not self.version:
            raise ValueError("Skill descriptor fields cannot be blank")
        if self.runtime is SkillRuntime.PYTHON:
            if self.classification is SkillClassification.BUSINESS:
                if self.business_skill is None or self.handler is not None:
                    raise ValueError(
                        "Python Business Skill must use the internal Skill SDK",
                    )
            elif self.handler is None or self.business_skill is not None:
                raise ValueError("Internal Python Skill requires a local handler")
        if self.runtime is SkillRuntime.RPA and self.provider is None:
            raise ValueError("RPA Skill requires a provider")
        if self.runtime is SkillRuntime.DISCOVERY and self.provider is None:
            raise ValueError("Discovery Skill requires a provider")

    def descriptor(self) -> SkillDescriptor:
        input_schema = (
            _build_business_skill_input_schema(self.input_model)
            if self.classification is SkillClassification.BUSINESS
            else None
        )
        return SkillDescriptor(
            skill_id=self.skill_id,
            display_name=self.display_name,
            runtime=self.runtime,
            provider=self.provider,
            version=self.version,
            classification=self.classification,
            input_schema=input_schema,
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


def _build_business_skill_input_schema(
    input_model: type[BaseModel],
) -> dict[str, Any]:
    """Generate the public input contract from the SDK Pydantic model."""

    schema = input_model.model_json_schema(mode="validation")
    payload = json.dumps(
        schema,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(payload) > BUSINESS_SKILL_INPUT_SCHEMA_MAX_BYTES:
        raise ValueError(
            "Business Skill input schema exceeds the 32 KiB capability limit",
        )
    return schema
