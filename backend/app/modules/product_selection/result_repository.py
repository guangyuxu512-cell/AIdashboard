"""Scoped result persistence/queries; authority is resolved by the service."""

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import aliased

from app.modules.product_selection.models import (
    ProductSelectionCandidate as Candidate, ProductSelectionObservation as Observation,
    ProductSelectionRun as Run, ProductSelectionResultItem as Item,
)
from app.modules.product_selection.repository import ProductSelectionRepository
from app.modules.product_selection.run_repository import SelectionRunRepository


class SelectionResultRepository:
    def __init__(self, session):
        self.session = session

    def candidate(self, candidate_id):
        return self.session.get(Candidate, candidate_id)

    def observation(self, observation_id):
        return self.session.get(Observation, observation_id)

    def executions(self, execution_ids):
        if not execution_ids:
            return {}
        return {row.run_id: row for row in self.session.scalars(select(Run).where(
            Run.run_id.in_(execution_ids), Run.operation_kind == "rank", Run.reused_run_id.is_(None)))}

    def has_prior_hit(self, candidate_id, key, run_id):
        return self.session.scalar(select(Item.item_id).join(Observation,
            Observation.observation_id == Item.observation_id).where(
            Observation.candidate_id == candidate_id, Item.discovery_scope_hash == key,
            Item.execution_run_id != run_id).limit(1)) is not None

    def legacy_evidence(self, candidate_id, team_id, shop_id):
        return self.session.execute(select(Observation, Run).join(Run,
            Run.run_id == Observation.last_run_id).where(
            Observation.candidate_id == candidate_id, Observation.request_shop_id == shop_id,
            Run.team_id == team_id, Run.operation_kind == "rank", Run.reused_run_id.is_(None))).all()

    def append(self, item):
        self.session.add(item)

    def membership(self, execution_id, observation_id):
        return self.session.scalar(select(Item).where(Item.execution_run_id == execution_id,
            Item.observation_id == observation_id))

    def visible_counts(self, actor, execution_ids):
        if not execution_ids:
            return {}
        statement = ProductSelectionRepository.visible_statement(actor).join(Item,
            Item.observation_id == Observation.observation_id).join(Run, Run.run_id == Item.execution_run_id).where(
            Item.execution_run_id.in_(execution_ids), Run.operation_kind == "rank", Run.reused_run_id.is_(None),
            Run.team_id == Candidate.team_id, Run.request_shop_id == Observation.request_shop_id)
        return dict(self.session.execute(statement.with_only_columns(Item.execution_run_id,
            func.count(func.distinct(Observation.candidate_id))).group_by(Item.execution_run_id)).all())

    def batches(self, actor, strategy_id, *, shop_id, offset, limit):
        canonical = aliased(Run)
        statement = SelectionRunRepository.visible_statement(actor).with_only_columns(Run, canonical).join(
            canonical, canonical.run_id == func.coalesce(Run.reused_run_id, Run.run_id)).where(
            Run.strategy_id == strategy_id, Run.operation_kind == "rank", canonical.operation_kind == "rank",
            canonical.team_id == Run.team_id, canonical.request_shop_id == Run.request_shop_id,
            canonical.request_fingerprint == Run.request_fingerprint, canonical.reused_run_id.is_(None))
        if shop_id is not None:
            statement = statement.where(Run.request_shop_id == shop_id)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.execute(statement.order_by(Run.created_at.desc(), Run.run_id.desc()).offset(offset).limit(limit)).all()
        return rows, total

    def list(self, actor, *, shop_id, blocked, strategy_id, execution_id, day_bounds,
             discovery_state, scope_hash, search, offset, limit, sort, descending):
        statement = ProductSelectionRepository.visible_statement(actor).where(Candidate.blocked == blocked)
        if shop_id is not None:
            statement = statement.where(Observation.request_shop_id == shop_id)
        if scope_hash is not None:
            statement = statement.where(Observation.source_scope_hash == scope_hash)
        has_hits = execution_id is not None or strategy_id is not None or day_bounds is not None
        if has_hits:
            statement = statement.join(Item, Item.observation_id == Observation.observation_id).join(
                Run, Run.run_id == Item.execution_run_id).where(
                Run.operation_kind == "rank", Run.reused_run_id.is_(None),
                Run.team_id == Candidate.team_id, Run.request_shop_id == Observation.request_shop_id)
            if execution_id is not None:
                statement = statement.where(Item.execution_run_id == execution_id)
            elif strategy_id is not None:
                receipt = aliased(Run)
                statement = statement.where(exists(select(receipt.run_id).where(
                    receipt.strategy_id == strategy_id, receipt.operation_kind == "rank",
                    func.coalesce(receipt.reused_run_id, receipt.run_id) == Run.run_id,
                    receipt.team_id == Run.team_id, receipt.request_shop_id == Run.request_shop_id,
                    receipt.request_fingerprint == Run.request_fingerprint).correlate(Run)))
            if day_bounds is not None:
                statement = statement.where(Item.hit_at >= day_bounds[0], Item.hit_at < day_bounds[1])
            if discovery_state is not None:
                statement = statement.where(Item.discovery_state == discovery_state)
            # Matching events first; a later known event must not erase today's new hit.
            order = (Item.hit_at.desc(), Item.item_id.desc(), Observation.observation_id.desc())
            ranked = statement.with_only_columns(Observation.observation_id, Item.item_id,
                func.row_number().over(partition_by=Observation.candidate_id, order_by=order).label("pos")).subquery()
            chosen = select(Observation, Item).join(ranked,
                ranked.c.observation_id == Observation.observation_id).join(Item,
                Item.item_id == ranked.c.item_id).where(ranked.c.pos == 1)
        else:
            ranked = statement.with_only_columns(Observation.observation_id,
                func.row_number().over(partition_by=Observation.candidate_id,
                    order_by=(Observation.checked_at.desc(), Observation.observation_id.desc())).label("pos")).subquery()
            # Only genuine current membership, never infer old history from last_run_id.
            valid_run = exists(select(Run.run_id).where(
                Run.run_id == Item.execution_run_id, Run.operation_kind == "rank",
                Run.reused_run_id.is_(None), Run.team_id == Candidate.team_id,
                Run.request_shop_id == Observation.request_shop_id).correlate(Item, Observation, Candidate))
            chosen = select(Observation, Item).join(ranked,
                ranked.c.observation_id == Observation.observation_id).join(Candidate,
                Candidate.candidate_id == Observation.candidate_id).outerjoin(Item, and_(
                Item.observation_id == Observation.observation_id,
                Item.execution_run_id == Observation.last_run_id, valid_run)).where(ranked.c.pos == 1)
        if search:
            if has_hits:
                chosen = chosen.join(Candidate, Candidate.candidate_id == Observation.candidate_id)
            chosen = chosen.where(or_(Observation.title.icontains(search, autoescape=True),
                Candidate.platform_product_id.icontains(search, autoescape=True)))
        total = self.session.scalar(select(func.count()).select_from(chosen.subquery())) or 0
        unknown = self.session.scalar(select(func.count()).select_from(chosen.where(or_(
            Item.item_id.is_(None), Item.discovery_state == "unknown")).subquery())) or 0
        column = {"checked_at": Item.hit_at if has_hits else Observation.checked_at,
            "first_on_shelf_date": Observation.first_on_shelf_date,
            "rank": Item.snapshot["rank"].as_integer() if has_hits else Observation.rank}[sort]
        rows = self.session.execute(chosen.order_by(
            (column.desc() if descending else column.asc()).nulls_last(), Observation.candidate_id).offset(offset).limit(limit)).all()
        return rows, total, unknown, has_hits
