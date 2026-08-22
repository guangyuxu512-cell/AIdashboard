import asyncio
import struct
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.contracts import RuntimeEventType
from app.providers.yingdao import (
    RuntimeYingdaoAdapter,
    YingdaoExecutionRequest,
    YingdaoTriggerError,
    YingdaoTaskLogError,
    YingdaoTaskLogFollower,
    YingdaoTaskLogParser,
    YingdaoVersionResolver,
    build_shadowbot_run_uri,
)
from app.runtime_events import RuntimeEventBus


def make_installation(tmp_path: Path, root_version: str) -> Path:
    root = tmp_path / "ShadowBot"
    root.mkdir()
    (root / "ShadowBot.exe").touch()
    (root / f"version-{root_version}").touch()
    return root


def version_reader(path: Path) -> str:
    for marker in path.parent.glob("version-*"):
        return marker.name.removeprefix("version-")
    return path.parent.name.removeprefix("shadowbot-")


@pytest.mark.parametrize("version", ["6.3.6", "6.2.23"])
def test_version_resolver_allows_only_verified_versions(
    tmp_path: Path,
    version: str,
) -> None:
    environment = YingdaoVersionResolver(
        make_installation(tmp_path, version),
        version_reader=version_reader,
    ).resolve()

    assert environment.execution_available is True
    assert environment.execution_version == version


def test_version_resolver_denies_639_execution_without_requiring_cli(
    tmp_path: Path,
) -> None:
    root = make_installation(tmp_path, "6.3.9")

    environment = YingdaoVersionResolver(
        root,
        version_reader=version_reader,
    ).resolve()

    assert environment.provider_version == "6.3.9"
    assert environment.execution_available is False
    assert environment.execution_version is None


def test_version_resolver_prefers_636_over_6223(tmp_path: Path) -> None:
    root = make_installation(tmp_path, "6.2.23")
    preferred = root / "shadowbot-6.3.6"
    preferred.mkdir()
    (preferred / "ShadowBot.exe").touch()

    environment = YingdaoVersionResolver(
        root,
        version_reader=version_reader,
    ).resolve()

    assert environment.execution_version == "6.3.6"
    assert environment.execution_executable_path == preferred / "ShadowBot.exe"


def test_version_resolver_supports_only_nested_version_directories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "ShadowBot"
    root.mkdir()
    for version in ("6.2.23", "6.3.6", "6.3.9"):
        directory = root / f"shadowbot-{version}"
        directory.mkdir()
        (directory / "ShadowBot.Shell.exe").touch()

    environment = YingdaoVersionResolver(
        root,
        version_reader=version_reader,
    ).resolve()

    assert environment.provider_version == "6.3.9"
    assert environment.execution_version == "6.3.6"
    assert environment.execution_executable_path == (
        root / "shadowbot-6.3.6" / "ShadowBot.Shell.exe"
    )


def test_version_resolver_uses_636_with_current_639_and_multiple_versions(
    tmp_path: Path,
) -> None:
    root = make_installation(tmp_path, "6.3.9")
    for version in ("6.2.23", "6.3.6", "6.3.9"):
        directory = root / f"shadowbot-{version}"
        directory.mkdir()
        (directory / "ShadowBot.Shell.exe").touch()

    environment = YingdaoVersionResolver(
        root,
        version_reader=version_reader,
    ).resolve()

    assert environment.provider_version == "6.3.9"
    assert environment.execution_version == "6.3.6"
    assert environment.execution_executable_path == (
        root / "shadowbot-6.3.6" / "ShadowBot.Shell.exe"
    )


def test_shadowbot_uri_uses_standard_encoding() -> None:
    uri = build_shadowbot_run_uri(
        "app-uuid",
        {"name": "测试 用户&1", "payload": {"ok": True}},
    )

    assert uri.startswith("shadowbot:Run?robot-uuid=app-uuid&")
    assert "%E6%B5%8B%E8%AF%95+%E7%94%A8%E6%88%B7%261" in uri
    assert "payload=%7B%22ok%22%3Atrue%7D" in uri


def encode_record(level: int, message: str) -> bytes:
    payload = message.encode("utf-8")
    ticks = 638_914_344_000_000_000
    return bytes([level]) + struct.pack("<QI", ticks, len(payload)) + payload


def test_tasklog_parser_supports_multiple_and_partial_records() -> None:
    parser = YingdaoTaskLogParser()
    payload = encode_record(1, "one") + encode_record(3, "二")

    assert parser.feed(payload[:15]) == []
    records = parser.feed(payload[15:])

    assert [(record.level, record.message) for record in records] == [
        ("L1", "one"),
        ("L3", "二"),
    ]
    assert records[0].event_at.tzinfo is UTC
    assert parser.buffered_bytes == 0


def test_tasklog_parser_rejects_bad_length() -> None:
    parser = YingdaoTaskLogParser(max_message_bytes=8)
    bad = bytes([1]) + struct.pack("<QI", 1, 99)

    with pytest.raises(YingdaoTaskLogError) as error:
        parser.feed(bad)

    assert error.value.code == "YINGDAO_TASKLOG_INVALID"


def test_tasklog_follower_keeps_incremental_offset_and_verified_terminal(
    tmp_path: Path,
) -> None:
    task_id = uuid4()
    path = tmp_path / f"{uuid4()}.tasklog"
    path.write_bytes(encode_record(2, "robot task Safe App started"))
    bus = RuntimeEventBus()
    events = []
    bus.subscribe(events.append)
    follower = YingdaoTaskLogFollower(
        path=path,
        task_id=task_id,
        app_uuid="safe-app",
        app_name="Safe App",
        yingdao_task_uuid=path.stem,
        event_bus=bus,
    )

    asyncio.run(follower.read_available())
    first_offset = follower.read_offset
    with path.open("ab") as stream:
        stream.write(encode_record(2, "robot task Safe App exited"))
    asyncio.run(follower.read_available())

    assert first_offset > 0
    assert follower.read_offset == path.stat().st_size
    assert follower.started is True
    assert follower.exited is True
    assert [event.event_type for event in events] == [
        RuntimeEventType.LOG,
        RuntimeEventType.STATUS,
        RuntimeEventType.LOG,
        RuntimeEventType.PROGRESS,
    ]


def test_runtime_adapter_has_provider_single_execution_lock(tmp_path: Path) -> None:
    class Discovery:
        data_root = tmp_path

        async def discover(self):
            raise AssertionError

    adapter = RuntimeYingdaoAdapter(
        discovery_service=Discovery(),  # type: ignore[arg-type]
        install_root=tmp_path,
        data_root=tmp_path,
        event_bus=RuntimeEventBus(),
    )

    async def scenario() -> None:
        order = []

        async def enter(name: str) -> None:
            async with adapter._execution_lock:
                order.append(f"{name}:start")
                await asyncio.sleep(0.01)
                order.append(f"{name}:end")

        await asyncio.gather(enter("a"), enter("b"))
        assert order == ["a:start", "a:end", "b:start", "b:end"]

    asyncio.run(scenario())


def test_runtime_adapter_reports_launcher_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_runtime_adapter(tmp_path)
    monkeypatch.setattr(
        'app.providers.yingdao.adapter.YingdaoVersionResolver.resolve',
        lambda _self: execution_environment(tmp_path),
    )

    async def fail_to_start(*_args):
        raise OSError('fixture launch failure')

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', fail_to_start)

    with pytest.raises(YingdaoTriggerError) as error:
        asyncio.run(adapter.execute(request))

    assert error.value.code == 'RPA_TRIGGER_FAILED'


def test_runtime_adapter_reports_missing_tasklog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_runtime_adapter(tmp_path, association_timeout=0.01)
    monkeypatch.setattr(
        'app.providers.yingdao.adapter.YingdaoVersionResolver.resolve',
        lambda _self: execution_environment(tmp_path),
    )

    class Process:
        async def wait(self):
            return 0

    async def start(*_args):
        return Process()

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', start)

    with pytest.raises(YingdaoTriggerError) as error:
        asyncio.run(adapter.execute(request))

    assert error.value.code == 'YINGDAO_TASKLOG_NOT_FOUND'


def execution_environment(tmp_path: Path):
    executable = tmp_path / 'ShadowBot.exe'
    executable.touch(exist_ok=True)
    return SimpleNamespace(
        execution_available=True,
        execution_executable_path=executable,
        execution_version='6.2.23',
        execution_unavailable_reason=None,
    )


def make_runtime_adapter(
    tmp_path: Path,
    *,
    association_timeout: float = 0.1,
):
    user_id = 'test-user'
    (tmp_path / 'users' / user_id / 'task_logs').mkdir(parents=True)

    class Discovery:
        async def discover(self):
            raise AssertionError

    adapter = RuntimeYingdaoAdapter(
        discovery_service=Discovery(),  # type: ignore[arg-type]
        install_root=tmp_path,
        data_root=tmp_path,
        event_bus=RuntimeEventBus(),
        tasklog_association_timeout_seconds=association_timeout,
    )
    request = YingdaoExecutionRequest(
        task_id=uuid4(),
        skill_id='yingdao.test',
        app_id='safe-app',
        app_name='Safe App',
        user_id=user_id,
        params={},
        runtime_directory=tmp_path / 'runtime',
    )
    return adapter, request
