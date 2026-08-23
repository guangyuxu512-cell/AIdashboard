import asyncio
import logging
from typing import Protocol
from datetime import UTC, datetime

from app.client import WorkerApiClient, WorkerApiError
from app.config import WorkerSettings
from app.contracts import (
    ExecutionResult,
    ExecutionStatus,
    RuntimeEventType,
    SkillCapabilitySnapshot,
    WorkerTask,
)
from app.executors import Executor
from app.runtime_events import (
    BackendEventReporter,
    LocalRuntimeState,
    RuntimeEventBus,
)
from app.skills import SkillRegistry, registry
from app.version import WORKER_VERSION
from app.contracts import ProviderInventoryReport
from app.providers.yingdao.contracts import YingdaoDiscoveryResult


logger = logging.getLogger(__name__)


class ProviderDiscovery(Protocol):
    async def discover(self) -> YingdaoDiscoveryResult: ...


class Worker:
    def __init__(
        self,
        settings: WorkerSettings,
        client: WorkerApiClient,
        executor: Executor,
        event_bus: RuntimeEventBus | None = None,
        event_reporter: BackendEventReporter | None = None,
        local_runtime_state: LocalRuntimeState | None = None,
        provider_discovery: ProviderDiscovery | None = None,
        skill_registry: SkillRegistry = registry,
    ) -> None:
        self.settings = settings
        self.client = client
        self.executor = executor
        self.event_bus = event_bus or RuntimeEventBus()
        self.event_reporter = event_reporter
        self.local_runtime_state = local_runtime_state
        self.provider_discovery = provider_discovery
        self.skill_registry = skill_registry
        self.started_at = datetime.now(UTC)
        self.worker_version = WORKER_VERSION
        self._skill_snapshot_synced = False

    async def run(self, stop_event: asyncio.Event) -> None:
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(stop_event))
        reporter_task = (
            asyncio.create_task(self.event_reporter.run(stop_event))
            if self.event_reporter is not None
            else None
        )
        provider_task = (
            asyncio.create_task(self._provider_inventory_loop(stop_event))
            if self.provider_discovery is not None
            else None
        )
        try:
            while not stop_event.is_set():
                try:
                    task = await self.client.claim()
                    if task is not None:
                        await self._execute_task(task)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.warning("Worker poll cycle failed: %s", error)
                await self._wait_or_stop(
                    stop_event,
                    self.settings.poll_interval_seconds,
                )
        finally:
            heartbeat_task.cancel()
            if reporter_task is not None:
                reporter_task.cancel()
            if provider_task is not None:
                provider_task.cancel()
            await asyncio.gather(
                *[task for task in (heartbeat_task, reporter_task, provider_task) if task is not None],
                return_exceptions=True,
            )
            if self.local_runtime_state is not None:
                self.local_runtime_state.stop()
            await self.client.close()

    async def _heartbeat_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._heartbeat_once()
            await self._wait_or_stop(
                stop_event,
                self.settings.heartbeat_interval_seconds,
            )

    async def _heartbeat_once(self) -> None:
        try:
            await self.client.heartbeat(
                worker_version=self.worker_version,
                started_at=self.started_at,
            )
        except asyncio.CancelledError:
            raise
        except WorkerApiError as error:
            self._skill_snapshot_synced = False
            if self.local_runtime_state is not None:
                self.local_runtime_state.set_connection(
                    False,
                    token_status="invalid" if error.status_code == 401 else None,
                )
            logger.warning("Worker heartbeat failed: %s", error)
            return
        except Exception as error:
            self._skill_snapshot_synced = False
            if self.local_runtime_state is not None:
                self.local_runtime_state.set_connection(False)
            logger.warning("Worker heartbeat failed: %s", error)
            return

        if self.local_runtime_state is not None:
            self.local_runtime_state.set_connection(True, token_status="valid")
        if self._skill_snapshot_synced:
            return
        try:
            await self.client.report_skill_capabilities(
                SkillCapabilitySnapshot(
                    skills=list(self.skill_registry.descriptors()),
                ),
            )
            self._skill_snapshot_synced = True
            if self.local_runtime_state is not None:
                self.local_runtime_state.set_skill_sync(
                    True,
                    count=len(list(self.skill_registry.descriptors())),
                )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if self.local_runtime_state is not None:
                self.local_runtime_state.set_skill_sync(
                    False,
                    count=len(list(self.skill_registry.descriptors())),
                )
            logger.warning("Skill capability snapshot sync failed: %s", error)

    async def _provider_inventory_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                if self.provider_discovery is not None:
                    inventory = await self.provider_discovery.discover()
                    if self.local_runtime_state is not None:
                        self.local_runtime_state.set_provider_inventory(inventory)
                    await self.client.report_provider_inventory(
                        ProviderInventoryReport(
                            provider_code="yingdao",
                            inventory=inventory.model_dump(mode="json", by_alias=True),
                        ),
                    )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Provider inventory refresh failed: %s", error)
            await self._wait_or_stop(
                stop_event,
                self.settings.provider_inventory_interval_seconds,
            )

    async def _execute_task(self, task: WorkerTask) -> None:
        await self._send_immediate_heartbeat()
        definition = self.skill_registry.get(task.skill_id)
        if self.local_runtime_state is not None:
            self.local_runtime_state.begin_task(
                task,
                skill_display_name=(
                    definition.display_name if definition is not None else task.skill_id
                ),
            )
        self.event_bus.emit(
            task.task_id,
            RuntimeEventType.STATUS,
            "Worker 已领取任务",
            metadata={
                "phase": "queued",
                "provider": (
                    definition.provider.value
                    if definition is not None and definition.provider is not None
                    else (
                        definition.runtime.value if definition is not None else None
                    )
                ),
                "skill_display_name": (
                    definition.display_name if definition is not None else task.skill_id
                ),
            },
        )
        execution_task = asyncio.create_task(self.executor.execute(task))
        lease_task = asyncio.create_task(self._renew_lease(task))
        try:
            done, _ = await asyncio.wait(
                {execution_task, lease_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if lease_task in done:
                lease_error = lease_task.exception()
                if lease_error is not None:
                    execution_task.cancel()
                    await asyncio.gather(execution_task, return_exceptions=True)
                    raise lease_error
            result = await execution_task
            lease_task.cancel()
            await asyncio.gather(lease_task, return_exceptions=True)
            if (
                result.status is ExecutionStatus.SUCCESS
                and result.provider_inventory is not None
            ):
                try:
                    await self.client.report_provider_inventory(
                        result.provider_inventory,
                    )
                except Exception:
                    result = ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        error_code="PROVIDER_INVENTORY_REPORT_FAILED",
                        error_message="Provider inventory could not be saved",
                    )
            terminal_metadata = {
                "phase": (
                    "succeeded"
                    if result.status is ExecutionStatus.SUCCESS
                    else (
                        "timeout"
                        if result.error_code in {"RPA_TIMEOUT", "SKILL_TIMEOUT"}
                        else "failed"
                    )
                ),
            }
            if result.result is not None:
                for key in ("app_uuid", "app_name", "yingdao_task_uuid"):
                    if key in result.result:
                        terminal_metadata[key] = result.result[key]
            self.event_bus.emit(
                task.task_id,
                (
                    RuntimeEventType.COMPLETED
                    if result.status is ExecutionStatus.SUCCESS
                    else RuntimeEventType.FAILED
                ),
                (
                    "任务执行完成"
                    if result.status is ExecutionStatus.SUCCESS
                    else result.error_message or "任务执行失败"
                ),
                metadata=terminal_metadata,
            )
            if self.event_reporter is not None:
                await self.event_reporter.flush_task(task.task_id)
            if result.status is ExecutionStatus.SUCCESS:
                await self.client.complete(task.task_id, result.result or {})
            else:
                await self.client.fail(
                    task.task_id,
                    error_code=result.error_code or "SKILL_EXECUTION_FAILED",
                    error_message=result.error_message or "Skill execution failed",
                )
            if self.local_runtime_state is not None:
                self.local_runtime_state.finish_task()
        finally:
            if not execution_task.done():
                execution_task.cancel()
            if not lease_task.done():
                lease_task.cancel()
            await asyncio.gather(
                execution_task,
                lease_task,
                return_exceptions=True,
            )
            await self._send_immediate_heartbeat()

    async def _renew_lease(self, task: WorkerTask) -> None:
        while True:
            await asyncio.sleep(self.settings.lease_renew_interval_seconds)
            await self.client.renew(task.task_id)

    async def _send_immediate_heartbeat(self) -> None:
        try:
            await self.client.heartbeat(
                worker_version=self.worker_version,
                started_at=self.started_at,
            )
            if self.local_runtime_state is not None:
                self.local_runtime_state.set_connection(True, token_status="valid")
        except Exception as error:
            if self.local_runtime_state is not None:
                self.local_runtime_state.set_connection(False)
            logger.warning("Worker runtime heartbeat failed: %s", error)

    @staticmethod
    async def _wait_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except TimeoutError:
            pass
