"""Short-transaction fact writes/reads; no network or manual-run emulation."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ActorContextService, ModuleAccessService
from app.modules.product_selection.exceptions import (
    SelectionObservationNotFoundError, SelectionShopUnavailableError,
)
from app.modules.product_selection.models import (
    ProductSelectionCandidate, ProductSelectionObservation,
)
from app.modules.product_selection.repository import ProductSelectionRepository
from app.modules.product_selection.schemas import SelectionObservationRead
from app.modules.product_selection.run_contract import SelectionRunClaim, SelectionResolvedRequest
from app.modules.product_selection.run_repository import SelectionRunRepository
from app.modules.product_selection.exceptions import SelectionRunLeaseLostError
from app.modules.product_selection.source import SelectionSourceScope
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.repository import ShopRepository
from app.platforms.douyin.product_selection import (
    CompassBasicInfo, CompassSelectionIdentityError, CompassRankPage,
    CompassMetricRange, FieldObservation,
)


def _range_fact(
    observation: FieldObservation[CompassMetricRange], at: datetime,
) -> dict[str, Any]:
    fact: dict[str, Any] = {"state": observation.state, "retrieved_at": at.isoformat()}
    if observation.state == "available" and observation.value is not None:
        fact["value_range"] = [
            {"value": str(endpoint.value), "value_type": endpoint.value_type,
             "unit": endpoint.unit}
            for endpoint in observation.value.endpoints
        ]
    return fact


class ProductSelectionFactService:
    """Internal persistence boundary, not yet an executable selection API.

    Each method uses a dedicated short-lived Session. Actor, module and Shop
    authorization are re-read here after any external I/O performed upstream.
    A future executor must also check them before sending a platform request.
    """

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ProductSelectionRepository(session)
        self.shops = ShopRepository(session)

    def _current_actor(self, actor: ActorContext) -> ActorContext:
        self.session.expire_all()
        current = ActorContextService(self.session).resolve(
            user_id=actor.user_id, requested_team_id=actor.team_id,
        )
        ModuleAccessService(self.session).require_module_access(
            current, ModuleCode.PRODUCT_SELECTION,
        )
        return current

    def _execution_shop(self, actor: ActorContext, shop_id: UUID) -> None:
        shop = self.shops.get_for_actor(actor=actor, shop_id=shop_id)
        if shop is None or not shop.enabled or shop.platform != ShopPlatform.DOUYIN:
            raise SelectionShopUnavailableError()

    @staticmethod
    def _time_order(started_at: datetime, retrieved_at: datetime) -> None:
        if (
            started_at.utcoffset() is None or retrieved_at.utcoffset() is None
            or retrieved_at < started_at
        ):
            raise ValueError("Actual execution timestamps must be aware and ordered")

    def persist_rank_page(
        self, *, actor: ActorContext, shop_id: UUID, scope: SelectionSourceScope,
        page: CompassRankPage, started_at: datetime, retrieved_at: datetime,
        claim: SelectionRunClaim | None = None,
    ) -> tuple[UUID, ...]:
        self._time_order(started_at, retrieved_at)
        try:
            current = self._current_actor(actor)
            team_id = current.require_team_id()
            self._execution_shop(current, shop_id)
            run = self._fenced_run(current, claim, shop_id, scope, retrieved_at)
            # Stable identity dedup within a page as well as database-enforced
            # dedup across pages/processes. No candidate is invented for empty.
            products = {product.product_id: product for product in reversed(page.products)}
            saved: list[UUID] = []
            for product in sorted(products.values(), key=lambda item: item.product_id):
                candidate_id = self.repository.upsert_candidate(
                    team_id=team_id, user_id=current.user_id,
                    product_id=product.product_id, at=retrieved_at,
                )
                observation_id = self.repository.upsert_rank_observation(
                    candidate_id=candidate_id, shop_id=shop_id, scope=scope,
                    started_at=started_at, retrieved_at=retrieved_at,
                    last_run_id=claim.run_id if claim is not None else None,
                    date_selection=(SelectionResolvedRequest.model_validate(run.request_conditions).provenance().model_dump(mode="json")
                        if run is not None and claim.request.version in {2, 3, 4, 5, 6} else None),
                    first_listed_only=(claim.request.original.first_listed_only if claim is not None and claim.request.version in {3, 4, 5, 6} else False),
                    values={
                        "title": product.title, "image_url": product.image_url,
                        "merchant_snapshot": [
                            {"platform_shop_id": item.platform_shop_id, "name": item.name}
                            for item in product.merchants
                        ],
                        "price_band": product.price_band, "rank": product.rank,
                        "newly_on_ranking": product.newly_on_ranking,
                        "video_metric_ranges": {
                            "pay_amt": _range_fact(product.pay_amt, retrieved_at),
                            "pay_combo_cnt": _range_fact(product.pay_combo_cnt, retrieved_at),
                            "product_click_cnt": _range_fact(product.product_click_cnt, retrieved_at),
                            "video_cnt": _range_fact(product.video_cnt, retrieved_at),
                        },
                    },
                )
                if observation_id is not None:
                    saved.append(observation_id)
            if run is not None:
                run.stage = "basic_info"
                run.result_count = (run.result_count or 0) + len(products)
                run.saved_count += len(saved)
                run.updated_at = retrieved_at
            self.session.commit()
            return tuple(saved)
        except Exception:
            self.session.rollback()
            raise

    def _fenced_run(self, actor, claim, shop_id, scope, at):
        if claim is None:
            return None
        if (actor.user_id != claim.user_id or actor.require_team_id() != claim.team_id
            or shop_id != claim.shop_id):
            raise SelectionRunLeaseLostError()
        # Hold the row lock until the same commit as facts, counts and source
        # association. An expiry/replacement cannot pass between check/write.
        run = SelectionRunRepository(self.session).fence(claim, at)
        request = SelectionResolvedRequest.model_validate(run.request_conditions)
        if scope != request.actual_scope():
            raise SelectionRunLeaseLostError()
        return run

    def _writable_observation(
        self, actor: ActorContext, observation_id: UUID,
    ) -> ProductSelectionObservation:
        current = self._current_actor(actor)
        row = self.repository.get_for_actor(actor=current, observation_id=observation_id)
        if row is None:
            raise SelectionObservationNotFoundError()
        # Super accounts may read across teams, but writes need that record's
        # explicit Team context. No default Team or borrowed Shop ownership.
        if row.candidate_id is not None:
            candidate = self.session.get(ProductSelectionCandidate, row.candidate_id)
            if candidate is None or candidate.team_id != current.require_team_id():
                raise SelectionObservationNotFoundError()
        self._execution_shop(current, row.request_shop_id)
        return row

    def persist_basic_info(
        self, *, actor: ActorContext, observation_id: UUID,
        rank_started_at: datetime, retrieved_at: datetime, basic: CompassBasicInfo,
        claim: SelectionRunClaim | None = None,
    ) -> bool:
        self._time_order(rank_started_at, retrieved_at)
        try:
            row = self._writable_observation(actor, observation_id)
            run = self._fenced_run(actor, claim, row.request_shop_id,
                                   SelectionSourceScope.model_validate(row.source_context["business"]), retrieved_at)
            if claim is not None and row.last_run_id != claim.run_id:
                raise SelectionRunLeaseLostError()
            candidate = self.session.get(ProductSelectionCandidate, row.candidate_id)
            if candidate is None or candidate.platform_product_id != basic.product_id:
                raise CompassSelectionIdentityError()
            values: dict[str, Any] = {}
            if basic.category_path.state == "available":
                values["category_path"] = list(basic.category_path.value or ())
            if basic.first_on_shelf_date.state == "available":
                values["first_on_shelf_date"] = basic.first_on_shelf_date.value
            if basic.bad_comment_rate.state == "available" and basic.bad_comment_rate.value:
                values["bad_comment_rate_raw"] = basic.bad_comment_rate.value.value
                values["bad_comment_rate_unit"] = basic.bad_comment_rate.value.unit
            partial = any(field.state != "available" for field in (
                basic.category_path, basic.first_on_shelf_date, basic.bad_comment_rate,
            ))
            changed = self.repository.update_basic_info(
                observation_id=observation_id, rank_started_at=rank_started_at,
                retrieved_at=retrieved_at, values=values, partial=partial,
                once_for_run=claim is not None,
            )
            if run is not None and changed:
                if partial:
                    run.supplement_failed_count += 1
                else:
                    run.supplemented_count += 1
                run.updated_at = retrieved_at
            self.session.commit()
            return changed
        except Exception:
            self.session.rollback()
            raise

    def record_basic_info_failure(
        self, *, actor: ActorContext, observation_id: UUID,
        rank_started_at: datetime, at: datetime, error: AppError,
        claim: SelectionRunClaim | None = None,
    ) -> bool:
        self._time_order(rank_started_at, at)
        safe_codes = {
            "AUTH_INVALID", "PLATFORM_TIMEOUT", "PLATFORM_REQUEST_FAILED",
            "PLATFORM_SIGNER_FAILED", "PLATFORM_RESPONSE_INVALID",
            "DOUYIN_SELECTION_BUSINESS_REJECTED", "DOUYIN_SELECTION_PRODUCT_ID_MISMATCH",
        }
        try:
            row = self._writable_observation(actor, observation_id)
            run = self._fenced_run(actor, claim, row.request_shop_id,
                                   SelectionSourceScope.model_validate(row.source_context["business"]), at)
            if claim is not None and row.last_run_id != claim.run_id:
                raise SelectionRunLeaseLostError()
            changed = self.repository.record_basic_info_failure(
                observation_id=observation_id, rank_started_at=rank_started_at, at=at,
                code=error.code if error.code in safe_codes else "PLATFORM_REQUEST_FAILED",
                once_for_run=claim is not None,
            )
            if run is not None and changed:
                run.supplement_failed_count += 1
                run.updated_at = at
            self.session.commit()
            return changed
        except Exception:
            self.session.rollback()
            raise

    def list_latest(
        self, *, actor: ActorContext, shop_id: UUID | None = None,
        scope_hash: str | None = None, offset: int = 0, limit: int = 10,
        sort: Literal["checked_at", "first_on_shelf_date", "rank"] = "checked_at",
        descending: bool = True,
        search: str | None = None,
    ) -> tuple[list[ProductSelectionObservation], int]:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid bounded pagination")
        return self.repository.list_latest_for_actor(
            actor=self._current_actor(actor), shop_id=shop_id, scope_hash=scope_hash,
            offset=offset, limit=limit, sort=sort, descending=descending,
            search=search.strip() if search else None,
        )

    def get_observation(
        self, *, actor: ActorContext, observation_id: UUID,
    ) -> ProductSelectionObservation:
        row = self.repository.get_for_actor(
            actor=self._current_actor(actor), observation_id=observation_id,
        )
        if row is None:
            raise SelectionObservationNotFoundError()
        return row

    def _read_projection(
        self, rows: list[ProductSelectionObservation],
    ) -> list[SelectionObservationRead]:
        identities = self.repository.read_identities([row.observation_id for row in rows])
        return [SelectionObservationRead(
            observation_id=row.observation_id,
            last_run_id=row.last_run_id,
            candidate_id=row.candidate_id,
            product_id=identities[row.observation_id][0], platform="douyin",
            request_shop_id=row.request_shop_id,
            request_shop_name=identities[row.observation_id][1],
            source_scope_hash=row.source_scope_hash, source_context=row.source_context,
            period_begin=row.period_begin, period_end=row.period_end,
            title=row.title, image_url=row.image_url, source_url=row.source_url,
            merchants=row.merchant_snapshot, category_path=row.category_path,
            price_band=row.price_band, rank=row.rank, previous_rank=row.previous_rank,
            previous_checked_at=row.previous_checked_at,
            newly_on_ranking=row.newly_on_ranking, first_seen_at=row.first_seen_at,
            checked_at=row.checked_at, metrics_retrieved_at=row.metrics_retrieved_at,
            video_metric_ranges=row.video_metric_ranges,
            first_on_shelf_date=row.first_on_shelf_date,
            bad_comment_rate_raw=row.bad_comment_rate_raw,
            bad_comment_rate_unit=row.bad_comment_rate_unit,
            basic_info_retrieved_at=row.basic_info_retrieved_at,
            last_attempt_at=row.last_attempt_at, last_error_code=row.last_error_code,
            last_error_stage=row.last_error_stage,
        ) for row in rows]

    def list_read(
        self, *, actor: ActorContext, shop_id: UUID | None = None,
        scope_hash: str | None = None, offset: int = 0, limit: int = 10,
        sort: Literal["checked_at", "first_on_shelf_date", "rank"] = "checked_at",
        descending: bool = True, search: str | None = None,
    ) -> tuple[list[SelectionObservationRead], int]:
        rows, total = self.list_latest(
            actor=actor, shop_id=shop_id, scope_hash=scope_hash, offset=offset,
            limit=limit, sort=sort, descending=descending, search=search,
        )
        return self._read_projection(rows), total

    def get_read(
        self, *, actor: ActorContext, observation_id: UUID,
    ) -> SelectionObservationRead:
        row = self.get_observation(actor=actor, observation_id=observation_id)
        return self._read_projection([row])[0]
