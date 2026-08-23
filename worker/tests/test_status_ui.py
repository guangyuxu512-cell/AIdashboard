import json
from pathlib import Path
from uuid import uuid4

from pydantic import SecretStr

from app.local_config import LocalWorkerConfig
from app.status_ui import (
    _render_diagnostics,
    _render_status,
    read_runtime_status,
    should_open_configuration,
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


def test_existing_032_configuration_skips_first_setup() -> None:
    legacy = LocalWorkerConfig(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token=SecretStr("ccw_existing"),
        device_display_name=None,
        yingdao_install_root=None,
        yingdao_data_root=None,
        yingdao_test_app_id=None,
        configured_at_utc=None,
    )

    assert should_open_configuration(legacy) is False


def test_status_and_diagnostics_render_the_runtime_snapshot_without_token() -> None:
    state = {
        "device_display_name": "PC-11",
        "device_id": "device-11",
        "worker_version": "0.4.0",
        "connection_status": "connected",
        "token_status": "valid",
        "last_heartbeat_at": "2026-08-23T12:00:00+00:00",
        "skill_sync_status": "synced",
        "skill_count": 5,
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
    assert diagnostics["token"] == "有效"
    assert diagnostics["skills"] == "已同步"
    assert "ccw_" not in json.dumps({**status, **diagnostics})
