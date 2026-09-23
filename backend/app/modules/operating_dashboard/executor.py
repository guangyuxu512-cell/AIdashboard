from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.modules.operating_dashboard.repository import CollectionClaim
from app.modules.operating_dashboard.service import OperatingDashboardService
from app.platforms.douyin.operating_data_executor import (
    CollectionOutcome,
    CollectionStage,
    CollectionStatus,
    CollectionTimings,
    DailyCollectionRequest,
    DouyinOperatingDataBatchExecutor,
    ShopCollectionGuard,
    collect_douyin_operating_data_once,
)


logger = logging.getLogger(__name__)
SessionFactory = Callable[[], AbstractContextManager[Session]]
Collector = Callable[[DailyCollectionRequest], CollectionOutcome]


class OperatingDataCollectionExecutor:
    """Execute already-durable operating-data items without holding DB I/O locks.

    Claiming, the final enabled/deleted re-check, and outcome persistence each
    use a short independent database transaction.  The partial unique indexes
    on the collection-item table remain the cross-process duplicate guard;
    this executor only limits work *within* one Backend process.
    """

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        collector: Collector,
        settings: Settings,
    ) -> None:
        self._session_factory = session_factory
        self._collector = collector
        self._settings = settings

    def execute_available(self, *, collection_job_id: UUID | None = None) -> int:
        """Execute available work, optionally limited to one durable job.

        The optional scope never relaxes the global running-item count.  It
        only prevents a controlled invocation from claiming a different job.
        """

        claims: list[CollectionClaim] = []
        for _ in range(self._settings.douyin_compass_collection_concurrency):
            claim = self._prepare_next(collection_job_id=collection_job_id)
            if claim is None:
                break
            claims.append(claim)
        if not claims:
            return 0

        # Reuse the existing finite Douyin executor for bounded fan-out.  The
        # durable database claim remains authoritative across Backend
        # processes; a fresh guard only prevents the old in-memory guard from
        # treating a separate durable batch as an already-running Shop.
        claims_by_request = {
            (claim.shop_id, claim.business_date): claim for claim in claims
        }

        def execute_claim(request: DailyCollectionRequest) -> CollectionOutcome:
            return self._execute_claim(
                claims_by_request[(request.shop_id, request.statistic_date)],
            )

        DouyinOperatingDataBatchExecutor(
            execute_claim,
            max_concurrency=len(claims),
            guard=ShopCollectionGuard(),
        ).execute(
            DailyCollectionRequest(
                shop_id=claim.shop_id,
                statistic_date=claim.business_date,
            )
            for claim in claims
        )
        return len(claims)

    def _prepare_next(
        self,
        *,
        collection_job_id: UUID | None = None,
    ) -> CollectionClaim | None:
        now = datetime.now(UTC)
        lease_until = now + timedelta(
            seconds=self._settings.operating_dashboard_collection_lease_seconds,
        )
        with self._session_factory() as session:
            return OperatingDashboardService(
                session,
                settings=self._settings,
            ).prepare_next_collection(
                now=now,
                lease_until=lease_until,
                collection_job_id=collection_job_id,
            )

    def _execute_claim(self, claim: CollectionClaim) -> CollectionOutcome:
        with self._session_factory() as session:
            abandoned = OperatingDashboardService(
                session,
                settings=self._settings,
            ).abandon_claim_if_not_executable(claim)
        if abandoned:
            return CollectionOutcome(
                request=DailyCollectionRequest(
                    shop_id=claim.shop_id,
                    statistic_date=claim.business_date,
                ),
                status=CollectionStatus.SKIPPED,
                stage=CollectionStage.QUEUED,
                retryable=False,
                requires_reauthorization=False,
                failure_code="SHOP_DISABLED",
                timings=CollectionTimings(),
            )

        request = DailyCollectionRequest(
            shop_id=claim.shop_id,
            statistic_date=claim.business_date,
        )
        try:
            outcome = self._collector(request)
        except Exception:
            # A connector exception can carry an HTTP URL or platform context.
            # Do not log it verbatim; persist only the fixed safe failure code.
            logger.error(
                "Operating dashboard collection execution failed shop_id=%s",
                claim.shop_id,
            )
            outcome = CollectionOutcome(
                request=request,
                status=CollectionStatus.FAILED,
                stage=CollectionStage.EXECUTION,
                retryable=True,
                requires_reauthorization=False,
                failure_code="COLLECTION_EXECUTION_FAILED",
                timings=CollectionTimings(),
            )

        with self._session_factory() as session:
            OperatingDashboardService(
                session,
                settings=self._settings,
            ).finalize_collection(
                claim=claim,
                outcome=outcome,
                now=datetime.now(UTC),
            )
        return outcome


def build_operating_data_collection_executor(
    settings: Settings | None = None,
) -> OperatingDataCollectionExecutor:
    resolved_settings = settings or get_settings()

    def collect(request: DailyCollectionRequest) -> CollectionOutcome:
        return collect_douyin_operating_data_once(request, settings=resolved_settings)

    return OperatingDataCollectionExecutor(
        session_factory=get_session_factory(),
        collector=collect,
        settings=resolved_settings,
    )


async def execute_operating_data_collections_forever() -> None:
    settings = get_settings()
    executor = build_operating_data_collection_executor(settings)
    while True:
        try:
            processed = await asyncio.to_thread(executor.execute_available)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Operating dashboard collection scan failed")
            processed = 0
        if not processed:
            await asyncio.sleep(
                settings.operating_dashboard_collection_scan_interval_seconds,
            )
