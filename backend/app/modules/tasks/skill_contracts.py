from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskSkillId


class EchoSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=10_000)


class SleepSkillInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seconds: float = Field(gt=0, le=300)


SKILL_INPUT_MODELS: dict[TaskSkillId, type[BaseModel]] = {
    TaskSkillId.SYSTEM_ECHO: EchoSkillInput,
    TaskSkillId.SYSTEM_SLEEP: SleepSkillInput,
}


def validate_skill_input(
    skill_id: TaskSkillId,
    value: dict[str, Any],
) -> dict[str, Any]:
    return SKILL_INPUT_MODELS[skill_id].model_validate(value).model_dump(mode="json")
