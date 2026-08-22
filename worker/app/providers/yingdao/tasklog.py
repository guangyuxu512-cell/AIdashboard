import asyncio
import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from app.contracts import RuntimeEventType
from app.runtime_events import RuntimeEventBus


_HEADER_SIZE = 13
_MAX_MESSAGE_BYTES = 1024 * 1024
_DOTNET_MAX_TICKS = 3_155_378_975_999_999_999


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

    async def follow_until_terminal(self) -> None:
        while not self.exited:
            await self.read_available()
            if not self.exited:
                await asyncio.sleep(self.poll_interval_seconds)

    async def read_available(self) -> list[YingdaoTaskLogRecord]:
        try:
            data = await asyncio.to_thread(self._read_new_bytes)
        except (OSError, PermissionError):
            return []
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
            if record.message.strip() == f"robot task {self.app_name} started":
                self.started = True
                self.event_bus.emit(
                    self.task_id,
                    RuntimeEventType.STATUS,
                    f"影刀应用 {self.app_name} 已开始运行",
                    metadata={**metadata, "phase": "running"},
                )
            if record.message.strip() == f"robot task {self.app_name} exited":
                if self.started:
                    self.exited = True
                    self.event_bus.emit(
                        self.task_id,
                        RuntimeEventType.PROGRESS,
                        f"影刀应用 {self.app_name} 已退出",
                        metadata={**metadata, "phase": "succeeded"},
                    )
        return records

    def _read_new_bytes(self) -> bytes:
        with self.path.open("rb") as stream:
            stream.seek(self.read_offset)
            data = stream.read()
        self.read_offset += len(data)
        return data
