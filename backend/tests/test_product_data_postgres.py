import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import delete, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.product_data.models import (
    ShopProductDataCollectionBatch,
    ShopProductDataGeneration,
    ShopProductDataMetricSnapshot,
    ShopProductDataProduct,
    ShopProductDataSeries,
)
from app.modules.product_data.source import freeze_native_slice
from app.modules.access.models import Team  # Register the FK target in isolated test runs.
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.douyin.product_data import PRODUCT_METRICS
from tests.product_data_pg_support import FEATURE_DATABASE, guarded_feature_engine


pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    # This test never substitutes SQLite or another Feature database.
    result, facts = guarded_feature_engine()
    assert facts["database"] == FEATURE_DATABASE
    try:
        yield result
    finally:
        result.dispose()


@pytest.fixture
def graph(engine):
    session = Session(engine)
    try:
        user = User(display_name="stage-2a1-spd-constraints", enabled=True, is_super_account=True)
        shops = [Shop(display_name="stage-2a1-spd-" + str(uuid4()), platform=ShopPlatform.DOUYIN,
                      platform_shop_id=str(900000000 + index), enabled=True) for index in range(2)]
        session.add_all([user, *shops])
        session.flush()
        scopes = [freeze_native_slice(shop.shop_id, "1d", datetime(2026, 1, 2, tzinfo=UTC)) for shop in shops]
        series = []
        generations = []
        products = []
        for index, scope in enumerate(scopes):
            batch = ShopProductDataCollectionBatch(
                requested_by_user_id=user.user_id,
                requested_team_id=None,
                submission_key=uuid4(),
                period=scope.period,
                sale_type=scope.sale_type,
                content_type=scope.content_type,
            )
            series_row = ShopProductDataSeries(shop_id=scope.shop_id, rolling_series_hash=scope.rolling_series_hash,
                period=scope.period, sale_type="1", content_type="1", request_contract=scope.request_contract,
                metric_contract=scope.metric_contract, next_sequence=2, published_sequence=0)
            product = ShopProductDataProduct(shop_id=scope.shop_id, platform="douyin", platform_product_id=str(9000000000000000001 + index))
            session.add_all([batch, series_row, product]); session.flush()
            generation = ShopProductDataGeneration(
                collection_batch_id=batch.collection_batch_id, batch_position=0,
                series_id=series_row.series_id, shop_id=scope.shop_id, sequence=1,
                requested_by_user_id=user.user_id, requested_team_id=None, submission_key=uuid4(),
                period=scope.period, date_type=scope.date_type, start_date=scope.start_date, end_date=scope.end_date,
                source_scope_hash=scope.source_scope_hash, request_scope=scope.model_dump(mode="json"),
                status="running", stage="session_preparation", attempt_count=1,
                lease_id=uuid4(), lease_until=datetime.now(UTC)+timedelta(minutes=5),
                last_heartbeat_at=datetime.now(UTC), started_at=datetime.now(UTC))
            session.add(generation); session.flush()
            series.append(series_row); generations.append(generation); products.append(product)
        yield session, user, shops, series, generations, products
    finally:
        session.rollback()
        session.close()


def snapshot(generation, product):
    values = {metric.code: Decimal(0) for metric in PRODUCT_METRICS}
    return ShopProductDataMetricSnapshot(generation_id=generation.generation_id, shop_product_id=product.shop_product_id,
        shop_id=generation.shop_id, retrieved_at=datetime.now(UTC),
        raw_units={metric.code: metric.observed_unit for metric in PRODUCT_METRICS},
        metric_states={metric.code: "available" for metric in PRODUCT_METRICS}, **values)


def test_real_numeric_precision_and_zero_values_round_trip(graph):
    session, _, _, _, generations, products = graph
    row = snapshot(generations[0], products[0])
    row.pay_amt = Decimal("12345678901234567890.1234567890123456789")
    row.pay_refund_ratio = Decimal("0.12345678901234567890123456789")
    session.add(row); session.flush(); session.expire(row)
    assert row.pay_amt == Decimal("12345678901234567890.1234567890123456789")
    assert row.pay_refund_ratio == Decimal("0.12345678901234567890123456789")
    assert row.pay_cnt == 0 and row.metric_states["pay_cnt"] == "available"


@pytest.mark.parametrize("wrong_shop", [0, 1])
def test_same_shop_composite_foreign_keys_reject_cross_shop_facts(graph, wrong_shop):
    session, _, shops, _, generations, products = graph
    row = snapshot(generations[0], products[1])
    row.shop_id = shops[wrong_shop].shop_id
    with pytest.raises(IntegrityError) as error:
        with session.begin_nested(): session.add(row); session.flush()
    assert error.value.orig.sqlstate == "23503"


def test_current_pointer_cannot_reference_another_series(graph):
    session, _, _, series, generations, _ = graph
    with pytest.raises(IntegrityError) as error:
        with session.begin_nested():
            series[0].current_generation_id = generations[1].generation_id
            series[0].published_sequence = 1
            session.flush()
    assert error.value.orig.sqlstate == "23503"


def test_no_team_super_actor_idempotency_key_is_actually_unique(graph):
    session, _, _, _, generations, _ = graph
    first = session.get(ShopProductDataCollectionBatch, generations[0].collection_batch_id)
    second = session.get(ShopProductDataCollectionBatch, generations[1].collection_batch_id)
    with pytest.raises(IntegrityError) as error:
        with session.begin_nested():
            second.submission_key = first.submission_key
            session.flush()
    assert error.value.orig.diag.constraint_name == "uq_spd_batch_actor_key"


@pytest.mark.parametrize("mutation", ["null_available_unit", "null_state", "extra_key", "nan", "fractional_count"])
def test_json_null_cannot_bypass_checks_and_bad_values_are_rejected(graph, mutation):
    session, _, _, _, generations, products = graph
    row = snapshot(generations[0], products[0])
    if mutation == "null_available_unit": row.raw_units["pay_cnt"] = None
    if mutation == "null_state": row.metric_states["pay_cnt"] = None
    if mutation == "extra_key": row.raw_units["not_a_metric"] = 5
    if mutation == "nan": row.pay_amt = Decimal("NaN")
    if mutation == "fractional_count": row.pay_cnt = Decimal("1.5")
    with pytest.raises(IntegrityError) as error:
        with session.begin_nested(): session.add(row); session.flush()
    assert error.value.orig.sqlstate == "23514"


def test_unknown_units_and_missing_values_are_valid_without_zero_fill(graph):
    session, _, _, _, generations, products = graph
    row = snapshot(generations[0], products[0])
    row.pay_refund_ratio = None
    row.raw_units["pay_refund_ratio"] = 6
    row.metric_states["pay_refund_ratio"] = "missing"
    row.pay_amt = Decimal(-1)
    row.metric_states["pay_amt"] = "invalid"
    session.add(row); session.flush(); session.expire(row)
    assert row.pay_refund_ratio is None and row.raw_units["pay_refund_ratio"] == 6
    assert row.pay_amt == -1 and row.metric_states["pay_amt"] == "invalid"


def test_empty_0048_downgrade_and_upgrade_keep_existing_marker(engine):
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    marker = uuid4()
    with Session(engine) as session:
        assert all(session.scalar(text("SELECT count(*) FROM " + table)) == 0 for table in (
            "shop_product_data_collection_batches", "shop_product_data_metric_snapshots",
            "shop_product_data_generations", "shop_product_data_series", "shop_product_data_products"))
        session.add(User(user_id=marker, display_name="stage-2a1-spd-migration-marker", enabled=True))
        session.commit()
    try:
        checked, _ = guarded_feature_engine(); checked.dispose()
        command.downgrade(cfg, "20261017_0047")
        assert "shop_product_data_collection_batches" not in inspect(engine).get_table_names()
        assert "shop_product_data_generations" in inspect(engine).get_table_names()
        assert "collection_batch_id" not in {
            column["name"] for column in inspect(engine).get_columns("shop_product_data_generations")
        }
        with Session(engine) as session:
            assert session.get(User, marker) is not None
        checked, _ = guarded_feature_engine(); checked.dispose()
        command.upgrade(cfg, "20261019_0048")
        with Session(engine) as session:
            assert list(session.scalars(text("SELECT version_num FROM alembic_version"))) == ["20261019_0048"]
            assert session.get(User, marker) is not None
    finally:
        with Session(engine) as session:
            head = session.scalar(text("SELECT version_num FROM alembic_version"))
        if head != "20261019_0048":
            command.upgrade(cfg, "20261019_0048")
        with Session(engine) as session:
            session.execute(delete(User).where(User.user_id == marker)); session.commit()


def test_0047_fact_backfill_round_trip_is_lossless(engine):
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    user_id, shop_id, series_id = uuid4(), uuid4(), uuid4()
    generation_id, product_id, submission_key = uuid4(), uuid4(), uuid4()
    at = datetime(2026, 10, 18, 3, 4, 5, tzinfo=UTC)
    scope = freeze_native_slice(shop_id, "1d", at)
    units = {metric.code: metric.observed_unit for metric in PRODUCT_METRICS}
    states = {metric.code: "available" for metric in PRODUCT_METRICS}
    try:
        command.downgrade(cfg, "20261017_0047")
        with Session(engine) as session:
            session.add(User(user_id=user_id, display_name="stage-2a1-spd-backfill", enabled=True))
            session.add(Shop(
                shop_id=shop_id,
                display_name="stage-2a1-spd-backfill-shop",
                platform=ShopPlatform.DOUYIN,
                platform_shop_id="990000001",
                enabled=True,
            ))
            session.flush()
            session.execute(text("""
                INSERT INTO shop_product_data_series (
                    series_id, shop_id, rolling_series_hash, period, sale_type, content_type,
                    request_contract, metric_contract, next_sequence, published_sequence,
                    current_generation_id, previous_generation_id, created_at, updated_at
                ) VALUES (
                    :series_id, :shop_id, :rolling_hash, '1d', '1', '1',
                    :request_contract, :metric_contract, 2, 0, NULL, NULL, :at, :at
                )
            """), {
                "series_id": series_id,
                "shop_id": shop_id,
                "rolling_hash": scope.rolling_series_hash,
                "request_contract": scope.request_contract,
                "metric_contract": scope.metric_contract,
                "at": at,
            })
            session.execute(text("""
                INSERT INTO shop_product_data_generations (
                    generation_id, series_id, shop_id, sequence, requested_by_user_id,
                    requested_team_id, submission_key, period, date_type, start_date, end_date,
                    source_scope_hash, request_scope, status, received_pages, expected_total,
                    received_total, raw_complete_rows, unit_complete_rows, pages_complete, stage,
                    failure_code, lease_id, lease_until, started_at, finished_at, published_at,
                    created_at, updated_at
                ) VALUES (
                    :generation_id, :series_id, :shop_id, 1, :user_id, NULL, :submission_key,
                    '1d', '20', :start_date, :end_date, :source_hash,
                    CAST(:request_scope AS jsonb), 'succeeded', 1, 1, 1, 1, 1, true,
                    'complete', NULL, NULL, NULL, :at, :at, :at, :at, :at
                )
            """), {
                "generation_id": generation_id,
                "series_id": series_id,
                "shop_id": shop_id,
                "user_id": user_id,
                "submission_key": submission_key,
                "start_date": scope.start_date,
                "end_date": scope.end_date,
                "source_hash": scope.source_scope_hash,
                "request_scope": json.dumps(scope.model_dump(mode="json")),
                "at": at,
            })
            session.execute(text("""
                UPDATE shop_product_data_series
                SET current_generation_id = :generation_id, published_sequence = 1
                WHERE series_id = :series_id
            """), {"generation_id": generation_id, "series_id": series_id})
            session.add(ShopProductDataProduct(
                shop_product_id=product_id,
                shop_id=shop_id,
                platform="douyin",
                platform_product_id="990000000000000001",
            ))
            session.flush()
            session.add(ShopProductDataMetricSnapshot(
                generation_id=generation_id,
                shop_product_id=product_id,
                shop_id=shop_id,
                observed_title="backfilled product",
                observed_image_url=None,
                retrieved_at=at,
                raw_units=units,
                metric_states=states,
                **{metric.code: Decimal(0) for metric in PRODUCT_METRICS},
            ))
            session.commit()

        command.upgrade(cfg, "20261019_0048")
        with Session(engine) as session:
            generation = session.get(ShopProductDataGeneration, generation_id)
            batch = session.get(ShopProductDataCollectionBatch, generation_id)
            series = session.get(ShopProductDataSeries, series_id)
            assert generation.collection_batch_id == generation_id
            assert generation.batch_position == 0 and generation.attempt_count == 1
            assert generation.last_heartbeat_at == at
            assert batch.submission_key == submission_key and batch.created_at == at
            assert series.current_generation_id == generation_id
            assert session.get(
                ShopProductDataMetricSnapshot,
                (generation_id, product_id),
            ).pay_cnt == 0

        command.downgrade(cfg, "20261017_0047")
        with Session(engine) as session:
            assert session.scalar(text(
                "SELECT current_generation_id FROM shop_product_data_series WHERE series_id=:id",
            ), {"id": series_id}) == generation_id
            assert session.scalar(text(
                "SELECT count(*) FROM shop_product_data_metric_snapshots WHERE generation_id=:id",
            ), {"id": generation_id}) == 1
        command.upgrade(cfg, "20261019_0048")
    finally:
        with Session(engine) as session:
            head = session.scalar(text("SELECT version_num FROM alembic_version"))
        if head != "20261019_0048":
            command.upgrade(cfg, "20261019_0048")
        with Session(engine) as session:
            session.execute(update(ShopProductDataSeries).where(
                ShopProductDataSeries.series_id == series_id,
            ).values(current_generation_id=None, previous_generation_id=None, published_sequence=0))
            session.execute(delete(ShopProductDataMetricSnapshot).where(
                ShopProductDataMetricSnapshot.generation_id == generation_id,
            ))
            session.execute(delete(ShopProductDataGeneration).where(
                ShopProductDataGeneration.generation_id == generation_id,
            ))
            session.execute(delete(ShopProductDataCollectionBatch).where(
                ShopProductDataCollectionBatch.collection_batch_id == generation_id,
            ))
            session.execute(delete(ShopProductDataProduct).where(
                ShopProductDataProduct.shop_product_id == product_id,
            ))
            session.execute(delete(ShopProductDataSeries).where(
                ShopProductDataSeries.series_id == series_id,
            ))
            session.execute(delete(Shop).where(Shop.shop_id == shop_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()
