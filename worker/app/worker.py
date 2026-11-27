import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

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
from app.rpa_session_bridge import LocalShop
from app.shop_session_health import ShopSessionHealth
from app.skills import SkillRegistry, registry
from app.skills.registry import SkillClassification
from app.version import WORKER_VERSION
from app.task_images import TaskImagePreparer, TaskImagePreparationError


logger = logging.getLogger(__name__)
_PRECHECK_KIND = "douyin.category_schema"
_PRECHECK_DEVICE_LIMIT = 15
_COMPASS_KIND = "douyin.compass_selection"
_MERCHANT_KIND = "douyin.merchant_products"
# Do not start a background check near the end of a selection interval.
_HEALTH_MIN_SELECTION_GAP = 25.0


def _is_compass_selection(task: WorkerTask) -> bool:
    return (task.skill_id == _COMPASS_KIND and task.input.get('operation') in {'categories', 'rank', 'basic'}
            and len(task.local_shops) == 1)


def _is_parallel_shop_task(task: WorkerTask) -> bool:
    return (_is_compass_selection(task) or task.skill_id == _MERCHANT_KIND
            and task.input.get('operation') == 'list' and len(task.local_shops) == 1)


def _health_task_scope(task: WorkerTask) -> tuple[str, bool] | None:
    """Known platform shop and whether the task is a Compass selection."""
    if _is_parallel_shop_task(task):
        shop_id = task.local_shops[0].platform_shop_id
        return (shop_id, True) if shop_id else None
    if task.skill_id == _PRECHECK_KIND:
        shop_id = task.input.get("platform_shop_id")
        return (shop_id, False) if isinstance(shop_id, str) and shop_id else None
    # Other tasks may have their own local side effects: retain exclusive
    # behavior when their exact shop scope is not known to this runtime.
    return None


def _session_task_scope(task: WorkerTask) -> tuple[str, str, str] | None:
    if task.skill_id == _PRECHECK_KIND:
        local, platform, kind = task.input.get('local_shop_id'), task.input.get('platform_shop_id'), 'merchant'
    elif task.skill_id in {_MERCHANT_KIND, _COMPASS_KIND} and len(task.local_shops) == 1:
        source = task.local_shops[0]
        if source.platform != 'douyin':
            return None
        local, platform = source.local_shop_id, source.platform_shop_id
        kind = 'compass' if task.skill_id == _COMPASS_KIND else 'merchant'
    else:
        return None
    return (local, platform, kind) if isinstance(local, str) and local and isinstance(platform, str) and platform else None


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
        self._shop_health_probe_shop: str | None = None
        self._shop_health_probe_is_refresh = False
        self._pending_shop_refresh: dict[tuple[str, str | None], LocalShop] = {}
        self._session_rechecks: dict[tuple[str, str], set[str]] = {}
        self._recent_session_rechecks: dict[tuple[str, str, str, str], tuple[str | None, float]] = {}
        self._rpa_inventory_wakeup = asyncio.Event()
        self._refresh_done: dict[str, asyncio.Event] = {}
        self._task_expiry_revisions: dict[UUID, str] = {}
        self._last_rpa_inventory = None
        self._rpa_inventory_report_lock = asyncio.Lock()
        self._active_task_ids = set()
        self._active_health_scopes: dict[UUID, tuple[str, bool] | None] = {}
        self._next_capability_check = 0.0
        self.result_outbox = ResultOutbox(settings.runtime_root / "result-outbox")
        # A task acknowledgement must not erase independently pending local
        # recovery evidence. This outbox contains only shop IDs and revision.
        self.session_recovery_outbox = ResultOutbox(settings.runtime_root / "session-recovery-outbox")
        self.session_refresh_outbox = ResultOutbox(settings.runtime_root / "session-refresh-inflight")
        self._resumable_refreshes: list[TerminalDelivery] = []
        try:
            for item in self.session_refresh_outbox.pending():
                data = item.result or {}
                if (item.skill_id == 'system.rpa_session_refresh' and item.error_code == 'RPA_REFRESH_PENDING'
                        and isinstance(data.get('platform_shop_id'), str) and data['platform_shop_id']
                        and isinstance(data.get('local_shop_id'), str) and data['local_shop_id']
                        and isinstance(data.get('snapshot_revision'), str)
                        and isinstance(data.get('started_at'), str)):
                    self._resumable_refreshes.append(item)
                    self._refresh_done.setdefault(data['platform_shop_id'], asyncio.Event())
        except OutboxError:
            logger.error('Worker in-flight session refresh record is unreadable')
        # 0.5.18 cannot deserialize merchant deliveries. Keep the new format
        # separate so rolling back never blocks existing Worker tasks.
        self.merchant_outbox = ResultOutbox(settings.runtime_root / "result-outbox-merchant-v1")
        self.started_at = datetime.now(UTC)
        self.worker_version = WORKER_VERSION
        self._skill_snapshot_synced = False
        self._skill_snapshot_generation = 0
        self._skill_snapshot_lock = asyncio.Lock()
        self._terminal_delivery_lock = asyncio.Lock()
        self._selection_shop_locks: dict[str, asyncio.Lock] = {}
        self._selection_shop_last: dict[str, tuple[float, tuple | None, int | None]] = {}
        self._selection_shop_waiting: dict[str, float] = {}
        self._next_parallel_kind = 'precheck'
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
        resume_tasks = [asyncio.create_task(self._monitor_refresh(item, self._refresh_done[item.result['platform_shop_id']]))
                        for item in self._resumable_refreshes]
        prechecks: set[asyncio.Task[None]] = set()
        selections: set[asyncio.Task[None]] = set()
        try:
            while not stop_event.is_set():
                try:
                    for finished in tuple(prechecks | selections):
                        if finished.done():
                            prechecks.discard(finished)
                            selections.discard(finished)
                            try:
                                finished.result()
                            except asyncio.CancelledError:
                                pass
                            except Exception as error:
                                logger.warning("Worker parallel task failed: %s", error)
                    if not await self._deliver_pending_terminals():
                        # Keep retrying Operations results, but don't let one
                        # unrouteable result block unrelated queued work. The
                        # durable outbox is preserved across tasks and updates.
                        try:
                            pending = self.result_outbox.pending() + self.merchant_outbox.pending()
                            only_operations = bool(pending) and all(item.result_delivery == 'operations' for item in pending)
                        except OutboxError:
                            only_operations = False
                        if not only_operations:
                            if prechecks or selections:
                                await self._wait_for_prechecks_or_stop(prechecks | selections, stop_event)
                            else:
                                await self._wait_or_stop(stop_event, self.settings.poll_interval_seconds)
                            continue
                    if not prechecks and not selections:
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
                    elif prechecks or selections:
                        task = (None if self._base_update_pending else
                                await self._claim_parallel(prechecks=len(prechecks), selections=len(selections)))
                    else:
                        task = await self.client.claim()
                    if task is not None:
                        self._active_task_ids.add(task.task_id)
                        self._active_health_scopes[task.task_id] = _health_task_scope(task)
                        await self._preempt_health_for_task(task)
                        if task.skill_id == _PRECHECK_KIND:
                            prechecks.add(asyncio.create_task(self._execute_claimed_task(task)))
                            # Fill available slots immediately instead of adding
                            # the ordinary idle-poll interval to every claim.
                            continue
                        if _is_parallel_shop_task(task):
                            selections.add(asyncio.create_task(self._execute_claimed_task(task)))
                            continue
                        await self._execute_claimed_task(task)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    logger.warning("Worker poll cycle failed: %s", error)
                if prechecks or selections:
                    await self._wait_for_prechecks_or_stop(prechecks | selections, stop_event)
                else:
                    await self._wait_or_stop(stop_event, self.settings.poll_interval_seconds)
        finally:
            # As with the existing single-task loop, a normal stop waits for
            # already claimed work and its durable result before disconnecting.
            if prechecks or selections:
                await asyncio.gather(*prechecks, *selections, return_exceptions=True)
            heartbeat_supervisor_task.cancel()
            if reporter_task is not None:
                reporter_task.cancel()
            if rpa_task is not None:
                rpa_task.cancel()
            for resume_task in resume_tasks:
                resume_task.cancel()
            await self._cancel_shop_health_probe()
            await asyncio.gather(
                *resume_tasks,
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

    async def _claim_parallel(self, *, prechecks: int, selections: int) -> WorkerTask | None:
        choices = ('precheck', 'selection') if self._next_parallel_kind == 'precheck' else ('selection', 'precheck')
        for kind in choices:
            if kind == 'precheck' and prechecks >= _PRECHECK_DEVICE_LIMIT:
                continue
            if kind == 'selection' and selections >= self.settings.compass_basic_device_limit:
                continue
            method = getattr(self.client, 'claim_parallel', None)
            task = await method(kind) if method is not None else None
            # An old Backend does not know the new route. Its old precheck-only
            # endpoint remains safe while no basic task is running.
            if (task is None and kind == 'precheck' and not selections
                    and (method is None or getattr(self.client, 'parallel_claim_supported', True) is False)):
                task = await self.client.claim_precheck()
            if task is not None:
                self._next_parallel_kind = 'selection' if kind == 'precheck' else 'precheck'
                return task
        return None

    async def _execute_with_selection_interval(self, task: WorkerTask) -> ExecutionResult:
        await self._wait_for_shop_refresh(task)
        if not _is_parallel_shop_task(task):
            return await self._execute_with_snapshot_evidence(task)
        shop_id = task.local_shops[0].platform_shop_id or task.local_shops[0].local_shop_id
        lock = self._selection_shop_locks.setdefault(shop_id, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop()
            rank_keys = ('industry_id', 'category_id', 'brand_type', 'price_bin', 'begin_date', 'end_date', 'date_type')
            if task.skill_id == _MERCHANT_KIND:
                rank_scope = (_MERCHANT_KIND, task.input.get('sync_id'))
                page_value = task.input.get('page')
                state_order = {'on_sale': 0, 'offline': 1, 'forbidden': 2, 'draft': 3}.get(task.input.get('state'))
                page = state_order * 100001 + page_value if state_order is not None and type(page_value) is int else None
            else:
                rank_scope = (tuple(task.input.get(key) for key in rank_keys)
                              if task.input.get('operation') == 'rank' else None)
                page = task.input.get('page_no') if rank_scope is not None else None
            previous = self._selection_shop_last.get(shop_id)
            if previous is not None:
                next_page = (rank_scope is not None and rank_scope == previous[1] and type(page) is int
                             and type(previous[2]) is int and page != previous[2])
                lower = (self.settings.compass_page_min_interval_seconds if next_page
                         else self.settings.compass_basic_shop_interval_seconds)
                maximum = (self.settings.compass_page_max_interval_seconds if next_page
                           else self.settings.compass_shop_max_interval_seconds)
                deadline = previous[0] + random.uniform(lower, max(lower, maximum))
                remaining = deadline - loop.time()
                if remaining > 0:
                    self._selection_shop_waiting[shop_id] = deadline
                    try:
                        while (remaining := deadline - loop.time()) > 0:
                            await asyncio.sleep(remaining)
                    finally:
                        self._selection_shop_waiting.pop(shop_id, None)
            # A probe can run during the waiting interval, but must stop
            # before a same-shop selection request actually starts.
            await self._cancel_shop_probe_for(shop_id)
            logger.info('Shop task started shop=%s task=%s', shop_id, task.task_id)
            try:
                return await self._execute_with_snapshot_evidence(task)
            finally:
                self._selection_shop_last[shop_id] = (loop.time(), rank_scope, page)
                logger.info('Shop task finished shop=%s task=%s', shop_id, task.task_id)

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
                self._restore_session_recoveries(inventory.shops)
                try:
                    await self._report_rpa_inventory(inventory)
                except Exception:
                    # A temporary center outage must not suppress local recovery.
                    pass
                if (self.shop_session_health is not None
                        and (self._shop_health_probe is None or self._shop_health_probe.done())):
                    missing = None
                    eligible = [shop for shop in inventory.shops if shop.platform_shop_id
                                and self._refresh_shop_available(shop.platform_shop_id)]
                    if not self._refresh_done:
                        missing = self._take_pending_shop_refresh(
                            inventory.shops, excluded=frozenset(shop.platform_shop_id for shop in inventory.shops
                                if shop.platform_shop_id and not self._refresh_shop_available(shop.platform_shop_id)))
                        if missing is None:
                            missing = self.shop_session_health.missing_session_due(eligible)
                        if missing is None:
                            missing = self.shop_session_health.invalid_session_due(eligible)
                    excluded = frozenset(shop.platform_shop_id for shop in inventory.shops
                                         if shop.platform_shop_id and not self._health_shop_available(shop.platform_shop_id))
                    urgent = self._take_session_recheck(inventory.shops, excluded) if missing is None else None
                    shop = (urgent[0] if urgent is not None else
                            self.shop_session_health.due(inventory.shops, excluded_platform_ids=excluded)
                            if missing is None else None)
                    if urgent is not None and not self.shop_session_health.prioritize(*urgent):
                        shop = None
                    if missing is not None:
                        self._shop_health_probe_shop = missing.platform_shop_id
                        self._shop_health_probe_is_refresh = True
                        self._shop_health_probe = asyncio.create_task(self._run_shop_refresh(missing))
                    elif shop is not None:
                        self._shop_health_probe_shop = shop.platform_shop_id
                        self._shop_health_probe_is_refresh = False
                        self._shop_health_probe = asyncio.create_task(self._verify_local_shop(
                            inventory, shop, priority_kinds=urgent[1] if urgent is not None else None))
            except asyncio.CancelledError:
                raise
            except Exception:
                self._last_rpa_inventory = None
                try:
                    await self.client.report_rpa_inventory({"available": False})
                except Exception:
                    pass
            await self._wait_for_inventory(stop_event)

    async def _wait_for_inventory(self, stop_event: asyncio.Event) -> None:
        stop = asyncio.create_task(stop_event.wait())
        wake = asyncio.create_task(self._rpa_inventory_wakeup.wait())
        try:
            await asyncio.wait((stop, wake), timeout=self.settings.provider_inventory_interval_seconds,
                               return_when=asyncio.FIRST_COMPLETED)
            if wake.done() and wake.result():
                self._rpa_inventory_wakeup.clear()
        finally:
            for item in (stop, wake):
                if not item.done():
                    item.cancel()
            await asyncio.gather(stop, wake, return_exceptions=True)

    def _queue_session_recheck(self, task: WorkerTask, result: ExecutionResult, verified_revision: str | None = None) -> None:
        if self.shop_session_health is None or result.status is not ExecutionStatus.FAILED:
            return
        explicit = result.error_code == 'SHOP_SESSION_EXPIRED'
        # The merchant endpoint may use a new login message. Probe the local
        # identity after a business rejection, but never label it expired from
        # that rejection; rate-limit these probes independently per shop.
        if not explicit and not (task.skill_id == _MERCHANT_KIND and result.error_code == 'PLATFORM_BUSINESS_REJECTED'):
            return
        scope = _session_task_scope(task)
        if scope is None:
            return
        local, platform, kind = scope
        current = next((s for s in (self._last_rpa_inventory.shops if self._last_rpa_inventory else [])
                        if (s.local_shop_id, s.platform_shop_id) == (local, platform)), None)
        if (explicit and verified_revision and current is not None
                and current.session_revision == verified_revision):
            if self.shop_session_health.record_explicit_failure(current, kind):
                self._pending_shop_refresh[(local, platform)] = current
                self._rpa_inventory_wakeup.set()
            return
        revision = current.session_revision if current else None
        key = (local, platform, kind, 'explicit' if explicit else 'business')
        now = asyncio.get_running_loop().time()
        previous = self._recent_session_rechecks.get(key)
        if previous and previous[0] == revision and now - previous[1] < (30 if explicit else 300):
            return
        self._recent_session_rechecks[key] = (revision, now)
        self._session_rechecks.setdefault((local, platform), set()).add(kind)
        self._rpa_inventory_wakeup.set()

    def _take_session_recheck(self, shops: list[LocalShop], excluded: frozenset[str]):
        current = {(shop.local_shop_id, shop.platform_shop_id): shop for shop in shops}
        for key, kinds in tuple(self._session_rechecks.items()):
            shop = current.get(key)
            if shop is None:
                self._session_rechecks.pop(key, None)
                continue
            if shop.platform_shop_id in excluded:
                continue
            self._session_rechecks.pop(key, None)
            return shop, kinds
        return None

    def _restore_session_recoveries(self, shops: list[LocalShop]) -> None:
        if self.shop_session_health is None:
            return
        current = {(shop.local_shop_id, shop.platform_shop_id): shop for shop in shops}
        try:
            for item in self.session_recovery_outbox.pending():
                data = item.result or {}
                key = (data.get('local_shop_id'), data.get('platform_shop_id'))
                revision = data.get('snapshot_revision')
                kind = data.get('kind')
                try:
                    observed_at = datetime.fromisoformat(data.get('observed_at', ''))
                    if observed_at.tzinfo is None:
                        continue
                except (TypeError, ValueError):
                    continue
                expected_kind = 'compass' if item.skill_id == _COMPASS_KIND else 'merchant'
                if (item.skill_id not in {_PRECHECK_KIND, _MERCHANT_KIND, _COMPASS_KIND}
                        or item.error_code != 'SHOP_SESSION_EXPIRED' or kind != expected_kind
                        or not isinstance(revision, str) or len(revision) != 64):
                    continue
                shop = current.get(key)
                if shop is None or not shop.session_revision:
                    continue
                if shop.session_revision != revision:
                    self.session_recovery_outbox.acknowledge(item)
                elif self.shop_session_health.record_explicit_failure(shop, kind, observed_at):
                    self._pending_shop_refresh[key] = shop
        except OutboxError:
            logger.error('Worker session recovery evidence requires local attention')

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

    async def _verify_local_shop(self, inventory, shop, *, priority_kinds: set[str] | None = None) -> None:
        try:
            needs_refresh = await self.shop_session_health.check(shop)
            # A newer inventory object may still contain the exact same snapshot.
            latest = self._last_rpa_inventory
            current = next((item for item in latest.shops if
                (item.local_shop_id, item.platform_shop_id, item.session_revision, item.rpa_helper_digest)
                == (shop.local_shop_id, shop.platform_shop_id, shop.session_revision, shop.rpa_helper_digest)), None) if latest else None
            if current is not None:
                try:
                    await self._report_rpa_inventory(latest)
                except Exception:
                    pass
                # Reporting can yield while RPA saves or replaces the session.
                # Never schedule a refresh for the snapshot that just changed.
                latest = self._last_rpa_inventory
                current = next((item for item in latest.shops if
                    (item.local_shop_id, item.platform_shop_id, item.session_revision, item.rpa_helper_digest)
                    == (shop.local_shop_id, shop.platform_shop_id, shop.session_revision, shop.rpa_helper_digest)), None) if latest else None
                if needs_refresh and current is not None:
                    if not self._refresh_shop_available(current.platform_shop_id):
                        self._pending_shop_refresh[(current.local_shop_id, current.platform_shop_id)] = current
                    else:
                        self._shop_health_probe_is_refresh = True
                        await self._run_shop_refresh(current)
        except asyncio.CancelledError:
            if priority_kinds:
                self._session_rechecks.setdefault((shop.local_shop_id, shop.platform_shop_id), set()).update(priority_kinds)
            raise
        except Exception:
            # Status is advisory; retry on a later inventory cycle.
            pass
        finally:
            if self._session_rechecks:
                self._rpa_inventory_wakeup.set()

    def _take_pending_shop_refresh(self, shops: list[LocalShop], *, excluded: frozenset[str] = frozenset()) -> LocalShop | None:
        current = {(shop.local_shop_id, shop.platform_shop_id): shop for shop in shops}
        for key, previous in tuple(self._pending_shop_refresh.items()):
            shop = current.get(key)
            if shop is None:
                self._pending_shop_refresh.pop(key, None)
                continue
            if shop.platform_shop_id in excluded:
                continue  # A busy shop stays queued until its tasks finish.
            self._pending_shop_refresh.pop(key, None)
            if (shop is not None and shop.session_revision == previous.session_revision
                    and shop.rpa_helper_digest == previous.rpa_helper_digest):
                return shop
        return None

    def _refresh_shop_available(self, shop_id: str) -> bool:
        return all((scope := self._active_health_scopes.get(task_id)) is not None and scope[0] != shop_id
                   for task_id in self._active_task_ids)

    async def _wait_for_shop_refresh(self, task: WorkerTask) -> None:
        scope = _health_task_scope(task)
        while True:
            events = ([self._refresh_done[scope[0]]] if scope is not None and scope[0] in self._refresh_done
                      else list(self._refresh_done.values()) if scope is None else [])
            if not events:
                return
            await asyncio.gather(*(event.wait() for event in events))

    async def _run_shop_refresh(self, shop: LocalShop) -> None:
        shop_id = shop.platform_shop_id
        if not shop_id:
            return
        if not self._refresh_shop_available(shop_id):
            self._pending_shop_refresh[(shop.local_shop_id, shop_id)] = shop
            return
        done = asyncio.Event()
        self._refresh_done[shop_id] = done
        started = datetime.now(UTC)
        marker = TerminalDelivery(task_id=uuid4(), skill_id='system.rpa_session_refresh', status='failed',
            result={'local_shop_id': shop.local_shop_id, 'platform_shop_id': shop_id,
                    'snapshot_revision': shop.session_revision or 'missing', 'started_at': started.isoformat()},
            error_code='RPA_REFRESH_PENDING', error_message='设备正在刷新店铺会话')
        try:
            # Record before issuing the asynchronous launch so a crash at any
            # point cannot cause the next Worker to start a duplicate login.
            self.session_refresh_outbox.store(marker)
            if not await self.shop_session_health.request_refresh(shop):
                self.session_refresh_outbox.acknowledge(marker)
                return
            await self._monitor_refresh(marker, done)
        finally:
            if self._refresh_done.get(shop_id) is done:
                self._refresh_done.pop(shop_id, None)
            done.set()
            self._rpa_inventory_wakeup.set()

    async def _monitor_refresh(self, marker: TerminalDelivery, done: asyncio.Event) -> None:
        data = marker.result or {}
        local, shop_id, expected = data['local_shop_id'], data['platform_shop_id'], data['snapshot_revision']
        try:
            started = datetime.fromisoformat(data['started_at'])
            if started.tzinfo is None:
                raise ValueError('invalid timestamp')
            # RPA's login has a 180 s bound. Five minutes also preserves the
            # existing retry interval when the prior Worker disappeared.
            while datetime.now(UTC) < started + timedelta(minutes=5):
                try:
                    revision = await self.rpa_bridge.session_revision(local, shop_id)
                    status = await self.rpa_bridge.session_refresh_status(local, shop_id, expected)
                    if ((isinstance(revision, str) and revision != expected)
                            or status is not None and status.outcome != 'busy'
                            and status.observed_at >= started - timedelta(seconds=1)):
                        break
                except Exception:
                    pass
                await asyncio.sleep(3)
            self.session_refresh_outbox.acknowledge(marker)
        except asyncio.CancelledError:
            # Keep the marker on disk for the next Worker process.
            raise
        except Exception:
            logger.error('Worker could not reconcile in-flight session refresh')
        finally:
            if self._refresh_done.get(shop_id) is done:
                self._refresh_done.pop(shop_id, None)
            done.set()
            self._rpa_inventory_wakeup.set()

    async def _task_snapshot_revision(self, task: WorkerTask) -> str | None:
        if ((task.skill_id == _PRECHECK_KIND and task.input.get('skip_expired_session') is True)
                or self.rpa_bridge is None):
            return None
        scope = _session_task_scope(task)
        if scope is None:
            return None
        try:
            return await asyncio.wait_for(self.rpa_bridge.session_revision(scope[0], scope[1]), timeout=2)
        except Exception:
            return None

    async def _execute_with_snapshot_evidence(self, task: WorkerTask) -> ExecutionResult:
        # Take the initial revision after refresh and pacing waits, immediately
        # before the skill can read the session it will actually use.
        before = await self._task_snapshot_revision(task)
        result = await self._prepare_and_execute(task)
        real_precheck_failure = (task.skill_id != _PRECHECK_KIND or result.result
                                 and result.result.get('http_status') in (200, 401))
        if before and result.error_code == 'SHOP_SESSION_EXPIRED' and real_precheck_failure:
            after = await self._task_snapshot_revision(task)
            if before == after:
                self._task_expiry_revisions[task.task_id] = before
        return result

    def _health_shop_available(self, shop_id: str) -> bool:
        now = asyncio.get_running_loop().time()
        for task_id in self._active_task_ids:
            scope = self._active_health_scopes.get(task_id)
            if scope is None:
                return False
            if scope[0] == shop_id:
                deadline = self._selection_shop_waiting.get(shop_id, 0)
                if not scope[1] or deadline - now < _HEALTH_MIN_SELECTION_GAP:
                    return False
        return True

    async def _preempt_health_for_task(self, task: WorkerTask) -> None:
        probe = self._shop_health_probe
        if probe is None or probe.done():
            return
        scope = self._active_health_scopes.get(task.task_id)
        if self._shop_health_probe_is_refresh:
            return  # The claimed task waits for the RPA outcome instead.
        if scope is None or (scope[0] == self._shop_health_probe_shop
                             and not self._health_shop_available(scope[0])):
            await self._cancel_shop_health_probe()

    async def _cancel_shop_probe_for(self, shop_id: str) -> None:
        if self._shop_health_probe_shop == shop_id and not self._shop_health_probe_is_refresh:
            await self._cancel_shop_health_probe()

    async def _cancel_shop_health_probe(self) -> None:
        probe, self._shop_health_probe = self._shop_health_probe, None
        self._shop_health_probe_shop = None
        self._shop_health_probe_is_refresh = False
        if probe is not None:
            if not probe.done():
                probe.cancel()
            await asyncio.gather(probe, return_exceptions=True)

    async def _execute_claimed_task(self, task: WorkerTask) -> None:
        try:
            await self._execute_task(task)
        finally:
            self._active_task_ids.discard(task.task_id)
            self._active_health_scopes.pop(task.task_id, None)
            if self._session_rechecks or self._pending_shop_refresh:
                self._rpa_inventory_wakeup.set()

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
        if self.base_updater is None or self._active_task_ids or self._refresh_done:
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
        execution_task = asyncio.create_task(self._execute_with_selection_interval(task))
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
            verified_revision = self._task_expiry_revisions.pop(task.task_id, None)
            if verified_revision:
                local, platform, kind = _session_task_scope(task)
                try:
                    self.session_recovery_outbox.store(TerminalDelivery(
                        task_id=task.task_id, skill_id=task.skill_id, status='failed',
                        result={'local_shop_id': local, 'platform_shop_id': platform,
                                'kind': kind, 'snapshot_revision': verified_revision,
                                'observed_at': datetime.now(UTC).isoformat()},
                        error_code='SHOP_SESSION_EXPIRED', error_message='店铺登录状态已失效'))
                except (OSError, OutboxError):
                    # Never lose the task result because the separate recovery
                    # journal cannot currently be written.
                    logger.error('Worker could not persist session recovery evidence')
            # Once execution has returned, make its result durable before any
            # event flush, inventory report or completion network operation.
            outbox = self.merchant_outbox if delivery.skill_id == _MERCHANT_KIND else self.result_outbox
            outbox.store(delivery)
            self._queue_session_recheck(task, result, verified_revision)
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
            self._task_expiry_revisions.pop(task.task_id, None)
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
            pending = ([(self.result_outbox, item) for item in self.result_outbox.pending()]
                       + [(self.merchant_outbox, item) for item in self.merchant_outbox.pending()])
        except OutboxError:
            logger.error("Worker terminal outbox requires local attention")
            return False
        operations_pending = False
        for outbox, delivery in pending:
            try:
                if delivery.skill_id.startswith("yingdao."):
                    # Preserve old terminal evidence locally without replaying a
                    # retired task or blocking new Worker results.
                    outbox.reject(delivery)
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
                elif delivery.skill_id in {'douyin.compass_selection', 'douyin.merchant_products'} and delivery.result_delivery == 'operations':
                    kwargs = {'status': delivery.status, 'result': delivery.result,
                              'error_code': delivery.error_code, 'error_message': delivery.error_message}
                    if delivery.skill_id == 'douyin.merchant_products':
                        kwargs['skill_id'] = delivery.skill_id
                    digest = await self.client.deliver_operations_selection(delivery.task_id, **kwargs)
                    await self.client.acknowledge_operations_selection(
                        delivery.task_id, status=delivery.status, payload_sha256=digest,
                        error_code=delivery.error_code,
                    )
                elif delivery.status == "success":
                    await self.client.complete(delivery.task_id, delivery.result or {})
                else:
                    await self.client.fail(
                        delivery.task_id, error_code=delivery.error_code or "SKILL_EXECUTION_FAILED",
                        error_message=delivery.error_message or "Skill execution failed",
                    )
            except WorkerApiError as error:
                if delivery.result_delivery == 'operations':
                    operations_pending = True
                    await self._mark_operations_delivery_pending(delivery)
                    continue
                if error.status_code in {400, 403, 404, 409, 422}:
                    try:
                        outbox.reject(delivery)
                    except OutboxError:
                        logger.error("Worker terminal rejection requires local attention")
                        return False
                    logger.warning("Worker terminal result rejected task=%s status=%s",
                                   delivery.task_id, error.status_code)
                    continue
                return False
            except (OSError, httpx.HTTPError):
                if delivery.result_delivery == 'operations':
                    operations_pending = True
                    await self._mark_operations_delivery_pending(delivery)
                    continue
                return False
            outbox.acknowledge(delivery)
        return not operations_pending

    async def _mark_operations_delivery_pending(self, delivery: TerminalDelivery) -> None:
        try:
            await self.client.mark_operations_selection_pending(
                delivery.task_id, status=delivery.status, result=delivery.result,
                error_code=delivery.error_code, error_message=delivery.error_message,
            )
        except (WorkerApiError, OSError, httpx.HTTPError):
            # The durable local result remains in the outbox even if the
            # central service itself is temporarily unavailable.
            pass

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
