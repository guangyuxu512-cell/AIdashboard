import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.local_config import (
    LocalInputPaths,
    WindowsDpapiTokenProtector,
    WorkerConfigService,
    WorkerConfigurationError,
    WorkerConfigurationMissingError,
    get_default_local_input_paths,
    inspect_local_input_paths,
)


class ReversingProtector:
    def protect(self, value: str) -> str:
        return value[::-1]

    def unprotect(self, value: str) -> str:
        return value[::-1]


def test_config_service_uses_one_atomic_config_and_reuses_legacy_shape(
    tmp_path: Path,
) -> None:
    service = WorkerConfigService(tmp_path, protector=ReversingProtector())
    device_id = uuid4()

    saved = service.save(
        server_url="https://control.example.test/",
        device_id=device_id,
        device_token="ccw_secret",
        device_display_name="PC-A",
        yingdao_install_root=tmp_path / "ShadowBot",
    )

    payload = json.loads(service.path.read_text(encoding="utf-8"))
    assert payload["device_token_protected"] != "ccw_secret"
    assert "device_token" not in payload
    assert saved.device_id == device_id
    assert saved.device_token.get_secret_value() == "ccw_secret"
    assert saved.device_display_name == "PC-A"
    defaults = get_default_local_input_paths(tmp_path)
    assert saved.params_json_path == defaults.params_json_path
    assert saved.account_json_path == defaults.account_json_path
    assert saved.images_dir == defaults.images_dir
    assert payload["params_json_path"] == str(defaults.params_json_path)
    assert payload["account_json_path"] == str(defaults.account_json_path)
    assert payload["images_dir"] == str(defaults.images_dir)

    payload.pop("device_display_name")
    payload.pop("params_json_path")
    payload.pop("account_json_path")
    payload.pop("images_dir")
    service.path.write_text(json.dumps(payload), encoding="utf-8")
    legacy = service.load()
    assert legacy.device_id == device_id
    assert legacy.device_display_name is None
    assert legacy.params_json_path == defaults.params_json_path
    assert legacy.account_json_path == defaults.account_json_path
    assert legacy.images_dir == defaults.images_dir
    upgraded_payload = json.loads(service.path.read_text(encoding="utf-8"))
    assert upgraded_payload["params_json_path"] == str(defaults.params_json_path)
    assert upgraded_payload["account_json_path"] == str(defaults.account_json_path)
    assert upgraded_payload["images_dir"] == str(defaults.images_dir)


def test_missing_config_is_distinct(tmp_path: Path) -> None:
    service = WorkerConfigService(tmp_path, protector=ReversingProtector())
    with pytest.raises(WorkerConfigurationMissingError):
        service.load()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI")
def test_dpapi_round_trip_does_not_store_plaintext(tmp_path: Path) -> None:
    service = WorkerConfigService(
        tmp_path,
        protector=WindowsDpapiTokenProtector(),
    )
    service.save(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="ccw_dpapi-secret",
        device_display_name="PC-DPAPI",
        yingdao_install_root=None,
    )

    raw = service.path.read_text(encoding="utf-8")
    assert "ccw_dpapi-secret" not in raw
    assert service.load().device_token.get_secret_value() == "ccw_dpapi-secret"


def test_config_service_persists_custom_local_input_paths(tmp_path: Path) -> None:
    service = WorkerConfigService(tmp_path / "config", protector=ReversingProtector())
    local_input_root = tmp_path / "自定义输入"

    saved = service.save(
        server_url="https://control.example.test",
        device_id=uuid4(),
        device_token="ccw_custom",
        device_display_name="PC-Custom",
        yingdao_install_root=None,
        params_json_path=local_input_root / "参数.json",
        account_json_path=local_input_root / "账号.json",
        images_dir=local_input_root / "图片",
    )

    assert saved.params_json_path == (local_input_root / "参数.json").resolve()
    assert saved.account_json_path == (local_input_root / "账号.json").resolve()
    assert saved.images_dir == (local_input_root / "图片").resolve()
    assert inspect_local_input_paths(
        LocalInputPaths(
            params_json_path=saved.params_json_path,
            account_json_path=saved.account_json_path,
            images_dir=saved.images_dir,
        ),
    ) == {
        "params_json": "可写",
        "account_json": "可写",
        "images_dir": "可写",
    }


def test_config_rejects_same_json_target_and_filesystem_root(
    tmp_path: Path,
) -> None:
    service = WorkerConfigService(tmp_path, protector=ReversingProtector())
    shared_json = tmp_path / "shared.json"
    common = {
        "server_url": "https://control.example.test",
        "device_id": uuid4(),
        "device_token": "ccw_invalid",
        "device_display_name": None,
        "yingdao_install_root": None,
    }

    with pytest.raises(WorkerConfigurationError, match="must be different"):
        service.save(
            **common,
            params_json_path=shared_json,
            account_json_path=shared_json,
            images_dir=tmp_path / "images",
        )

    filesystem_root = tmp_path.resolve().anchor
    with pytest.raises(WorkerConfigurationError, match="filesystem root"):
        service.save(
            **common,
            params_json_path=tmp_path / "params.json",
            account_json_path=tmp_path / "account.json",
            images_dir=Path(filesystem_root),
        )

    with pytest.raises(WorkerConfigurationError, match="managed images"):
        service.save(
            **common,
            params_json_path=tmp_path / "images" / "params.json",
            account_json_path=tmp_path / "account.json",
            images_dir=tmp_path / "images",
        )
