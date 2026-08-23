import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.contracts import ExecutionResult, ExecutionStatus, SkillProcessInput
from app.runtime_events import RuntimeEventBus
from app.skills import registry
from app.skills.registry import SkillClassification, SkillRegistry, SkillRuntime
from app.skills.sdk.process_events import ProcessRuntimeEventWriter
from app.skills.sdk.runner import BusinessSkillRunner


async def execute_async(
    skill_id: str,
    payload: dict[str, Any],
    *,
    device_id: UUID,
    event_bus: RuntimeEventBus | None = None,
    skill_registry: SkillRegistry = registry,
) -> ExecutionResult:
    definition = skill_registry.get(skill_id)
    if definition is None:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code="SKILL_NOT_FOUND",
            error_message="Skill is not registered on this Worker",
        )
    if definition.runtime is not SkillRuntime.PYTHON:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code="SKILL_RUNTIME_MISMATCH",
            error_message="Skill cannot run in the Python process runtime",
        )
    try:
        process_input = SkillProcessInput.model_validate(payload)
        if process_input.skill_id != skill_id:
            raise ValueError("Skill ID mismatch")
        if definition.classification is SkillClassification.BUSINESS:
            return await BusinessSkillRunner(
                device_id=device_id,
                event_bus=event_bus or RuntimeEventBus(),
            ).execute(definition, process_input)
        if definition.handler is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error_code="SKILL_RUNTIME_MISMATCH",
                error_message="Internal Skill has no local process handler",
            )
        skill_input = definition.input_model.model_validate(process_input.params)
        result = definition.handler(skill_input)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, result=result)
    except (ValidationError, ValueError):
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code="SKILL_INPUT_INVALID",
            error_message="Skill input does not match the local contract",
        )
    except Exception:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code="SKILL_EXECUTION_FAILED",
            error_message="Skill execution failed",
        )


def execute(
    skill_id: str,
    payload: dict[str, Any],
    *,
    device_id: UUID = UUID(int=0),
    event_bus: RuntimeEventBus | None = None,
    skill_registry: SkillRegistry = registry,
) -> ExecutionResult:
    """Synchronous helper used by the process entry point and focused tests."""

    return asyncio.run(
        execute_async(
            skill_id,
            payload,
            device_id=device_id,
            event_bus=event_bus,
            skill_registry=skill_registry,
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_id")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("device_id", type=UUID)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input_path.read_text(encoding="utf-8"))
        event_bus = RuntimeEventBus()
        event_bus.subscribe(ProcessRuntimeEventWriter())
        result = execute(
            args.skill_id,
            payload,
            device_id=args.device_id,
            event_bus=event_bus,
        )
    except (OSError, ValueError):
        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code="SKILL_INPUT_UNREADABLE",
            error_message="Skill process input could not be read",
        )
    args.output_path.write_text(
        result.model_dump_json(),
        encoding="utf-8",
    )
    return 0 if result.status is ExecutionStatus.SUCCESS else 1


if __name__ == "__main__":
    raise SystemExit(main())
