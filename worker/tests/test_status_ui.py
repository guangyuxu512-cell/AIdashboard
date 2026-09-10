import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import SecretStr

from app.local_config import (
    DEFAULT_PRODUCTION_SERVER_URL,
    LocalWorkerConfig,
    WorkerConfigurationError,
)
from app.process_control import WorkerProcessInfo
from app.status_ui import (
    _render_diagnostics,
    _render_status,
    apply_provisioned_worker_configuration,
    read_runtime_status,
    should_open_configuration,
)


class _ConfigServiceStub:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.saved: dict[str, object] | None = None

    def save(self, **kwargs: object) -> LocalWorkerConfig:
        self.calls.append("save")
        self.saved = kwargs
        return LocalWorkerConfig(
            server_url=str(kwargs["server_url"]),
            device_id=kwargs["device_id"],  # type: ignore[arg-type]
            device_token=SecretStr(str(kwargs["device_token"])),
            device_display_name=kwargs["device_display_name"],  # type: ignore[arg-type]
            yingdao_install_root=kwargs["yingdao_install_root"],  # type: ignore[arg-type]
            yingdao_data_root=kwargs["yingdao_data_root"],  # type: ignore[arg-type]
            yingdao_test_app_id=kwargs["yingdao_test_app_id"],  # type: ignore[arg-type]
            params_json_path=kwargs["params_json_path"],  # type: ignore[arg-type]
            account_json_path=kwargs["account_json_path"],  # type: ignore[arg-type]
            images_dir=kwargs["images_dir"],  # type: ignore[arg-type]
            configured_at_utc=None,
        )


class _ProcessControllerStub:
    def __init__(
        self,
        calls: list[str],
        *,
        running: WorkerProcessInfo | None,
        stop_result: bool = True,
        start_result: WorkerProcessInfo | None = None,
    ) -> None:
        self.calls = calls
        self._running = running
        self.stop_result = stop_result
        self.start_result = start_result

    def running(self) -> WorkerProcessInfo | None:
        self.calls.append("running")
        return self._running

    def stop(self) -> bool:
        self.calls.append("stop")
        if self.stop_result:
            self._running = None
        return self.stop_result

    def start(self) -> WorkerProcessInfo | None:
        self.calls.append("start")
        self._running = self.start_result
        return self.start_result


def _process_info(device_id: UUID) -> WorkerProcessInfo:
    return WorkerProcessInfo(
        pid=1234,
        started_at_utc=datetime(2026, 9, 10, tzinfo=UTC),
        executable_path=Path("C:/worker/ecommerce-worker.exe"),
        device_id=device_id,
    )


def _apply_provisioned_identity(
    *,
    config_service: _ConfigServiceStub,
    process_controller: _ProcessControllerStub,
    current_task_id: object | None = None,
):
    return apply_provisioned_worker_configuration(
        config_service=config_service,  # type: ignore[arg-type]
        process_controller=process_controller,  # type: ignore[arg-type]
        current_task_id=current_task_id,
        server_url="https://119.29.188.118",
        device_id=UUID("0a4f2291-0000-4000-8000-000000000001"),
        device_token="test-worker-token",
        device_display_name="中控台设备",
        yingdao_install_root=Path("C:/ShadowBot"),
        yingdao_data_root=Path("C:/ShadowBot/data"),
        yingdao_test_app_id="app-1",
        params_json_path=Path("C:/worker/data/params.json"),
        account_json_path=Path("C:/worker/data/account.json"),
        images_dir=Path("C:/worker/data/images"),
    )


def test_tkinter_is_available_and_status_ui_reads_snapshot_only(
    tmp_path: Path,
) -> None:
    import tkinter

    assert tkinter.TkVersion > 0
    path = tmp_path / "runtime-status.json"
    path.write_text(
        json.dumps({"device_id": "device-a", "recent_events": []}),
        encoding="utf-8",
    )

    assert read_runtime_status(path)["device_id"] == "device-a"
    assert read_runtime_status(tmp_path / "missing.json") == {}
    assert should_open_configuration(None) is True
    assert DEFAULT_PRODUCTION_SERVER_URL == "https://119.29.188.118"


def test_existing_032_configuration_skips_first_setup() -> None:
    legacy = LocalWorkerConfig(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token=SecretStr("ccw_existing"),
        device_display_name=None,
        yingdao_install_root=None,
        yingdao_data_root=None,
        yingdao_test_app_id=None,
        params_json_path=Path("C:/worker/data/params.json"),
        account_json_path=Path("C:/worker/data/account.json"),
        images_dir=Path("C:/worker/data/images"),
        configured_at_utc=None,
    )

    assert should_open_configuration(legacy) is False


def test_reenrollment_stops_old_core_before_saving_new_provisioned_identity() -> None:
    calls: list[str] = []
    config_service = _ConfigServiceStub(calls)
    old_device_id = UUID("9b7644ca-0000-4000-8000-000000000001")
    new_device_id = UUID("0a4f2291-0000-4000-8000-000000000001")
    process_controller = _ProcessControllerStub(
        calls,
        running=_process_info(old_device_id),
        start_result=_process_info(new_device_id),
    )

    applied = _apply_provisioned_identity(
        config_service=config_service,
        process_controller=process_controller,
    )

    assert calls == ["running", "stop", "save", "start"]
    assert applied.core_running is True
    assert applied.config.device_id == new_device_id
    assert config_service.saved is not None
    assert config_service.saved["yingdao_data_root"] == Path("C:/ShadowBot/data")
    assert config_service.saved["params_json_path"] == Path("C:/worker/data/params.json")
    assert config_service.saved["account_json_path"] == Path("C:/worker/data/account.json")
    assert config_service.saved["images_dir"] == Path("C:/worker/data/images")


def test_reenrollment_preserves_old_identity_when_a_task_is_running() -> None:
    calls: list[str] = []
    config_service = _ConfigServiceStub(calls)
    process_controller = _ProcessControllerStub(
        calls,
        running=_process_info(UUID("9b7644ca-0000-4000-8000-000000000001")),
    )

    try:
        _apply_provisioned_identity(
            config_service=config_service,
            process_controller=process_controller,
            current_task_id="task-1",
        )
    except WorkerConfigurationError as error:
        assert "当前任务正在运行" in str(error)
    else:
        raise AssertionError("Expected active task to block identity switching")

    assert calls == []
    assert config_service.saved is None


def test_reenrollment_does_not_save_new_identity_when_old_core_wont_stop() -> None:
    calls: list[str] = []
    config_service = _ConfigServiceStub(calls)
    process_controller = _ProcessControllerStub(
        calls,
        running=_process_info(UUID("9b7644ca-0000-4000-8000-000000000001")),
        stop_result=False,
    )

    try:
        _apply_provisioned_identity(
            config_service=config_service,
            process_controller=process_controller,
        )
    except WorkerConfigurationError as error:
        assert "未能停止" in str(error)
    else:
        raise AssertionError("Expected failed old-Core stop to preserve configuration")

    assert calls == ["running", "stop"]
    assert config_service.saved is None


def test_reenrollment_stops_a_core_that_starts_with_the_wrong_identity() -> None:
    calls: list[str] = []
    config_service = _ConfigServiceStub(calls)
    process_controller = _ProcessControllerStub(
        calls,
        running=None,
        start_result=_process_info(UUID("9b7644ca-0000-4000-8000-000000000001")),
    )

    applied = _apply_provisioned_identity(
        config_service=config_service,
        process_controller=process_controller,
    )

    assert applied.core_running is False
    assert calls == ["running", "save", "start", "stop"]


def test_status_and_diagnostics_render_the_runtime_snapshot_without_token() -> None:
    state = {
        "device_display_name": "PC-11",
        "device_id": "device-11",
        "worker_version": "0.4.2",
        "connection_status": "connected",
        "token_status": "valid",
        "last_heartbeat_at": "2026-08-23T12:00:00+00:00",
        "updated_at": "2026-08-23T12:00:00+00:00",
        "skill_sync_status": "synced",
        "skill_count": 5,
        "business_skill_count": 0,
        "provider_status": "ready",
        "provider_version": "6.3.6",
        "provider_account": "GY00999",
        "provider_application_count": 10,
        "provider_refreshed_at": "2026-08-23T12:00:00+00:00",
        "skill_display_name": "运行影刀应用",
        "app_name": "原子模式单店模式",
        "current_task_id": "task-1",
        "started_at": "2026-08-23T12:00:00+00:00",
    }

    status = _render_status(state, running=True)
    diagnostics = _render_diagnostics(state, running=True)

    assert status["current_task"] == "原子模式单店模式 · 执行中"
    assert status["provider_version"] == "6.3.6"
    assert status["business_skill_count"] == "0"
    assert "5" not in status["business_skill_count"]
    assert diagnostics["token"] == "有效"
    assert diagnostics["skills"] == "已同步"
    assert "ccw_" not in json.dumps({**status, **diagnostics})


def test_diagnostics_include_local_input_path_health_without_contents() -> None:
    diagnostics = _render_diagnostics(
        {},
        running=False,
        local_inputs={
            "params_json": "可写",
            "account_json": "不可写",
            "images_dir": "未创建",
        },
    )

    assert diagnostics["params_json"] == "可写"
    assert diagnostics["account_json"] == "不可写"
    assert diagnostics["images_dir"] == "未创建"
    assert "credential-secret" not in json.dumps(
        diagnostics,
        ensure_ascii=False,
    )


def test_heartbeat_and_core_health_use_timestamp_freshness() -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    state = {
        "connection_status": "connected",
        "token_status": "valid",
        "last_heartbeat_at": (now - timedelta(seconds=5)).isoformat(),
        "updated_at": (now - timedelta(seconds=5)).isoformat(),
    }

    recent = _render_status(state, running=True, now=now)
    recent_diagnostics = _render_diagnostics(state, running=True, now=now)

    assert recent["connection_status"] == "已连接"
    assert recent["last_heartbeat"] == "5 秒前"
    assert recent["worker_status"] == "运行中"
    assert recent_diagnostics["backend"] == "正常"
    assert recent_diagnostics["heartbeat"] == "正常 · 5 秒前"

    state["last_heartbeat_at"] = (now - timedelta(seconds=46)).isoformat()
    stale = _render_status(state, running=True, now=now)
    stale_diagnostics = _render_diagnostics(state, running=True, now=now)

    assert stale["connection_status"] == "连接异常"
    assert stale["last_heartbeat"] == "46 秒前"
    assert stale_diagnostics["backend"] == "异常"
    assert stale_diagnostics["heartbeat"] == "已过期 · 46 秒前"

    state["last_heartbeat_at"] = now.isoformat()
    recovered = _render_status(state, running=True, now=now)

    assert recovered["connection_status"] == "已连接"
    assert recovered["last_heartbeat"] == "刚刚"


def test_running_core_with_stale_snapshot_is_reported_as_abnormal() -> None:
    now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
    state = {
        "last_heartbeat_at": now.isoformat(),
        "updated_at": (now - timedelta(seconds=91)).isoformat(),
        "token_status": "valid",
    }

    status = _render_status(state, running=True, now=now)
    diagnostics = _render_diagnostics(state, running=True, now=now)

    assert status["worker_status"] == "状态异常"
    assert diagnostics["process"] == "状态异常"
