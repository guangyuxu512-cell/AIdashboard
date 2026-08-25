import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from app.contracts import (
    ExecutionResult,
    ExecutionStatus,
    RuntimeEventType,
    SkillProcessInput,
    SkillProcessPaths,
    WorkerTask,
)
from app.local_input import LocalInputPreparationError, ensure_images_directory
from app.runtime import TaskRuntimeExistsError, TaskRuntimeManager, TaskRuntimePaths
from app.runtime_events import RuntimeEventBus
from app.skills import SkillRegistry, registry
from app.skills.registry import SkillRuntime
from app.skills.sdk.process_events import decode_process_event_line


logger = logging.getLogger(__name__)


class PythonExecutor:
    def __init__(
        self,
        runtime_root: Path,
        event_bus: RuntimeEventBus | None = None,
        *,
        device_id: UUID,
        images_dir: Path,
        skill_registry: SkillRegistry = registry,
    ) -> None:
        self.runtime = TaskRuntimeManager(runtime_root)
        self.event_bus = event_bus or RuntimeEventBus()
        self.device_id = device_id
        self.images_dir = images_dir.resolve()
        self.registry = skill_registry

    def can_claim(self) -> bool:
        return True

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        definition = self.registry.get(task.skill_id)
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
        try:
            ensure_images_directory(self.images_dir)
        except LocalInputPreparationError as error:
            return self._finish(
                paths,
                self._failure(error.code, error.message),
            )
        self.runtime.write_json(
            paths.input,
            SkillProcessInput(
                task_id=task.task_id,
                skill_id=task.skill_id,
                params=task.input,
                accounts=task.accounts,
                paths=SkillProcessPaths(images=self.images_dir),
            ).model_dump(mode="json"),
        )
        self.runtime.write_status(paths, status="running")
        self.event_bus.emit(
            task.task_id,
            RuntimeEventType.STATUS,
            "Python Skill 已开始执行",
            metadata={"provider": "python", "phase": "running"},
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *build_skill_process_command(task, paths, self.device_id),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError:
            return self._finish(
                paths,
                self._failure(
                    "SKILL_PROCESS_START_FAILED",
                    "Skill process could not be started",
                ),
            )

        assert process.stdout is not None
        assert process.stderr is not None
        stdout_task = asyncio.create_task(
            self._forward_stdout(process.stdout, paths.stdout, task),
        )
        stderr_task = asyncio.create_task(
            self._forward_stream(process.stderr, paths.stderr),
        )
        timed_out = False
        process_timeout = definition.timeout_seconds + (
            1.0 if definition.business_skill is not None else 0.0
        )
        try:
            try:
                await asyncio.wait_for(
                    process.wait(),
                    timeout=process_timeout,
                )
            except TimeoutError:
                process.kill()
                await process.wait()
                timed_out = True
            except asyncio.CancelledError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                raise
        finally:
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

        if timed_out:
            return self._finish(
                paths,
                self._failure("SKILL_TIMEOUT", "Skill execution timed out"),
            )

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

    async def _forward_stdout(
        self,
        stream: asyncio.StreamReader,
        path: Path,
        task: WorkerTask,
    ) -> None:
        with path.open("ab") as output:
            while line := await stream.readline():
                try:
                    event = decode_process_event_line(line)
                except (ValidationError, ValueError):
                    logger.warning(
                        "Python Skill process emitted an invalid runtime event task=%s",
                        task.task_id,
                    )
                    output.write(line)
                    output.flush()
                    continue
                if event is None:
                    output.write(line)
                    output.flush()
                    continue
                if event.task_id != task.task_id:
                    logger.warning(
                        "Python Skill process event Task ID mismatch task=%s",
                        task.task_id,
                    )
                    continue
                self.event_bus.emit(
                    task.task_id,
                    event.event_type,
                    event.message,
                    level=event.level,
                    event_at=event.event_at,
                    metadata=event.metadata,
                )

    @staticmethod
    async def _forward_stream(stream: asyncio.StreamReader, path: Path) -> None:
        with path.open("ab") as output:
            while chunk := await stream.read(64 * 1024):
                output.write(chunk)
                output.flush()

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
    device_id: UUID,
) -> list[str]:
    arguments = [
        task.skill_id,
        str(paths.input),
        str(paths.output),
        str(device_id),
    ]
    if getattr(sys, "frozen", False):
        return [sys.executable, "--skill-runner", *arguments]
    return [sys.executable, "-m", "app.skills.runner", *arguments]
