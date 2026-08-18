import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.contracts import ExecutionResult, ExecutionStatus, SkillProcessInput
from app.skills import registry


def execute(skill_id: str, payload: dict[str, Any]) -> ExecutionResult:
    definition = registry.get(skill_id)
    if definition is None:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code="SKILL_NOT_FOUND",
            error_message="Skill is not registered on this Worker",
        )
    try:
        process_input = SkillProcessInput.model_validate(payload)
        skill_input = definition.input_model.model_validate(process_input.params)
        result = definition.handler(skill_input)
        return ExecutionResult(status=ExecutionStatus.SUCCESS, result=result)
    except ValidationError:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_id")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input_path.read_text(encoding="utf-8"))
        result = execute(args.skill_id, payload)
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
