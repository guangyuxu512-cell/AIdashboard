import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlencode

from app.contracts import RuntimeEventType
from app.providers.yingdao.contracts import (
    YingdaoDiscoveryResult,
    YingdaoExecutionRequest,
    YingdaoExecutionResult,
    YingdaoExecutionStatus,
)
from app.providers.yingdao.discovery import YingdaoDiscoveryService
from app.providers.yingdao.environment import YingdaoVersionResolver
from app.providers.yingdao.tasklog import (
    YingdaoTaskLogError,
    YingdaoTaskLogFollower,
    YingdaoTaskLogParser,
)
from app.runtime_events import RuntimeEventBus


class YingdaoTriggerError(RuntimeError):
    def __init__(self, message: str, *, code: str = "RPA_TRIGGER_FAILED") -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class YingdaoAdapter(Protocol):
    async def discover(self) -> YingdaoDiscoveryResult: ...

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]: ...

    async def cleanup(self, request: YingdaoExecutionRequest) -> None: ...


def build_shadowbot_run_uri(app_uuid: str, params: Mapping[str, Any]) -> str:
    query: list[tuple[str, str]] = [("robot-uuid", app_uuid)]
    for key, value in params.items():
        encoded_value = (
            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            if isinstance(value, (dict, list))
            else str(value)
        )
        query.append((str(key), encoded_value))
    return f"shadowbot:Run?{urlencode(query)}"


class RuntimeYingdaoAdapter:
    def __init__(
        self,
        *,
        discovery_service: YingdaoDiscoveryService,
        install_root: Path,
        data_root: Path,
        event_bus: RuntimeEventBus,
        tasklog_association_timeout_seconds: float = 15,
    ) -> None:
        self.discovery_service = discovery_service
        self.install_root = install_root.resolve()
        self.data_root = data_root.resolve()
        self.event_bus = event_bus
        self.tasklog_association_timeout_seconds = tasklog_association_timeout_seconds
        self._execution_lock = asyncio.Lock()

    async def discover(self) -> YingdaoDiscoveryResult:
        return await self.discovery_service.discover()

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]:
        async with self._execution_lock:
            environment = YingdaoVersionResolver(self.install_root).resolve()
            if (
                not environment.execution_available
                or environment.execution_executable_path is None
            ):
                raise YingdaoTriggerError(
                    environment.execution_unavailable_reason
                    or "Yingdao execution version is unavailable",
                    code="YINGDAO_EXECUTION_VERSION_UNSUPPORTED",
                )

            task_logs = self.data_root / "users" / request.user_id / "task_logs"
            if not task_logs.is_dir():
                raise YingdaoTriggerError(
                    "Yingdao task_logs directory was not found",
                    code="YINGDAO_TASKLOG_DIRECTORY_NOT_FOUND",
                )
            before = {
                path.resolve(): (path.stat().st_size, path.stat().st_mtime_ns)
                for path in task_logs.glob("*.tasklog")
                if path.is_file()
            }
            dispatch_at = datetime.now(UTC)
            uri = build_shadowbot_run_uri(request.app_id, request.params)
            metadata = {
                "provider": "yingdao",
                "app_uuid": request.app_id,
                "app_name": request.app_name,
                "phase": "launching",
                "execution_version": environment.execution_version,
            }
            self.event_bus.emit(
                request.task_id,
                RuntimeEventType.STATUS,
                f"正在启动影刀应用 {request.app_name}",
                metadata=metadata,
            )
            try:
                process = await asyncio.create_subprocess_exec(
                    str(environment.execution_executable_path),
                    uri,
                )
            except OSError as error:
                raise YingdaoTriggerError(
                    "ShadowBot.exe could not be started",
                ) from error
            asyncio.create_task(process.wait())

            tasklog = await self._wait_for_tasklog(
                task_logs,
                before=before,
                dispatch_at=dispatch_at,
                app_name=request.app_name,
            )
            yingdao_task_uuid = tasklog.stem
            self.event_bus.emit(
                request.task_id,
                RuntimeEventType.STATUS,
                "影刀已接受任务并创建运行日志",
                metadata={
                    **metadata,
                    "yingdao_task_uuid": yingdao_task_uuid,
                },
            )
            follower = YingdaoTaskLogFollower(
                path=tasklog,
                task_id=request.task_id,
                app_uuid=request.app_id,
                app_name=request.app_name,
                yingdao_task_uuid=yingdao_task_uuid,
                event_bus=self.event_bus,
            )
            try:
                await follower.follow_until_terminal()
            except YingdaoTaskLogError as error:
                raise YingdaoTriggerError(error.message, code=error.code) from error
            if not follower.started or not follower.exited:
                raise YingdaoTriggerError(
                    "Yingdao tasklog did not contain verified start and exit records",
                    code="RPA_RESULT_INVALID",
                )
            return YingdaoExecutionResult(
                status=YingdaoExecutionStatus.SUCCESS,
                result={
                    "app_uuid": request.app_id,
                    "app_name": request.app_name,
                    "yingdao_task_uuid": yingdao_task_uuid,
                    "execution_version": environment.execution_version,
                },
            ).model_dump(mode="json")

    async def _wait_for_tasklog(
        self,
        directory: Path,
        *,
        before: dict[Path, tuple[int, int]],
        dispatch_at: datetime,
        app_name: str,
    ) -> Path:
        deadline = asyncio.get_running_loop().time() + (
            self.tasklog_association_timeout_seconds
        )
        candidates: set[Path] = set()
        while asyncio.get_running_loop().time() < deadline:
            for path in directory.glob("*.tasklog"):
                resolved = path.resolve()
                if resolved in before or not path.is_file():
                    continue
                try:
                    modified_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
                except OSError:
                    continue
                if modified_at >= dispatch_at - timedelta(seconds=2):
                    candidates.add(resolved)
            if len(candidates) == 1:
                return next(iter(candidates))
            for candidate in sorted(candidates):
                if await asyncio.to_thread(
                    self._tasklog_mentions_app,
                    candidate,
                    app_name,
                ):
                    return candidate
            await asyncio.sleep(0.2)
        raise YingdaoTriggerError(
            "Yingdao did not create a new tasklog for this dispatch",
            code="YINGDAO_TASKLOG_NOT_FOUND",
        )

    @staticmethod
    def _tasklog_mentions_app(path: Path, app_name: str) -> bool:
        try:
            parser = YingdaoTaskLogParser()
            records = parser.feed(path.read_bytes())
        except (OSError, YingdaoTaskLogError):
            return False
        return any(app_name in record.message for record in records)

    async def cleanup(self, request: YingdaoExecutionRequest) -> None:
        del request


class UnavailableYingdaoAdapter:
    """Production-safe placeholder until a complete local trigger exists."""

    async def discover(self) -> YingdaoDiscoveryResult:
        return YingdaoDiscoveryResult(provider_available=False)

    async def execute(
        self,
        request: YingdaoExecutionRequest,
    ) -> Mapping[str, Any]:
        del request
        raise YingdaoTriggerError("Yingdao trigger contract is not configured")

    async def cleanup(self, request: YingdaoExecutionRequest) -> None:
        del request
