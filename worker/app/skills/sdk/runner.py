from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import logging
import traceback
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.contracts import ExecutionResult, ExecutionStatus, SkillProcessInput
from app.runtime_events import RuntimeEventBus
from app.skills.registry import (
    SkillClassification,
    SkillDefinition,
    SkillRuntime,
)
from app.skills.sdk.contracts import (
    SkillContext,
    SkillContextPaths,
    SkillExecutionError,
    SkillResult,
)


logger = logging.getLogger(__name__)


class BusinessSkillRunner:
    def __init__(self, *, device_id: UUID, event_bus: RuntimeEventBus) -> None:
        self.device_id = device_id
        self.event_bus = event_bus

    async def execute(
        self,
        definition: SkillDefinition,
        process_input: SkillProcessInput,
    ) -> ExecutionResult:
        skill = definition.business_skill
        if (
            skill is None
            or definition.classification is not SkillClassification.BUSINESS
            or definition.runtime is not SkillRuntime.PYTHON
        ):
            return self._failure(
                "SKILL_RUNTIME_MISMATCH",
                "Skill cannot run through the Business Skill SDK",
            )
        try:
            validated_input = definition.input_model.model_validate(
                process_input.params,
            )
        except ValidationError:
            return self._failure(
                "SKILL_INPUT_INVALID",
                "Skill input does not match the local contract",
            )

        context = SkillContext(
            task_id=process_input.task_id,
            device_id=self.device_id,
            skill_id=process_input.skill_id,
            timeout_seconds=definition.timeout_seconds,
            deadline=datetime.now(UTC) + timedelta(seconds=definition.timeout_seconds),
            _event_bus=self.event_bus,
            accounts=[
                account.model_dump(mode="json")
                for account in process_input.accounts
            ],
            shop_ids=tuple(process_input.shop_ids or ()),
            paths=SkillContextPaths(images=process_input.paths.images),
        )
        try:
            result = await asyncio.wait_for(
                skill.run(context, validated_input),
                timeout=definition.timeout_seconds,
            )
            if not isinstance(result, SkillResult):
                return self._failure(
                    "SKILL_RESULT_INVALID",
                    "Skill returned an invalid result",
                )
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result.model_dump(mode="json"),
            )
        except TimeoutError:
            context._mark_cancelled()
            return self._failure("SKILL_TIMEOUT", "Skill execution timed out")
        except SkillExecutionError as error:
            context.log(
                "Business Skill reported an execution error",
                level="error",
                metadata={
                    "error_code": error.code,
                    "retryable": error.retryable,
                },
            )
            return self._failure(error.code, error.message)
        except asyncio.CancelledError:
            context._mark_cancelled()
            raise
        except Exception as error:
            safe_traceback = "\n".join(
                f'  File "{frame.filename}", line {frame.lineno}, in {frame.name}'
                for frame in traceback.extract_tb(error.__traceback__)
            )
            logger.error(
                "Unexpected Business Skill failure task=%s skill=%s type=%s\n%s",
                process_input.task_id,
                process_input.skill_id,
                type(error).__name__,
                safe_traceback,
            )
            context.log(
                "Business Skill failed unexpectedly",
                level="error",
                metadata={"error_code": "SKILL_EXECUTION_FAILED"},
            )
            return self._failure(
                "SKILL_EXECUTION_FAILED",
                "Skill execution failed",
            )

    @staticmethod
    def _failure(code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code=code,
            error_message=message,
        )
