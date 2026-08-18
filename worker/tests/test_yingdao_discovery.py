import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from app.config import WorkerSettings
from app.contracts import (
    ExecutionResult,
    ExecutionStatus,
    ProviderInventoryReport,
    WorkerTask,
)
from app.executors.discovery import ProviderDiscoveryExecutor
from app.providers.yingdao import YingdaoDiscoveryError, YingdaoDiscoveryService
from app.skills import registry
from app.skills.registry import SkillProvider
from app.worker import Worker


class StubYingdaoDiscoveryService(YingdaoDiscoveryService):
    def __init__(self, *args: Any, auth_data: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.auth_data = auth_data
        self.calls: list[tuple[str, ...]] = []

    async def _run_cli(self, cli_path: Path, *arguments: str) -> dict[str, Any]:
        self.calls.append(arguments)
        if arguments == ("system", "health"):
            return {"ok": True, "data": {"status": "ready"}}
        if arguments == ("auth", "current"):
            return {"ok": True, "data": self.auth_data}
        raise AssertionError(f"Unexpected CLI arguments: {arguments}")


def create_yingdao_fixture(tmp_path: Path) -> tuple[Path, Path, str]:
    install_root = tmp_path / "ShadowBot"
    install_root.mkdir()
    (install_root / "shadowbot.shell-cli.exe").touch()
    (install_root / "ShadowBot.exe").touch()

    user_id = "current-user-123"
    data_root = tmp_path / "local-data"
    user_directory = data_root / "users" / user_id
    user_directory.mkdir(parents=True)
    with sqlite3.connect(user_directory / "user.db3") as connection:
        connection.execute(
            "CREATE TABLE developmentsync_apps_v2 "
            "(uuid TEXT, name TEXT, isRecycleBin INTEGER, modifyTime INTEGER)",
        )
        connection.executemany(
            "INSERT INTO developmentsync_apps_v2 VALUES (?, ?, ?, ?)",
            [
                ("app-2", "应用二", 0, 2),
                ("app-recycled", "已回收", 1, 3),
                ("app-1", "应用一", 0, 1),
            ],
        )
    for app_id, app_name in (("app-1", "应用一"), ("app-2", "应用二")):
        package_directory = user_directory / "apps" / app_id / "xbot_robot"
        package_directory.mkdir(parents=True)
        (package_directory / "package.json").write_text(
            json.dumps(
                {
                    "uuid": app_id,
                    "name": app_name,
                    "version": "1",
                    "startup": "main",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return install_root, data_root, user_id


def create_service(
    tmp_path: Path,
    *,
    logged_in: bool = True,
) -> tuple[StubYingdaoDiscoveryService, str]:
    install_root, data_root, user_id = create_yingdao_fixture(tmp_path)
    service = StubYingdaoDiscoveryService(
        install_root=install_root,
        data_root=data_root,
        command_timeout_seconds=1,
        version_reader=lambda _: "6.2.23",
        auth_data={
            "loggedIn": logged_in,
            "displayName": "GY00999",
            "accountType": "PersonalBasic",
            "isEnterprise": False,
            "userId": user_id,
        },
    )
    return service, user_id


def test_discovery_reads_only_current_user_and_non_recycled_apps(
    tmp_path: Path,
) -> None:
    service, user_id = create_service(tmp_path)
    unrelated_user = service.data_root / "users" / "newest-but-not-current"
    unrelated_user.mkdir(parents=True)

    result = asyncio.run(service.discover())

    assert service.calls == [("system", "health"), ("auth", "current")]
    assert result.provider_version == "6.2.23"
    assert result.logged_in is True
    assert result.account_display == "GY00999"
    assert result.account_type == "PersonalBasic"
    assert result.enterprise_account is False
    assert result.user_id == user_id
    assert [application.app_id for application in result.applications] == [
        "app-2",
        "app-1",
    ]
    assert all(
        application.package_version == "1"
        and application.entrypoint == "main"
        for application in result.applications
    )


def test_discovery_reports_not_logged_in_without_scanning_users(
    tmp_path: Path,
) -> None:
    service, _ = create_service(tmp_path, logged_in=False)

    with pytest.raises(YingdaoDiscoveryError) as error:
        asyncio.run(service.discover())

    assert error.value.code == "YINGDAO_NOT_LOGGED_IN"
    assert service.calls == [("system", "health"), ("auth", "current")]


def test_discovery_fails_with_diagnostic_when_one_package_is_broken(
    tmp_path: Path,
) -> None:
    service, user_id = create_service(tmp_path)
    package_path = (
        service.data_root
        / "users"
        / user_id
        / "apps"
        / "app-2"
        / "xbot_robot"
        / "package.json"
    )
    package_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(YingdaoDiscoveryError) as error:
        asyncio.run(service.discover())

    assert error.value.code == "YINGDAO_PACKAGE_INVALID"
    assert "app-2" in error.value.message


def test_discovery_executor_produces_generic_inventory_report(tmp_path: Path) -> None:
    service, _ = create_service(tmp_path)
    executor = ProviderDiscoveryExecutor(
        tmp_path / "runtime",
        registry,
        {SkillProvider.YINGDAO: service},
    )
    task = WorkerTask(
        task_id=uuid4(),
        skill_id="yingdao.discover",
        input={},
        lease_until="2026-08-20T12:00:00+00:00",
    )

    result = asyncio.run(executor.execute(task))

    assert result.status is ExecutionStatus.SUCCESS
    assert result.provider_inventory is not None
    assert result.provider_inventory.provider_code == "yingdao"
    assert result.provider_inventory.inventory["available"] is True
    assert "provider_available" not in result.provider_inventory.inventory


class StubExecutor:
    def __init__(self, result: ExecutionResult) -> None:
        self.result = result

    async def execute(self, task: WorkerTask) -> ExecutionResult:
        return self.result


class RecordingWorkerClient:
    def __init__(self, *, inventory_failure: bool = False) -> None:
        self.inventory_failure = inventory_failure
        self.events: list[str] = []

    async def heartbeat(self, **kwargs: Any) -> None:
        self.events.append("heartbeat")

    async def renew(self, task_id: object) -> None:
        self.events.append("renew")

    async def report_provider_inventory(self, report: object) -> None:
        self.events.append("inventory")
        if self.inventory_failure:
            raise RuntimeError("inventory unavailable")

    async def complete(self, task_id: object, result: object) -> None:
        self.events.append("complete")

    async def fail(self, task_id: object, **kwargs: Any) -> None:
        self.events.append(f"fail:{kwargs['error_code']}")


def create_worker(
    tmp_path: Path,
    client: RecordingWorkerClient,
) -> tuple[Worker, WorkerTask]:
    settings = WorkerSettings(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="secret-token",
        runtime_root=tmp_path,
        lease_renew_interval_seconds=30,
    )
    report = ProviderInventoryReport(
        provider_code="yingdao",
        inventory={"provider": "yingdao"},
    )
    worker = Worker(
        settings,
        client,  # type: ignore[arg-type]
        StubExecutor(
            ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={"provider": "yingdao"},
                provider_inventory=report,
            ),
        ),  # type: ignore[arg-type]
    )
    task = WorkerTask(
        task_id=uuid4(),
        skill_id="yingdao.discover",
        input={},
        lease_until=datetime.now(UTC),
    )
    return worker, task


def test_worker_reports_inventory_before_completing_task(tmp_path: Path) -> None:
    client = RecordingWorkerClient()
    worker, task = create_worker(tmp_path, client)

    asyncio.run(worker._execute_task(task))

    assert client.events == ["heartbeat", "inventory", "complete", "heartbeat"]


def test_inventory_report_failure_fails_task_without_completing(
    tmp_path: Path,
) -> None:
    client = RecordingWorkerClient(inventory_failure=True)
    worker, task = create_worker(tmp_path, client)

    asyncio.run(worker._execute_task(task))

    assert client.events == [
        "heartbeat",
        "inventory",
        "fail:PROVIDER_INVENTORY_REPORT_FAILED",
        "heartbeat",
    ]
