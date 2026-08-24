from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskSkillId
from app.modules.workers.business_skill_schema import (
    normalize_business_skill_input,
)


class EchoSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=10_000)


class SleepSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seconds: float = Field(gt=0, le=300)


class YingdaoTestSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class YingdaoDiscoverSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class YingdaoApplicationRunSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(min_length=1, max_length=200)
    params: dict[str, Any] = Field(default_factory=dict)


SKILL_INPUT_MODELS: dict[TaskSkillId, type[BaseModel]] = {
    TaskSkillId.SYSTEM_ECHO: EchoSkillInput,
    TaskSkillId.SYSTEM_SLEEP: SleepSkillInput,
    TaskSkillId.YINGDAO_TEST: YingdaoTestSkillInput,
    TaskSkillId.YINGDAO_DISCOVER: YingdaoDiscoverSkillInput,
    TaskSkillId.YINGDAO_APP_RUN: YingdaoApplicationRunSkillInput,
}


def validate_skill_input(
    skill_id: str | TaskSkillId,
    value: dict[str, Any],
    *,
    classification: str | None = None,
    input_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        known_skill_id = TaskSkillId(skill_id)
    except ValueError:
        known_skill_id = None
    if known_skill_id is not None:
        return (
            SKILL_INPUT_MODELS[known_skill_id]
            .model_validate(value)
            .model_dump(mode="json")
        )
    if classification == "business":
        return normalize_business_skill_input(input_schema, value)
    return normalize_business_skill_input(None, value)
