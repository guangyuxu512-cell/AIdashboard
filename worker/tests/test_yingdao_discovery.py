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


def create_yingdao_fixture(
    tmp_path: Path,
    *,
    version: str = "6.2.23",
) -> tuple[Path, Path, str]:
    install_root = tmp_path / "ShadowBot"
    install_root.mkdir()
    (install_root / "ShadowBot.exe").touch()

    user_id = "906515367141965826"
    data_root = tmp_path / "local-data"
    user_directory = data_root / "users" / user_id
    user_directory.mkdir(parents=True)
    (user_directory / "username.ini").write_text("GY00999", encoding="utf-8")
    with sqlite3.connect(user_directory / "user.db3") as connection:
        connection.execute(
            "CREATE TABLE developmentsync_apps_v2 "
            "(uuid TEXT, name TEXT, ownerName TEXT, "
            "isRecycleBin INTEGER, modifyTime INTEGER)",
        )
        connection.executemany(
            "INSERT INTO developmentsync_apps_v2 VALUES (?, ?, ?, ?, ?)",
            [
                ("app-2", "应用二", "GY00999", 0, 2),
                ("app-recycled", "已回收", "GY00999", 1, 3),
                ("app-1", "应用一", "GY00999", 0, 1),
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
    (install_root / f"version-{version}").touch()
    return install_root, data_root, user_id


def create_service(
    tmp_path: Path,
    *,
    version: str = "6.2.23",
    selected_user_id: str | None = None,
) -> tuple[YingdaoDiscoveryService, str]:
    install_root, data_root, user_id = create_yingdao_fixture(
        tmp_path,
        version=version,
    )
    service = YingdaoDiscoveryService(
        install_root=install_root,
        data_root=data_root,
        user_id=selected_user_id,
        version_reader=lambda _: version,
    )
    return service, user_id


def test_6223_discovery_reads_local_current_user_and_non_recycled_apps(
    tmp_path: Path,
) -> None:
    service, user_id = create_service(tmp_path)
    unrelated_user = service.data_root / "users" / "901104047195107330"
    unrelated_user.mkdir(parents=True)
    (unrelated_user / "user.db3").touch()

    result = asyncio.run(service.discover())

    assert result.provider_version == "6.2.23"
    assert result.logged_in is True
    assert result.account_display == "GY00999"
    assert result.account_type is None
    assert result.enterprise_account is None
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


def test_discovery_uses_unique_database_owner_without_username_marker(
    tmp_path: Path,
) -> None:
    service, user_id = create_service(tmp_path)
    (service.data_root / "users" / user_id / "username.ini").unlink()

    result = asyncio.run(service.discover())

    assert result.user_id == user_id
    assert result.account_display == "GY00999"
    assert len(result.applications) == 2


def test_discovery_rejects_multiple_databases_without_current_account_marker(
    tmp_path: Path,
) -> None:
    service, user_id = create_service(tmp_path)
    (service.data_root / "users" / user_id / "username.ini").unlink()
    unrelated_user = service.data_root / "users" / "901104047195107330"
    unrelated_user.mkdir(parents=True)
    (unrelated_user / "user.db3").touch()

    with pytest.raises(YingdaoDiscoveryError) as error:
        asyncio.run(service.discover())

    assert error.value.code == "YINGDAO_ACCOUNT_AMBIGUOUS"


def test_discovery_uses_configured_account_with_multiple_unmarked_databases(
    tmp_path: Path,
) -> None:
    service, user_id = create_service(
        tmp_path,
        selected_user_id="906515367141965826",
    )
    (service.data_root / "users" / user_id / "username.ini").unlink()
    unrelated_user = service.data_root / "users" / "901104047195107330"
    unrelated_user.mkdir(parents=True)
    (unrelated_user / "user.db3").touch()

    result = asyncio.run(service.discover())

    assert result.user_id == user_id
    assert result.account_display == "GY00999"
    assert len(result.applications) == 2


def test_discovery_rejects_missing_configured_account(tmp_path: Path) -> None:
    service, _ = create_service(
        tmp_path,
        selected_user_id="901104047195107330",
    )

    with pytest.raises(YingdaoDiscoveryError) as error:
        asyncio.run(service.discover())

    assert error.value.code == "YINGDAO_ACCOUNT_NOT_FOUND"


def test_discovery_reports_not_logged_in_without_local_user_database(
    tmp_path: Path,
) -> None:
    service, _ = create_service(tmp_path)
    empty_data_root = tmp_path / "empty-local-data"
    (empty_data_root / "users").mkdir(parents=True)
    service.data_root = empty_data_root

    with pytest.raises(YingdaoDiscoveryError) as error:
        asyncio.run(service.discover())

    assert error.value.code == "YINGDAO_NOT_LOGGED_IN"


def test_636_discovery_ignores_unlogged_639_cli_and_starts_no_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, user_id = create_service(tmp_path, version="6.3.6")
    assert service.install_root is not None
    cli_directory = service.install_root / "shadowbot-6.3.9"
    cli_directory.mkdir()
    (cli_directory / "shadowbot.shell-cli.exe").touch()

    async def reject_process_start(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Discovery must not start the 6.3.9 CLI")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", reject_process_start)

    result = asyncio.run(service.discover())

    assert result.provider_version == "6.3.6"
    assert result.execution_available is True
    assert result.execution_version == "6.3.6"
    assert result.user_id == user_id
    assert len(result.applications) == 2


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
