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
from app.modules.product_data.exceptions import ProductDataCollectionBusyError
from app.modules.product_data.models import (
    ShopProductDataGeneration as Generation, ShopProductDataMetricSnapshot as Snapshot,
    ShopProductDataProduct as Product, ShopProductDataSeries as Series,
)
from app.modules.product_data.schemas import ProductDataCollectionRequest
from app.modules.product_data.service import ProductDataService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from tests.product_data_pg_support import guarded_feature_engine


pytestmark = pytest.mark.integration


@pytest.fixture
def committed_graph():
    engine, facts = guarded_feature_engine()
    assert facts["database"] == "control_center_feat_shop_product_data"
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
            assert session.scalar(text("SELECT current_database()")) == "control_center_feat_shop_product_data"
            session.execute(update(Series).where(Series.shop_id.in_(shop_ids)).values(
                current_generation_id=None, previous_generation_id=None, published_sequence=0))
            session.execute(delete(Snapshot).where(Snapshot.shop_id.in_(shop_ids)))
            session.execute(delete(Generation).where(Generation.shop_id.in_(shop_ids)))
            session.execute(delete(Product).where(Product.shop_id.in_(shop_ids)))
            session.execute(delete(Series).where(Series.shop_id.in_(shop_ids)))
            session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()
        engine.dispose()


def race(graph, commands, capacity=5):
    barrier = Barrier(2)
    settings = Settings(product_data_collection_execution_enabled=True, product_data_collection_max_running=capacity)
    def run(command):
        with Session(graph.engine, expire_on_commit=False) as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            session.execute(text("SET LOCAL statement_timeout = '10s'"))
            actor = ActorContextService(session).resolve(user_id=graph.user_id, requested_team_id=None)
            barrier.wait(timeout=10)
            try:
                receipt, lease = ProductDataService(session, settings=settings).request_collection(actor, command)
                return receipt.generation_id, lease
            except ProductDataCollectionBusyError as error:
                assert error.details is None
                return "busy", None
    with ThreadPoolExecutor(max_workers=2) as pool:
        return list(pool.map(run, commands))


def command(graph, shop=0, key=None):
    return ProductDataCollectionRequest(shop_id=graph.shop_ids[shop], period="1d", submission_key=key or uuid4())


def test_same_actor_key_concurrent_submission_returns_one_generation_and_one_execution_lease(committed_graph):
    graph = committed_graph
    request = command(graph)
    result = race(graph, [request, request])
    assert result[0][0] == result[1][0] and result[0][0] != "busy"
    assert sum(lease is not None for _, lease in result) == 1
    with Session(graph.engine) as session:
        assert session.scalar(select(func.count()).select_from(Generation).where(Generation.shop_id.in_(graph.shop_ids))) == 1


def test_different_keys_same_slice_concurrent_submission_is_busy_not_duplicate(committed_graph):
    graph = committed_graph
    result = race(graph, [command(graph), command(graph)])
    assert sum(value == "busy" for value, _ in result) == 1


def test_capacity_check_is_atomic_across_different_shops(committed_graph):
    graph = committed_graph
    result = race(graph, [command(graph), command(graph, shop=1)], capacity=1)
    assert sum(value == "busy" for value, _ in result) == 1
