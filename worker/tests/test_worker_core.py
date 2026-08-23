import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import httpx
from pydantic import BaseModel

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.contracts import (
    ExecutionResult,
    ExecutionStatus,
    SkillCapabilitySnapshot,
    WorkerTask,
)
from app.executors.python import PythonExecutor, build_skill_process_command
from app.runtime import TaskRuntimePaths
from app.single_instance import WorkerAlreadyRunningError, WorkerSingleInstance
from app.skills.runner import execute
from app.skills import SkillDefinition, SkillRegistry, registry
from app.skills.registry import SkillClassification, SkillRuntime
from app.worker import Worker


def test_worker_configuration_defaults() -> None:
    settings = WorkerSettings(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="secret-token",
    )
    assert settings.poll_interval_seconds == 3
    assert settings.heartbeat_interval_seconds == 15
    assert settings.lease_renew_interval_seconds == 20
    assert settings.log_max_bytes == 5 * 1024 * 1024
    assert settings.log_backup_count == 5
    assert settings.device_token.get_secret_value() == "secret-token"


def test_skill_descriptors_keep_stable_cross_system_metadata() -> None:
    descriptors = {item.skill_id: item for item in registry.descriptors()}

    assert set(descriptors) == {
        "system.echo",
        "system.sleep",
        "yingdao.test",
        "yingdao.discover",
        "yingdao.app.run",
    }
    assert descriptors["system.echo"].model_dump() == {
        "skill_id": "system.echo",
        "display_name": "Echo",
        "runtime": "python",
        "provider": None,
        "version": "1",
        "classification": "internal",
    }
    assert descriptors["yingdao.discover"].model_dump() == {
        "skill_id": "yingdao.discover",
        "display_name": "影刀能力发现",
        "runtime": "discovery",
        "provider": "yingdao",
        "version": "1",
        "classification": "internal",
    }
    assert all(
        descriptor.classification is SkillClassification.INTERNAL
        for descriptor in descriptors.values()
    )


def test_new_skill_definition_defaults_to_business_classification() -> None:
    descriptor = build_snapshot_registry("refund.sync").descriptors()[0]

    assert descriptor.classification is SkillClassification.BUSINESS


class CapabilityRecordingClient:
    def __init__(self) -> None:
        self.heartbeat_error: Exception | None = None
        self.snapshots: list[list[str]] = []

    async def heartbeat(self, **_: object) -> None:
        if self.heartbeat_error is not None:
            raise self.heartbeat_error

    async def report_skill_capabilities(self, snapshot: object) -> None:
        self.snapshots.append([skill.skill_id for skill in snapshot.skills])


class UnusedExecutor:
    async def execute(self, task: WorkerTask) -> ExecutionResult:
        del task
        return ExecutionResult(status=ExecutionStatus.SUCCESS)


def build_snapshot_registry(*skill_ids: str) -> SkillRegistry:
    snapshot_registry = SkillRegistry()
    for skill_id in skill_ids:
        snapshot_registry.register(
            SkillDefinition(
                skill_id=skill_id,
                display_name=skill_id,
                version="1",
                input_model=BaseModel,
                runtime=SkillRuntime.PYTHON,
                timeout_seconds=30,
                handler=lambda _: {},
            ),
        )
    return snapshot_registry


def test_worker_syncs_registry_snapshot_on_start_and_reconnect() -> None:
    client = CapabilityRecordingClient()
    settings = WorkerSettings(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="secret-token",
    )
    worker = Worker(
        settings,
        client,  # type: ignore[arg-type]
        UnusedExecutor(),
        skill_registry=build_snapshot_registry("system.echo", "system.sleep"),
    )

    asyncio.run(worker._heartbeat_once())
    asyncio.run(worker._heartbeat_once())
    assert client.snapshots == [["system.echo", "system.sleep"]]

    client.heartbeat_error = RuntimeError("offline")
    asyncio.run(worker._heartbeat_once())
    client.heartbeat_error = None
    asyncio.run(worker._heartbeat_once())
    assert client.snapshots == [
        ["system.echo", "system.sleep"],
        ["system.echo", "system.sleep"],
    ]


def test_worker_capability_payload_uses_authenticated_device_headers() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["path"] = request.url.path
        observed["device_id"] = request.headers.get("X-Device-ID")
        observed["authorization"] = request.headers.get("Authorization")
        observed["payload"] = json.loads(request.content)
        return httpx.Response(200, json=[])

    settings = WorkerSettings(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="secret-token",
    )
    http_client = httpx.AsyncClient(
        base_url="https://control.example.test",
        transport=httpx.MockTransport(handler),
        headers={
            "Authorization": "Bearer secret-token",
            "X-Device-ID": str(settings.device_id),
        },
    )
    client = WorkerApiClient(settings, http_client)
    asyncio.run(
        client.report_skill_capabilities(
            SkillCapabilitySnapshot(skills=list(registry.descriptors())),
        ),
    )
    asyncio.run(http_client.aclose())

    assert observed["path"] == "/api/v1/worker/skill-capabilities"
    assert observed["device_id"] == str(settings.device_id)
    assert observed["authorization"] == "Bearer secret-token"
    payload = observed["payload"]
    assert isinstance(payload, dict)
    assert "device_id" not in payload
    assert {skill["skill_id"] for skill in payload["skills"]} == {
        "system.echo",
        "system.sleep",
        "yingdao.app.run",
        "yingdao.test",
        "yingdao.discover",
    }
    assert {skill["classification"] for skill in payload["skills"]} == {
        "internal",
    }


def test_worker_snapshot_after_upgrade_contains_only_current_registry_skills() -> None:
    client = CapabilityRecordingClient()
    settings = WorkerSettings(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="secret-token",
    )
    before_upgrade = Worker(
        settings,
        client,  # type: ignore[arg-type]
        UnusedExecutor(),
        skill_registry=build_snapshot_registry("system.echo", "removed.skill"),
    )
    after_upgrade = Worker(
        settings,
        client,  # type: ignore[arg-type]
        UnusedExecutor(),
        skill_registry=build_snapshot_registry("system.echo"),
    )

    asyncio.run(before_upgrade._heartbeat_once())
    asyncio.run(after_upgrade._heartbeat_once())
    assert client.snapshots == [
        ["system.echo", "removed.skill"],
        ["system.echo"],
    ]


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


def test_frozen_python_executor_reenters_the_packaged_skill_runner(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    task = WorkerTask(
        task_id=uuid4(),
        skill_id="system.echo",
        input={"message": "packaged"},
        lease_until="2026-08-19T12:00:00+00:00",
    )
    paths = TaskRuntimePaths(
        directory=tmp_path,
        input=tmp_path / "input.json",
        status=tmp_path / "status.json",
        output=tmp_path / "output.json",
        stdout=tmp_path / "stdout.log",
        stderr=tmp_path / "stderr.log",
        artifacts=tmp_path / "artifacts",
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)  # type: ignore[attr-defined]

    command = build_skill_process_command(task, paths)

    assert command == [
        sys.executable,
        "--skill-runner",
        "system.echo",
        str(paths.input),
        str(paths.output),
    ]


@pytest.mark.skipif(os.name != "nt", reason="Windows named mutex")
def test_windows_mutex_blocks_the_same_device_identity() -> None:
    device_id = uuid4()

    with WorkerSingleInstance(device_id):
        with pytest.raises(WorkerAlreadyRunningError):
            with WorkerSingleInstance(device_id):
                pass
