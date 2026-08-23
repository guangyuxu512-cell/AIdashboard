from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.tasks.enums import TaskSkillId


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
    skill_id: TaskSkillId,
    value: dict[str, Any],
) -> dict[str, Any]:
    return SKILL_INPUT_MODELS[skill_id].model_validate(value).model_dump(mode="json")
