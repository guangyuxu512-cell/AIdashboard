import asyncio
import errno
import os
import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal
from uuid import UUID

from app.contracts import RuntimeEventType
from app.runtime_events import RuntimeEventBus


_HEADER_SIZE = 13
_MAX_MESSAGE_BYTES = 1024 * 1024
_DOTNET_MAX_TICKS = 3_155_378_975_999_999_999

TaskLogReadFailureKind = Literal[
    "file_busy",
    "file_missing",
    "permission_denied",
    "io_error",
]


class YingdaoTaskLogError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class YingdaoTaskLogRecord:
    raw_level: int
    level: str
    event_at: datetime
    message: str


@dataclass
class _TaskLogReadFailureState:
    started_at: datetime
    total_attempts: int
    kind_counts: dict[TaskLogReadFailureKind, int]


class YingdaoTaskLogParser:
    def __init__(self, *, max_message_bytes: int = _MAX_MESSAGE_BYTES) -> None:
        self.max_message_bytes = max_message_bytes
        self._buffer = bytearray()

    @property
    def buffered_bytes(self) -> int:
        return len(self._buffer)

    def feed(self, data: bytes) -> list[YingdaoTaskLogRecord]:
        self._buffer.extend(data)
        records: list[YingdaoTaskLogRecord] = []
        while len(self._buffer) >= _HEADER_SIZE:
            raw_level = self._buffer[0]
            ticks = struct.unpack_from("<Q", self._buffer, 1)[0]
            message_length = struct.unpack_from("<I", self._buffer, 9)[0]
            if message_length > self.max_message_bytes:
                raise YingdaoTaskLogError(
                    "YINGDAO_TASKLOG_INVALID",
                    "Yingdao tasklog record length is invalid",
                )
            record_size = _HEADER_SIZE + message_length
            if len(self._buffer) < record_size:
                break
            message_bytes = bytes(self._buffer[_HEADER_SIZE:record_size])
            del self._buffer[:record_size]
            try:
                message = message_bytes.decode("utf-8")
                event_at = dotnet_ticks_to_datetime(ticks)
            except (UnicodeDecodeError, OverflowError, ValueError) as error:
                raise YingdaoTaskLogError(
                    "YINGDAO_TASKLOG_INVALID",
                    "Yingdao tasklog record is invalid",
                ) from error
            records.append(
                YingdaoTaskLogRecord(
                    raw_level=raw_level,
                    level=f"L{raw_level}",
                    event_at=event_at,
                    message=message,
                ),
            )
        return records


def dotnet_ticks_to_datetime(ticks: int) -> datetime:
    ticks &= 0x3FFF_FFFF_FFFF_FFFF
    if ticks > _DOTNET_MAX_TICKS:
        raise ValueError(".NET ticks are outside the DateTime range")
    microseconds, _ = divmod(ticks, 10)
    return datetime(1, 1, 1, tzinfo=UTC) + timedelta(microseconds=microseconds)


class YingdaoTaskLogFollower:
    def __init__(
        self,
        *,
        path: Path,
        task_id: UUID,
        app_uuid: str,
        app_name: str,
        yingdao_task_uuid: str,
        event_bus: RuntimeEventBus,
        poll_interval_seconds: float = 0.2,
    ) -> None:
        self.path = path
        self.task_id = task_id
        self.app_uuid = app_uuid
        self.app_name = app_name
        self.yingdao_task_uuid = yingdao_task_uuid
        self.event_bus = event_bus
        self.poll_interval_seconds = poll_interval_seconds
        self.read_offset = 0
        self.parser = YingdaoTaskLogParser()
        self.started = False
        self.exited = False
        self._read_failure: _TaskLogReadFailureState | None = None

    async def follow_until_terminal(self) -> None:
        while not self.exited:
            await self.read_available()
            if not self.exited:
                await asyncio.sleep(self.poll_interval_seconds)

    async def read_available(self) -> list[YingdaoTaskLogRecord]:
        try:
            data = await asyncio.to_thread(self._read_new_bytes)
        except OSError as error:
            self._record_read_failure(error)
            return []
        self._record_read_recovery()
        records = self.parser.feed(data)
        for record in records:
            metadata = {
                "provider": "yingdao",
                "app_uuid": self.app_uuid,
                "app_name": self.app_name,
                "yingdao_task_uuid": self.yingdao_task_uuid,
                "phase": "running" if self.started else "launching",
            }
            self.event_bus.emit(
                self.task_id,
                RuntimeEventType.LOG,
                record.message,
                level=record.level,
                event_at=record.event_at,
                metadata=metadata,
            )
            message = record.message.strip()
            if message == f"robot task {self.app_name} started" or message.startswith(
                "开始执行",
            ):
                self.started = True
                self.event_bus.emit(
                    self.task_id,
                    RuntimeEventType.STATUS,
                    f"影刀应用 {self.app_name} 已开始运行",
                    metadata={**metadata, "phase": "running"},
                )
            if message == f"robot task {self.app_name} exited" or message == "执行结束":
                if self.started:
                    self.exited = True
                    self.event_bus.emit(
                        self.task_id,
                        RuntimeEventType.PROGRESS,
                        f"影刀应用 {self.app_name} 已退出",
                        metadata={**metadata, "phase": "succeeded"},
                    )
        return records

    def _record_read_failure(self, error: OSError) -> None:
        winerror = getattr(error, "winerror", None)
        if (
            winerror is None
            and os.name == "nt"
            and error.errno in {errno.EACCES, errno.EPERM}
        ):
            winerror = self._probe_windows_read_error(self.path)
        kind = self._classify_read_failure(error, winerror=winerror)
        now = datetime.now(UTC)
        if self._read_failure is None:
            self._read_failure = _TaskLogReadFailureState(
                started_at=now,
                total_attempts=0,
                kind_counts={},
            )
        state = self._read_failure
        state.total_attempts += 1
        state.kind_counts[kind] = state.kind_counts.get(kind, 0) + 1

        # One event per failure kind keeps a persistent lock from flooding the
        # Runtime Event Bus while still exposing a changed failure reason.
        if state.kind_counts[kind] > 1:
            return
        messages = {
            "file_busy": "影刀运行日志文件正被占用，Worker 将保持任务占用并继续等待",
            "file_missing": "影刀运行日志文件暂时消失，Worker 将保持任务占用并继续等待",
            "permission_denied": "影刀运行日志读取被拒绝，Worker 将保持任务占用并继续等待",
            "io_error": "影刀运行日志读取失败，Worker 将保持任务占用并继续等待",
        }
        self.event_bus.emit(
            self.task_id,
            RuntimeEventType.LOG,
            messages[kind],
            level="warning",
            metadata={
                **self._event_metadata(),
                "tasklog_read_status": "failed",
                "tasklog_read_error": kind,
                "tasklog_read_error_type": type(error).__name__,
                "tasklog_read_errno": error.errno,
                "tasklog_read_winerror": winerror,
                "tasklog_read_failure_started_at": state.started_at.isoformat(),
            },
        )

    def _record_read_recovery(self) -> None:
        state = self._read_failure
        if state is None:
            return
        recovered_at = datetime.now(UTC)
        duration_ms = max(
            0,
            int((recovered_at - state.started_at).total_seconds() * 1000),
        )
        self.event_bus.emit(
            self.task_id,
            RuntimeEventType.LOG,
            "影刀运行日志读取已恢复，继续从上次位置读取",
            level="info",
            metadata={
                **self._event_metadata(),
                "tasklog_read_status": "recovered",
                "tasklog_read_failure_count": state.total_attempts,
                "tasklog_read_failure_kinds": sorted(state.kind_counts),
                "tasklog_read_failure_started_at": state.started_at.isoformat(),
                "tasklog_read_failure_duration_ms": duration_ms,
                "tasklog_read_offset": self.read_offset,
                "tasklog_buffered_bytes": self.parser.buffered_bytes,
            },
        )
        self._read_failure = None

    def _event_metadata(self) -> dict[str, str]:
        return {
            "provider": "yingdao",
            "app_uuid": self.app_uuid,
            "app_name": self.app_name,
            "yingdao_task_uuid": self.yingdao_task_uuid,
            "phase": "running" if self.started else "launching",
        }

    @staticmethod
    def _classify_read_failure(
        error: OSError,
        *,
        winerror: int | None = None,
    ) -> TaskLogReadFailureKind:
        if isinstance(error, FileNotFoundError) or error.errno == errno.ENOENT:
            return "file_missing"
        if winerror in {32, 33} or error.errno in {
            errno.EBUSY,
            getattr(errno, "ETXTBSY", errno.EBUSY),
        }:
            return "file_busy"
        if isinstance(error, PermissionError) or error.errno in {
            errno.EACCES,
            errno.EPERM,
        }:
            return "permission_denied"
        return "io_error"

    @staticmethod
    def _probe_windows_read_error(path: Path) -> int | None:
        """Recover the Win32 code hidden by Python's errno=13 conversion."""
        import ctypes
        from ctypes import wintypes

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
            0x00000001 | 0x00000002 | 0x00000004,
            None,
            3,
            0x80,
            None,
        )
        invalid_handle = ctypes.c_void_p(-1).value
        if handle == invalid_handle:
            return ctypes.get_last_error()
        close_handle(handle)
        return None

    def _read_new_bytes(self) -> bytes:
        with self.path.open("rb") as stream:
            stream.seek(self.read_offset)
            data = stream.read()
        self.read_offset += len(data)
        return data
