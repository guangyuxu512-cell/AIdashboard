import asyncio
from collections.abc import Mapping
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.contracts import (
    ExecutionResult,
    ExecutionStatus,
    RuntimeEventType,
    WorkerTask,
)
from app.providers.yingdao import (
    YingdaoAdapter,
    YingdaoExecutionRequest,
    YingdaoExecutionResult,
    YingdaoExecutionStatus,
    YingdaoTriggerError,
)
from app.runtime import TaskRuntimeExistsError, TaskRuntimeManager, TaskRuntimePaths
from app.runtime_events import RuntimeEventBus
from app.skills.registry import SkillProvider, SkillRegistry, SkillRuntime


logger = logging.getLogger(__name__)


class RPAExecutor:
    def __init__(
        self,
        runtime_root: Path,
        registry: SkillRegistry,
        providers: Mapping[SkillProvider, YingdaoAdapter],
        event_bus: RuntimeEventBus | None = None,
        provider_app_ids: Mapping[str, str] | None = None,
    ) -> None:
        self.runtime = TaskRuntimeManager(runtime_root)
        self.registry = registry
        self.providers = providers
        self.event_bus = event_bus or RuntimeEventBus()
        self.provider_app_ids = provider_app_ids or {}
        self._provider_slots = {
            provider: asyncio.Semaphore(1) for provider in providers
        }
        self._deferred_provider_tasks: set[asyncio.Task[None]] = set()

    def can_claim(self) -> bool:
        """Keep new Tasks pending while a timed-out Provider is still active."""

        return all(not slot.locked() for slot in self._provider_slots.values())

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
        self.event_bus.emit(
            task.task_id,
            RuntimeEventType.STATUS,
            "RPA 任务正在准备执行",
            metadata={"phase": "queued"},
        )
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
        dynamic_app_id = task.input.get("app_id")
        provider_app_id = (
            str(dynamic_app_id)
            if dynamic_app_id is not None
            else self.provider_app_ids.get(task.skill_id) or definition.provider_app_id
        )
        if provider_app_id is None:
            return self._finish(
                paths,
                self._failure(
                    "RPA_APPLICATION_NOT_CONFIGURED",
                    "RPA Skill has no local application mapping",
                ),
            )
        if not any(
            app.app_id == provider_app_id
            for app in discovery.applications
        ):
            return self._finish(
                paths,
                self._failure(
                    "RPA_APPLICATION_NOT_FOUND",
                    "Mapped RPA application is not available",
                ),
            )
        application = next(
            app for app in discovery.applications if app.app_id == provider_app_id
        )
        request = YingdaoExecutionRequest(
            task_id=task.task_id,
            skill_id=task.skill_id,
            app_id=provider_app_id,
            app_name=application.app_name,
            user_id=discovery.user_id or "",
            params=(
                task.input.get("params", {})
                if isinstance(task.input.get("params", {}), dict)
                else {}
            ),
            runtime_directory=paths.directory,
        )
        slot = self._provider_slots[definition.provider]
        await slot.acquire()
        provider_task = asyncio.create_task(adapter.execute(request))
        cleanup_deferred = False
        try:
            raw_result = await asyncio.wait_for(
                asyncio.shield(provider_task),
                timeout=definition.timeout_seconds,
            )
        except TimeoutError:
            cleanup_deferred = True
            deferred = asyncio.create_task(
                self._drain_provider_execution(
                    provider_task,
                    adapter,
                    request,
                    slot,
                    paths.stderr,
                ),
            )
            self._deferred_provider_tasks.add(deferred)
            deferred.add_done_callback(self._deferred_provider_tasks.discard)
            return self._finish(
                paths,
                self._failure("RPA_TIMEOUT", "RPA execution timed out"),
            )
        except YingdaoTriggerError as error:
            return self._finish(
                paths,
                self._failure(error.code, error.message),
            )
        except Exception:
            return self._finish(
                paths,
                self._failure("RPA_TRIGGER_FAILED", "RPA application trigger failed"),
            )
        finally:
            if not cleanup_deferred:
                if not provider_task.done():
                    provider_task.cancel()
                    await asyncio.gather(provider_task, return_exceptions=True)
                await self._cleanup_provider(adapter, request, paths.stderr)
                slot.release()

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

    async def _drain_provider_execution(
        self,
        provider_task: asyncio.Task[Mapping[str, Any]],
        adapter: YingdaoAdapter,
        request: YingdaoExecutionRequest,
        slot: asyncio.Semaphore,
        stderr_path: Path,
    ) -> None:
        try:
            await provider_task
        except asyncio.CancelledError:
            provider_task.cancel()
            await asyncio.gather(provider_task, return_exceptions=True)
            raise
        except Exception as error:
            logger.warning(
                "Timed-out RPA provider finished with error type=%s",
                type(error).__name__,
            )
        finally:
            await self._cleanup_provider(adapter, request, stderr_path)
            slot.release()

    @staticmethod
    async def _cleanup_provider(
        adapter: YingdaoAdapter,
        request: YingdaoExecutionRequest,
        stderr_path: Path,
    ) -> None:
        try:
            await adapter.cleanup(request)
        except Exception as error:
            with stderr_path.open("a", encoding="utf-8") as stderr:
                stderr.write(f"RPA cleanup failed: {type(error).__name__}\n")

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
