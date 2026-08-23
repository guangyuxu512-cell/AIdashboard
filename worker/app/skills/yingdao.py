from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.skills.registry import (
    SkillClassification,
    SkillDefinition,
    SkillProvider,
    SkillRuntime,
    registry,
)


class YingdaoTestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class YingdaoDiscoverInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class YingdaoApplicationRunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(min_length=1, max_length=200)
    params: dict[str, Any] = Field(default_factory=dict)


registry.register(
    SkillDefinition(
        skill_id="yingdao.app.run",
        display_name="运行影刀应用",
        version="1",
        input_model=YingdaoApplicationRunInput,
        runtime=SkillRuntime.RPA,
        provider=SkillProvider.YINGDAO,
        provider_app_id=None,
        timeout_seconds=3600,
        classification=SkillClassification.INTERNAL,
    ),
)
registry.register(
    SkillDefinition(
        skill_id="yingdao.test",
        display_name="影刀测试",
        version="1",
        input_model=YingdaoTestInput,
        runtime=SkillRuntime.RPA,
        provider=SkillProvider.YINGDAO,
        provider_app_id=None,
        timeout_seconds=60,
        classification=SkillClassification.INTERNAL,
    ),
)
registry.register(
    SkillDefinition(
        skill_id="yingdao.discover",
        display_name="影刀能力发现",
        version="1",
        input_model=YingdaoDiscoverInput,
        runtime=SkillRuntime.DISCOVERY,
        provider=SkillProvider.YINGDAO,
        timeout_seconds=60,
        classification=SkillClassification.INTERNAL,
    ),
)
