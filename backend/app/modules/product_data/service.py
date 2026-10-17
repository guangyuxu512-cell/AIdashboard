from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.access.contracts import ActorContext
from app.modules.access.exceptions import TeamAccessDeniedError
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ActorContextService, ModuleAccessService
from app.modules.product_data.collection import CompleteProductDataSnapshot
from app.modules.product_data.exceptions import (
    ProductDataCollectionBusyError, ProductDataCollectionLimitExceededError,
    ProductDataCollectionUnavailableError, ProductDataGenerationNotFoundError,
    ProductDataIdempotencyConflictError, ProductDataPublicationRejectedError, ProductDataSourceInvalidError,
    ProductDataUnsupportedError,
)
from app.modules.product_data.repository import ProductDataRepository
from app.modules.product_data.schemas import (
    METRIC_BY_CODE, ProductDataCollectionRequest, ProductDataCoverageRead, ProductDataGenerationRead,
    ProductDataListRead, ProductDataMetricRead, ProductDataQuery, ProductDataRowRead,
)
from app.modules.product_data.source import ProductDataSlice, freeze_native_slice
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.exceptions import ShopNotFoundError
from app.platforms.douyin.product_data import PRODUCT_METRICS
from app.platforms.exceptions import PlatformIdentityMismatchError, PlatformResponseInvalidError


@dataclass(frozen=True)
class ProductDataExecutionContext:
    scope: ProductDataSlice
    platform_shop_id: str
    requester_id: UUID
    requester_team_id: UUID | None


class ProductDataService:
    def __init__(self, session: Session, *, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.repository = ProductDataRepository(session)

    def _actor(self, actor):
        current = ActorContextService(self.session).resolve(user_id=actor.user_id, requested_team_id=actor.team_id)
        if current.team_id != actor.team_id:
            raise TeamAccessDeniedError()
        ModuleAccessService(self.session).require_module_access(current, ModuleCode.SHOP)
        return current

    def _shop(self, actor, shop_id, *, collect=False):
        shop = self.repository.shop(actor, shop_id)
        if shop is None:
            raise ShopNotFoundError()
        if shop.platform != ShopPlatform.DOUYIN or (collect and (not shop.enabled or not shop.platform_shop_id)):
            raise ProductDataUnsupportedError()
        return shop

    @staticmethod
    def _scope(generation):
        try:
            scope = ProductDataSlice.model_validate(generation.request_scope)
        except ValidationError:
            raise ProductDataSourceInvalidError() from None
        if (scope.shop_id != generation.shop_id or scope.source_scope_hash != generation.source_scope_hash
                or scope.period != generation.period or scope.date_type != generation.date_type
                or scope.start_date != generation.start_date or scope.end_date != generation.end_date):
            raise ProductDataSourceInvalidError()
        return scope

    def _receipt(self, generation):
        return ProductDataGenerationRead(
            generation_id=generation.generation_id, scope=self._scope(generation), status=generation.status,
            stage=generation.stage, received_pages=generation.received_pages, expected_total=generation.expected_total,
            received_total=generation.received_total, pages_complete=generation.pages_complete,
            raw_complete_rows=generation.raw_complete_rows, unit_complete_rows=generation.unit_complete_rows,
            failure_code=generation.failure_code, created_at=generation.created_at, started_at=generation.started_at,
            finished_at=generation.finished_at, published_at=generation.published_at,
            lease_expired=generation.status == "running" and generation.lease_until <= self.repository.now(),
        )

    def request_collection(self, actor: ActorContext, request: ProductDataCollectionRequest):
        actor = self._actor(actor)
        self._shop(actor, request.shop_id, collect=True)
        # One transaction-scoped domain decision lock protects capacity,
        # cross-process duplicate intent and sequence allocation. No I/O here.
        self.repository.submission_lock()
        self.session.expire_all()
        actor = self._actor(actor)
        self._shop(actor, request.shop_id, collect=True)
        previous = self.repository.by_key(actor.user_id, request.submission_key)
        if previous is not None:
            scope = self._scope(previous)
            if (previous.requested_team_id != actor.team_id or previous.shop_id != request.shop_id
                    or scope.period != request.period or scope.sale_type != request.sale_type
                    or scope.content_type != request.content_type):
                raise ProductDataIdempotencyConflictError()
            receipt = self._receipt(previous)
            self.session.commit()
            return receipt, None
        if not self.settings.product_data_collection_execution_enabled:
            raise ProductDataCollectionUnavailableError()
        scope = freeze_native_slice(request.shop_id, request.period, self.repository.now())
        self.repository.expire_requested_slice(scope)
        if self.repository.busy(scope, self.settings.product_data_collection_max_running):
            raise ProductDataCollectionBusyError()
        try:
            generation = self.repository.create_generation(actor, request, scope, self.settings.product_data_collection_lease_seconds)
            lease_id = generation.lease_id
            receipt = self._receipt(generation)
            self.session.commit()
            return receipt, lease_id
        except IntegrityError as error:
            self.session.rollback()
            constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
            if constraint not in {"uq_spd_generation_actor_key", "uq_spd_active_slice"}:
                raise
            # Never expose another actor's run or constraint parameters.
            raise ProductDataCollectionBusyError() from None

    def read_generation(self, actor, generation_id):
        actor = self._actor(actor)
        generation = self.repository.visible_generation(actor, generation_id)
        if generation is None:
            raise ProductDataGenerationNotFoundError()
        return self._receipt(generation)

    def prepare_execution(self, generation_id, lease_id):
        generation = self.repository.live_generation(generation_id, lease_id)
        if generation is None:
            raise ProductDataPublicationRejectedError()
        actor = ActorContextService(self.session).resolve(user_id=generation.requested_by_user_id,
                                                         requested_team_id=generation.requested_team_id)
        if actor.team_id != generation.requested_team_id:
            raise TeamAccessDeniedError()
        ModuleAccessService(self.session).require_module_access(actor, ModuleCode.SHOP)
        shop = self._shop(actor, generation.shop_id, collect=True)
        return ProductDataExecutionContext(self._scope(generation), shop.platform_shop_id,
                                           actor.user_id, actor.team_id)

    def note_progress(self, generation_id, lease_id, page):
        self.prepare_execution(generation_id, lease_id)
        generation = self.repository.live_generation(generation_id, lease_id, lock=True)
        if generation is None:
            raise ProductDataPublicationRejectedError()
        if page.total > self.settings.product_data_collection_max_pages * 10:
            raise ProductDataCollectionLimitExceededError(page.total)
        if not self.repository.note_progress(generation, page):
            raise PlatformResponseInvalidError(details={"failure_stage": "collection_coverage", "reason": "page_total_changed"})
        self.session.commit()

    def publish(self, generation_id, lease_id, snapshot: CompleteProductDataSnapshot):
        context = self.prepare_execution(generation_id, lease_id)
        generation = self.repository.generation(generation_id)
        series = self.repository.lock_series(generation.series_id)
        # Lock waits must not reuse pre-wait authorization facts.
        self.session.expire_all()
        context = self.prepare_execution(generation_id, lease_id)
        generation = self.repository.live_generation(generation_id, lease_id, lock=True)
        if (generation is None or series.published_sequence >= generation.sequence
                or series.rolling_series_hash != snapshot.scope.rolling_series_hash
                or context.scope != snapshot.scope or snapshot.total < 1
                or len(snapshot.products) != snapshot.total
                or len({row.product_id for row in snapshot.products}) != snapshot.total
                or snapshot.page_count > self.settings.product_data_collection_max_pages
                or snapshot.page_count != (snapshot.total + 9) // 10):
            raise ProductDataPublicationRejectedError()
        codes = tuple(metric.code for metric in PRODUCT_METRICS)
        for row in snapshot.products:
            if row.platform_shop_id != context.platform_shop_id:
                raise PlatformIdentityMismatchError()
            if tuple(item.definition.code for item in row.metrics) != codes:
                raise ProductDataSourceInvalidError()
        now = self.repository.now()
        self.repository.store_complete_rows(generation, snapshot, now)
        if not self.repository.finalize_success(generation, lease_id, snapshot, now):
            self.session.rollback()
            raise ProductDataPublicationRejectedError()
        series.previous_generation_id = series.current_generation_id
        series.current_generation_id = generation_id
        series.published_sequence = generation.sequence
        self.session.commit()

    def fail(self, generation_id, lease_id, code, stage, *, expected_total: int | None = None):
        if expected_total is not None and (
            code != ProductDataCollectionLimitExceededError.code
            or type(expected_total) is not int or not 0 < expected_total <= 2_147_483_647
        ):
            raise ValueError("Invalid collection-limit receipt total")
        changed = self.repository.mark_failed(generation_id, lease_id, code, stage, expected_total=expected_total)
        self.session.commit()
        return changed

    def list(self, actor, query: ProductDataQuery):
        actor = self._actor(actor)
        query.require_verified_units()
        if query.shop_id is not None:
            self._shop(actor, query.shop_id)
        rows, total, collected_shops = self.repository.list_facts(actor, query)
        items = []
        for snapshot, product, shop, generation in rows:
            scope = self._scope(generation)
            metrics = {}
            for code, definition in METRIC_BY_CODE.items():
                raw_value = getattr(snapshot, code)
                unit = snapshot.raw_units[code]
                metrics[code] = ProductDataMetricRead(state=snapshot.metric_states[code],
                    raw_value=format(raw_value, "f") if raw_value is not None else None, raw_unit=unit,
                    unit_verified=definition.unit_verified and unit == definition.observed_unit)
            items.append(ProductDataRowRead(shop_product_id=product.shop_product_id,
                generation_id=generation.generation_id, shop_id=shop.shop_id, shop_name=shop.display_name,
                product_id=product.platform_product_id, title=snapshot.observed_title,
                image_url=snapshot.observed_image_url, metrics=metrics, scope=scope, retrieved_at=snapshot.retrieved_at))
        supported = self.repository.supported_shop_ids(actor, query.shop_id)
        return ProductDataListRead(items=items, total=total, page=query.page, page_size=query.page_size,
            coverage=ProductDataCoverageRead(supported_shop_count=len(supported), collected_shop_count=len(collected_shops),
                missing_shop_ids=[value for value in supported if value not in set(collected_shops)],
                collection_available=self.settings.product_data_collection_execution_enabled,
                unit_unconfirmed_codes=[code for code, metric in METRIC_BY_CODE.items() if not metric.unit_verified]))
