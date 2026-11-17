import asyncio
import logging
from datetime import UTC, datetime

import httpx

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
    _redact_value,
    _SENSITIVE_MESSAGE,
)
from app.result_outbox import OutboxError, ResultOutbox, TerminalDelivery
from app.shop_session_health import ShopSessionHealth
from app.skills import SkillRegistry, registry
from app.skills.registry import SkillClassification
from app.version import WORKER_VERSION
from app.task_images import TaskImagePreparer, TaskImagePreparationError


logger = logging.getLogger(__name__)
_PRECHECK_KIND = "douyin.category_schema"
_PRECHECK_DEVICE_LIMIT = 15


class Worker:
    def __init__(
        self,
        settings: WorkerSettings,
        client: WorkerApiClient,
        executor: Executor,
        event_bus: RuntimeEventBus | None = None,
        event_reporter: BackendEventReporter | None = None,
        local_runtime_state: LocalRuntimeState | None = None,
        skill_registry: SkillRegistry = registry,
        image_preparer: TaskImagePreparer | None = None,
        capability_runtime = None,
        rpa_bridge = None,
        base_updater = None,
    ) -> None:
        self.settings = settings
        self.client = client
        self.executor = executor
        self.event_bus = event_bus or RuntimeEventBus()
        self.event_reporter = event_reporter
        self.local_runtime_state = local_runtime_state
        self.skill_registry = skill_registry
        self.image_preparer = image_preparer
        self.capability_runtime = capability_runtime
        self.rpa_bridge = rpa_bridge
        self.base_updater = base_updater
        self._next_base_check = 0.0
        self._base_update_pending = False
        self.shop_session_health = ShopSessionHealth(rpa_bridge) if rpa_bridge is not None else None
        self._shop_health_probe: asyncio.Task[None] | None = None
        self._last_rpa_inventory = None
        self._rpa_inventory_report_lock = asyncio.Lock()
        self._active_task_ids = set()
        self._next_capability_check = 0.0
        self.result_outbox = ResultOutbox(settings.runtime_root / "result-outbox")
        self.started_at = datetime.now(UTC)
        self.worker_version = WORKER_VERSION
        self._skill_snapshot_synced = False
        self._skill_snapshot_generation = 0
        self._skill_snapshot_lock = asyncio.Lock()
        self._terminal_delivery_lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._heartbeat_consecutive_failures = 0

    async def run(self, stop_event: asyncio.Event) -> None:
        heartbeat_supervisor_task = asyncio.create_task(
            self._heartbeat_supervisor(stop_event),
            name="worker-heartbeat-supervisor",
        )
        reporter_task = (
            asyncio.create_task(self.event_reporter.run(stop_event))
            if self.event_reporter is not None
            else None
        )
        rpa_task = (asyncio.create_task(self._rpa_inventory_loop(stop_event))
                    if self.capability_runtime is not None else None)
        prechecks: set[asyncio.Task[None]] = set()
        try:
            while not stop_event.is_set():
                try:
                    for finished in tuple(prechecks):
                        if finished.done():
                            prechecks.remove(finished)
                            try:
                                finished.result()
                            except asyncio.CancelledError:
                                pass
                            except Exception as error:
                                logger.warning("Worker precheck task failed: %s", error)
                    if not await self._deliver_pending_terminals():
                        await self._wait_or_stop(stop_event, self.settings.poll_interval_seconds)
                        continue
                    if not prechecks:
                        # Capability files must not change under active tasks.
                        await self._refresh_capabilities_if_due()
                        if self._base_update_pending:
                            self._next_base_check = 0.0
                        if await self._update_base_if_idle():
                            stop_event.set()
                            break
                        self._base_update_pending = False
                    else:
                        await self._check_base_update_for_drain()
                    if not self.executor.can_claim():
                        task = None
                    elif prechecks and not self._base_update_pending and len(prechecks) < _PRECHECK_DEVICE_LIMIT:
                        task = await self.client.claim_precheck()
                    elif prechecks:
                        task = None
                    else:
                        task = await self.client.claim()
                    if task is not None:
                        # Verification never adds a competing platform request
                        # when actual work starts on this Worker.
                        self._active_task_ids.add(task.task_id)
                        await self._cancel_shop_health_probe()
                        if task.skill_id == _PRECHECK_KIND:
                            prechecks.add(asyncio.create_task(self._execute_claimed_task(task)))
                            # Fill available slots immediately instead of adding
                            # the ordinary idle-poll interval to every claim.
                            continue
                        await self._execute_claimed_task(task)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.warning("Worker poll cycle failed: %s", error)
                if prechecks:
                    await self._wait_for_prechecks_or_stop(prechecks, stop_event)
                else:
                    await self._wait_or_stop(stop_event, self.settings.poll_interval_seconds)
        finally:
            # As with the existing single-task loop, a normal stop waits for
            # already claimed work and its durable result before disconnecting.
            if prechecks:
                await asyncio.gather(*prechecks, return_exceptions=True)
            heartbeat_supervisor_task.cancel()
            if reporter_task is not None:
                reporter_task.cancel()
            if rpa_task is not None:
                rpa_task.cancel()
            await self._cancel_shop_health_probe()
            await asyncio.gather(
                *[
                    task
                    for task in (
                        heartbeat_supervisor_task,
                        reporter_task,
                        rpa_task,
                    )
                    if task is not None
                ],
                return_exceptions=True,
            )
            if self.local_runtime_state is not None:
                self.local_runtime_state.stop()
            await self.client.close()

    async def _wait_for_prechecks_or_stop(
        self, prechecks: set[asyncio.Task[None]], stop_event: asyncio.Event,
    ) -> None:
        stop_wait = asyncio.create_task(stop_event.wait())
        try:
            await asyncio.wait(
                [*prechecks, stop_wait],
                timeout=self.settings.poll_interval_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            if not stop_wait.done():
                stop_wait.cancel()
            await asyncio.gather(stop_wait, return_exceptions=True)

    async def _heartbeat_supervisor(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(stop_event),
                name="worker-heartbeat-loop",
            )
            self._heartbeat_task = heartbeat_task
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                current_task = asyncio.current_task()
                if current_task is not None and current_task.cancelling():
                    raise
                if stop_event.is_set():
                    return
                logger.error("Worker heartbeat loop was cancelled unexpectedly")
            except Exception as error:
                logger.exception(
                    "Worker heartbeat loop exited unexpectedly: %s",
                    error,
                )
            else:
                if stop_event.is_set():
                    return
                logger.error("Worker heartbeat loop exited unexpectedly")
            finally:
                if self._heartbeat_task is heartbeat_task:
                    self._heartbeat_task = None

            if stop_event.is_set():
                return
            logger.warning(
                "Worker heartbeat loop restarting in %.1f seconds",
                self.settings.heartbeat_interval_seconds,
            )
            await self._wait_or_stop(
                stop_event,
                self.settings.heartbeat_interval_seconds,
            )

    async def _heartbeat_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            await self._heartbeat_once()
            await self._wait_or_stop(
                stop_event,
                self.settings.heartbeat_interval_seconds,
            )

    async def _heartbeat_once(
        self,
        *,
        sync_skill_capabilities: bool = True,
    ) -> bool:
        try:
            await self.client.heartbeat(
                worker_version=self.worker_version,
                started_at=self.started_at,
            )
        except asyncio.CancelledError:
            raise
        except WorkerApiError as error:
            self._record_heartbeat_failure(
                error,
                token_status=(
                    "invalid" if error.status_code in {401, 403} else None
                ),
            )
            return False
        except Exception as error:
            self._record_heartbeat_failure(error)
            return False

        self._record_heartbeat_success()
        if not sync_skill_capabilities:
            return True
        # Only one report may be in flight: a late old response must never
        # overwrite a newer snapshot or mark it as synchronized.
        async with self._skill_snapshot_lock:
            for _ in range(2):
                if self._skill_snapshot_synced:
                    break
                generation = self._skill_snapshot_generation
                descriptors = self._current_skill_descriptors()
                try:
                    await self.client.report_skill_capabilities(
                        SkillCapabilitySnapshot(skills=descriptors),
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    self._set_skill_sync_state(False, self._current_skill_descriptors())
                    logger.warning("Skill capability snapshot sync failed: %s", error)
                    break
                if generation == self._skill_snapshot_generation:
                    self._skill_snapshot_synced = True
                    self._set_skill_sync_state(True, descriptors)
                    break
                # The installed set changed while this report was in flight.
                # Retry once immediately; another change waits for the next
                # ordinary heartbeat instead of an unbounded retry loop.
                self._skill_snapshot_synced = False
                self._set_skill_sync_state(False, self._current_skill_descriptors())
        return True

    def _current_skill_descriptors(self):
        descriptors = list(self.skill_registry.descriptors())
        if self.capability_runtime is not None:
            descriptors.extend(self.capability_runtime.descriptors())
        return descriptors

    def _set_skill_sync_state(self, synced, descriptors) -> None:
        if self.local_runtime_state is None:
            return
        try:
            self.local_runtime_state.set_skill_sync(
                synced,
                count=len(descriptors),
                business_count=sum(item.classification is SkillClassification.BUSINESS for item in descriptors),
            )
        except Exception as error:
            logger.warning("Worker skill sync status update failed: %s", error)

    def _invalidate_skill_snapshot(self) -> None:
        self._skill_snapshot_generation += 1
        self._skill_snapshot_synced = False
        self._set_skill_sync_state(False, self._current_skill_descriptors())

    def _record_heartbeat_failure(
        self,
        error: Exception,
        *,
        token_status: str | None = None,
    ) -> None:
        self._invalidate_skill_snapshot()
        self._heartbeat_consecutive_failures += 1
        self._set_local_connection(False, token_status=token_status)
        if (
            self._heartbeat_consecutive_failures == 1
            or self._heartbeat_consecutive_failures % 10 == 0
        ):
            logger.warning(
                "Worker heartbeat failed (consecutive=%s): %s",
                self._heartbeat_consecutive_failures,
                error,
            )

    def _record_heartbeat_success(self) -> None:
        previous_failures = self._heartbeat_consecutive_failures
        self._heartbeat_consecutive_failures = 0
        self._set_local_connection(True, token_status="valid")
        if previous_failures:
            logger.info(
                "Worker heartbeat recovered after %s consecutive failure(s)",
                previous_failures,
            )

    def _set_local_connection(
        self,
        connected: bool,
        *,
        token_status: str | None = None,
    ) -> None:
        if self.local_runtime_state is None:
            return
        try:
            self.local_runtime_state.set_connection(
                connected,
                token_status=token_status,
            )
        except Exception as error:
            logger.warning("Worker runtime status update failed: %s", error)

    async def _rpa_inventory_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                inventory = await self.rpa_bridge.list_shops()
                self._last_rpa_inventory = inventory
                await self._report_rpa_inventory(inventory)
                if (self.shop_session_health is not None and not self._active_task_ids
                        and (self._shop_health_probe is None or self._shop_health_probe.done())):
                    shop = self.shop_session_health.due(inventory.shops)
                    if shop is not None:
                        self._shop_health_probe = asyncio.create_task(self._verify_local_shop(inventory, shop))
            except asyncio.CancelledError:
                raise
            except Exception:
                self._last_rpa_inventory = None
                try:
                    await self.client.report_rpa_inventory({"available": False})
                except Exception:
                    pass
            await self._wait_or_stop(stop_event, self.settings.provider_inventory_interval_seconds)

    async def _report_rpa_inventory(self, inventory) -> None:
        async with self._rpa_inventory_report_lock:
            if self._last_rpa_inventory is not inventory:
                return
            shops = []
            for shop in inventory.shops:
                item = shop.model_dump(mode="json", by_alias=True)
                if self.shop_session_health is not None:
                    item.update(self.shop_session_health.report(shop))
                shops.append(item)
            await self.client.report_rpa_inventory({"available": True,
                "installation_id": str(inventory.installation_id), "shops": shops})

    async def _verify_local_shop(self, inventory, shop) -> None:
        try:
            await self.shop_session_health.check(shop)
            # An older probe may not replace a newly discovered RPA snapshot.
            if self._last_rpa_inventory is inventory:
                await self._report_rpa_inventory(inventory)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Status is advisory; retry on a later inventory cycle.
            pass

    async def _cancel_shop_health_probe(self) -> None:
        probe, self._shop_health_probe = self._shop_health_probe, None
        if probe is not None:
            if not probe.done():
                probe.cancel()
            await asyncio.gather(probe, return_exceptions=True)

    async def _execute_claimed_task(self, task: WorkerTask) -> None:
        try:
            await self._execute_task(task)
        finally:
            self._active_task_ids.discard(task.task_id)

    async def _refresh_capabilities_if_due(self) -> None:
        if self.capability_runtime is None:
            return
        now = asyncio.get_running_loop().time()
        if now < self._next_capability_check:
            return
        self._next_capability_check = now + self.settings.capability_update_interval_seconds
        previous = self.capability_runtime.descriptors()
        try:
            changed = await self.capability_runtime.updater.sync_when_idle(
                self.client, idle=True, validate_entry=self.capability_runtime.validate_entry)
            self.capability_runtime.refresh()
            if changed or previous != self.capability_runtime.descriptors():
                self._invalidate_skill_snapshot()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Offline/update failure keeps the last signed package, provided it
            # still passes its local integrity check.
            try:
                self.capability_runtime.refresh()
            except Exception:
                self._invalidate_skill_snapshot()
            else:
                if previous != self.capability_runtime.descriptors():
                    self._invalidate_skill_snapshot()
            logger.warning("Capability update unavailable; retaining verified release when possible")

    async def _update_base_if_idle(self) -> bool:
        if self.base_updater is None or self._active_task_ids:
            return False
        now = asyncio.get_running_loop().time()
        if now < self._next_base_check:
            return False
        self._next_base_check = now + self.settings.base_update_interval_seconds
        try:
            # Preserve task events as well as durable results before stopping.
            if self.event_reporter is not None and len(self.event_reporter.buffer):
                if not await self.event_reporter.flush_once() or len(self.event_reporter.buffer):
                    return False
            release = await self.base_updater.stage_when_idle(self.client, idle=True)
            if release is None:
                return False
            from app.base_update_handoff import start_handoff
            return await asyncio.to_thread(start_handoff, self.base_updater, release)
        except asyncio.CancelledError:
            raise
        except WorkerApiError as error:
            if error.status_code != 404:
                logger.warning("Worker base update unavailable (HTTP %s); keeping current version", error.status_code)
        except Exception as error:
            from app.base_updates import BaseUpdateError
            reason = str(error) if isinstance(error, BaseUpdateError) else type(error).__name__
            logger.warning("Worker base update unavailable (%s); keeping current version", reason)
        return False

    async def _check_base_update_for_drain(self) -> None:
        """Stop taking new work when an authenticated release is available."""
        if self.base_updater is None or self._base_update_pending:
            return
        now = asyncio.get_running_loop().time()
        if now < self._next_base_check:
            return
        self._next_base_check = now + self.settings.base_update_interval_seconds
        try:
            self._base_update_pending = await self.base_updater.update_available(self.client)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A network outage must not stop ordinary work.
            self._base_update_pending = False

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
        execution_task = asyncio.create_task(self._prepare_and_execute(task))
        lease_task = asyncio.create_task(self._renew_lease(task))
        try:
            done, _ = await asyncio.wait(
                {execution_task, lease_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if lease_task in done and execution_task not in done:
                lease_error = lease_task.exception()
                if lease_error is not None:
                    execution_task.cancel()
                    await asyncio.gather(execution_task, return_exceptions=True)
                    raise lease_error
            result = await execution_task
            safe_message = _SENSITIVE_MESSAGE.sub(
                lambda match: f"{match.group(1)}=[REDACTED]",
                result.error_message or "Skill execution failed",
            )
            delivery = TerminalDelivery(
                task_id=task.task_id,
                skill_id=task.skill_id,
                result_delivery=task.result_delivery,
                status=result.status.value,
                result=_redact_value(result.result or {}) if result.status is ExecutionStatus.SUCCESS
                else (_redact_value(result.result) if result.result is not None else None),
                error_code=result.error_code or "SKILL_EXECUTION_FAILED"
                if result.status is ExecutionStatus.FAILED else None,
                error_message=safe_message if result.status is ExecutionStatus.FAILED else None,
            )
            # Once execution has returned, make its result durable before any
            # event flush, inventory report or completion network operation.
            self.result_outbox.store(delivery)
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
            await self._deliver_pending_terminals()
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
            if self.local_runtime_state is not None:
                self.local_runtime_state.finish_task(task.task_id)
            await self._send_immediate_heartbeat()

    async def _deliver_pending_terminals(self) -> bool:
        """Deliver stored results before claiming another task; never rerun them."""
        async with self._terminal_delivery_lock:
            return await self._deliver_pending_terminals_locked()

    async def _deliver_pending_terminals_locked(self) -> bool:
        try:
            pending = self.result_outbox.pending()
        except OutboxError:
            logger.error("Worker terminal outbox requires local attention")
            return False
        for delivery in pending:
            try:
                if delivery.skill_id.startswith("yingdao."):
                    # Preserve old terminal evidence locally without replaying a
                    # retired task or blocking new Worker results.
                    self.result_outbox.reject(delivery)
                    continue
                if delivery.skill_id == "douyin.category_schema":
                    if delivery.result_delivery == "product":
                        digest = await self.client.deliver_product_precheck(
                            delivery.task_id, status=delivery.status, result=delivery.result,
                            error_code=delivery.error_code, error_message=delivery.error_message,
                        )
                        await self.client.acknowledge_product_precheck(
                            delivery.task_id, status=delivery.status, payload_sha256=digest,
                            error_code=delivery.error_code,
                        )
                    else:
                        await self.client.complete_precheck(
                            delivery.task_id, status=delivery.status,
                            result=delivery.result, error_code=delivery.error_code,
                            error_message=delivery.error_message,
                        )
                elif delivery.status == "success":
                    await self.client.complete(delivery.task_id, delivery.result or {})
                else:
                    await self.client.fail(
                        delivery.task_id, error_code=delivery.error_code or "SKILL_EXECUTION_FAILED",
                        error_message=delivery.error_message or "Skill execution failed",
                    )
            except WorkerApiError as error:
                if error.status_code in {400, 403, 404, 409, 422}:
                    try:
                        self.result_outbox.reject(delivery)
                    except OutboxError:
                        logger.error("Worker terminal rejection requires local attention")
                        return False
                    logger.warning("Worker terminal result rejected task=%s status=%s",
                                   delivery.task_id, error.status_code)
                    continue
                return False
            except (OSError, httpx.HTTPError):
                return False
            self.result_outbox.acknowledge(delivery)
        return True

    async def _prepare_and_execute(self, task: WorkerTask) -> ExecutionResult:
        if self.capability_runtime is not None and (
            self.capability_runtime.has_skill(task.skill_id) or task.skill_id == "douyin.category_schema"
        ):
            return await self.capability_runtime.execute(task)
        if self.image_preparer is not None:
            self.event_bus.emit(
                task.task_id,
                RuntimeEventType.STATUS,
                "Worker 正在准备任务图片",
                metadata={"phase": "preparing_images"},
            )
            try:
                prepared = await self.image_preparer.prepare(task)
            except TaskImagePreparationError as error:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error_code=error.code,
                    error_message=error.message,
                )
            self.event_bus.emit(
                task.task_id,
                RuntimeEventType.STATUS,
                "任务图片准备完成",
                metadata={"phase": "images_ready", "image_count": len(prepared)},
            )
        return await self.executor.execute(task)

    async def _renew_lease(self, task: WorkerTask) -> None:
        while True:
            await asyncio.sleep(self.settings.lease_renew_interval_seconds)
            await self.client.renew(task.task_id)

    async def _send_immediate_heartbeat(self) -> None:
        await self._heartbeat_once(sync_skill_capabilities=False)

    @staticmethod
    async def _wait_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except TimeoutError:
            pass
