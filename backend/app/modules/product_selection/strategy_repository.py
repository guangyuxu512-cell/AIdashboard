from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, aliased

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.product_selection.models import ProductSelectionRun as Run, ProductSelectionStrategy as Strategy
from app.modules.product_selection.run_repository import SelectionRunRepository
from app.modules.shops.models import Shop


class SelectionStrategyRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def visible(actor: ActorContext):
        statement = select(Strategy).join(Shop, Shop.shop_id == Strategy.request_shop_id).where(Shop.deleted_at.is_(None))
        if not actor.is_super_account:
            statement = statement.where(
                Strategy.team_id == actor.require_team_id(),
                exists(select(TeamShopAccess.team_id).where(
                    TeamShopAccess.team_id == actor.team_id,
                    TeamShopAccess.shop_id == Strategy.request_shop_id,
                )),
            )
        elif actor.team_id is not None:
            statement = statement.where(Strategy.team_id == actor.team_id)
        return statement

    def get(self, actor: ActorContext, strategy_id: UUID, *, lock: bool = False):
        statement = self.visible(actor).where(Strategy.strategy_id == strategy_id)
        if lock:
            statement = statement.with_for_update(of=Strategy).execution_options(populate_existing=True)
        return self.session.scalar(statement)

    def list(self, actor: ActorContext, *, offset: int, limit: int, search: str | None):
        statement = self.visible(actor)
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
            statement = statement.where(Strategy.name.ilike(f"%{escaped}%", escape="\\"))
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = list(self.session.scalars(statement.order_by(Strategy.updated_at.desc(), Strategy.strategy_id).offset(offset).limit(limit)))
        return rows, total

    def shops(self, rows: list[Strategy]):
        return dict(self.session.execute(select(Shop.shop_id, Shop.display_name).where(Shop.shop_id.in_([row.request_shop_id for row in rows]))).all()) if rows else {}

    def latest_runs(self, actor: ActorContext, rows: list[Strategy]):
        if not rows:
            return {}
        # A reused receipt remains this strategy's submission. Resolve it to
        # the existing canonical without changing that execution's association.
        ranked = SelectionRunRepository.visible_statement(actor).with_only_columns(
            Run.strategy_id, Run.run_id,
            func.row_number().over(partition_by=Run.strategy_id, order_by=(Run.created_at.desc(), Run.run_id.desc())).label("rn"),
        ).where(Run.strategy_id.in_([row.strategy_id for row in rows])).subquery()
        receipt = aliased(Run)
        execution = aliased(Run)
        statement = select(ranked.c.strategy_id, execution).join(receipt, receipt.run_id == ranked.c.run_id).join(
            execution, execution.run_id == func.coalesce(receipt.reused_run_id, receipt.run_id),
        ).where(ranked.c.rn == 1, execution.team_id == receipt.team_id, execution.request_shop_id == receipt.request_shop_id)
        return {key: run for key, run in self.session.execute(statement).all()}
