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


def test_existing_identity_and_legacy_files_survive_upgrade(tmp_path: Path) -> None:
    service = WorkerConfigService(tmp_path, protector=ReversingProtector())
    device_id = uuid4()
    saved = service.save(server_url="https://control.example.test/", device_id=device_id,
        device_token="synthetic-device-token", device_display_name="PC-A")
    payload = json.loads(service.path.read_text(encoding="utf-8"))
    assert payload["device_token_protected"] != "synthetic-device-token"
    assert "device_token" not in payload
    assert saved.images_dir == get_default_local_input_paths(tmp_path).images_dir

    legacy_file = tmp_path / "old-account.json"
    legacy_file.write_text("legacy", encoding="utf-8")
    payload["yingdao_install_root"] = "old-unused-path"
    payload["params_json_path"] = str(tmp_path / "does-not-exist" / "params.json")
    payload["account_json_path"] = str(legacy_file)
    payload.pop("images_dir")
    service.path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = service.load()
    assert loaded.device_id == device_id
    assert loaded.device_token.get_secret_value() == "synthetic-device-token"
    assert loaded.server_url == "https://control.example.test"
    assert loaded.images_dir == get_default_local_input_paths(tmp_path).images_dir
    assert legacy_file.read_text(encoding="utf-8") == "legacy"


def test_missing_config_is_distinct(tmp_path: Path) -> None:
    with pytest.raises(WorkerConfigurationMissingError):
        WorkerConfigService(tmp_path, protector=ReversingProtector()).load()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI")
def test_dpapi_round_trip_does_not_store_plaintext(tmp_path: Path) -> None:
    service = WorkerConfigService(tmp_path, protector=WindowsDpapiTokenProtector())
    service.save(server_url="https://control.example.test", device_id=uuid4(),
        device_token="synthetic-secret", device_display_name="PC")
    assert "synthetic-secret" not in service.path.read_text(encoding="utf-8")
    assert service.load().device_token.get_secret_value() == "synthetic-secret"


def test_custom_images_directory_and_filesystem_root_guard(tmp_path: Path) -> None:
    service = WorkerConfigService(tmp_path / "config", protector=ReversingProtector())
    options = {"server_url": "https://control.example.test", "device_id": uuid4(),
        "device_token": "synthetic", "device_display_name": None}
    images = tmp_path / "自定义图片"
    saved = service.save(**options, images_dir=images)
    assert saved.images_dir == images.resolve()
    assert inspect_local_input_paths(LocalInputPaths(images_dir=images)) == {"images_dir": "可写"}
    with pytest.raises(WorkerConfigurationError, match="filesystem root"):
        service.save(**options, images_dir=Path(tmp_path.resolve().anchor))
