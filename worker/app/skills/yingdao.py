from pydantic import BaseModel, ConfigDict

from app.skills.registry import (
    SkillDefinition,
    SkillProvider,
    SkillRuntime,
    registry,
)


class YingdaoTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class YingdaoDiscoverInput(BaseModel):
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
registry.register(
    SkillDefinition(
        skill_id="yingdao.discover",
        input_model=YingdaoDiscoverInput,
        runtime=SkillRuntime.DISCOVERY,
        provider=SkillProvider.YINGDAO,
        timeout_seconds=60,
    ),
)
