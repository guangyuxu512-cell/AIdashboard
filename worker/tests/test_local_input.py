import json
from enum import StrEnum
from pathlib import Path

import pytest

from app.contracts import AccountPayload, WorkerTask
from app.local_config import LocalInputPaths, write_json_atomic as real_write_json_atomic
from app.local_input import LocalInputBridge, LocalInputPreparationError


class RunMode(StrEnum):
    SAFE = "safe"


def make_bridge(tmp_path: Path) -> LocalInputBridge:
    return LocalInputBridge(
        LocalInputPaths(
            params_json_path=tmp_path / "data" / "params.json",
            account_json_path=tmp_path / "data" / "account.json",
            images_dir=tmp_path / "data" / "images",
        ),
    )


def make_account(
    *,
    shop_id: str = "7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
    shop_name: str | None = "中文店铺",
    secret: str = "task-secret",
) -> AccountPayload:
    return AccountPayload(
        shop_id=shop_id,
        shop_name=shop_name,
        platform_code="DOUYIN",
        login_identifier="测试账号",
        secret=secret,
        preferred_verification_channel="SMS",
    )


def test_bridge_writes_readable_utf8_json_and_creates_images(
    tmp_path: Path,
) -> None:
    bridge = make_bridge(tmp_path)

    bridge.prepare(
        params={
            "关键词": "夏季连衣裙",
            "enabled": True,
            "count": 10,
            "ratio": 0.5,
            "mode": RunMode.SAFE,
        },
        accounts=[make_account()],
    )

    params_text = bridge.paths.params_json_path.read_text(encoding="utf-8")
    account_text = bridge.paths.account_json_path.read_text(encoding="utf-8")
    assert "夏季连衣裙" in params_text
    assert "测试账号" in account_text
    assert json.loads(params_text) == {
        "关键词": "夏季连衣裙",
        "enabled": True,
        "count": 10,
        "ratio": 0.5,
        "mode": "safe",
    }
    assert json.loads(account_text) == {
        "店铺列表": [
            {
                "店铺ID": "7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
                "店铺名称": "中文店铺",
                "平台编码": "DOUYIN",
                "登录账号": "测试账号",
                "登录密码": "task-secret",
                "首选验证方式": "SMS",
            },
        ],
    }
    assert "login_identifier" not in account_text
    assert bridge.paths.images_dir.is_dir()
    assert not list(bridge.paths.params_json_path.parent.glob(".*.tmp"))


def test_bridge_preserves_order_and_duplicate_shop_names(tmp_path: Path) -> None:
    bridge = make_bridge(tmp_path)
    bridge.prepare(
        params={},
        accounts=[
            make_account(
                shop_id="7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
                shop_name="同名店铺",
            ),
            make_account(
                shop_id="423fac66-4b82-4ed0-8077-24a60aaf4bf6",
                shop_name="同名店铺",
            ),
        ],
    )

    shops = json.loads(bridge.paths.account_json_path.read_text("utf-8"))["店铺列表"]
    assert [(item["店铺ID"], item["店铺名称"]) for item in shops] == [
        ("7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b", "同名店铺"),
        ("423fac66-4b82-4ed0-8077-24a60aaf4bf6", "同名店铺"),
    ]


def test_new_worker_accepts_the_prior_account_contract_without_shop_name() -> None:
    task = WorkerTask.model_validate(
        {
            "task_id": "7cb00c72-f6f9-4e89-9ac6-f1ce03c5544b",
            "skill_id": "system.echo",
            "input": {"message": "compatibility"},
            "lease_until": "2026-09-10T12:00:00+00:00",
            "accounts": [
                {
                    "shop_id": "423fac66-4b82-4ed0-8077-24a60aaf4bf6",
                    "platform_code": "douyin",
                    "login_identifier": "legacy-account",
                    "secret": "not-logged",
                    "preferred_verification_channel": "manual",
                },
            ],
        },
    )

    assert task.accounts[0].shop_name is None


def test_bridge_fully_overwrites_params_and_stale_account(tmp_path: Path) -> None:
    bridge = make_bridge(tmp_path)
    bridge.prepare(
        params={"a": 1},
        accounts=[make_account(secret="task-a-secret")],
    )
    existing_image = bridge.paths.images_dir / "existing.jpg"
    existing_image.write_bytes(b"fixture")

    bridge.prepare(params={"b": 2}, accounts=[])

    assert json.loads(bridge.paths.params_json_path.read_text("utf-8")) == {
        "b": 2,
    }
    assert json.loads(bridge.paths.account_json_path.read_text("utf-8")) == {
        "店铺列表": [],
    }
    assert "task-a-secret" not in bridge.paths.account_json_path.read_text("utf-8")
    # There is no Server -> Worker image collection contract in V1, so the
    # generic bridge only guarantees the managed directory and does not guess
    # whether an existing collection should be removed.
    assert existing_image.exists()


def test_bridge_writes_empty_params_instead_of_reusing_previous_task(
    tmp_path: Path,
) -> None:
    bridge = make_bridge(tmp_path)
    bridge.prepare(params={"old": True}, accounts=[])

    bridge.prepare(params={}, accounts=[])

    assert json.loads(bridge.paths.params_json_path.read_text("utf-8")) == {}


def test_bridge_preserves_backend_materialized_parameter_preset_envelope(
    tmp_path: Path,
) -> None:
    bridge = make_bridge(tmp_path)
    envelope = {
        "format_version": 1,
        "common_parameters": {"标题": "公共", "启用": False},
        "shop_parameters": {
            "shop-a": {"标题": "店铺 A", "数量": 0},
        },
    }

    bridge.prepare(params=envelope, accounts=[])

    assert json.loads(bridge.paths.params_json_path.read_text("utf-8")) == envelope
    assert json.loads(bridge.paths.account_json_path.read_text("utf-8")) == {
        "店铺列表": [],
    }


def test_bridge_reports_safe_error_without_payload_and_stops_preparation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge = make_bridge(tmp_path)

    def fail_write(path: Path, payload: dict[str, object]) -> None:
        del path, payload
        raise OSError("private_marker=must-not-escape")

    monkeypatch.setattr("app.local_input.write_json_atomic", fail_write)

    with pytest.raises(LocalInputPreparationError) as captured:
        bridge.prepare(
            params={"private_marker": "must-not-escape"},
            accounts=[make_account(secret="must-not-escape")],
        )

    assert captured.value.code == "LOCAL_PARAMS_FILE_PREPARATION_FAILED"
    assert captured.value.message == "本地参数文件准备失败"
    assert "must-not-escape" not in str(captured.value)
    assert not bridge.paths.images_dir.exists()


def test_bridge_distinguishes_account_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bridge = make_bridge(tmp_path)
    call_count = 0

    def fail_second_write(path: Path, payload: dict[str, object]) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("account payload intentionally omitted")
        real_write_json_atomic(path, payload)

    monkeypatch.setattr("app.local_input.write_json_atomic", fail_second_write)

    with pytest.raises(LocalInputPreparationError) as captured:
        bridge.prepare(params={"ok": True}, accounts=[make_account(secret="hidden")])

    assert captured.value.code == "LOCAL_ACCOUNT_FILE_PREPARATION_FAILED"
    assert captured.value.message == "账号文件准备失败"
    assert "hidden" not in str(captured.value)
