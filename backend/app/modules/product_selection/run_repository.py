from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session, aliased

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.product_selection.exceptions import SelectionRunLeaseLostError
from app.modules.product_selection.models import ProductSelectionRun as Run
from app.modules.product_selection.models import ProductSelectionObservation as Observation, ProductSelectionCandidate as Candidate
from app.modules.product_selection.basic_contract import SelectionBasicRequest, SelectionBasicExecution
from app.modules.product_selection.run_contract import SelectionResolvedRequest, SelectionRunClaim
from app.modules.shops.models import Shop


class SelectionRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def visible_statement(actor: ActorContext):
        statement = select(Run).join(Shop, Shop.shop_id == Run.request_shop_id).where(Shop.deleted_at.is_(None))
        if not actor.is_super_account:
            statement = statement.where(
                Run.team_id == actor.require_team_id(),
                exists(select(TeamShopAccess.team_id).where(
                    TeamShopAccess.team_id == actor.team_id,
                    TeamShopAccess.shop_id == Run.request_shop_id,
                )),
            )
        elif actor.team_id is not None:
            statement = statement.where(Run.team_id == actor.team_id)
        return statement

    def get_for_actor(self, actor: ActorContext, run_id: UUID) -> Run | None:
        return self.session.scalar(self.visible_statement(actor).where(Run.run_id == run_id))

    def receipts_for_actor(self, actor: ActorContext, receipt_ids: list[UUID]):
        if not receipt_ids: return {}
        canonical = aliased(Run)
        statement = self.visible_statement(actor).with_only_columns(Run, canonical).join(
            canonical, canonical.run_id == func.coalesce(Run.reused_run_id, Run.run_id),
        ).where(Run.run_id.in_(receipt_ids), canonical.team_id == Run.team_id,
            canonical.request_shop_id == Run.request_shop_id, canonical.request_fingerprint == Run.request_fingerprint,
            canonical.reused_run_id.is_(None))
        return {receipt.run_id: (receipt, execution) for receipt, execution in self.session.execute(statement)}

    def list_for_actor(self, actor: ActorContext, *, shop_id: UUID | None, offset: int, limit: int) -> tuple[list[Run], int]:
        statement = self.visible_statement(actor)
        statement = statement.where(Run.reused_run_id.is_(None), Run.operation_kind == "rank")
        if shop_id is not None:
            statement = statement.where(Run.request_shop_id == shop_id)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        return list(self.session.scalars(statement.order_by(Run.created_at.desc(), Run.run_id).offset(offset).limit(limit))), total

    def find_submission(self, *, team_id: UUID, user_id: UUID, key: UUID) -> Run | None:
        return self.session.scalar(select(Run).where(
            Run.team_id == team_id, Run.created_by_user_id == user_id, Run.submission_key == key,
        ))

    def latest_basic_for_actor(self, actor, observation_id):
        return self.session.scalar(self.visible_statement(actor).where(
            Run.operation_kind == "basic_info", Run.target_observation_id == observation_id,
            Run.reused_run_id.is_(None)).order_by(Run.created_at.desc(), Run.run_id.desc()).limit(1))

    def find_active(self, *, team_id: UUID, shop_id: UUID, fingerprint: str) -> Run | None:
        return self.session.scalar(select(Run).where(
            Run.team_id == team_id, Run.request_shop_id == shop_id,
            Run.request_fingerprint == fingerprint, Run.status.in_(("pending", "running")),
        ).with_for_update())

    def find_strategy_active(self, *, team_id: UUID, strategy_id: UUID) -> Run | None:
        """Canonical activity includes this strategy's reused submissions.

        A future due-service caller must hold the authorized strategy lock.
        This is a persistence predicate, not an authorization shortcut or a
        second execution state machine. Terminal canonicals no longer block.
        """
        receipt = aliased(Run)
        submitted = exists(select(receipt.run_id).where(
            receipt.strategy_id == strategy_id, receipt.team_id == team_id,
            func.coalesce(receipt.reused_run_id, receipt.run_id) == Run.run_id,
            receipt.request_shop_id == Run.request_shop_id,
            receipt.request_fingerprint == Run.request_fingerprint,
        ).correlate(Run))
        return self.session.scalar(select(Run).where(
            Run.team_id == team_id, Run.reused_run_id.is_(None),
            Run.status.in_(("pending", "running")), submitted,
        ).order_by(Run.created_at, Run.run_id).limit(1))

    def recover_expired(self, now: datetime) -> int:
        result = self.session.execute(update(Run).where(
            Run.status == "running", Run.lease_expires_at <= now,
        ).values(
            status="interrupted", finished_at=now, updated_at=now,
            error_code="PRODUCT_SELECTION_RUN_INTERRUPTED", error_stage="execution",
            lease_id=None, lease_expires_at=None,
        ))
        return result.rowcount

    def strategy_running_conflict(self, *, team_id: UUID, strategy_id: UUID, exclude_run_id: UUID) -> bool:
        receipt, execution = aliased(Run), aliased(Run)
        return bool(self.session.scalar(select(exists(select(receipt.run_id).join(
            execution, execution.run_id == func.coalesce(receipt.reused_run_id, receipt.run_id),
        ).where(
            receipt.team_id == team_id, receipt.strategy_id == strategy_id,
            execution.run_id != exclude_run_id, execution.status == "running",
            receipt.team_id == execution.team_id,
            receipt.request_shop_id == execution.request_shop_id,
            receipt.request_fingerprint == execution.request_fingerprint,
        )))))

    @staticmethod
    def validated_request(row: Run) -> SelectionResolvedRequest | SelectionBasicRequest:
        if row.operation_kind == "basic_info":
            request = SelectionBasicRequest.model_validate(row.request_conditions)
            if (request.shop_id != row.request_shop_id or request.observation_id != row.target_observation_id
                or row.strategy_id is not None or row.result_detail_version is not None
                or request.fingerprint() != row.request_fingerprint):
                raise ValueError("Basic request does not match its closed target")
            return request
        if row.operation_kind != "rank":
            raise ValueError("Unknown selection operation")
        request = SelectionResolvedRequest.model_validate(row.request_conditions)
        if request.original.shop_id != row.request_shop_id:
            raise ValueError("Frozen request does not match its Shop FK")
        if request.strategy_queue is not None and (
            request.strategy_queue.strategy_id != row.strategy_id
            or request.fingerprint() != row.request_fingerprint
        ):
            raise ValueError("Strategy queue metadata does not match the canonical/receipt")
        if row.reused_run_id is None and request.fingerprint() != row.request_fingerprint:
            raise ValueError("Canonical frozen request does not match its key")
        return request

    @staticmethod
    def eligible_pending_statement():
        running = aliased(Run, name="running_execution")
        candidate_link = aliased(Run, name="candidate_submission")
        running_link = aliased(Run, name="running_submission")
        busy_shop = exists(select(running.run_id).where(
            running.status == "running", running.request_shop_id == Run.request_shop_id,
        ).correlate(Run))
        busy_strategy = exists(select(candidate_link.run_id).join(
            running_link, running_link.strategy_id == candidate_link.strategy_id,
        ).join(
            running, func.coalesce(running_link.reused_run_id, running_link.run_id) == running.run_id,
        ).where(
            func.coalesce(candidate_link.reused_run_id, candidate_link.run_id) == Run.run_id,
            candidate_link.strategy_id.is_not(None),
            candidate_link.team_id == Run.team_id,
            candidate_link.request_shop_id == Run.request_shop_id,
            candidate_link.request_fingerprint == Run.request_fingerprint,
            running.status == "running",
            running_link.team_id == running.team_id,
            running_link.request_shop_id == running.request_shop_id,
            running_link.request_fingerprint == running.request_fingerprint,
        ).correlate(Run))
        # Busy shops/strategies stay pending; they cannot head-of-line block
        # another eligible shop. Reused receipts never consume a worker slot.
        return select(Run).where(
            Run.status == "pending", Run.reused_run_id.is_(None),
            ~busy_shop, ~busy_strategy,
        ).order_by(Run.created_at, Run.run_id).with_for_update(skip_locked=True).limit(1)

    def lock_execution_decision(self, *, wait: bool = False) -> bool:
        key = func.hashtext("product_selection_run_claim")
        if wait:
            self.session.execute(select(func.pg_advisory_xact_lock(key)))
            return True
        return bool(self.session.scalar(select(func.pg_try_advisory_xact_lock(key))))

    def claim_next(self, *, now: datetime, lease_until: datetime, max_running: int = 1) -> SelectionRunClaim | None:
        if type(max_running) is not int or max_running < 1:
            raise ValueError("Selection execution capacity must be a positive integer")
        # Selection-only transaction lock serializes count + claim across
        # processes. No platform I/O or generic Shop/PC/operating-data lock.
        if not self.lock_execution_decision():
            return None
        self.recover_expired(now)
        if (self.session.scalar(select(func.count()).select_from(Run).where(Run.status == "running")) or 0) >= max_running:
            return None
        row = self.session.scalar(self.eligible_pending_statement())
        if row is None:
            return None
        try:
            request = self.validated_request(row)
            if isinstance(request, SelectionBasicRequest):
                source = self.session.scalar(select(Observation).join(Candidate,
                    Candidate.candidate_id == Observation.candidate_id).where(
                    Observation.observation_id == request.observation_id,
                    Observation.request_shop_id == row.request_shop_id,
                    Observation.candidate_id == request.candidate_id,
                    Observation.source_scope_hash == request.source_scope_hash,
                    Candidate.team_id == row.team_id, Candidate.platform_product_id == request.product_id,
                ).with_for_update(of=Observation).execution_options(populate_existing=True))
                if source is None or request.execution is not None:
                    raise ValueError("Basic execution target cannot be claimed")
                source.basic_info_version += 1
                request = request.model_copy(update={"execution": SelectionBasicExecution(
                    rank_started_at=source.last_successful_request_started_at,
                    basic_version=source.basic_info_version, started_at=now)})
                row.request_conditions = request.model_dump(mode="json")
        except ValueError:
            row.status, row.stage = "failed", "completed"
            row.error_code, row.error_stage = "PRODUCT_SELECTION_RUN_CONTRACT_INVALID", "execution"
            row.finished_at, row.updated_at = now, now
            return None
        row.status, row.stage = "running", "session"
        if row.operation_kind == "rank" and row.result_detail_version is None and row.started_at is None and row.saved_count == 0:
            row.result_detail_version = 1
        row.started_at, row.updated_at = now, now
        row.lease_id, row.lease_expires_at = uuid4(), lease_until
        return SelectionRunClaim(
            row.run_id, row.lease_id, row.team_id, row.created_by_user_id,
            row.request_shop_id, now,
            request,
        )

    def fence(self, claim: SelectionRunClaim, now: datetime) -> Run:
        row = self.session.scalar(select(Run).where(
            Run.run_id == claim.run_id, Run.lease_id == claim.lease_id,
            Run.status == "running", Run.lease_expires_at > now,
            Run.lease_expires_at > func.clock_timestamp(),
            Run.team_id == claim.team_id, Run.created_by_user_id == claim.user_id,
            Run.request_shop_id == claim.shop_id,
            Run.reused_run_id.is_(None),
        ).with_for_update().execution_options(populate_existing=True))
        # SELECT may wait on a writer. Recheck DB time after acquiring the
        # fence, not only the WHERE expression evaluated before that wait.
        database_now = self.session.scalar(select(func.clock_timestamp()))
        if (row is None or row.lease_expires_at is None or row.lease_expires_at <= database_now
            or row.request_fingerprint != claim.request.fingerprint()):
            raise SelectionRunLeaseLostError()
        try:
            request = self.validated_request(row)
            if isinstance(request, SelectionBasicRequest) and request != claim.request:
                raise ValueError("Basic execution version changed")
        except ValueError:
            raise SelectionRunLeaseLostError() from None
        return row
