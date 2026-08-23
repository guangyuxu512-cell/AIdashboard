import asyncio
import struct
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.contracts import RuntimeEventType
from app.providers.yingdao import (
    RuntimeYingdaoAdapter,
    YingdaoExecutionRequest,
    YingdaoApplication,
    YingdaoProcess,
    YingdaoRuntimeEndpoint,
    YingdaoSession,
    YingdaoSessionAccount,
    YingdaoTriggerError,
    YingdaoTaskLogError,
    YingdaoTaskLogFollower,
    YingdaoTaskLogParser,
    build_shadowbot_run_uri,
)
from app.runtime_events import RuntimeEventBus


class FakeSessionAdapter:
    def __init__(self, executable: Path) -> None:
        self.session = YingdaoSession(
            endpoint=YingdaoRuntimeEndpoint(
                YingdaoProcess(123, executable, "6.3.6"),
                "http://127.0.0.1:42500",
            ),
            account=YingdaoSessionAccount(
                True,
                "GY00999",
                "GY00999",
                "test-user",
                "PersonalBasic",
                None,
            ),
        )

    async def current(self, *, start_if_missing: bool = True) -> YingdaoSession:
        assert start_if_missing
        return self.session


class FakeApplicationAdapter:
    async def list(self, session: YingdaoSession) -> list[YingdaoApplication]:
        del session
        return [YingdaoApplication(app_id="safe-app", app_name="Safe App")]

    async def detail(self, session: YingdaoSession, app_id: str) -> dict[str, object]:
        del session
        assert app_id == "safe-app"
        return {"appId": app_id}


def test_shadowbot_uri_uses_standard_encoding() -> None:
    uri = build_shadowbot_run_uri(
        "app-uuid",
        {"name": "测试 用户&1", "enabled": True, "payload": {"ok": True}},
    )

    assert uri.startswith("shadowbot:Run?robot-uuid=app-uuid&")
    assert "%E6%B5%8B%E8%AF%95+%E7%94%A8%E6%88%B7%261" in uri
    assert "enabled=true" in uri
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


def test_tasklog_follower_accepts_verified_636_chinese_terminal_messages(
    tmp_path: Path,
) -> None:
    path = tmp_path / f"{uuid4()}.tasklog"
    path.write_bytes(encode_record(2, "开始执行应用") + encode_record(2, "执行结束"))
    follower = YingdaoTaskLogFollower(
        path=path,
        task_id=uuid4(),
        app_uuid="safe-app",
        app_name="Safe App",
        yingdao_task_uuid=path.stem,
        event_bus=RuntimeEventBus(),
    )

    asyncio.run(follower.read_available())

    assert follower.started is True
    assert follower.exited is True


def test_runtime_adapter_has_provider_single_execution_lock(tmp_path: Path) -> None:
    class Discovery:
        data_root = tmp_path

        async def discover(self):
            raise AssertionError

    adapter = RuntimeYingdaoAdapter(
        discovery_service=Discovery(),  # type: ignore[arg-type]
        session_adapter=FakeSessionAdapter(tmp_path / "ShadowBot.exe"),  # type: ignore[arg-type]
        application_adapter=FakeApplicationAdapter(),  # type: ignore[arg-type]
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
    async def fail_to_start(*_args):
        raise OSError('fixture launch failure')

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', fail_to_start)

    with pytest.raises(YingdaoTriggerError) as error:
        asyncio.run(adapter.execute(request))

    assert error.value.code == 'RPA_TRIGGER_FAILED'


def test_runtime_adapter_rejects_application_missing_from_current_account(
    tmp_path: Path,
) -> None:
    adapter, request = make_runtime_adapter(tmp_path)

    async def empty_list(_session: YingdaoSession) -> list[YingdaoApplication]:
        return []

    adapter.application_adapter.list = empty_list  # type: ignore[method-assign]

    with pytest.raises(YingdaoTriggerError) as error:
        asyncio.run(adapter.execute(request))

    assert error.value.code == "YINGDAO_APPLICATION_NOT_FOUND"


def test_runtime_adapter_reports_missing_tasklog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, request = make_runtime_adapter(tmp_path, association_timeout=0.01)
    class Process:
        async def wait(self):
            return 0

    async def start(*_args):
        return Process()

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', start)

    with pytest.raises(YingdaoTriggerError) as error:
        asyncio.run(adapter.execute(request))

    assert error.value.code == 'YINGDAO_TASKLOG_NOT_FOUND'


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

    executable = tmp_path / 'ShadowBot.exe'
    executable.touch(exist_ok=True)

    adapter = RuntimeYingdaoAdapter(
        discovery_service=Discovery(),  # type: ignore[arg-type]
        session_adapter=FakeSessionAdapter(executable),  # type: ignore[arg-type]
        application_adapter=FakeApplicationAdapter(),  # type: ignore[arg-type]
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
