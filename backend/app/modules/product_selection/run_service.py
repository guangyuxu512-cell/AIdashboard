"""Short transactions for manual intentions, progress, claims and terminal state."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.modules.access.contracts import ActorContext
from app.modules.product_selection.exceptions import (
    SelectionExecutionDisabledError,
    SelectionRunConflictError, SelectionRunNotFoundError,
    SelectionSubmissionBusyError,
    SelectionRunLeaseLostError,
)
from app.modules.product_selection.models import ProductSelectionRun
from app.modules.product_selection.run_contract import (
    SelectionResolvedRequest, SelectionRunClaim, SelectionRunCreate,
    SelectionRunOriginal, SelectionRunRead, SelectionRunReceipt, SelectionDateOutcome,
    SelectionFallbackReason, SelectionPrimaryBusinessError,
    SelectionStrategySnapshot,
)
from app.modules.product_selection.run_repository import SelectionRunRepository
from app.modules.product_selection.request_mapping import freeze_short_video_request, validate_shop_category
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.product_selection.strategy_queue_key import SelectionStrategyQueueKey


RequestResolver = Callable[[SelectionRunOriginal, datetime], SelectionResolvedRequest]


def selection_request_mapping_available() -> bool:
    return True


def resolve_selection_request(original: SelectionRunOriginal, now: datetime) -> SelectionResolvedRequest:
    return freeze_short_video_request(original, now)


SAFE_ERROR_CODES = {
    "AUTH_INVALID", "PLATFORM_TIMEOUT", "PLATFORM_REQUEST_FAILED", "PLATFORM_SIGNER_FAILED",
    "PLATFORM_RESPONSE_INVALID", "DOUYIN_SELECTION_BUSINESS_REJECTED",
    "DOUYIN_SELECTION_PRODUCT_ID_MISMATCH", "SHOP_SESSION_NOT_CONFIGURED",
    "SHOP_SESSION_AUTHENTICATION_INVALID", "SHOP_SESSION_PAYLOAD_INVALID",
    "SESSION_ENCRYPTION_UNAVAILABLE",
    "PLATFORM_IDENTITY_MISMATCH", "PRODUCT_SELECTION_SHOP_UNAVAILABLE",
    "MODULE_ACCESS_DENIED", "TEAM_ACCESS_DENIED", "HUMAN_USER_DISABLED",
    "PRODUCT_SELECTION_ACCESS_REVOKED", "PRODUCT_SELECTION_EXECUTION_FAILED",
}


def safe_run_error(error: AppError) -> tuple[str, str, str | int | None]:
    code = error.code if error.code in SAFE_ERROR_CODES else "PRODUCT_SELECTION_EXECUTION_FAILED"
    stage = {
        "AUTH_INVALID": "session", "PLATFORM_SIGNER_FAILED": "signer",
        "PLATFORM_TIMEOUT": "http", "PLATFORM_REQUEST_FAILED": "http",
        "PLATFORM_RESPONSE_INVALID": "response_parse",
        "DOUYIN_SELECTION_BUSINESS_REJECTED": "platform_business",
        "DOUYIN_SELECTION_PRODUCT_ID_MISMATCH": "response_parse",
        "PRODUCT_SELECTION_SHOP_UNAVAILABLE": "authorization",
        "PRODUCT_SELECTION_ACCESS_REVOKED": "authorization",
        "MODULE_ACCESS_DENIED": "authorization", "TEAM_ACCESS_DENIED": "authorization",
        "HUMAN_USER_DISABLED": "authorization",
        "SHOP_SESSION_NOT_CONFIGURED": "session",
        "SHOP_SESSION_AUTHENTICATION_INVALID": "session",
        "SHOP_SESSION_PAYLOAD_INVALID": "session",
        "SESSION_ENCRYPTION_UNAVAILABLE": "session",
        "PLATFORM_IDENTITY_MISMATCH": "session",
    }.get(code, "execution")
    business_code = None
    if code == "DOUYIN_SELECTION_BUSINESS_REJECTED" and isinstance(error.details, dict):
        value = error.details.get("platform_code")
        # The parser has already restricted the scalar. Repeat the boundary
        # here; bool, URL, long text and exception messages cannot be stored.
        if type(value) is int:
            business_code = value
        elif type(value) is str and 1 <= len(value) <= 64 and all(c.isalnum() or c in "_.-" for c in value):
            business_code = value
    return code, stage, business_code


class SelectionRunService:
    def __init__(self, session: Session, *, settings: Settings | None = None, resolver: RequestResolver = resolve_selection_request, category_reader=None):
        self.session = session
        self.repository = SelectionRunRepository(session)
        self.facts = ProductSelectionFactService(session)
        self.settings = settings or get_settings()
        self.resolver = resolver
        self.category_reader = category_reader

    def submit(self, actor: ActorContext, command: SelectionRunCreate, *, now: datetime | None = None) -> SelectionRunReceipt:
        at = now or datetime.now(UTC)
        original = command.original()
        try:
            current = self._submission_actor(actor, command)
            team_id = current.require_team_id()
            old = self.repository.find_submission(team_id=team_id, user_id=current.user_id, key=command.submission_key)
            if old is not None:
                if old.operation_kind != "rank":
                    raise SelectionRunConflictError()
                visible = self.repository.get_for_actor(current, old.run_id)
                if visible is None:
                    raise SelectionRunNotFoundError()
                saved = SelectionResolvedRequest.model_validate(old.request_conditions)
                if (saved.original != original or old.strategy_id != command.strategy_id
                    or (saved.strategy is not None and saved.strategy.version != command.strategy_version)):
                    raise SelectionRunConflictError()
                result = self._receipt(current, old)
                self.session.commit()
                return result
            self.facts._execution_shop(current, command.shop_id)
            if not self.settings.product_selection_execution_enabled:
                raise SelectionExecutionDisabledError()
            resolved = self.resolver(original, at)
            if resolved.original != original:
                raise ValueError("A resolver cannot replace original user conditions")
            if resolved.version >= 2:
                # Release guard/read transactions before checking the current
                # shop's real category tree. No platform I/O in a DB transaction.
                self.session.rollback()
                if self.category_reader is None:
                    from app.core.database import get_session_factory
                    from app.modules.product_selection.category_service import SelectionCategoryService
                    tree = SelectionCategoryService(get_session_factory()).read(current, command.shop_id)
                else:
                    tree = self.category_reader(current, command.shop_id)
                validate_shop_category(original, tree)
                current = self._submission_actor(actor, command)
                self.facts._execution_shop(current, command.shop_id)
            if command.strategy_id is not None:
                from app.modules.product_selection.strategy_service import SelectionStrategyService
                row = SelectionStrategyService(self.session).writable(current, command.strategy_id, expected_version=command.strategy_version)
                if row.request_shop_id != command.shop_id:
                    raise SelectionRunConflictError()
                if resolved.version not in {3, 4, 5, 6, 7, 8, 9}:
                    raise ValueError("Strategy association requires the versioned execution contract")
                resolved = resolved.model_copy(update={"strategy": SelectionStrategySnapshot(strategy_id=row.strategy_id, version=row.version)})
            result = self._persist_submission(current, command, resolved, at=at)
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def _persist_submission(
        self, current: ActorContext, command: SelectionRunCreate,
        resolved: SelectionResolvedRequest, *, at: datetime,
    ) -> SelectionRunReceipt:
        """Shared persistence step; its authorized caller owns the transaction.

        No HTTP, commit or outer rollback here. Manual submit performs its
        existing category/authorization/CAS checks first. The registered
        Schedule path does the same under Strategy/occurrence locks and commits
        Run, audit and next together. This helper never owns an outer commit.
        """
        self.repository.lock_execution_decision(wait=True)
        # A decision lock may have waited behind another writer/claim. Recheck
        # current personnel/module/Shop authority before attaching a receipt.
        current = self._submission_actor(current, command)
        self.facts._execution_shop(current, command.shop_id)
        self.repository.recover_expired(at)
        team_id = current.require_team_id()
        original = command.original()
        if resolved.original != original:
            raise SelectionRunConflictError()
        for _ in range(3):
            try:
                with self.session.begin_nested():
                    # Replayed keys never resolve relative dates again.
                    row = self.repository.find_submission(team_id=team_id, user_id=current.user_id, key=command.submission_key)
                    if row is not None:
                        if row.operation_kind != "rank":
                            raise SelectionRunConflictError()
                        saved = SelectionResolvedRequest.model_validate(row.request_conditions)
                        if (saved.original != original or row.strategy_id != command.strategy_id
                            or (saved.strategy is not None and saved.strategy.version != command.strategy_version)):
                            raise SelectionRunConflictError()
                    else:
                        isolated = None
                        if command.strategy_id is not None:
                            metadata = SelectionStrategyQueueKey.from_request(resolved, strategy_id=command.strategy_id)
                            isolated = SelectionResolvedRequest.model_validate(resolved.model_dump(mode="json") | {"strategy_queue": metadata.model_dump(mode="json")})
                        # Once a conflict queue exists, repeated submissions
                        # keep using it even after the original conflict ends.
                        active = self.repository.find_active(team_id=team_id, shop_id=command.shop_id, fingerprint=isolated.fingerprint()) if isolated is not None else None
                        if active is None:
                            active = self.repository.find_active(team_id=team_id, shop_id=command.shop_id, fingerprint=resolved.fingerprint())
                        if active is None and resolved.version == 8:
                            legacy_pages = resolved.legacy_paging_request()
                            active = self.repository.find_active(team_id=team_id, shop_id=command.shop_id, fingerprint=legacy_pages.fingerprint())
                        # Preserve the old v2 canonical/hash during upgrade.
                        if active is None and resolved.legacy_paging_request().version == 3 and original.rank_to <= 20 and not original.first_listed_only:
                            legacy = SelectionResolvedRequest.model_validate(resolved.legacy_paging_request().model_dump(mode="json") | {"version": 2, "strategy": None})
                            active = self.repository.find_active(team_id=team_id, shop_id=command.shop_id, fingerprint=legacy.fingerprint())
                        conflict = (active is not None and active.status == "running" and command.strategy_id is not None
                            and self.repository.strategy_running_conflict(team_id=team_id, strategy_id=command.strategy_id, exclude_run_id=active.run_id))
                        if conflict:
                            active = None
                        shared = isolated if conflict else resolved
                        if active is not None:
                            active_request = SelectionResolvedRequest.model_validate(active.request_conditions)
                            shared = active_request.model_copy(update={
                                "version": 3 if active_request.version == 2 else active_request.version,
                                "strategy": resolved.strategy,
                            })
                        row = ProductSelectionRun(
                            run_id=uuid4(), team_id=team_id, created_by_user_id=current.user_id,
                            request_shop_id=command.shop_id, submission_key=command.submission_key,
                            strategy_id=command.strategy_id,
                            operation_kind="rank", result_detail_version=1 if active is None else None,
                            request_fingerprint=active.request_fingerprint if active is not None else shared.fingerprint(),
                            request_conditions=shared.model_dump(mode="json"),
                            reused_run_id=active.run_id if active is not None else None,
                            status="reused" if active is not None else "pending", stage="queued",
                            result_count=None, saved_count=0, supplemented_count=0,
                            supplement_failed_count=0, created_at=at, updated_at=at,
                        )
                        self.session.add(row)
                        self.session.flush()
                    result = self._receipt(current, row)
                return result
            except IntegrityError as collision:
                constraint = getattr(getattr(collision.orig, "diag", None), "constraint_name", None)
                if constraint not in {"uq_selection_run_submission", "uq_selection_run_active_request"}:
                    raise
        raise SelectionSubmissionBusyError()

    def create_for_schedule(self, actor: ActorContext, command: SelectionRunCreate, *, tree, at: datetime) -> SelectionRunReceipt:
        """Called under Strategy→Schedule locks; caller commits run/audit/next.

        Category I/O has already ended. No helper commit/rollback, independent
        executor, theoretical-date freeze or device context is introduced.
        """
        from app.modules.product_selection.strategy_service import SelectionStrategyService
        if not self.settings.product_selection_execution_enabled:
            raise SelectionExecutionDisabledError()
        if command.strategy_id is None:
            raise SelectionRunConflictError()
        current = self._submission_actor(actor, command)
        self.facts._execution_shop(current, command.shop_id)
        row = SelectionStrategyService(self.session).writable(current, command.strategy_id, expected_version=command.strategy_version)
        if row.request_shop_id != command.shop_id or not row.enabled:
            raise SelectionRunConflictError()
        resolved = self.resolver(command.original(), at)
        validate_shop_category(resolved.original, tree)
        resolved = resolved.model_copy(update={"strategy": SelectionStrategySnapshot(strategy_id=row.strategy_id, version=row.version)})
        return self._persist_submission(current, command, resolved, at=at)

    def _submission_actor(self, actor: ActorContext, command: SelectionRunCreate) -> ActorContext:
        if command.strategy_id is not None:
            from app.modules.product_selection.strategy_service import SelectionStrategyService
            current, _ = SelectionStrategyService(self.session).existing_context(actor, command.strategy_id)
            return current
        return self.facts._current_actor(actor)

    def _read(self, actor: ActorContext, row: ProductSelectionRun) -> SelectionRunRead:
        try:
            self.repository.validated_request(row)
        except ValueError:
            raise SelectionRunNotFoundError() from None
        canonical = row
        if row.reused_run_id is not None:
            canonical = self.repository.get_for_actor(actor, row.reused_run_id)
            if (canonical is None or canonical.reused_run_id is not None
                or canonical.team_id != row.team_id or canonical.request_shop_id != row.request_shop_id
                or canonical.request_fingerprint != row.request_fingerprint):
                raise SelectionRunNotFoundError()
            try:
                self.repository.validated_request(canonical)
            except ValueError:
                raise SelectionRunNotFoundError() from None
        return SelectionRunRead.model_validate(canonical)

    def _receipt(self, actor: ActorContext, row: ProductSelectionRun) -> SelectionRunReceipt:
        execution = self._read(actor, row)
        return SelectionRunReceipt(
            receipt_id=row.run_id, submission_key=row.submission_key,
            execution_run_id=execution.run_id, reused=row.reused_run_id is not None,
            strategy=SelectionResolvedRequest.model_validate(row.request_conditions).strategy,
            execution=execution,
        )

    def get(self, actor: ActorContext, run_id: UUID) -> SelectionRunRead:
        current = self.facts._current_actor(actor)
        # A verified super account may submit a saved strategy from another
        # selected Team. Its exact receipt/canonical progress must remain
        # readable without changing the global list filter. The canonical can
        # be an older unassociated run reused by that strategy, so use the
        # immutable run Team rather than guessing a strategy association.
        lookup = replace(current, team_id=None) if current.is_super_account else current
        row = self.repository.get_for_actor(lookup, run_id)
        if row is None:
            raise SelectionRunNotFoundError()
        if current.is_super_account:
            current = self.facts._current_actor(replace(current, team_id=row.team_id))
            # Authority can change between lookup and resource resolution.
            # Never return a row found with the earlier super visibility.
            row = self.repository.get_for_actor(current, run_id)
            if row is None:
                raise SelectionRunNotFoundError()
        return self._read(current, row)

    def list(self, actor: ActorContext, *, shop_id: UUID | None, offset: int, limit: int) -> tuple[list[SelectionRunRead], int]:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid bounded pagination")
        current = self.facts._current_actor(actor)
        rows, total = self.repository.list_for_actor(current, shop_id=shop_id, offset=offset, limit=limit)
        return [self._read(current, row) for row in rows], total

    def recover_expired(self, *, now: datetime | None = None) -> int:
        self.repository.lock_execution_decision(wait=True)
        count = self.repository.recover_expired(now or datetime.now(UTC))
        self.session.commit()
        return count

    def claim_next(self, *, now: datetime | None = None) -> SelectionRunClaim | None:
        at = now or datetime.now(UTC)
        if not self.settings.product_selection_execution_enabled:
            return None
        try:
            claim = self.repository.claim_next(now=at, lease_until=at + timedelta(seconds=self.settings.product_selection_run_lease_seconds), max_running=self.settings.product_selection_concurrency)
            self.session.commit()
            return claim
        except IntegrityError as collision:
            self.session.rollback()
            constraint = getattr(getattr(collision.orig, "diag", None), "constraint_name", None)
            if constraint in {"uq_selection_run_running_shop", "uq_selection_run_running_strategy"}:
                return None
            raise
        except Exception:
            self.session.rollback()
            raise

    def _execution_actor(self, claim: SelectionRunClaim) -> ActorContext:
        from app.modules.access.service import ActorContextService
        current = ActorContextService(self.session).resolve(user_id=claim.user_id, requested_team_id=claim.team_id)
        current = self.facts._current_actor(current)
        self.facts._execution_shop(current, claim.shop_id)
        return current

    def authorize(self, claim: SelectionRunClaim, *, stage: str, now: datetime | None = None) -> ActorContext:
        at = now or datetime.now(UTC)
        try:
            current = self._execution_actor(claim)
            row = self.repository.fence(claim, at)
            row.stage = stage
            row.lease_expires_at = at + timedelta(seconds=self.settings.product_selection_run_lease_seconds)
            row.updated_at = at
            self.session.commit()
            return current
        except Exception:
            self.session.rollback()
            raise

    def finish(self, claim: SelectionRunClaim, *, error: AppError | None = None, now: datetime | None = None) -> None:
        at = now or datetime.now(UTC)
        try:
            # A still-valid lease may terminate after revocation, but cannot
            # write any facts. Do not require a now-revoked actor to end a run.
            row = self.repository.fence(claim, at)
            if error is not None:
                request = self.repository.validated_request(row)
                if row.operation_kind == "rank" and request.date_outcome is not None and request.date_outcome.state == "fallback_checking":
                    outcome = request.date_outcome.model_copy(update={"state": "fallback_failed"})
                    row.request_conditions = request.model_copy(update={"date_outcome": outcome}).model_dump(mode="json")
                row.error_code, row.error_stage, row.platform_business_code = safe_run_error(error)
                row.status = "partial" if row.saved_count else "failed"
            else:
                row.status = "partial" if row.supplement_failed_count or (row.operation_kind == "rank" and row.saved_count != row.result_count) else "succeeded"
                if row.supplement_failed_count:
                    row.error_code, row.error_stage = "PRODUCT_SELECTION_BASIC_INFO_INCOMPLETE", "basic_info"
                if row.result_count is None:
                    row.status, row.error_code = "failed", "PRODUCT_SELECTION_EXECUTION_FAILED"
            row.stage, row.finished_at, row.updated_at = "completed", at, at
            row.lease_id, row.lease_expires_at = None, None
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def choose_window(
        self, claim: SelectionRunClaim, state: str, *, now: datetime | None = None,
        fallback_reason: SelectionFallbackReason | None = None,
        primary_error: SelectionPrimaryBusinessError | None = None,
    ) -> SelectionResolvedRequest:
        """Lease-fenced monotonic outcome; never change dates after persistence."""
        at = now or datetime.now(UTC)
        try:
            self._execution_actor(claim)
            row = self.repository.fence(claim, at)
            request = SelectionResolvedRequest.model_validate(row.request_conditions)
            previous = request.date_outcome.state if request.date_outcome is not None else None
            allowed = {None: {"primary", "fallback_checking"}, "fallback_checking": {"backup", "backup_empty", "both_empty"}}
            if request.single_window():
                allowed = {None: {"primary"}}
            if (request.version not in {2, 3, 4, 5, 6, 7, 8, 9} or state not in allowed.get(previous, set())
                or row.saved_count != 0 or row.result_count is not None
                or ((request.original.price_mode != "all" or request.original.brand != "all") and (primary_error is not None or fallback_reason == "primary_business_rejection_probe"))):
                raise SelectionRunLeaseLostError()
            if previous is not None:
                if fallback_reason is not None or primary_error is not None:
                    raise SelectionRunLeaseLostError()
                outcome = SelectionDateOutcome.model_validate(request.date_outcome.model_dump() | {"state": state})
            else:
                outcome = SelectionDateOutcome(
                    state=state,
                    fallback_reason=(fallback_reason or "primary_success_empty") if state == "fallback_checking" else fallback_reason,
                    primary_error=primary_error,
                )
            request = request.model_copy(update={"date_outcome": outcome})
            row.request_conditions = request.model_dump(mode="json")
            row.updated_at = at
            self.session.commit()
            return request
        except Exception:
            self.session.rollback()
            raise
