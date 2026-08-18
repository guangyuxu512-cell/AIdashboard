import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.contracts import ExecutionResult, WorkerTask


class TaskRuntimeExistsError(RuntimeError):
    """Raised when a Task runtime directory would overwrite an earlier run."""


@dataclass(frozen=True)
class TaskRuntimePaths:
    directory: Path
    input: Path
    status: Path
    output: Path
    stdout: Path
    stderr: Path
    artifacts: Path


class TaskRuntimeManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def prepare(self, task: WorkerTask) -> TaskRuntimePaths:
        directory = self.root / str(task.task_id)
        if directory.exists():
            raise TaskRuntimeExistsError(str(task.task_id))
        directory.mkdir(parents=True, exist_ok=False)
        paths = TaskRuntimePaths(
            directory=directory,
            input=directory / "input.json",
            status=directory / "status.json",
            output=directory / "output.json",
            stdout=directory / "stdout.log",
            stderr=directory / "stderr.log",
            artifacts=directory / "artifacts",
        )
        paths.artifacts.mkdir()
        paths.stdout.touch()
        paths.stderr.touch()
        self.write_json(
            paths.input,
            {
                "task_id": str(task.task_id),
                "skill_id": task.skill_id,
                "params": task.input,
            },
        )
        return paths

    def write_status(self, paths: TaskRuntimePaths, **payload: Any) -> None:
        self.write_json(paths.status, payload)

    def finish(self, paths: TaskRuntimePaths, result: ExecutionResult) -> None:
        payload = result.model_dump(mode="json")
        self.write_json(paths.output, payload)
        self.write_status(
            paths,
            status=result.status.value,
            error_code=result.error_code,
            error_message=result.error_message,
        )

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
