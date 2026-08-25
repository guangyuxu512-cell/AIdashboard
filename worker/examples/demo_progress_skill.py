"""SDK development template. This module is not imported by the production Registry."""

import asyncio

from pydantic import Field

from app.skills.registry import (
    SkillClassification,
    SkillDescriptor,
    SkillRegistry,
    SkillRuntime,
)
from app.skills.sdk import (
    BusinessSkillInput,
    SkillContext,
    SkillExecutionError,
    SkillResult,
    register_business_skill,
)


class DemoProgressInput(BusinessSkillInput):
    steps: int = Field(gt=0, le=100)
    fail_at: int | None = Field(default=None, gt=0, le=100)


class DemoProgressSkill:
    descriptor = SkillDescriptor(
        skill_id="demo.progress",
        display_name="SDK进度测试",
        runtime=SkillRuntime.PYTHON,
        provider=None,
        version="1",
        classification=SkillClassification.BUSINESS,
    )
    input_model = DemoProgressInput
    timeout_seconds = 30.0

    async def run(
        self,
        ctx: SkillContext,
        input: DemoProgressInput,
    ) -> SkillResult:
        accounts = ctx.accounts
        image_dir = ctx.paths.images
        ctx.log(
            "SDK Demo 已开始",
            metadata={
                "account_count": len(accounts),
                "images_directory_configured": bool(image_dir),
            },
        )
        for account in accounts:
            ctx.log(
                "SDK Demo 已取得店铺账号上下文",
                metadata={"shop_id": str(account["shop_id"])},
            )
        for current in range(1, input.steps + 1):
            if ctx.is_cancelled:
                raise SkillExecutionError(
                    "DEMO_CANCELLED",
                    "SDK Demo 已取消",
                    retryable=False,
                )
            if input.fail_at == current:
                raise SkillExecutionError(
                    "DEMO_EXPECTED_FAILURE",
                    "SDK Demo 按测试参数失败",
                    retryable=False,
                )
            await asyncio.sleep(0)
            ctx.progress(
                current=current,
                total=input.steps,
                message=f"已完成 {current}/{input.steps}",
            )
        return SkillResult(
            summary="SDK进度测试完成",
            data={"processed": input.steps},
        )


def register(registry: SkillRegistry) -> None:
    """Explicit test/dev registration; production never calls this function."""

    register_business_skill(registry, DemoProgressSkill())
