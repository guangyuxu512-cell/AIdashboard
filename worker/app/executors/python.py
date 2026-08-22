import asyncio
import sys
from pathlib import Path

from pydantic import ValidationError

from app.contracts import (
    ExecutionResult,
    ExecutionStatus,
    RuntimeEventType,
    WorkerTask,
)
from app.runtime import TaskRuntimeExistsError, TaskRuntimeManager, TaskRuntimePaths
from app.runtime_events import RuntimeEventBus
from app.skills import registry
from app.skills.registry import SkillRuntime


class PythonExecutor:
    def __init__(
        self,
        runtime_root: Path,
        event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self.runtime = TaskRuntimeManager(runtime_root)
        self.event_bus = event_bus or RuntimeEventBus()

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        definition = registry.get(task.skill_id)
        if definition is None:
            return self._failure(
                "SKILL_NOT_FOUND",
                "Skill is not registered on this Worker",
            )
        if definition.runtime is not SkillRuntime.PYTHON:
            return self._failure(
                "SKILL_RUNTIME_MISMATCH",
                "Skill is not registered for the Python runtime",
            )

        try:
            paths = self.runtime.prepare(task)
        except TaskRuntimeExistsError:
            return self._failure(
                "RUNTIME_DIRECTORY_EXISTS",
                "Task runtime directory already exists",
            )
        self.runtime.write_status(paths, status="running")
        self.event_bus.emit(
            task.task_id,
            RuntimeEventType.STATUS,
            "Python Skill 已开始执行",
            metadata={"provider": "python", "phase": "running"},
        )

        with (
            paths.stdout.open("wb") as stdout_file,
            paths.stderr.open("wb") as stderr_file,
        ):
            process = await asyncio.create_subprocess_exec(
                *build_skill_process_command(task, paths),
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
                return self._finish(
                    paths,
                    self._failure("SKILL_TIMEOUT", "Skill execution timed out"),
                )
            except asyncio.CancelledError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                raise

        if not paths.output.exists():
            return self._finish(
                paths,
                self._failure(
                    "SKILL_PROCESS_FAILED",
                    "Skill process exited without a result",
                ),
            )
        try:
            result = ExecutionResult.model_validate_json(
                paths.output.read_text(encoding="utf-8"),
            )
        except (OSError, ValidationError):
            result = self._failure(
                "SKILL_OUTPUT_INVALID",
                "Skill process returned an invalid result",
            )
        return self._finish(paths, result)

    def _finish(
        self,
        paths: TaskRuntimePaths,
        result: ExecutionResult,
    ) -> ExecutionResult:
        self.runtime.finish(paths, result)
        return result

    @staticmethod
    def _failure(code: str, message: str) -> ExecutionResult:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error_code=code,
            error_message=message,
        )


def build_skill_process_command(
    task: WorkerTask,
    paths: TaskRuntimePaths,
) -> list[str]:
    arguments = [task.skill_id, str(paths.input), str(paths.output)]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--skill-runner", *arguments]
    return [sys.executable, "-m", "app.skills.runner", *arguments]
