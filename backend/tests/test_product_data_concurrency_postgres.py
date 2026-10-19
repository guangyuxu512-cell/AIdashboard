"""Two independent PostgreSQL connections, synthetic intents only."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.service import ActorContextService
from app.modules.product_data.models import (
    ShopProductDataCollectionBatch as CollectionBatch,
    ShopProductDataGeneration as Generation, ShopProductDataMetricSnapshot as Snapshot,
    ShopProductDataProduct as Product, ShopProductDataSeries as Series,
)
from app.modules.product_data.schemas import (
    ProductDataCollectionBatchRequest,
    ProductDataCollectionRequest,
)
from app.modules.product_data.service import ProductDataService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from tests.product_data_pg_support import FEATURE_DATABASE, guarded_feature_engine


pytestmark = pytest.mark.integration


@pytest.fixture
def committed_graph():
    engine, facts = guarded_feature_engine()
    assert facts["database"] == FEATURE_DATABASE
    user_id, shop_ids = uuid4(), [uuid4(), uuid4()]
    try:
        with Session(engine) as session:
            session.add(User(user_id=user_id, display_name="stage-2a1-spd-race", enabled=True, is_super_account=True))
            session.add_all([Shop(shop_id=value, display_name="stage-2a1-spd-race-" + str(index),
                platform=ShopPlatform.DOUYIN, platform_shop_id=str(980000000 + index), enabled=True)
                for index, value in enumerate(shop_ids)])
            session.commit()
        yield SimpleNamespace(engine=engine, user_id=user_id, shop_ids=shop_ids)
    finally:
        # Only exact UUIDs created by this fixture, in the independently verified DB.
        with Session(engine) as session:
            assert session.scalar(text("SELECT current_database()")) == FEATURE_DATABASE
            session.execute(update(Series).where(Series.shop_id.in_(shop_ids)).values(
                current_generation_id=None, previous_generation_id=None, published_sequence=0))
            session.execute(delete(Snapshot).where(Snapshot.shop_id.in_(shop_ids)))
            session.execute(delete(Generation).where(Generation.shop_id.in_(shop_ids)))
            session.execute(delete(CollectionBatch).where(
                CollectionBatch.requested_by_user_id == user_id,
            ))
            session.execute(delete(Product).where(Product.shop_id.in_(shop_ids)))
            session.execute(delete(Series).where(Series.shop_id.in_(shop_ids)))
            session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()
        engine.dispose()


def race_submit(graph, commands, capacity=5):
    barrier = Barrier(2)
    settings = Settings(product_data_collection_execution_enabled=True, product_data_collection_max_running=capacity)
    def run(command):
        with Session(graph.engine, expire_on_commit=False) as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            session.execute(text("SET LOCAL statement_timeout = '10s'"))
            actor = ActorContextService(session).resolve(user_id=graph.user_id, requested_team_id=None)
            barrier.wait(timeout=10)
            receipt, lease = ProductDataService(
                session,
                settings=settings,
            ).request_collection(actor, command)
            return receipt.generation_id, lease
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, commands))


def command(graph, shop=0, key=None):
    return ProductDataCollectionRequest(shop_id=graph.shop_ids[shop], period="1d", submission_key=key or uuid4())


def race_claim(graph, *, capacity=5):
    barrier = Barrier(2)
    settings = Settings(
        product_data_collection_execution_enabled=True,
        product_data_collection_max_running=capacity,
    )

    def run(_index):
        with Session(graph.engine, expire_on_commit=False) as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            session.execute(text("SET LOCAL statement_timeout = '10s'"))
            barrier.wait(timeout=10)
            return ProductDataService(session, settings=settings).claim_next()

    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, range(2)))


def enqueue_committed(graph, *commands, capacity=5):
    settings = Settings(
        product_data_collection_execution_enabled=True,
        product_data_collection_max_running=capacity,
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        actor = ActorContextService(session).resolve(
            user_id=graph.user_id,
            requested_team_id=None,
        )
        return [
            ProductDataService(session, settings=settings)
            .request_collection(actor, item)[0]
            for item in commands
        ]


def test_same_actor_key_concurrent_submission_returns_one_pending_generation(committed_graph):
    graph = committed_graph
    request = command(graph)
    result = race_submit(graph, [request, request])
    assert result[0][0] == result[1][0]
    assert all(lease is None for _, lease in result)
    with Session(graph.engine) as session:
        assert session.scalar(select(func.count()).select_from(Generation).where(Generation.shop_id.in_(graph.shop_ids))) == 1
        assert session.scalar(select(func.count()).select_from(CollectionBatch).where(
            CollectionBatch.requested_by_user_id == graph.user_id,
        )) == 1


def test_different_keys_same_slice_concurrent_submission_queues_both(committed_graph):
    graph = committed_graph
    result = race_submit(graph, [command(graph), command(graph)])
    assert len({value for value, _ in result}) == 2
    assert all(lease is None for _, lease in result)
    with Session(graph.engine) as session:
        statuses = list(session.scalars(select(Generation.status).where(
            Generation.shop_id == graph.shop_ids[0],
        )))
        assert statuses == ["pending", "pending"]


def test_capacity_check_is_atomic_across_different_shops(committed_graph):
    graph = committed_graph
    enqueue_committed(graph, command(graph), command(graph, shop=1), capacity=1)
    result = race_claim(graph, capacity=1)
    assert sum(value is not None for value in result) == 1
    with Session(graph.engine) as session:
        assert session.scalar(select(func.count()).select_from(Generation).where(
            Generation.status == "running",
        )) == 1
        assert session.scalar(select(func.count()).select_from(Generation).where(
            Generation.status == "pending",
        )) == 1


def test_same_shop_is_serial_across_independent_claimers(committed_graph):
    graph = committed_graph
    enqueue_committed(graph, command(graph), command(graph))
    result = race_claim(graph, capacity=5)
    assert sum(value is not None for value in result) == 1
    with Session(graph.engine) as session:
        assert session.scalar(select(func.count()).select_from(Generation).where(
            Generation.shop_id == graph.shop_ids[0],
            Generation.status == "running",
        )) == 1
        assert session.scalar(select(func.count()).select_from(Generation).where(
            Generation.shop_id == graph.shop_ids[0],
            Generation.status == "pending",
        )) == 1


def test_busy_shop_does_not_block_another_shop(committed_graph):
    graph = committed_graph
    receipts = enqueue_committed(
        graph,
        command(graph),
        command(graph),
        command(graph, shop=1),
    )
    settings = Settings(
        product_data_collection_execution_enabled=True,
        product_data_collection_max_running=5,
    )
    with Session(graph.engine, expire_on_commit=False) as session:
        service = ProductDataService(session, settings=settings)
        first = service.claim_next()
        second = service.claim_next()
    assert first is not None and second is not None
    claimed = {first.generation_id, second.generation_id}
    assert receipts[0].generation_id in claimed
    assert receipts[1].generation_id not in claimed
    assert receipts[2].generation_id in claimed


def test_hundred_shop_batch_stays_durable_and_releases_five_slots(
    committed_graph,
):
    graph = committed_graph
    extra_shop_ids = [uuid4() for _ in range(98)]
    all_shop_ids = tuple(graph.shop_ids + extra_shop_ids)
    batch_id = None
    try:
        with Session(graph.engine) as session:
            session.add_all([
                Shop(
                    shop_id=shop_id,
                    display_name=f"stage-2a1-spd-batch-{position:03d}",
                    platform=ShopPlatform.DOUYIN,
                    platform_shop_id=str(981000000 + position),
                    enabled=True,
                )
                for position, shop_id in enumerate(extra_shop_ids, start=2)
            ])
            session.commit()

        settings = Settings(
            product_data_collection_execution_enabled=True,
            product_data_collection_max_running=5,
        )
        with Session(graph.engine, expire_on_commit=False) as session:
            actor = ActorContextService(session).resolve(
                user_id=graph.user_id,
                requested_team_id=None,
            )
            service = ProductDataService(session, settings=settings)
            receipt = service.request_collection_batch(
                actor,
                ProductDataCollectionBatchRequest(
                    shop_ids=all_shop_ids,
                    period="1d",
                    submission_key=uuid4(),
                ),
            )
            batch_id = receipt.collection_batch_id
            assert receipt.total_count == receipt.pending_count == 100

            active = [service.claim_next() for _ in range(5)]
            assert all(active)
            assert service.claim_next() is None
            seen = set()
            while active:
                claim = active.pop(0)
                assert claim is not None
                assert claim.generation_id not in seen
                seen.add(claim.generation_id)
                assert service.fail(
                    claim.generation_id,
                    claim.lease_id,
                    "PLATFORM_TIMEOUT",
                    "platform_response",
                )
                replacement = service.claim_next()
                if replacement is not None:
                    active.append(replacement)
                assert len(active) <= 5

            final = service.read_batch(actor, batch_id)
            assert len(seen) == 100
            assert final.status == "failed"
            assert final.failed_count == final.total_count == 100
            assert final.pending_count == final.running_count == 0
    finally:
        with Session(graph.engine) as session:
            if batch_id is not None:
                session.execute(delete(Generation).where(
                    Generation.collection_batch_id == batch_id,
                ))
                session.execute(delete(CollectionBatch).where(
                    CollectionBatch.collection_batch_id == batch_id,
                ))
            session.execute(delete(Series).where(
                Series.shop_id.in_(all_shop_ids),
            ))
            session.execute(delete(Shop).where(
                Shop.shop_id.in_(extra_shop_ids),
            ))
            session.commit()
