import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.local_config import (
    WindowsDpapiTokenProtector,
    WorkerConfigService,
    WorkerConfigurationMissingError,
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

    payload.pop("device_display_name")
    service.path.write_text(json.dumps(payload), encoding="utf-8")
    legacy = service.load()
    assert legacy.device_id == device_id
    assert legacy.device_display_name is None


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
