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

from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.core.security import get_secret_cipher
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionVersionConflictError,
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.operating_data import (
    CompassDailyMetrics,
    DouyinOperatingDataBusinessError,
    DouyinOperatingDataConnector,
    DouyinOperatingDataMetricMissingError,
    DouyinOperatingDataMetricNotReadyError,
    DouyinOperatingDataMetricUnavailableError,
)
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
    PlatformSignerFailedError,
)
from app.platforms.registry import create_platform_connectors


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


class SessionAwareDouyinOperatingDataCollector:
    """Coordinates existing ShopSession validation with the Douyin connector."""

    def __init__(
        self,
        *,
        health_service: ShopSessionHealthService,
        session_accessor: ShopSessionAccessor,
        connector: DouyinOperatingDataConnector,
    ) -> None:
        self._health_service = health_service
        self._session_accessor = session_accessor
        self._connector = connector

    def collect(self, request: DailyCollectionRequest) -> CollectionOutcome:
        started_at = monotonic()
        preparation_started_at = started_at
        try:
            self._health_service.check(request.shop_id, force=False)
            auth_context = self._session_accessor.get_auth_context(
                request.shop_id,
                ShopPlatform.DOUYIN,
            )
        except (
            PlatformAuthenticationInvalidError,
            ShopSessionAuthenticationInvalidError,
            ShopSessionNotConfiguredError,
            ShopSessionPayloadInvalidError,
        ):
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PREPARATION,
                failure_code="SHOP_REAUTHORIZATION_REQUIRED",
                retryable=False,
                requires_reauthorization=True,
                started_at=started_at,
            )
        except PlatformIdentityMismatchError:
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PREPARATION,
                failure_code="SHOP_SESSION_IDENTITY_MISMATCH",
                retryable=False,
                requires_reauthorization=True,
                started_at=started_at,
            )
        except SessionVersionConflictError:
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PREPARATION,
                failure_code="SHOP_SESSION_VERSION_CONFLICT",
                retryable=True,
                requires_reauthorization=False,
                started_at=started_at,
            )
        except PlatformRequestTimeoutError:
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PREPARATION,
                failure_code="SHOP_SESSION_VALIDATION_TIMEOUT",
                retryable=True,
                requires_reauthorization=False,
                started_at=started_at,
            )
        except PlatformResponseInvalidError:
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PREPARATION,
                failure_code="SHOP_SESSION_VALIDATION_INVALID_RESPONSE",
                retryable=False,
                requires_reauthorization=False,
                started_at=started_at,
            )
        except PlatformRequestFailedError:
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PREPARATION,
                failure_code="SHOP_SESSION_VALIDATION_FAILED",
                retryable=True,
                requires_reauthorization=False,
                started_at=started_at,
            )

        preparation_duration_ms = round((monotonic() - preparation_started_at) * 1000)
        try:
            read = self._connector.fetch_daily_metrics(
                request.shop_id,
                auth_context,
                request.statistic_date,
                request_lid=request.request_lid,
            )
        except PlatformAuthenticationInvalidError:
            self._mark_invalid_if_current(request.shop_id, auth_context.session_version)
            return self._failure(
                request,
                stage=CollectionStage.PLATFORM_RESPONSE,
                failure_code="SHOP_REAUTHORIZATION_REQUIRED",
                retryable=False,
                requires_reauthorization=True,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
            )
        except PlatformSignerFailedError as error:
            return self._failure(
                request,
                stage=CollectionStage.SIGNING,
                failure_code=error.code,
                retryable=_error_detail(error, "retryable", True) is True,
                requires_reauthorization=False,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
            )
        except DouyinOperatingDataBusinessError as error:
            return self._failure(
                request,
                stage=CollectionStage.PLATFORM_RESPONSE,
                failure_code=error.code,
                retryable=False,
                requires_reauthorization=False,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
            )
        except PlatformRequestTimeoutError:
            return self._failure(
                request,
                stage=CollectionStage.PLATFORM_RESPONSE,
                failure_code="DOUYIN_PLATFORM_TIMEOUT",
                retryable=True,
                requires_reauthorization=False,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
            )
        except PlatformResponseInvalidError as error:
            return self._failure(
                request,
                stage=CollectionStage.RESPONSE_PARSE,
                failure_code=_response_parse_failure_code(error),
                failure_message=_safe_response_parse_failure_message(error),
                retryable=False,
                requires_reauthorization=False,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
            )
        except PlatformRequestFailedError:
            return self._failure(
                request,
                stage=CollectionStage.PLATFORM_RESPONSE,
                failure_code="DOUYIN_PLATFORM_REQUEST_FAILED",
                retryable=True,
                requires_reauthorization=False,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
            )

        try:
            self._health_service.apply_response_cookie_updates(
                auth_context,
                read.cookie_updates,
            )
        except SessionVersionConflictError:
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PERSISTENCE,
                failure_code="SHOP_SESSION_VERSION_CONFLICT",
                retryable=True,
                requires_reauthorization=False,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
                signature_ms=read.signature_duration_ms,
                platform_response_ms=read.platform_duration_ms,
                response_parse_ms=read.parse_duration_ms,
            )
        except (
            ShopSessionAuthenticationInvalidError,
            ShopSessionNotConfiguredError,
            ShopSessionPayloadInvalidError,
        ):
            return self._failure(
                request,
                stage=CollectionStage.SESSION_PERSISTENCE,
                failure_code="SHOP_REAUTHORIZATION_REQUIRED",
                retryable=False,
                requires_reauthorization=True,
                started_at=started_at,
                session_preparation_ms=preparation_duration_ms,
                signature_ms=read.signature_duration_ms,
                platform_response_ms=read.platform_duration_ms,
                response_parse_ms=read.parse_duration_ms,
            )

        return CollectionOutcome(
            request=request,
            status=CollectionStatus.SUCCEEDED,
            stage=CollectionStage.COMPLETE,
            retryable=False,
            requires_reauthorization=False,
            failure_code=None,
            metrics=read.metrics,
            timings=CollectionTimings(
                session_preparation_ms=preparation_duration_ms,
                signature_ms=read.signature_duration_ms,
                platform_response_ms=read.platform_duration_ms,
                response_parse_ms=read.parse_duration_ms,
                total_ms=round((monotonic() - started_at) * 1000),
            ),
        )

    def _mark_invalid_if_current(self, shop_id: UUID, expected_version: int) -> None:
        try:
            self._session_accessor.mark_validation_status(
                shop_id,
                expected_version,
                ShopSessionStatus.INVALID,
            )
        except SessionVersionConflictError:
            # Another Electron refresh won the version race.  Its newly saved
            # Session remains authoritative and must not be overwritten.
            return

    @staticmethod
    def _failure(
        request: DailyCollectionRequest,
        *,
        stage: CollectionStage,
        failure_code: str,
        failure_message: str | None = None,
        retryable: bool,
        requires_reauthorization: bool,
        started_at: float,
        session_preparation_ms: int | None = None,
        signature_ms: int | None = None,
        platform_response_ms: int | None = None,
        response_parse_ms: int | None = None,
    ) -> CollectionOutcome:
        return CollectionOutcome(
            request=request,
            status=CollectionStatus.FAILED,
            stage=stage,
            retryable=retryable,
            requires_reauthorization=requires_reauthorization,
            failure_code=failure_code,
            failure_message=failure_message,
            timings=CollectionTimings(
                session_preparation_ms=session_preparation_ms,
                signature_ms=signature_ms,
                platform_response_ms=platform_response_ms,
                response_parse_ms=response_parse_ms,
                total_ms=round((monotonic() - started_at) * 1000),
            ),
        )


def build_douyin_operating_data_batch_executor(
    settings: Settings | None = None,
) -> DouyinOperatingDataBatchExecutor:
    """Build an explicit server-side executor; it is not a background Cron."""

    resolved_settings = settings or get_settings()
    def collect(request: DailyCollectionRequest) -> CollectionOutcome:
        return collect_douyin_operating_data_once(request, settings=resolved_settings)

    return DouyinOperatingDataBatchExecutor(
        collect,
        max_concurrency=resolved_settings.douyin_compass_collection_concurrency,
    )


def collect_douyin_operating_data_once(
    request: DailyCollectionRequest,
    *,
    settings: Settings | None = None,
) -> CollectionOutcome:
    """Use the established server Session/Signer path for one read-only call.

    The durable dashboard executor owns database job claiming and persistence.
    This function deliberately owns only the existing Session-aware external
    request path, so no database transaction remains open across platform I/O.
    """

    resolved_settings = settings or get_settings()
    cipher = get_secret_cipher()
    with get_session_factory()() as session:
        accessor = ShopSessionAccessor(session, cipher)
        health_service = ShopSessionHealthService(
            session,
            accessor,
            create_platform_connectors(),
            session_service=ShopSessionService(session, cipher),
            settings=resolved_settings,
        )
        return SessionAwareDouyinOperatingDataCollector(
            health_service=health_service,
            session_accessor=accessor,
            connector=DouyinOperatingDataConnector(),
        ).collect(request)


def _error_detail(error: PlatformRequestFailedError, key: str, default: object) -> object:
    details = error.details
    return details.get(key, default) if isinstance(details, dict) else default


def _safe_response_parse_failure_message(error: PlatformResponseInvalidError) -> str:
    """Return a stable parse hint without exposing a platform payload."""

    if isinstance(error, DouyinOperatingDataMetricUnavailableError):
        return "抖店平台未提供可确认的经营指标值"
    if isinstance(error, DouyinOperatingDataMetricNotReadyError):
        return "抖店经营指标暂未就绪"
    if isinstance(error, DouyinOperatingDataMetricMissingError):
        return "抖店经营数据响应缺少必要指标"
    metric = _error_detail(error, "metric", None)
    labels = {
        "income_amt": "成交金额",
        "pay_cnt": "成交订单数",
    }
    if metric in labels:
        return f"抖店经营数据响应缺少或无法读取必要指标：{labels[metric]}"
    return "抖店经营数据响应无效"


def _response_parse_failure_code(error: PlatformResponseInvalidError) -> str:
    """Map only audited core-value variants to public-safe item codes."""

    if isinstance(
        error,
        (
            DouyinOperatingDataMetricUnavailableError,
            DouyinOperatingDataMetricNotReadyError,
            DouyinOperatingDataMetricMissingError,
        ),
    ):
        return error.code
    return "DOUYIN_OPERATING_DATA_INVALID_RESPONSE"
