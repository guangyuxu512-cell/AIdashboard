from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, case, exists, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased

from app.modules.access.contracts import ActorContext
from app.modules.access.models import TeamShopAccess
from app.modules.product_data.collection import CompleteProductDataSnapshot
from app.modules.product_data.models import (
    ShopProductDataCollectionBatch as CollectionBatch,
    ShopProductDataGeneration as Generation, ShopProductDataMetricSnapshot as Snapshot,
    ShopProductDataProduct as Product, ShopProductDataSeries as Series,
)
from app.modules.product_data.schemas import METRIC_BY_CODE, ProductDataQuery
from app.modules.product_data.source import ProductDataSlice, REQUEST_CONTRACT
from app.platforms.douyin.product_data import PRODUCT_METRIC_CONTRACT
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.shared.identifiers import generate_id


@dataclass(frozen=True)
class ProductDataCollectionClaim:
    generation_id: UUID
    lease_id: UUID


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

    def collection_shops(self, actor):
        statement = self._shop_scope(select(Shop), actor).where(
            Shop.deleted_at.is_(None),
            Shop.enabled.is_(True),
            Shop.platform == ShopPlatform.DOUYIN,
            Shop.platform_shop_id.is_not(None),
        )
        return list(self.session.scalars(statement.order_by(Shop.display_name, Shop.shop_id)))

    def batch_by_key(self, user_id, submission_key):
        return self.session.scalar(select(CollectionBatch).where(
            CollectionBatch.requested_by_user_id == user_id,
            CollectionBatch.submission_key == submission_key,
        ))

    def batch(self, collection_batch_id):
        return self.session.get(CollectionBatch, collection_batch_id)

    def batch_generations(self, collection_batch_id):
        return list(self.session.execute(
            select(Generation, Shop)
            .join(Shop, Shop.shop_id == Generation.shop_id)
            .where(Generation.collection_batch_id == collection_batch_id)
            .order_by(Generation.batch_position, Generation.generation_id)
        ))

    def batch_shop_ids(self, collection_batch_id):
        return tuple(self.session.scalars(
            select(Generation.shop_id)
            .where(Generation.collection_batch_id == collection_batch_id)
            .order_by(Generation.shop_id)
        ))

    def visible_batch(self, actor, collection_batch_id):
        statement = select(CollectionBatch).where(
            CollectionBatch.collection_batch_id == collection_batch_id,
        )
        if not actor.is_super_account:
            statement = statement.where(
                CollectionBatch.requested_by_user_id == actor.user_id,
                CollectionBatch.requested_team_id == actor.require_team_id(),
                ~exists(
                    select(Generation.generation_id)
                    .join(Shop, Shop.shop_id == Generation.shop_id)
                    .where(
                        Generation.collection_batch_id == CollectionBatch.collection_batch_id,
                        or_(
                            Shop.deleted_at.is_not(None),
                            ~exists(
                                select(TeamShopAccess.shop_id).where(
                                    TeamShopAccess.shop_id == Shop.shop_id,
                                    TeamShopAccess.team_id == actor.require_team_id(),
                                )
                            ),
                        ),
                    )
                ),
            )
        return self.session.scalar(statement)

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

    def create_batch(self, actor, request, scopes):
        batch = CollectionBatch(
            collection_batch_id=generate_id(),
            requested_by_user_id=actor.user_id,
            requested_team_id=actor.team_id,
            submission_key=request.submission_key,
            period=request.period,
            sale_type=request.sale_type,
            content_type=request.content_type,
        )
        self.session.add(batch)
        self.session.flush()
        generations = []
        for position, scope in enumerate(scopes):
            generations.append(self._create_generation(
                actor,
                request,
                scope,
                collection_batch_id=batch.collection_batch_id,
                batch_position=position,
            ))
        return batch, generations

    def _create_generation(
        self,
        actor,
        request,
        scope,
        *,
        collection_batch_id,
        batch_position,
    ):
        self.session.execute(pg_insert(Series).values(
            series_id=generate_id(), shop_id=scope.shop_id, rolling_series_hash=scope.rolling_series_hash,
            period=scope.period, sale_type=scope.sale_type, content_type=scope.content_type,
            request_contract=scope.request_contract, metric_contract=scope.metric_contract,
        ).on_conflict_do_nothing(constraint="uq_spd_series_scope"))
        series = self.session.scalar(select(Series).where(
            Series.shop_id == scope.shop_id, Series.rolling_series_hash == scope.rolling_series_hash).with_for_update())
        generation = Generation(
            generation_id=generate_id(), collection_batch_id=collection_batch_id,
            batch_position=batch_position, series_id=series.series_id, shop_id=scope.shop_id,
            sequence=series.next_sequence, requested_by_user_id=actor.user_id, requested_team_id=actor.team_id,
            submission_key=request.submission_key, period=scope.period, date_type=scope.date_type,
            start_date=scope.start_date, end_date=scope.end_date, source_scope_hash=scope.source_scope_hash,
            request_scope=scope.model_dump(mode="json"), status="pending", stage="queued",
            attempt_count=0,
        )
        series.next_sequence += 1
        self.session.add(generation)
        self.session.flush()
        return generation

    def lock_execution_decision(self, *, wait=False):
        key = func.hashtext("shop_product_data_collection_claim")
        if wait:
            self.session.execute(select(func.pg_advisory_xact_lock(key)))
            return True
        return bool(self.session.scalar(select(func.pg_try_advisory_xact_lock(key))))

    def claim_next(self, *, lease_seconds, max_running):
        if type(max_running) is not int or max_running < 1:
            raise ValueError("Product Data execution capacity must be positive")
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("Product Data lease must be positive")
        if not self.lock_execution_decision():
            return None
        now = self.now()
        live_running = and_(
            Generation.status == "running",
            Generation.lease_until > now,
        )
        running = self.session.scalar(
            select(func.count()).select_from(Generation).where(live_running)
        ) or 0
        if running >= max_running:
            return None
        other = aliased(Generation, name="other_product_data_run")
        busy_shop = exists(select(other.generation_id).where(
            other.generation_id != Generation.generation_id,
            other.shop_id == Generation.shop_id,
            other.status == "running",
            other.lease_until > now,
        )).correlate(Generation)
        candidate = self.session.scalar(
            select(Generation)
            .where(
                or_(
                    Generation.status == "pending",
                    and_(Generation.status == "running", Generation.lease_until <= now),
                ),
                ~busy_shop,
            )
            .order_by(
                case((Generation.status == "running", 0), else_=1),
                Generation.created_at,
                Generation.generation_id,
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if candidate is None:
            return None
        lease_id = generate_id()
        candidate.status = "running"
        candidate.stage = "session_preparation"
        candidate.failure_code = None
        candidate.attempt_count += 1
        candidate.lease_id = lease_id
        candidate.lease_until = now + timedelta(seconds=lease_seconds)
        candidate.last_heartbeat_at = now
        candidate.started_at = candidate.started_at or now
        candidate.finished_at = None
        candidate.published_at = None
        candidate.pages_complete = False
        candidate.received_pages = 0
        candidate.expected_total = None
        candidate.received_total = None
        candidate.raw_complete_rows = None
        candidate.unit_complete_rows = None
        self.session.flush()
        return ProductDataCollectionClaim(candidate.generation_id, lease_id)

    def live_generation(self, generation_id, lease_id, *, lock=False):
        statement = select(Generation).where(
            Generation.generation_id == generation_id, Generation.lease_id == lease_id,
            Generation.status == "running", Generation.lease_until > func.clock_timestamp())
        generation = self.session.scalar(statement.with_for_update() if lock else statement)
        if lock and generation is not None and generation.lease_until <= self.now():
            return None
        return generation

    def heartbeat(self, generation_id, lease_id, *, stage, lease_seconds):
        generation = self.live_generation(generation_id, lease_id, lock=True)
        if generation is None:
            return None
        now = self.now()
        if generation.lease_until <= now:
            return None
        generation.stage = stage
        generation.last_heartbeat_at = now
        generation.lease_until = now + timedelta(seconds=lease_seconds)
        return generation

    def mark_failed(self, generation_id, lease_id, code, stage, *, expected_total=None):
        values = dict(status="failed", stage=stage, failure_code=code, lease_id=None, lease_until=None,
                      finished_at=func.clock_timestamp(), pages_complete=False)
        if expected_total is not None:
            # Keep an already observed total stable; fill only missing diagnostic
            # coverage, in the same live-lease CAS as the terminal failure.
            values["expected_total"] = func.coalesce(Generation.expected_total, expected_total)
        result = self.session.execute(update(Generation).where(
            Generation.generation_id == generation_id, Generation.lease_id == lease_id,
            Generation.status == "running", Generation.lease_until > func.clock_timestamp(),
        ).values(**values))
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
                                        Snapshot.raw_units[interval.metric].astext == str(METRIC_BY_CODE[interval.metric].observed_unit))
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
