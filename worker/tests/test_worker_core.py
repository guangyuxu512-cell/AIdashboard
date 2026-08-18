import asyncio
import json
from pathlib import Path
from uuid import uuid4

from app.config import WorkerSettings
from app.contracts import ExecutionStatus, WorkerTask
from app.executors.python import PythonExecutor
from app.skills.runner import execute


def test_worker_configuration_defaults() -> None:
    settings = WorkerSettings(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="secret-token",
    )
    assert settings.poll_interval_seconds == 3
    assert settings.heartbeat_interval_seconds == 15
    assert settings.lease_renew_interval_seconds == 20
    assert settings.device_token.get_secret_value() == "secret-token"


def test_python_process_runner_keeps_echo_sleep_and_blocks_unknown_skills() -> None:
    task_id = uuid4()
    echo = execute(
        "system.echo",
        {
            "task_id": str(task_id),
            "skill_id": "system.echo",
            "params": {"message": "hello"},
        },
    )
    sleep = execute(
        "system.sleep",
        {
            "task_id": str(task_id),
            "skill_id": "system.sleep",
            "params": {"seconds": 0.01},
        },
    )
    unknown = execute(
        "system.command",
        {
            "task_id": str(task_id),
            "skill_id": "system.command",
            "params": {"command": "whoami"},
        },
    )

    assert echo.status is ExecutionStatus.SUCCESS
    assert echo.result == {"message": "hello"}
    assert sleep.status is ExecutionStatus.SUCCESS
    assert sleep.result == {"slept_seconds": 0.01}
    assert unknown.status is ExecutionStatus.FAILED
    assert unknown.error_code == "SKILL_NOT_FOUND"


def test_python_executor_creates_isolated_runtime_files(tmp_path: Path) -> None:
    task = WorkerTask(
        task_id=uuid4(),
        skill_id="system.echo",
        input={"message": "hello"},
        lease_until="2026-08-19T12:00:00+00:00",
    )
    result = asyncio.run(PythonExecutor(tmp_path).execute(task))
    task_directory = tmp_path / str(task.task_id)

    assert result.status is ExecutionStatus.SUCCESS
    assert result.result == {"message": "hello"}
    assert (task_directory / "input.json").exists()
    assert (task_directory / "output.json").exists()
    assert (task_directory / "stdout.log").exists()
    assert (task_directory / "stderr.log").exists()
    assert (task_directory / "status.json").exists()
    assert (task_directory / "artifacts").is_dir()
    runtime_input = json.loads((task_directory / "input.json").read_text("utf-8"))
    assert runtime_input == {
        "task_id": str(task.task_id),
        "skill_id": "system.echo",
        "params": {"message": "hello"},
    }

    duplicate = asyncio.run(PythonExecutor(tmp_path).execute(task))
    assert duplicate.status is ExecutionStatus.FAILED
    assert duplicate.error_code == "RUNTIME_DIRECTORY_EXISTS"
