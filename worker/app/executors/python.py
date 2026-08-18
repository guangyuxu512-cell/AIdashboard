import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.skills import registry


class PythonExecutor:
    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root.resolve()

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        definition = registry.get(task.skill_id)
        if definition is None:
            return self._failure(
                "SKILL_NOT_FOUND",
                "Skill is not registered on this Worker",
            )

        task_directory = self.runtime_root / str(task.task_id)
        if task_directory.exists():
            return self._failure(
                "RUNTIME_DIRECTORY_EXISTS",
                "Task runtime directory already exists",
            )
        task_directory.mkdir(parents=True, exist_ok=False)
        input_path = task_directory / "input.json"
        output_path = task_directory / "output.json"
        stdout_path = task_directory / "stdout.log"
        stderr_path = task_directory / "stderr.log"
        input_path.write_text(
            json.dumps(
                {"task_id": str(task.task_id), "params": task.input},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with (
            stdout_path.open("wb") as stdout_file,
            stderr_path.open("wb") as stderr_file,
        ):
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "app.skills.runner",
                task.skill_id,
                str(input_path),
                str(output_path),
                stdout=stdout_file,
                stderr=stderr_file,
            )
            try:
                await asyncio.wait_for(
                    process.wait(),
                    timeout=definition.timeout_seconds,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                return self._failure("SKILL_TIMEOUT", "Skill execution timed out")
            except asyncio.CancelledError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                raise

        if not output_path.exists():
            return self._failure(
                "SKILL_PROCESS_FAILED",
                "Skill process exited without a result",
            )
        try:
            return ExecutionResult.model_validate_json(
                output_path.read_text(encoding="utf-8"),
            )
        except (OSError, ValidationError):
            return self._failure(
                "SKILL_OUTPUT_INVALID",
                "Skill process returned an invalid result",
            )

    @staticmethod
    def _failure(code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code=code,
            error_message=message,
        )
