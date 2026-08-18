import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.skills.registry import SkillDefinition, SkillRuntime, registry


class EchoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(max_length=10_000)


class SleepInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seconds: float = Field(gt=0, le=300)


def echo_skill(data: BaseModel) -> dict[str, Any]:
    value = EchoInput.model_validate(data.model_dump())
    return {"message": value.message}


def sleep_skill(data: BaseModel) -> dict[str, Any]:
    value = SleepInput.model_validate(data.model_dump())
    time.sleep(value.seconds)
    return {"slept_seconds": value.seconds}


registry.register(
    SkillDefinition(
        skill_id="system.echo",
        input_model=EchoInput,
        runtime=SkillRuntime.PYTHON,
        timeout_seconds=30,
        handler=echo_skill,
    ),
)
registry.register(
    SkillDefinition(
        skill_id="system.sleep",
        input_model=SleepInput,
        runtime=SkillRuntime.PYTHON,
        timeout_seconds=330,
        handler=sleep_skill,
    ),
)
