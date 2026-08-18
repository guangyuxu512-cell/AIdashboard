import asyncio
import logging
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

from app.client import WorkerApiClient
from app.config import WorkerSettings
from app.contracts import ExecutionStatus, WorkerTask
from app.executors import Executor


logger = logging.getLogger(__name__)


def get_worker_version() -> str:
    try:
        return version("ecommerce-control-worker")
    except PackageNotFoundError:
        return "0.1.0"


class Worker:
    def __init__(
        self,
        settings: WorkerSettings,
        client: WorkerApiClient,
        executor: Executor,
    ) -> None:
        self.settings = settings
        self.client = client
        self.executor = executor
        self.started_at = datetime.now(UTC)
        self.worker_version = get_worker_version()

    async def run(self, stop_event: asyncio.Event) -> None:
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(stop_event))
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
            await asyncio.gather(heartbeat_task, return_exceptions=True)
            await self.client.close()

    async def _heartbeat_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self.client.heartbeat(
                    worker_version=self.worker_version,
                    started_at=self.started_at,
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Worker heartbeat failed: %s", error)
            await self._wait_or_stop(
                stop_event,
                self.settings.heartbeat_interval_seconds,
            )

    async def _execute_task(self, task: WorkerTask) -> None:
        await self._send_immediate_heartbeat()
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
            if result.status is ExecutionStatus.SUCCESS:
                if result.provider_inventory is not None:
                    try:
                        await self.client.report_provider_inventory(
                            result.provider_inventory,
                        )
                    except Exception:
                        await self.client.fail(
                            task.task_id,
                            error_code="PROVIDER_INVENTORY_REPORT_FAILED",
                            error_message="Provider inventory could not be saved",
                        )
                        return
                await self.client.complete(task.task_id, result.result or {})
            else:
                await self.client.fail(
                    task.task_id,
                    error_code=result.error_code or "SKILL_EXECUTION_FAILED",
                    error_message=result.error_message or "Skill execution failed",
                )
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
        except Exception as error:
            logger.warning("Worker runtime heartbeat failed: %s", error)

    @staticmethod
    async def _wait_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except TimeoutError:
            pass
