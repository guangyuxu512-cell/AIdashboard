import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from app.contracts import (
    ExecutionResult,
    ExecutionStatus,
    ProviderInventoryReport,
    WorkerTask,
)
from app.providers.yingdao import (
    YingdaoDiscoveryError,
    YingdaoDiscoveryResult,
)
from app.runtime import TaskRuntimeExistsError, TaskRuntimeManager, TaskRuntimePaths
from app.skills.registry import SkillProvider, SkillRegistry, SkillRuntime


class ProviderDiscoveryService(Protocol):
    async def discover(self) -> YingdaoDiscoveryResult: ...


class ProviderDiscoveryExecutor:
    def __init__(
        self,
        runtime_root: Path,
        registry: SkillRegistry,
        providers: Mapping[SkillProvider, ProviderDiscoveryService],
    ) -> None:
        self.runtime = TaskRuntimeManager(runtime_root)
        self.registry = registry
        self.providers = providers

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        definition = self.registry.get(task.skill_id)
        if definition is None:
            return self._failure("SKILL_NOT_FOUND", "Skill is not registered")
        if (
            definition.runtime is not SkillRuntime.DISCOVERY
            or definition.provider is None
        ):
            return self._failure(
                "SKILL_RUNTIME_MISMATCH",
                "Skill is not registered for provider discovery",
            )
        try:
            definition.input_model.model_validate(task.input)
        except ValidationError:
            return self._failure(
                "SKILL_INPUT_INVALID",
                "Skill input does not match the local contract",
            )
        try:
            paths = self.runtime.prepare(task)
        except TaskRuntimeExistsError:
            return self._failure(
                "RUNTIME_DIRECTORY_EXISTS",
                "Task runtime directory already exists",
            )
        self.runtime.write_status(paths, status="running")

        service = self.providers.get(definition.provider)
        if service is None:
            return self._finish(
                paths,
                self._failure(
                    "PROVIDER_DISCOVERY_UNAVAILABLE",
                    "Provider discovery is not configured on this Worker",
                ),
            )
        try:
            inventory = await asyncio.wait_for(
                service.discover(),
                timeout=definition.timeout_seconds,
            )
        except TimeoutError:
            return self._finish(
                paths,
                self._failure(
                    "PROVIDER_DISCOVERY_TIMEOUT",
                    "Provider discovery timed out",
                ),
            )
        except YingdaoDiscoveryError as error:
            return self._finish(paths, self._failure(error.code, error.message))
        except Exception:
            return self._finish(
                paths,
                self._failure(
                    "PROVIDER_DISCOVERY_FAILED",
                    "Provider discovery failed",
                ),
            )

        payload = inventory.model_dump(mode="json", by_alias=True)
        result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            result=payload,
            provider_inventory=ProviderInventoryReport(
                provider_code=definition.provider.value,
                inventory=payload,
            ),
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
