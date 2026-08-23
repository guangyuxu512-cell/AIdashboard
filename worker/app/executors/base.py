from typing import Protocol

from app.contracts import ExecutionResult, WorkerTask


class Executor(Protocol):
    def can_claim(self) -> bool: ...

    async def execute(self, task: WorkerTask) -> ExecutionResult: ...
