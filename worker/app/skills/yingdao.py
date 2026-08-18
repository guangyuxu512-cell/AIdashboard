from pydantic import BaseModel, ConfigDict

from app.skills.registry import (
    SkillDefinition,
    SkillProvider,
    SkillRuntime,
    registry,
)


class YingdaoTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


registry.register(
    SkillDefinition(
        skill_id="yingdao.test",
        input_model=YingdaoTestInput,
        runtime=SkillRuntime.RPA,
        provider=SkillProvider.YINGDAO,
        provider_app_id=None,
        timeout_seconds=60,
    ),
)
