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
from app.modules.product_selection.run_contract import (
    SelectionResolvedRequest, SelectionRunClaim, SelectionPrimaryBusinessError, SelectionFallbackReason,
)
from app.modules.product_selection.run_service import (
    SelectionRunService, selection_request_mapping_available, safe_run_error,
)
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.platforms.douyin.product_selection import (
    CompassBasicInfo, CompassRankPage, CompassSelectionBusinessError,
)
from app.platforms.exceptions import PlatformRequestFailedError
from app.platforms.exceptions import PlatformResponseInvalidError


class SelectionPlatformIO(Protocol):
    """The production adapter uses the existing Accessor/HTTP/Signer, not browser fetch.

    This protocol is also the isolated synthetic-test injection boundary.
    Production submissions use the bounded frozen plan and execution switch.
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

    def _choose(
        self, claim: SelectionRunClaim, state: str, *,
        fallback_reason: SelectionFallbackReason | None = None,
        primary_error: SelectionPrimaryBusinessError | None = None,
    ) -> SelectionResolvedRequest:
        with self.session_factory() as session:
            return SelectionRunService(session, settings=self.settings).choose_window(
                claim, state, fallback_reason=fallback_reason, primary_error=primary_error,
            )

    @staticmethod
    def _business_probe_allowed(request: SelectionResolvedRequest, failure: CompassSelectionBusinessError) -> bool:
        """A user-approved date probe, not a date-not-ready or generic retry rule."""
        code, stage, value = safe_run_error(failure)
        original, scope = request.original, request.scope
        return (
            request.version == 2 and request.date_plan is not None
            and original.channel == "short-video" and original.period == "7d"
            and original.brand == "all" and original.price_mode == "all"
            and original.price_above is None and original.price_below is None
            and not original.first_listed_only
            and scope.date_type == "21" and scope.rank_data_type == "1"
            and scope.brand_type == "-1" and scope.price_bin == "不限"
            and scope.search_info == "" and scope.activity_id == ""
            and code == "DOUYIN_SELECTION_BUSINESS_REJECTED" and stage == "platform_business"
            and type(value) in {int, str} and value in {621000704, "621000704"}
        )

    def _rank(self, claim, context, request, page_no):
        self._authorize(claim, "rank")
        page = self.platform.rank(context, request, page_no)
        if page.page_no != page_no or page.page_size != request.page_size:
            raise PlatformResponseInvalidError()
        # An inconsistent first-page count is not a confirmed empty榜单.
        if page_no == 1 and not page.products and page.total != 0:
            raise PlatformResponseInvalidError()
        return page

    def _select_first_page(self, claim, context):
        request = claim.request
        primary_error = None
        try:
            first = self._rank(claim, context, request, 1)
        except CompassSelectionBusinessError as failure:
            if not self._business_probe_allowed(request, failure):
                raise
            code, stage, value = safe_run_error(failure)
            primary_error = SelectionPrimaryBusinessError(
                error_code=code, error_stage=stage, platform_business_code=value,
            )
            first = None
        if first is not None and first.products:
            chosen = self._choose(claim, "primary")
        else:
            reason = "primary_business_rejection_probe" if primary_error is not None else "primary_success_empty"
            self._choose(claim, "fallback_checking", fallback_reason=reason, primary_error=primary_error)
            assert request.date_plan is not None
            # A per-call legacy-shaped request supplies only the actual scope;
            # lease/idempotency checks always use the original frozen claim.
            backup_request = SelectionResolvedRequest(
                original=request.original, scope=request.date_plan.backup_scope,
                page_numbers=request.page_numbers,
            )
            backup = self._rank(claim, context, backup_request, 1)
            state = "backup" if backup.products else "backup_empty" if primary_error is not None else "both_empty"
            chosen = self._choose(claim, state)
            if state != "both_empty":
                first = backup
        actual_request = SelectionResolvedRequest(
            original=request.original, scope=chosen.actual_scope(), page_numbers=request.page_numbers,
        )
        return actual_request, first, chosen.date_outcome.state in {"both_empty", "backup_empty"}

    def execute_claim(self, claim: SelectionRunClaim) -> None:
        error = None
        try:
            self._authorize(claim, "session")
            context = self.platform.session_context(claim.shop_id)
            if context.shop_id != claim.shop_id:
                raise PlatformRequestFailedError()
            request = claim.request
            first = None
            empty_window = False
            if request.version == 2:
                request, first, empty_window = self._select_first_page(claim, context)
            seen: set[str] = set()
            for page_no in ((1,) if empty_window else request.page_numbers):
                page = first if page_no == 1 and first is not None else self._rank(claim, context, request, page_no)
                if claim.request.version == 2:
                    if any(p.rank is None for p in page.products):
                        raise PlatformResponseInvalidError()
                    # Filter by returned official rank, not page-local row index.
                    page = replace(page, products=tuple(p for p in page.products
                        if claim.request.original.rank_from <= p.rank <= claim.request.original.rank_to))
                # Dedup before persistence/counts, including repeated identities
                # across pages. Keep platform rank, never use a local row number.
                page = replace(page, products=tuple(p for p in page.products if p.product_id not in seen))
                seen.update(p.product_id for p in page.products)
                actor = self._authorize(claim, "persistence")
                with self.session_factory() as session:
                    saved = ProductSelectionFactService(session).persist_rank_page(
                        actor=actor, shop_id=claim.shop_id, scope=request.scope,
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
