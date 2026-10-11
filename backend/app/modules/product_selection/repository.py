from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, case, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.product_selection.models import (
    ProductSelectionCandidate as Candidate,
    ProductSelectionObservation as Observation,
)
from app.modules.product_selection.source import SelectionSourceScope
from app.modules.shops.models import Shop
from app.shared.identifiers import generate_id


METRIC_NAMES = ("pay_amt", "pay_combo_cnt", "product_click_cnt", "video_cnt")


class ProductSelectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _basic_unattempted():
        # Even identical timestamp precision must not count the callback
        # twice. Rank refresh resets the attempt/error and advances checked_at.
        return and_(
            Observation.last_attempt_at == Observation.checked_at,
            Observation.last_error_stage.is_(None),
            Observation.basic_info_retrieved_at.is_(None)
            | (Observation.basic_info_retrieved_at < Observation.checked_at),
        )

    def upsert_candidate(
        self, *, team_id: UUID, user_id: UUID, product_id: str, at: datetime,
    ) -> UUID:
        statement = insert(Candidate).values(
            candidate_id=generate_id(), team_id=team_id,
            created_by_user_id=user_id, platform="douyin",
            platform_product_id=product_id, created_at=at, updated_at=at,
        )
        return self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_selection_candidate_team_product",
                set_={"updated_at": func.greatest(Candidate.updated_at, at)},
            ).returning(Candidate.candidate_id),
        ).scalar_one()

    def upsert_rank_observation(
        self, *, candidate_id: UUID, shop_id: UUID, scope: SelectionSourceScope,
        values: dict[str, Any], started_at: datetime, retrieved_at: datetime,
        last_run_id: UUID | None = None,
        date_selection: dict[str, Any] | None = None,
    ) -> UUID | None:
        allowed = {
            "title", "image_url", "merchant_snapshot", "price_band", "rank",
            "newly_on_ranking", "video_metric_ranges",
        }
        if set(values) != allowed:
            raise ValueError("Only declared rank facts may be persisted")
        context = scope.context()
        if date_selection is not None:
            context["date_selection"] = date_selection
        statement = insert(Observation).values(
            observation_id=generate_id(), candidate_id=candidate_id,
            request_shop_id=shop_id, source_scope_hash=scope.fingerprint(),
            last_run_id=last_run_id,
            source_context=context, period_begin=scope.period_begin,
            period_end=scope.period_end, first_seen_at=retrieved_at,
            checked_at=retrieved_at, metrics_retrieved_at=retrieved_at,
            last_attempt_at=retrieved_at,
            last_successful_request_started_at=started_at,
            created_at=retrieved_at, updated_at=retrieved_at, **values,
        )
        incoming = statement.excluded
        metrics: list[Any] = []
        for name in METRIC_NAMES:
            old = Observation.video_metric_ranges[name]
            new = incoming.video_metric_ranges[name]
            metrics.extend((name, case(
                (new["state"].astext == "available", new),
                (old["state"].astext == "available", old),
                else_=new,
            )))
        return self.session.execute(
            statement.on_conflict_do_update(
                constraint="uq_selection_observation_source",
                set_={
                    "source_context": incoming.source_context,
                    "title": func.coalesce(incoming.title, Observation.title),
                    "image_url": func.coalesce(incoming.image_url, Observation.image_url),
                    "merchant_snapshot": case(
                        (func.jsonb_array_length(incoming.merchant_snapshot) > 0,
                         incoming.merchant_snapshot),
                        else_=Observation.merchant_snapshot,
                    ),
                    "price_band": func.coalesce(incoming.price_band, Observation.price_band),
                    "previous_rank": case(
                        (incoming.rank.is_not(None), Observation.rank),
                        else_=Observation.previous_rank,
                    ),
                    "previous_checked_at": case(
                        (incoming.rank.is_not(None), Observation.checked_at),
                        else_=Observation.previous_checked_at,
                    ),
                    "rank": func.coalesce(incoming.rank, Observation.rank),
                    "newly_on_ranking": incoming.newly_on_ranking,
                    "checked_at": incoming.checked_at,
                    "metrics_retrieved_at": incoming.metrics_retrieved_at,
                    "video_metric_ranges": func.jsonb_build_object(*metrics),
                    "last_attempt_at": incoming.last_attempt_at,
                    "last_successful_request_started_at": incoming.last_successful_request_started_at,
                    "last_error_code": None,
                    "last_error_stage": None,
                    "last_run_id": (incoming.last_run_id if last_run_id is not None else Observation.last_run_id),
                    "updated_at": incoming.updated_at,
                },
                # Equal/older starts cannot overwrite a later successful run,
                # even when that old request returns after the newer request.
                where=(Observation.last_successful_request_started_at < started_at),
            ).returning(Observation.observation_id),
        ).scalar_one_or_none()

    def update_basic_info(
        self, *, observation_id: UUID, rank_started_at: datetime,
        retrieved_at: datetime, values: dict[str, Any], partial: bool,
        once_for_run: bool = False,
    ) -> bool:
        allowed = {
            "category_path", "first_on_shelf_date", "bad_comment_rate_raw",
            "bad_comment_rate_unit",
        }
        if not set(values) <= allowed:
            raise ValueError("Only declared basic-info facts may be persisted")
        changed = self.session.execute(
            update(Observation).where(
                Observation.observation_id == observation_id,
                Observation.last_successful_request_started_at == rank_started_at,
                Observation.last_attempt_at <= retrieved_at,
                self._basic_unattempted() if once_for_run else True,
                (Observation.basic_info_retrieved_at.is_(None)
                 | (Observation.basic_info_retrieved_at < retrieved_at)),
            ).values(
                **values, basic_info_retrieved_at=(
                    Observation.basic_info_retrieved_at if partial else retrieved_at
                ),
                last_attempt_at=retrieved_at, updated_at=retrieved_at,
                last_error_code="PRODUCT_SELECTION_BASIC_INFO_PARTIAL" if partial else None,
                last_error_stage="basic_info_parse" if partial else None,
            ).returning(Observation.observation_id),
        ).scalar_one_or_none()
        return changed is not None

    def record_basic_info_failure(
        self, *, observation_id: UUID, rank_started_at: datetime,
        at: datetime, code: str, once_for_run: bool = False,
    ) -> bool:
        changed = self.session.execute(
            update(Observation).where(
                Observation.observation_id == observation_id,
                Observation.last_successful_request_started_at == rank_started_at,
                Observation.last_attempt_at <= at,
                self._basic_unattempted() if once_for_run else True,
            ).values(
                last_attempt_at=at, updated_at=at, last_error_code=code,
                last_error_stage="basic_info_request",
            ).returning(Observation.observation_id),
        ).scalar_one_or_none()
        return changed is not None

    @staticmethod
    def visible_statement(actor: ActorContext):
        statement = select(Observation).join(
            Candidate, Candidate.candidate_id == Observation.candidate_id,
        ).join(Shop, Shop.shop_id == Observation.request_shop_id).where(
            Shop.deleted_at.is_(None),
        )
        if not actor.is_super_account:
            statement = statement.where(
                Candidate.team_id == actor.require_team_id(),
                exists(select(TeamShopAccess.team_id).where(
                    TeamShopAccess.team_id == actor.team_id,
                    TeamShopAccess.shop_id == Observation.request_shop_id,
                )),
            )
        elif actor.team_id is not None:
            statement = statement.where(Candidate.team_id == actor.team_id)
        return statement

    def get_for_actor(
        self, *, actor: ActorContext, observation_id: UUID,
    ) -> Observation | None:
        return self.session.scalar(self.visible_statement(actor).where(
            Observation.observation_id == observation_id,
        ))

    def list_latest_for_actor(
        self, *, actor: ActorContext, shop_id: UUID | None = None,
        scope_hash: str | None = None, offset: int = 0, limit: int = 10,
        sort: Literal["checked_at", "first_on_shelf_date", "rank"] = "checked_at",
        descending: bool = True,
        search: str | None = None,
    ) -> tuple[list[Observation], int]:
        statement = self.visible_statement(actor)
        if shop_id is not None:
            statement = statement.where(Observation.request_shop_id == shop_id)
        if scope_hash is not None:
            statement = statement.where(Observation.source_scope_hash == scope_hash)
        # Authorization and source filters precede latest-source selection,
        # so an invisible newer source cannot leak values or hide a visible one.
        ranked = statement.add_columns(func.row_number().over(
            partition_by=Observation.candidate_id,
            order_by=(Observation.checked_at.desc(), Observation.observation_id.desc()),
        ).label("source_position")).subquery()
        ids = select(ranked.c.observation_id).where(ranked.c.source_position == 1)
        filtered = select(Observation).join(
            Candidate, Candidate.candidate_id == Observation.candidate_id,
        ).where(Observation.observation_id.in_(ids))
        if search:
            filtered = filtered.where(or_(
                Observation.title.icontains(search, autoescape=True),
                Candidate.platform_product_id.icontains(search, autoescape=True),
            ))
        total = self.session.scalar(
            select(func.count()).select_from(filtered.subquery()),
        ) or 0
        sort_column = {
            "checked_at": Observation.checked_at,
            "first_on_shelf_date": Observation.first_on_shelf_date,
            "rank": Observation.rank,
        }[sort]
        order = sort_column.desc() if descending else sort_column.asc()
        rows = self.session.scalars(
            filtered
            .order_by(order.nulls_last(), Observation.candidate_id.asc())
            .offset(offset).limit(limit),
        ).all()
        return list(rows), total

    def read_identities(
        self, observation_ids: list[UUID],
    ) -> dict[UUID, tuple[str, str]]:
        """Batch projection for already-scoped observations, not a new lookup API."""
        if not observation_ids:
            return {}
        rows = self.session.execute(select(
            Observation.observation_id, Candidate.platform_product_id, Shop.display_name,
        ).join(
            Candidate, Candidate.candidate_id == Observation.candidate_id,
        ).join(
            Shop, Shop.shop_id == Observation.request_shop_id,
        ).where(Observation.observation_id.in_(observation_ids))).all()
        return {key: (product_id, shop_name) for key, product_id, shop_name in rows}
