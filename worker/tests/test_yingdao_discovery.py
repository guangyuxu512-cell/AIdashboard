import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import WorkerSettings
from app.contracts import ExecutionResult, ExecutionStatus, ProviderInventoryReport, WorkerTask
from app.executors.discovery import ProviderDiscoveryExecutor
from app.providers.yingdao import (
    YingdaoApplication,
    YingdaoDiscoveryService,
    YingdaoProcess,
    YingdaoProviderStatus,
    YingdaoRuntimeEndpoint,
    YingdaoSession,
    YingdaoSessionAccount,
    YingdaoSessionError,
)
from app.skills import registry
from app.skills.registry import SkillProvider
from app.worker import Worker


def session() -> YingdaoSession:
    return YingdaoSession(
        endpoint=YingdaoRuntimeEndpoint(
            process=YingdaoProcess(1234, Path("ShadowBot.Shell.exe"), "6.3.6"),
            base_url="http://127.0.0.1:42500",
        ),
        account=YingdaoSessionAccount(
            logged_in=True,
            user_name="GY00999",
            display_name="GY00999",
            user_id="906515367141965826",
            account_type="PersonalBasic",
            enterprise_name=None,
        ),
    )


class FakeSessionAdapter:
    def __init__(self, error: YingdaoSessionError | None = None) -> None:
        self.error = error
        self.calls = 0

    async def current(self, *, start_if_missing: bool = True) -> YingdaoSession:
        assert start_if_missing is True
        self.calls += 1
        if self.error:
            raise self.error
        return session()


class FakeApplicationAdapter:
    def __init__(self) -> None:
        self.calls = 0

    async def list(self, current: YingdaoSession) -> list[YingdaoApplication]:
        assert current.account.user_id == "906515367141965826"
        self.calls += 1
        return [
            YingdaoApplication(app_id="app-1", app_name="应用一", version_id="v1"),
            YingdaoApplication(app_id="app-2", app_name="应用二", version_id="v2"),
        ]


def create_service(error: YingdaoSessionError | None = None) -> YingdaoDiscoveryService:
    return YingdaoDiscoveryService(
        session_adapter=FakeSessionAdapter(error),  # type: ignore[arg-type]
        application_adapter=FakeApplicationAdapter(),  # type: ignore[arg-type]
    )


def test_636_discovery_uses_current_session_and_cloud_applications() -> None:
    result = asyncio.run(create_service().discover())

    assert result.status is YingdaoProviderStatus.READY
    assert result.provider_available is True
    assert result.provider_version == "6.3.6"
    assert result.account_display == "GY00999"
    assert result.user_id == "906515367141965826"
    assert [item.app_id for item in result.applications] == ["app-1", "app-2"]
    assert result.applications[0].version_id == "v1"


def test_discovery_does_not_read_local_user_database(tmp_path: Path) -> None:
    local_database = tmp_path / "users" / "other" / "user.db3"
    local_database.parent.mkdir(parents=True)
    local_database.write_text("ambiguous local cache", encoding="utf-8")

    result = asyncio.run(create_service().discover())

    assert result.status is YingdaoProviderStatus.READY
    assert result.account_display == "GY00999"


def test_expected_provider_states_are_inventory_not_worker_failures() -> None:
    cases = [
        ("YINGDAO_NOT_INSTALLED", YingdaoProviderStatus.NOT_INSTALLED),
        ("YINGDAO_VERSION_UNSUPPORTED", YingdaoProviderStatus.VERSION_UNSUPPORTED),
        ("YINGDAO_NOT_LOGGED_IN", YingdaoProviderStatus.NEED_LOGIN),
        ("YINGDAO_INTERFACE_UNREACHABLE", YingdaoProviderStatus.INTERFACE_UNREACHABLE),
    ]
    for code, expected_status in cases:
        result = asyncio.run(
            create_service(YingdaoSessionError(code, "fixture reason")).discover(),
        )
        assert result.status is expected_status
        assert result.provider_available is False
        assert result.status_reason_code == code
        assert result.applications == []


def test_discovery_executor_produces_generic_inventory_report(tmp_path: Path) -> None:
    executor = ProviderDiscoveryExecutor(
        tmp_path / "runtime",
        registry,
        {SkillProvider.YINGDAO: create_service()},
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
    assert result.provider_inventory.inventory["status"] == "ready"
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


def create_worker(tmp_path: Path, client: RecordingWorkerClient) -> tuple[Worker, WorkerTask]:
    settings = WorkerSettings(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="secret-token",
        runtime_root=tmp_path,
        lease_renew_interval_seconds=30,
    )
    worker = Worker(
        settings,
        client,  # type: ignore[arg-type]
        StubExecutor(
            ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={"provider": "yingdao"},
                provider_inventory=ProviderInventoryReport(
                    provider_code="yingdao",
                    inventory={"provider": "yingdao"},
                ),
            ),
        ),  # type: ignore[arg-type]
    )
    return worker, WorkerTask(
        task_id=uuid4(),
        skill_id="yingdao.discover",
        input={},
        lease_until=datetime.now(UTC),
    )


def test_worker_reports_inventory_before_completing_task(tmp_path: Path) -> None:
    client = RecordingWorkerClient()
    worker, task = create_worker(tmp_path, client)
    asyncio.run(worker._execute_task(task))
    assert client.events == ["heartbeat", "inventory", "complete", "heartbeat"]


def test_inventory_report_failure_fails_task_without_completing(tmp_path: Path) -> None:
    client = RecordingWorkerClient(inventory_failure=True)
    worker, task = create_worker(tmp_path, client)
    asyncio.run(worker._execute_task(task))
    assert client.events == [
        "heartbeat",
        "inventory",
        "fail:PROVIDER_INVENTORY_REPORT_FAILED",
        "heartbeat",
    ]
