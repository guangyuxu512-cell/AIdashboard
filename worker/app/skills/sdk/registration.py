from __future__ import annotations

import inspect
import re
from typing import Any, cast

from app.skills.registry import (
    SkillClassification,
    SkillDefinition,
    SkillRegistry,
    SkillRuntime,
)
from app.skills.sdk.contracts import BusinessSkill, BusinessSkillInput


_BUSINESS_SKILL_ID = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
)


def register_business_skill(
    skill_registry: SkillRegistry,
    skill: BusinessSkill[Any],
) -> SkillDefinition:
    """Register one SDK Business Skill in the existing Skill Registry."""

    descriptor = skill.descriptor
    if descriptor.classification is not SkillClassification.BUSINESS:
        raise ValueError("SDK Skill classification must be business")
    if descriptor.runtime is not SkillRuntime.PYTHON:
        raise ValueError("SDK Business Skill runtime must be python")
    if descriptor.provider is not None:
        raise ValueError("SDK V1 Python Business Skill cannot own an RPA provider")
    if (
        not _BUSINESS_SKILL_ID.fullmatch(descriptor.skill_id)
        or descriptor.skill_id.endswith(".py")
    ):
        raise ValueError("Business Skill ID must use stable dotted business syntax")
    if not issubclass(skill.input_model, BusinessSkillInput):
        raise ValueError("Business Skill input must extend BusinessSkillInput")
    if skill.input_model.model_config.get("extra") != "forbid":
        raise ValueError("Business Skill input must forbid extra fields")
    if not inspect.iscoroutinefunction(skill.run):
        raise ValueError("Business Skill run() must be async")
    if skill.timeout_seconds <= 0:
        raise ValueError("Business Skill timeout must be greater than zero")

    definition = SkillDefinition(
        skill_id=descriptor.skill_id,
        display_name=descriptor.display_name,
        version=descriptor.version,
        input_model=skill.input_model,
        runtime=descriptor.runtime,
        timeout_seconds=skill.timeout_seconds,
        provider=descriptor.provider,
        classification=descriptor.classification,
        business_skill=cast(BusinessSkill[Any], skill),
    )
    definition.descriptor()
    skill_registry.register(definition)
    return definition
