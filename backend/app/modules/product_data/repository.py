from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.product_data.collection import CompleteProductDataSnapshot
from app.modules.product_data.models import (
    ShopProductDataGeneration as Generation, ShopProductDataMetricSnapshot as Snapshot,
    ShopProductDataProduct as Product, ShopProductDataSeries as Series,
)
from app.modules.product_data.schemas import METRIC_BY_CODE, ProductDataQuery
from app.modules.product_data.source import ProductDataSlice, REQUEST_CONTRACT
from app.platforms.douyin.product_data import PRODUCT_METRIC_CONTRACT
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.shared.identifiers import generate_id


class ProductDataRepository:
    def __init__(self, session: Session):
        self.session = session

    def now(self):
        return self.session.scalar(select(func.clock_timestamp()))

    @staticmethod
    def _shop_scope(statement, actor):
        if actor.is_super_account:
            return statement
        return statement.where(select(TeamShopAccess.shop_id).where(
            TeamShopAccess.shop_id == Shop.shop_id,
            TeamShopAccess.team_id == actor.require_team_id(),
        ).exists())

    def shop(self, actor: ActorContext, shop_id: UUID):
        return self.session.scalar(self._shop_scope(select(Shop), actor).where(
            Shop.shop_id == shop_id, Shop.deleted_at.is_(None)))

    def supported_shop_ids(self, actor, shop_id=None):
        statement = self._shop_scope(select(Shop.shop_id), actor).where(
            Shop.deleted_at.is_(None), Shop.platform == ShopPlatform.DOUYIN)
        if shop_id is not None:
            statement = statement.where(Shop.shop_id == shop_id)
        return list(self.session.scalars(statement.order_by(Shop.shop_id)))

    def by_key(self, user_id, submission_key):
        return self.session.scalar(select(Generation).where(
            Generation.requested_by_user_id == user_id, Generation.submission_key == submission_key))

    def visible_generation(self, actor, generation_id):
        statement = self._shop_scope(select(Generation).join(Shop, Shop.shop_id == Generation.shop_id), actor).where(
            Generation.generation_id == generation_id, Shop.deleted_at.is_(None))
        if not actor.is_super_account:
            statement = statement.where(Generation.requested_by_user_id == actor.user_id,
                                        Generation.requested_team_id == actor.require_team_id())
        return self.session.scalar(statement)

    def generation(self, generation_id):
        return self.session.get(Generation, generation_id)

    def submission_lock(self):
        # Product Data only, transaction scoped, never held across external I/O.
        self.session.execute(select(func.pg_advisory_xact_lock(0x535044470047)))

    def expire_requested_slice(self, scope):
        self.session.execute(update(Generation).where(
            Generation.shop_id == scope.shop_id, Generation.source_scope_hash == scope.source_scope_hash,
            Generation.status == "running", Generation.lease_until <= func.clock_timestamp(),
        ).values(status="failed", stage="execution", failure_code="PRODUCT_DATA_LEASE_EXPIRED",
                 lease_id=None, lease_until=None, finished_at=func.clock_timestamp()))

    def busy(self, scope, max_running):
        active = self.session.scalar(select(Generation.generation_id).where(
            Generation.shop_id == scope.shop_id, Generation.source_scope_hash == scope.source_scope_hash,
            Generation.status.in_(["pending", "running"])).limit(1))
        running = self.session.scalar(select(func.count()).select_from(Generation).where(
            Generation.status == "running", Generation.lease_until > func.clock_timestamp())) or 0
        return active is not None or running >= max_running

    def create_generation(self, actor, request, scope, lease_seconds):
        self.session.execute(pg_insert(Series).values(
            series_id=generate_id(), shop_id=scope.shop_id, rolling_series_hash=scope.rolling_series_hash,
            period=scope.period, sale_type=scope.sale_type, content_type=scope.content_type,
            request_contract=scope.request_contract, metric_contract=scope.metric_contract,
        ).on_conflict_do_nothing(constraint="uq_spd_series_scope"))
        series = self.session.scalar(select(Series).where(
            Series.shop_id == scope.shop_id, Series.rolling_series_hash == scope.rolling_series_hash).with_for_update())
        now = self.now()
        generation = Generation(
            generation_id=generate_id(), series_id=series.series_id, shop_id=scope.shop_id,
            sequence=series.next_sequence, requested_by_user_id=actor.user_id, requested_team_id=actor.team_id,
            submission_key=request.submission_key, period=scope.period, date_type=scope.date_type,
            start_date=scope.start_date, end_date=scope.end_date, source_scope_hash=scope.source_scope_hash,
            request_scope=scope.model_dump(mode="json"), status="running", stage="session_preparation",
            lease_id=generate_id(), lease_until=now+timedelta(seconds=lease_seconds), started_at=now,
        )
        series.next_sequence += 1
        self.session.add(generation)
        self.session.flush()
        return generation

    def live_generation(self, generation_id, lease_id, *, lock=False):
        statement = select(Generation).where(
            Generation.generation_id == generation_id, Generation.lease_id == lease_id,
            Generation.status == "running", Generation.lease_until > func.clock_timestamp())
        return self.session.scalar(statement.with_for_update() if lock else statement)

    def mark_failed(self, generation_id, lease_id, code, stage):
        result = self.session.execute(update(Generation).where(
            Generation.generation_id == generation_id, Generation.lease_id == lease_id,
            Generation.status == "running", Generation.lease_until > func.clock_timestamp(),
        ).values(status="failed", stage=stage, failure_code=code, lease_id=None, lease_until=None,
                 finished_at=func.clock_timestamp(), pages_complete=False))
        return result.rowcount == 1

    def note_progress(self, generation, page):
        if generation.expected_total is not None and generation.expected_total != page.total:
            return False
        generation.expected_total = page.total
        generation.received_total = (generation.received_total or 0) + len(page.products)
        generation.received_pages += 1
        generation.stage = "platform_response"
        return True

    def lock_series(self, series_id):
        return self.session.scalar(select(Series).where(Series.series_id == series_id).with_for_update())

    def store_complete_rows(self, generation, snapshot: CompleteProductDataSnapshot, now):
        identities = sorted(row.product_id for row in snapshot.products)
        self.session.execute(pg_insert(Product).on_conflict_do_nothing(constraint="uq_spd_product_identity"), [
            {"shop_product_id": generate_id(), "shop_id": generation.shop_id, "platform": "douyin", "platform_product_id": value}
            for value in identities
        ])
        products = {row.platform_product_id: row.shop_product_id for row in self.session.scalars(
            select(Product).where(Product.shop_id == generation.shop_id, Product.platform == "douyin",
                                  Product.platform_product_id.in_(identities)))}
        values = []
        for row in snapshot.products:
            values.append({
                "generation_id": generation.generation_id, "shop_product_id": products[row.product_id],
                "shop_id": generation.shop_id, "observed_title": row.title.value, "observed_image_url": row.image.value,
                "retrieved_at": now, "raw_units": {item.definition.code: item.raw_unit for item in row.metrics},
                "metric_states": {item.definition.code: item.state for item in row.metrics},
                **{item.definition.code: item.raw_value for item in row.metrics},
            })
        self.session.execute(insert(Snapshot).execution_options(render_nulls=True), values)

    def finalize_success(self, generation, lease_id, snapshot, now):
        result = self.session.execute(update(Generation).where(
            Generation.generation_id == generation.generation_id, Generation.lease_id == lease_id,
            Generation.status == "running", Generation.lease_until > func.clock_timestamp(),
        ).values(status="succeeded", stage="complete", failure_code=None, lease_id=None, lease_until=None,
                 expected_total=snapshot.total, received_total=snapshot.total, received_pages=snapshot.page_count,
                 pages_complete=True, raw_complete_rows=snapshot.raw_complete_rows,
                 unit_complete_rows=snapshot.display_complete_rows, finished_at=now, published_at=now))
        return result.rowcount == 1

    def _latest_published(self, actor, query):
        statement = self._shop_scope(select(
            Generation.generation_id.label("generation_id"), Generation.shop_id.label("shop_id"),
            func.row_number().over(partition_by=Generation.shop_id, order_by=Generation.sequence.desc()).label("position"),
        ).join(Shop, Shop.shop_id == Generation.shop_id).join(Series, Series.series_id == Generation.series_id), actor).where(
            Shop.deleted_at.is_(None), Shop.platform == ShopPlatform.DOUYIN,
            Generation.status == "succeeded", Generation.published_at.is_not(None),
            Generation.period == query.period, Generation.start_date == query.start_date, Generation.end_date == query.end_date,
            Series.period == query.period, Series.sale_type == query.sale_type, Series.content_type == query.content_type,
            Series.request_contract == REQUEST_CONTRACT,
            Series.metric_contract == PRODUCT_METRIC_CONTRACT,
        )
        if query.shop_id is not None:
            statement = statement.where(Shop.shop_id == query.shop_id)
        ranked = statement.subquery()
        return select(ranked.c.generation_id, ranked.c.shop_id).where(ranked.c.position == 1).subquery()

    def list_facts(self, actor, query: ProductDataQuery):
        latest = self._latest_published(actor, query)
        statement = self._shop_scope(select(Snapshot, Product, Shop, Generation)
            .join(Product, Product.shop_product_id == Snapshot.shop_product_id)
            .join(Generation, Generation.generation_id == Snapshot.generation_id)
            .join(latest, latest.c.generation_id == Generation.generation_id)
            .join(Shop, Shop.shop_id == Snapshot.shop_id), actor)
        if query.product_id:
            statement = statement.where(Product.platform_product_id.contains(query.product_id, autoescape=True))
        if query.product_name:
            statement = statement.where(Snapshot.observed_title.icontains(query.product_name, autoescape=True))
        for interval in query.ranges:
            column = getattr(Snapshot, interval.metric)
            statement = statement.where(Snapshot.metric_states[interval.metric].astext == "available",
                                        Snapshot.raw_units[interval.metric].astext == "5")
            if interval.min_value is not None: statement = statement.where(column >= interval.min_value)
            if interval.max_value is not None: statement = statement.where(column < interval.max_value)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        ordering = []
        if query.sort_field:
            field = query.sort_field
            if field in METRIC_BY_CODE:
                value = case((and_(Snapshot.metric_states[field].astext == "available",
                                   Snapshot.raw_units[field].astext == str(METRIC_BY_CODE[field].observed_unit)),
                              getattr(Snapshot, field)), else_=None)
            else:
                value = {"shop_name": Shop.display_name, "product_id": Product.platform_product_id,
                         "title": Snapshot.observed_title, "retrieved_at": Snapshot.retrieved_at}[field]
            ordering.append((value.desc() if query.sort_direction == "desc" else value.asc()).nulls_last())
        else:
            ordering.extend([Shop.display_name.asc(), Product.platform_product_id.asc()])
        rows = list(self.session.execute(statement.order_by(*ordering, Shop.shop_id.asc(), Product.shop_product_id.asc())
                    .offset((query.page-1)*query.page_size).limit(query.page_size)))
        collected_shops = list(self.session.scalars(select(latest.c.shop_id)))
        return rows, total, collected_shops
