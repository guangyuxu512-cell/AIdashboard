from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
import logging
from threading import Lock
from time import monotonic
from typing import Iterator
from uuid import UUID

from app.core.config import Settings
from app.platforms.douyin.operating_data import CompassDailyMetrics


logger = logging.getLogger(__name__)


class CollectionStage(StrEnum):
    QUEUED = "queued"
    SESSION_PREPARATION = "session_preparation"
    SIGNING = "signing"
    PLATFORM_RESPONSE = "platform_response"
    RESPONSE_PARSE = "response_parse"
    SESSION_PERSISTENCE = "session_persistence"
    EXECUTION = "execution"
    COMPLETE = "complete"


class CollectionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED_REAUTHORIZATION = "paused_reauthorization"


@dataclass(frozen=True)
class DailyCollectionRequest:
    shop_id: UUID
    statistic_date: date
    # The capture proves `_lid` is per-request context, but does not prove a
    # reusable server-side generation rule.  It stays optional and transient.
    request_lid: str | None = None


@dataclass(frozen=True)
class CollectionTimings:
    queue_wait_ms: int = 0
    session_preparation_ms: int | None = None
    signature_ms: int | None = None
    platform_response_ms: int | None = None
    response_parse_ms: int | None = None
    total_ms: int = 0


@dataclass(frozen=True)
class CollectionOutcome:
    request: DailyCollectionRequest
    status: CollectionStatus
    stage: CollectionStage
    retryable: bool
    requires_reauthorization: bool
    timings: CollectionTimings
    failure_code: str | None = None
    # This may reach the human collection-progress API.  It therefore carries
    # only a fixed, locally-derived explanation, never a platform message,
    # URL, cookie, signed query, or response fragment.
    failure_message: str | None = None
    metrics: CompassDailyMetrics | None = None


Collector = Callable[[DailyCollectionRequest], CollectionOutcome]


class ShopCollectionGuard:
    """In-process guard for one Shop's sequential read-only collection."""

    def __init__(self) -> None:
        self._locks: dict[UUID, Lock] = {}
        self._locks_guard = Lock()

    @contextmanager
    def try_acquire(self, shop_id: UUID) -> Iterator[bool]:
        with self._locks_guard:
            lock = self._locks.setdefault(shop_id, Lock())
        acquired = lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                lock.release()


PROCESS_SHOP_COLLECTION_GUARD = ShopCollectionGuard()


class DouyinOperatingDataBatchExecutor:
    """Run a finite, read-only Compass batch without a persistent job table.

    Outcomes carry the shop/date/stage/retry state for the caller.  This
    process-local guard prevents duplicate in-process work only; a durable
    multi-process scheduler requires a future persisted collection-job model.
    """

    def __init__(
        self,
        collector: Collector,
        *,
        max_concurrency: int = 5,
        guard: ShopCollectionGuard | None = None,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self._collector = collector
        self._max_concurrency = max_concurrency
        self._guard = guard or PROCESS_SHOP_COLLECTION_GUARD

    def execute(
        self,
        requests: Iterable[DailyCollectionRequest],
    ) -> list[CollectionOutcome]:
        queued_at = monotonic()
        request_list = list(requests)
        outcomes: dict[int, CollectionOutcome] = {}
        queues: OrderedDict[UUID, deque[int]] = OrderedDict()
        seen_shop_days: set[tuple[UUID, date]] = set()

        for index, request in enumerate(request_list):
            key = (request.shop_id, request.statistic_date)
            if key in seen_shop_days:
                outcomes[index] = self._skipped(
                    request,
                    failure_code="DUPLICATE_SHOP_DATE",
                )
                continue
            seen_shop_days.add(key)
            queues.setdefault(request.shop_id, deque()).append(index)

        ready_shops = deque(queues.keys())
        in_flight: dict[Future[CollectionOutcome], tuple[UUID, int]] = {}
        with ThreadPoolExecutor(max_workers=self._max_concurrency) as worker_pool:
            while ready_shops or in_flight:
                while ready_shops and len(in_flight) < self._max_concurrency:
                    shop_id = ready_shops.popleft()
                    shop_queue = queues[shop_id]
                    if not shop_queue:
                        continue
                    index = shop_queue.popleft()
                    future = worker_pool.submit(
                        self._execute_one,
                        request_list[index],
                        queued_at,
                    )
                    in_flight[future] = (shop_id, index)

                if not in_flight:
                    continue
                completed, _ = wait(
                    in_flight,
                    return_when=FIRST_COMPLETED,
                )
                for future in completed:
                    shop_id, index = in_flight.pop(future)
                    outcome = self._future_outcome(
                        future,
                        request_list[index],
                        queued_at,
                    )
                    outcomes[index] = outcome
                    remaining = queues[shop_id]
                    if outcome.requires_reauthorization:
                        while remaining:
                            blocked_index = remaining.popleft()
                            outcomes[blocked_index] = self._paused_for_reauthorization(
                                request_list[blocked_index],
                            )
                    elif remaining:
                        # The same shop can only receive its next date after
                        # the previous request completes; other ready shops
                        # are still eligible to fill the shared concurrency.
                        ready_shops.append(shop_id)

        return [outcomes[index] for index in range(len(request_list))]

    def _execute_one(
        self,
        request: DailyCollectionRequest,
        queued_at: float,
    ) -> CollectionOutcome:
        queue_wait_ms = round((monotonic() - queued_at) * 1000)
        with self._guard.try_acquire(request.shop_id) as acquired:
            if not acquired:
                return CollectionOutcome(
                    request=request,
                    status=CollectionStatus.SKIPPED,
                    stage=CollectionStage.QUEUED,
                    retryable=True,
                    requires_reauthorization=False,
                    failure_code="SHOP_COLLECTION_IN_PROGRESS",
                    timings=CollectionTimings(queue_wait_ms=queue_wait_ms),
                )
            outcome = self._collector(request)
        return replace(
            outcome,
            timings=replace(outcome.timings, queue_wait_ms=queue_wait_ms),
        )

    @staticmethod
    def _future_outcome(
        future: Future[CollectionOutcome],
        request: DailyCollectionRequest,
        queued_at: float,
    ) -> CollectionOutcome:
        try:
            return future.result()
        except Exception:
            # Avoid logging exception text: an HTTP exception may embed a
            # signed URL.  The public outcome remains safe and retryable.
            logger.error(
                "Douyin daily collection worker failed unexpectedly shop_id=%s",
                request.shop_id,
            )
            return CollectionOutcome(
                request=request,
                status=CollectionStatus.FAILED,
                stage=CollectionStage.EXECUTION,
                retryable=True,
                requires_reauthorization=False,
                failure_code="COLLECTION_EXECUTION_FAILED",
                timings=CollectionTimings(
                    queue_wait_ms=round((monotonic() - queued_at) * 1000),
                ),
            )

    @staticmethod
    def _skipped(
        request: DailyCollectionRequest,
        *,
        failure_code: str,
    ) -> CollectionOutcome:
        return CollectionOutcome(
            request=request,
            status=CollectionStatus.SKIPPED,
            stage=CollectionStage.QUEUED,
            retryable=False,
            requires_reauthorization=False,
            failure_code=failure_code,
            timings=CollectionTimings(),
        )

    @staticmethod
    def _paused_for_reauthorization(
        request: DailyCollectionRequest,
    ) -> CollectionOutcome:
        return CollectionOutcome(
            request=request,
            status=CollectionStatus.PAUSED_REAUTHORIZATION,
            stage=CollectionStage.SESSION_PREPARATION,
            retryable=False,
            requires_reauthorization=True,
            failure_code="SHOP_REAUTHORIZATION_REQUIRED",
            timings=CollectionTimings(),
        )


def collect_douyin_operating_data_once(
    request: DailyCollectionRequest, *, settings: Settings | None = None,
) -> CollectionOutcome:
    """Server collection is retired; a future Worker adapter must be explicit."""
    del request, settings
    raise RuntimeError("经营数据采集已暂停")
