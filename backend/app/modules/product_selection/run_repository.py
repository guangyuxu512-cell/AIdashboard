from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, func, select, update
from sqlalchemy.orm import Session

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

    def recover_expired(self, now: datetime) -> int:
        result = self.session.execute(update(Run).where(
            Run.status == "running", Run.lease_expires_at <= now,
        ).values(
            status="interrupted", finished_at=now, updated_at=now,
            error_code="PRODUCT_SELECTION_RUN_INTERRUPTED", error_stage="execution",
            lease_id=None, lease_expires_at=None,
        ))
        return result.rowcount

    def claim_next(self, *, now: datetime, lease_until: datetime) -> SelectionRunClaim | None:
        # A single small manual executor across processes, not a Shop-global
        # lock. Conditions remain coalesced by the active unique index.
        self.recover_expired(now)
        if self.session.scalar(select(exists().where(Run.status == "running"))):
            return None
        row = self.session.scalar(select(Run).where(Run.status == "pending", Run.reused_run_id.is_(None)).order_by(
            Run.created_at, Run.run_id,
        ).with_for_update(skip_locked=True).limit(1))
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
