"""Bounded, business-only executor. DB sessions never surround platform I/O."""

import asyncio
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_session_factory
from app.core.exceptions import AppError
from app.modules.product_selection.exceptions import SelectionRunLeaseLostError
from app.modules.product_selection.run_contract import SelectionResolvedRequest, SelectionRunClaim
from app.modules.product_selection.run_service import (
    SelectionRunService, selection_request_mapping_available,
)
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.platforms.douyin.product_selection import CompassBasicInfo, CompassRankPage
from app.platforms.exceptions import PlatformRequestFailedError


class SelectionPlatformIO(Protocol):
    """The production adapter uses the existing Accessor/HTTP/Signer, not browser fetch.

    This protocol is also the isolated synthetic-test injection boundary.
    Production submissions remain blocked until request mappings are frozen.
    """

    def session_context(self, shop_id: UUID) -> ShopSessionAuthContext: ...
    def rank(self, context: ShopSessionAuthContext, request: SelectionResolvedRequest, page_no: int) -> CompassRankPage: ...
    def basic_info(self, context: ShopSessionAuthContext, product_id: str) -> CompassBasicInfo: ...


class SelectionRunExecutor:
    def __init__(self, *, session_factory: Callable[[], AbstractContextManager[Session]], platform: SelectionPlatformIO, settings: Settings):
        self.session_factory, self.platform, self.settings = session_factory, platform, settings

    def execute_available(self) -> int:
        with self.session_factory() as session:
            service = SelectionRunService(session, settings=self.settings)
            service.recover_expired()
            claim = service.claim_next()
        if claim is None:
            return 0
        self.execute_claim(claim)
        return 1

    def recover_only(self) -> int:
        with self.session_factory() as session:
            return SelectionRunService(session, settings=self.settings).recover_expired()

    def _authorize(self, claim: SelectionRunClaim, stage: str):
        with self.session_factory() as session:
            return SelectionRunService(session, settings=self.settings).authorize(claim, stage=stage)

    def execute_claim(self, claim: SelectionRunClaim) -> None:
        error = None
        try:
            self._authorize(claim, "session")
            context = self.platform.session_context(claim.shop_id)
            if context.shop_id != claim.shop_id:
                raise PlatformRequestFailedError()
            seen: set[str] = set()
            for page_no in claim.request.page_numbers:
                self._authorize(claim, "rank")
                page = self.platform.rank(context, claim.request, page_no)
                if page.page_no != page_no or page.page_size != claim.request.page_size:
                    from app.platforms.exceptions import PlatformResponseInvalidError
                    raise PlatformResponseInvalidError()
                # Dedup before persistence/counts, including repeated identities
                # across pages. Keep platform rank, never use a local row number.
                page = replace(page, products=tuple(p for p in page.products if p.product_id not in seen))
                seen.update(p.product_id for p in page.products)
                actor = self._authorize(claim, "persistence")
                with self.session_factory() as session:
                    saved = ProductSelectionFactService(session).persist_rank_page(
                        actor=actor, shop_id=claim.shop_id, scope=claim.request.scope,
                        page=page, started_at=claim.started_at, retrieved_at=datetime.now(UTC), claim=claim,
                    )
                for observation_id in saved:
                    actor = self._authorize(claim, "basic_info")
                    # Resolve only this authorized persisted source, then close
                    # the DB session before making the single basic-info call.
                    with self.session_factory() as session:
                        product_id = ProductSelectionFactService(session).get_read(
                            actor=actor, observation_id=observation_id,
                        ).product_id
                    try:
                        basic = self.platform.basic_info(context, product_id)
                    except AppError as basic_error:
                        with self.session_factory() as session:
                            ProductSelectionFactService(session).record_basic_info_failure(
                                actor=actor, observation_id=observation_id, rank_started_at=claim.started_at,
                                at=datetime.now(UTC), error=basic_error, claim=claim,
                            )
                        if basic_error.code in {"AUTH_INVALID", "PLATFORM_IDENTITY_MISMATCH"}:
                            raise basic_error
                    else:
                        with self.session_factory() as session:
                            ProductSelectionFactService(session).persist_basic_info(
                                actor=actor, observation_id=observation_id, rank_started_at=claim.started_at,
                                retrieved_at=datetime.now(UTC), basic=basic, claim=claim,
                            )
        except SelectionRunLeaseLostError:
            # Expiry reconciliation owns interrupted state; a late executor
            # must not replace it or rewrite facts after it loses its lease.
            return
        except AppError as failure:
            error = failure
        except Exception:
            # No arbitrary exception/URL/payload enters logs or run records.
            error = PlatformRequestFailedError()
        try:
            with self.session_factory() as session:
                SelectionRunService(session, settings=self.settings).finish(claim, error=error)
        except SelectionRunLeaseLostError:
            return


def build_selection_run_executor(settings: Settings | None = None) -> SelectionRunExecutor:
    from app.modules.product_selection.platform_io import SelectionStoredSessionIO
    factory = get_session_factory()
    return SelectionRunExecutor(
        session_factory=factory, platform=SelectionStoredSessionIO(factory),
        settings=settings or get_settings(),
    )


async def execute_selection_runs_forever() -> None:
    settings = get_settings()
    # Neither an environment switch nor a stale pending row may turn unknown
    # UI mappings into platform calls. Tests use an explicitly injected adapter.
    if not settings.product_selection_execution_enabled:
        return
    executor = build_selection_run_executor(settings)
    while True:
        try:
            if selection_request_mapping_available():
                processed = await asyncio.to_thread(executor.execute_available)
            else:
                # Reconcile an expired lease even while a mapping is disabled;
                # do not claim or resend a pending/interrupted platform request.
                await asyncio.to_thread(executor.recover_only)
                processed = 0
        except asyncio.CancelledError:
            # Canceling this await does not cancel an HTTP thread. Its finite
            # HTTP timeout and DB lease fence remain the late-write protection.
            raise
        except Exception:
            # Do not log an exception which may contain a signed URL/DSN.
            processed = 0
        if not processed:
            await asyncio.sleep(1)
