import asyncio
import json
import logging
import os
import re
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.client import WorkerApiClient
from app.contracts import RuntimeEvent, RuntimeEventType, WorkerTask
from app.version import WORKER_VERSION


logger = logging.getLogger(__name__)
RuntimeEventSubscriber = Callable[[RuntimeEvent], None]
_SENSITIVE_KEYS = frozenset(
    {"password", "token", "authorization", "cookie", "cookies", "secret"},
)
_SENSITIVE_MESSAGE = re.compile(
    r"(?i)\b(password|token|authorization|cookie|secret)\b\s*[:=]\s*[^\s,;]+",
)


def _redact_value(value: Any, key: str | None = None) -> Any:
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(child_key): _redact_value(child_value, str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(child) for child in value]
    return value


class RuntimeEventBus:
    def __init__(self) -> None:
        self._next_seq: dict[UUID, int] = {}
        self._subscribers: list[RuntimeEventSubscriber] = []

    def subscribe(self, subscriber: RuntimeEventSubscriber) -> None:
        self._subscribers.append(subscriber)

    def emit(
        self,
        task_id: UUID,
        event_type: RuntimeEventType,
        message: str,
        *,
        level: str = "worker",
        event_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeEvent:
        seq = self._next_seq.get(task_id, 1)
        self._next_seq[task_id] = seq + 1
        safe_message = _SENSITIVE_MESSAGE.sub(
            lambda match: f"{match.group(1)}=[REDACTED]",
            message,
        )
        event = RuntimeEvent(
            seq=seq,
            task_id=task_id,
            event_type=event_type,
            level=level,
            message=safe_message,
            event_at=event_at or datetime.now(UTC),
            metadata=_redact_value(metadata or {}),
        )
        for subscriber in tuple(self._subscribers):
            subscriber(event)
        return event


class RuntimeEventBuffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._events: deque[RuntimeEvent] = deque()

    def append(self, event: RuntimeEvent) -> None:
        if len(self._events) >= self.capacity:
            dropped = self._events.popleft()
            logger.error(
                "Runtime event buffer full; dropped task=%s seq=%s",
                dropped.task_id,
                dropped.seq,
            )
        self._events.append(event)

    def peek_batch(self, limit: int) -> list[RuntimeEvent]:
        if not self._events:
            return []
        task_id = self._events[0].task_id
        batch: list[RuntimeEvent] = []
        for event in self._events:
            if event.task_id != task_id or len(batch) >= limit:
                break
            batch.append(event)
        return batch

    def acknowledge(self, events: list[RuntimeEvent]) -> None:
        for expected in events:
            if not self._events or self._events[0] != expected:
                raise RuntimeError("Runtime event buffer acknowledgement is out of order")
            self._events.popleft()

    def has_task(self, task_id: UUID) -> bool:
        return any(event.task_id == task_id for event in self._events)

    def __len__(self) -> int:
        return len(self._events)


class BackendEventReporter:
    def __init__(
        self,
        client: WorkerApiClient,
        buffer: RuntimeEventBuffer,
        *,
        flush_interval_seconds: float,
        batch_size: int,
        retry_count: int,
    ) -> None:
        self.client = client
        self.buffer = buffer
        self.flush_interval_seconds = flush_interval_seconds
        self.batch_size = batch_size
        self.retry_count = retry_count
        self._flush_lock = asyncio.Lock()

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self.flush_once()
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.flush_interval_seconds,
                )
            except TimeoutError:
                pass

    async def flush_once(self) -> bool:
        async with self._flush_lock:
            batch = self.buffer.peek_batch(self.batch_size)
            if not batch:
                return True
            try:
                await self.client.report_task_events(batch[0].task_id, batch)
            except Exception as error:
                logger.warning("Runtime event batch upload failed: %s", error)
                return False
            self.buffer.acknowledge(batch)
            return True

    async def flush_task(self, task_id: UUID) -> bool:
        for attempt in range(self.retry_count):
            while self.buffer.has_task(task_id):
                if not await self.flush_once():
                    break
            if not self.buffer.has_task(task_id):
                return True
            await asyncio.sleep(min(0.2 * (attempt + 1), 1.0))
        return not self.buffer.has_task(task_id)


class LocalRuntimeState:
    def __init__(
        self,
        *,
        path: Path,
        device_id: UUID,
        device_display_name: str | None = None,
        server_url: str | None = None,
        recent_limit: int = 50,
    ) -> None:
        self.path = path.resolve()
        self.recent_limit = recent_limit
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=recent_limit)
        self._state: dict[str, Any] = {
            "device_id": str(device_id),
            "device_display_name": device_display_name,
            "worker_version": WORKER_VERSION,
            "server_url": server_url,
            "connection_status": "disconnected",
            "token_status": "configured",
            "last_heartbeat_at": None,
            "skill_sync_status": "not_synced",
            "skill_count": 0,
            "provider_status": None,
            "provider_version": None,
            "provider_account": None,
            "provider_application_count": None,
            "provider_refreshed_at": None,
            "worker_status": "running",
            "current_task_id": None,
            "skill_display_name": None,
            "provider": None,
            "app_name": None,
            "phase": None,
            "latest_message": None,
            "started_at": None,
            "updated_at": datetime.now(UTC).isoformat(),
            "recent_events": [],
        }
        self._write()

    def begin_task(self, task: WorkerTask, *, skill_display_name: str) -> None:
        self._state.update(
            {
                "current_task_id": str(task.task_id),
                "skill_display_name": skill_display_name,
                "provider": None,
                "app_name": None,
                "phase": "queued",
                "latest_message": "任务已领取",
                "started_at": datetime.now(UTC).isoformat(),
            },
        )
        self._write()

    def set_connection(
        self,
        connected: bool,
        *,
        token_status: str | None = None,
    ) -> None:
        self._state["connection_status"] = (
            "connected" if connected else "disconnected"
        )
        if connected:
            self._state["last_heartbeat_at"] = datetime.now(UTC).isoformat()
        if token_status is not None:
            self._state["token_status"] = token_status
        self._write()

    def set_skill_sync(self, synced: bool, *, count: int) -> None:
        self._state["skill_sync_status"] = "synced" if synced else "not_synced"
        self._state["skill_count"] = count
        self._write()

    def set_provider_inventory(self, inventory: Any) -> None:
        status = getattr(inventory, "status", None)
        self._state.update(
            {
                "provider_status": (
                    status.value if hasattr(status, "value") else status
                ),
                "provider_version": getattr(inventory, "provider_version", None),
                "provider_account": getattr(inventory, "account_display", None),
                "provider_application_count": len(
                    getattr(inventory, "applications", []) or [],
                ),
                "provider_refreshed_at": (
                    getattr(inventory, "discovered_at", None).isoformat()
                    if getattr(inventory, "discovered_at", None) is not None
                    else datetime.now(UTC).isoformat()
                ),
            },
        )
        self._write()

    def consume(self, event: RuntimeEvent) -> None:
        metadata = event.metadata
        self._state.update(
            {
                "current_task_id": str(event.task_id),
                "provider": metadata.get("provider", self._state.get("provider")),
                "app_name": metadata.get("app_name", self._state.get("app_name")),
                "phase": metadata.get("phase", self._state.get("phase")),
                "latest_message": event.message,
            },
        )
        self._recent_events.append(
            {
                "seq": event.seq,
                "task_id": str(event.task_id),
                "event_type": event.event_type.value,
                "level": event.level,
                "message": event.message,
                "event_at": event.event_at.isoformat(),
            },
        )
        self._write()

    def stop(self) -> None:
        self._state["worker_status"] = "stopped"
        self._write()

    def finish_task(self) -> None:
        self._state.update(
            {
                "current_task_id": None,
                "skill_display_name": None,
                "provider": None,
                "app_name": None,
                "phase": None,
                "latest_message": None,
                "started_at": None,
            },
        )
        self._write()

    def _write(self) -> None:
        self._state["updated_at"] = datetime.now(UTC).isoformat()
        self._state["recent_events"] = list(self._recent_events)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(self._state, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
