from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.product_selection.exceptions import SelectionRunLeaseLostError
from app.modules.product_selection.models import ProductSelectionRun as Run
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

    def list_for_actor(self, actor: ActorContext, *, shop_id: UUID | None, offset: int, limit: int) -> tuple[list[Run], int]:
        statement = self.visible_statement(actor)
        statement = statement.where(Run.reused_run_id.is_(None))
        if shop_id is not None:
            statement = statement.where(Run.request_shop_id == shop_id)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        return list(self.session.scalars(statement.order_by(Run.created_at.desc(), Run.run_id).offset(offset).limit(limit))), total

    def find_submission(self, *, team_id: UUID, user_id: UUID, key: UUID) -> Run | None:
        return self.session.scalar(select(Run).where(
            Run.team_id == team_id, Run.created_by_user_id == user_id, Run.submission_key == key,
        ))

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

    @staticmethod
    def eligible_pending_statement():
        running, receipt = aliased(Run), aliased(Run)
        busy_shop = exists(select(running.run_id).where(
            running.status == "running", running.request_shop_id == Run.request_shop_id,
        ).correlate(Run))
        linked_strategy = exists(select(receipt.run_id).where(
            receipt.reused_run_id == running.run_id,
            receipt.strategy_id == Run.strategy_id,
        ).correlate(Run, running))
        busy_strategy = exists(select(running.run_id).where(
            running.status == "running", Run.strategy_id.is_not(None),
            or_(running.strategy_id == Run.strategy_id, linked_strategy),
        ).correlate(Run))
        # Busy shops/strategies stay pending; they cannot head-of-line block
        # another eligible shop. Reused receipts never consume a worker slot.
        return select(Run).where(
            Run.status == "pending", Run.reused_run_id.is_(None),
            ~busy_shop, ~busy_strategy,
        ).order_by(Run.created_at, Run.run_id).with_for_update(skip_locked=True).limit(1)

    def claim_next(self, *, now: datetime, lease_until: datetime, max_running: int = 1) -> SelectionRunClaim | None:
        if type(max_running) is not int or max_running < 1:
            raise ValueError("Selection execution capacity must be a positive integer")
        # Selection-only transaction lock serializes count + claim across
        # processes. No platform I/O or generic Shop/PC/operating-data lock.
        if not self.session.scalar(select(func.pg_try_advisory_xact_lock(func.hashtext("product_selection_run_claim")))):
            return None
        self.recover_expired(now)
        if (self.session.scalar(select(func.count()).select_from(Run).where(Run.status == "running")) or 0) >= max_running:
            return None
        row = self.session.scalar(self.eligible_pending_statement())
        if row is None:
            return None
        row.status, row.stage = "running", "session"
        row.started_at, row.updated_at = now, now
        row.lease_id, row.lease_expires_at = uuid4(), lease_until
        return SelectionRunClaim(
            row.run_id, row.lease_id, row.team_id, row.created_by_user_id,
            row.request_shop_id, now,
            SelectionResolvedRequest.model_validate(row.request_conditions),
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
        return row
