from typing import Protocol

from app.contracts import ExecutionResult, WorkerTask


class Executor(Protocol):
    async def execute(self, task: WorkerTask) -> ExecutionResult: ...
