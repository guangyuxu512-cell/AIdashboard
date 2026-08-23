from collections.abc import Mapping

from app.contracts import ExecutionResult, ExecutionStatus, WorkerTask
from app.executors.base import Executor
from app.skills.registry import SkillRegistry, SkillRuntime


class ExecutorRouter:
    def __init__(
        self,
        registry: SkillRegistry,
        executors: Mapping[SkillRuntime, Executor],
    ) -> None:
        self.registry = registry
        self.executors = executors

    def can_claim(self) -> bool:
        return all(executor.can_claim() for executor in self.executors.values())

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        definition = self.registry.get(task.skill_id)
        if definition is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error_code="SKILL_NOT_FOUND",
                error_message="Skill is not registered on this Worker",
            )
        executor = self.executors.get(definition.runtime)
        if executor is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error_code="SKILL_RUNTIME_UNAVAILABLE",
                error_message="Skill runtime is unavailable on this Worker",
            )
        return await executor.execute(task)
