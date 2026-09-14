import asyncio
import errno
import json
import struct
import sys
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
from app.runtime_events import LocalRuntimeState, RuntimeEventBus


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


def test_tasklog_follower_recovers_without_losing_partial_record(
    tmp_path: Path,
) -> None:
    task_id = uuid4()
    path = tmp_path / f"{uuid4()}.tasklog"
    started = encode_record(2, "robot task Safe App started")
    exited = encode_record(2, "robot task Safe App exited")
    interrupted_payload = started + exited[:17]
    path.write_bytes(interrupted_payload)
    state_path = tmp_path / "runtime-status.json"
    state = LocalRuntimeState(path=state_path, device_id=uuid4())
    bus = RuntimeEventBus()
    events = []
    bus.subscribe(events.append)
    bus.subscribe(state.consume)
    follower = YingdaoTaskLogFollower(
        path=path,
        task_id=task_id,
        app_uuid="safe-app",
        app_name="Safe App",
        yingdao_task_uuid=path.stem,
        event_bus=bus,
    )

    asyncio.run(follower.read_available())
    interrupted_offset = follower.read_offset
    buffered_bytes = follower.parser.buffered_bytes
    path.unlink()
    asyncio.run(follower.read_available())
    asyncio.run(follower.read_available())

    assert follower.read_offset == interrupted_offset
    assert follower.parser.buffered_bytes == buffered_bytes
    assert follower.exited is False

    path.write_bytes(started + exited)
    recovered_records = asyncio.run(follower.read_available())
    runtime_state = json.loads(state_path.read_text(encoding="utf-8"))
    failures = [
        event
        for event in events
        if event.metadata.get("tasklog_read_status") == "failed"
    ]
    recoveries = [
        event
        for event in events
        if event.metadata.get("tasklog_read_status") == "recovered"
    ]

    assert [record.message for record in recovered_records] == [
        "robot task Safe App exited",
    ]
    assert follower.read_offset == path.stat().st_size
    assert follower.parser.buffered_bytes == 0
    assert follower.started is True
    assert follower.exited is True
    assert len(failures) == 1
    assert failures[0].metadata["tasklog_read_error"] == "file_missing"
    assert len(recoveries) == 1
    assert recoveries[0].metadata["tasklog_read_failure_count"] == 2
    assert recoveries[0].metadata["tasklog_read_offset"] == path.stat().st_size
    assert [
        event["message"]
        for event in runtime_state["recent_events"]
        if "运行日志" in event["message"]
    ] == [
        "影刀运行日志文件暂时消失，Worker 将保持任务占用并继续等待",
        "影刀运行日志读取已恢复，继续从上次位置读取",
    ]


def test_tasklog_follower_deduplicates_persistent_permission_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / f"{uuid4()}.tasklog"
    path.write_bytes(encode_record(2, "robot task Safe App started"))
    bus = RuntimeEventBus()
    events = []
    bus.subscribe(events.append)
    follower = YingdaoTaskLogFollower(
        path=path,
        task_id=uuid4(),
        app_uuid="safe-app",
        app_name="Safe App",
        yingdao_task_uuid=path.stem,
        event_bus=bus,
    )
    original_read = follower._read_new_bytes

    def deny_read() -> bytes:
        raise PermissionError(errno.EACCES, "fixture access denied")

    monkeypatch.setattr(follower, "_read_new_bytes", deny_read)
    for _ in range(3):
        asyncio.run(follower.read_available())

    failures = [
        event
        for event in events
        if event.metadata.get("tasklog_read_status") == "failed"
    ]
    assert len(failures) == 1
    assert failures[0].metadata["tasklog_read_error"] == "permission_denied"
    assert follower.read_offset == 0
    assert follower.exited is False

    monkeypatch.setattr(follower, "_read_new_bytes", original_read)
    asyncio.run(follower.read_available())
    recoveries = [
        event
        for event in events
        if event.metadata.get("tasklog_read_status") == "recovered"
    ]
    assert len(recoveries) == 1
    assert recoveries[0].metadata["tasklog_read_failure_count"] == 3


def test_tasklog_follower_keeps_waiting_during_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / f"{uuid4()}.tasklog"
    path.write_bytes(b"")
    bus = RuntimeEventBus()
    events = []
    bus.subscribe(events.append)
    follower = YingdaoTaskLogFollower(
        path=path,
        task_id=uuid4(),
        app_uuid="safe-app",
        app_name="Safe App",
        yingdao_task_uuid=path.stem,
        event_bus=bus,
        poll_interval_seconds=0.001,
    )
    original_read = follower._read_new_bytes

    def busy_read() -> bytes:
        error = OSError(errno.EBUSY, "fixture file busy")
        raise error

    monkeypatch.setattr(follower, "_read_new_bytes", busy_read)

    async def scenario() -> None:
        following = asyncio.create_task(follower.follow_until_terminal())
        await asyncio.sleep(0.01)
        assert following.done() is False
        assert follower.exited is False

        path.write_bytes(
            encode_record(2, "robot task Safe App started")
            + encode_record(2, "robot task Safe App exited"),
        )
        monkeypatch.setattr(follower, "_read_new_bytes", original_read)
        await asyncio.wait_for(following, timeout=1)

    asyncio.run(scenario())

    assert follower.started is True
    assert follower.exited is True
    failures = [
        event
        for event in events
        if event.metadata.get("tasklog_read_status") == "failed"
    ]
    assert len(failures) == 1
    assert failures[0].metadata["tasklog_read_error"] == "file_busy"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows sharing fault only")
def test_tasklog_follower_reports_real_windows_exclusive_file_lock(
    tmp_path: Path,
) -> None:
    import ctypes
    from ctypes import wintypes

    path = (tmp_path / f"{uuid4()}.tasklog").resolve()
    path.write_bytes(
        encode_record(2, "robot task Safe App started")
        + encode_record(2, "robot task Safe App exited"),
    )
    bus = RuntimeEventBus()
    events = []
    bus.subscribe(events.append)
    follower = YingdaoTaskLogFollower(
        path=path,
        task_id=uuid4(),
        app_uuid="safe-app",
        app_name="Safe App",
        yingdao_task_uuid=path.stem,
        event_bus=bus,
    )
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        str(path),
        0x80000000,
        0,
        None,
        3,
        0x80,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    assert handle != invalid_handle

    try:
        asyncio.run(follower.read_available())
    finally:
        assert close_handle(handle)

    failures = [
        event
        for event in events
        if event.metadata.get("tasklog_read_status") == "failed"
    ]
    assert len(failures) == 1
    assert failures[0].metadata["tasklog_read_error"] == "file_busy"
    assert failures[0].metadata["tasklog_read_error_type"] == "PermissionError"
    assert failures[0].metadata["tasklog_read_winerror"] == 32
    assert follower.read_offset == 0
    assert follower.exited is False

    asyncio.run(follower.read_available())
    assert follower.started is True
    assert follower.exited is True
    assert len(
        [
            event
            for event in events
            if event.metadata.get("tasklog_read_status") == "recovered"
        ],
    ) == 1


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
