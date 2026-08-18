import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.providers.yingdao import (
    YingdaoAdapter,
    YingdaoExecutionRequest,
    YingdaoExecutionResult,
    YingdaoExecutionStatus,
    YingdaoTriggerError,
)
from app.runtime import TaskRuntimeExistsError, TaskRuntimeManager, TaskRuntimePaths
from app.skills.registry import SkillProvider, SkillRegistry, SkillRuntime


class RPAExecutor:
    def __init__(
        self,
        runtime_root: Path,
        registry: SkillRegistry,
        providers: Mapping[SkillProvider, YingdaoAdapter],
    ) -> None:
        self.runtime = TaskRuntimeManager(runtime_root)
        self.registry = registry
        self.providers = providers

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        definition = self.registry.get(task.skill_id)
        if definition is None:
            return self._failure("SKILL_NOT_FOUND", "Skill is not registered")
        if definition.runtime is not SkillRuntime.RPA or definition.provider is None:
            return self._failure(
                "SKILL_RUNTIME_MISMATCH",
                "Skill is not registered for the RPA runtime",
            )
        try:
            paths = self.runtime.prepare(task)
        except TaskRuntimeExistsError:
            return self._failure(
                "RUNTIME_DIRECTORY_EXISTS",
                "Task runtime directory already exists",
            )

        self.runtime.write_status(paths, status="running")
        adapter = self.providers.get(definition.provider)
        request: YingdaoExecutionRequest | None = None
        if adapter is None:
            return self._finish(
                paths,
                self._failure(
                    "RPA_PROVIDER_UNAVAILABLE",
                    "RPA provider is not configured on this Worker",
                ),
            )

        try:
            discovery = await adapter.discover()
        except Exception:
            return self._finish(
                paths,
                self._failure(
                    "RPA_PROVIDER_UNAVAILABLE",
                    "RPA provider discovery failed",
                ),
            )
        if not discovery.provider_available:
            return self._finish(
                paths,
                self._failure(
                    "RPA_PROVIDER_UNAVAILABLE",
                    "RPA provider is unavailable on this Worker",
                ),
            )
        if definition.provider_app_id is None:
            return self._finish(
                paths,
                self._failure(
                    "RPA_APPLICATION_NOT_CONFIGURED",
                    "RPA Skill has no local application mapping",
                ),
            )
        if not any(
            app.app_id == definition.provider_app_id
            for app in discovery.applications
        ):
            return self._finish(
                paths,
                self._failure(
                    "RPA_APPLICATION_NOT_FOUND",
                    "Mapped RPA application is not available",
                ),
            )
        request = YingdaoExecutionRequest(
            task_id=task.task_id,
            skill_id=task.skill_id,
            app_id=definition.provider_app_id,
            params=task.input,
            runtime_directory=paths.directory,
        )
        try:
            raw_result = await asyncio.wait_for(
                adapter.execute(request),
                timeout=definition.timeout_seconds,
            )
        except TimeoutError:
            return self._finish(
                paths,
                self._failure("RPA_TIMEOUT", "RPA execution timed out"),
            )
        except YingdaoTriggerError:
            return self._finish(
                paths,
                self._failure("RPA_TRIGGER_FAILED", "RPA application trigger failed"),
            )
        except Exception:
            return self._finish(
                paths,
                self._failure("RPA_TRIGGER_FAILED", "RPA application trigger failed"),
            )
        finally:
            try:
                await adapter.cleanup(request)
            except Exception as error:
                with paths.stderr.open("a", encoding="utf-8") as stderr:
                    stderr.write(f"RPA cleanup failed: {type(error).__name__}\n")

        try:
            provider_result = YingdaoExecutionResult.model_validate(raw_result)
        except ValidationError:
            return self._finish(
                paths,
                self._failure(
                    "RPA_RESULT_INVALID",
                    "RPA provider returned an invalid result",
                ),
            )
        return self._finish(paths, self._map_result(provider_result))

    def _map_result(self, result: YingdaoExecutionResult) -> ExecutionResult:
        if result.status is YingdaoExecutionStatus.SUCCESS:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result.result or {},
            )
        if result.status is YingdaoExecutionStatus.FAILED:
            return self._failure(
                "RPA_EXECUTION_FAILED",
                result.error_message or "RPA execution failed",
            )
        return self._failure(
            "RPA_RESULT_INVALID",
            "RPA provider returned a non-terminal result",
        )

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
