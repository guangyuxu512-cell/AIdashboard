from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import delete, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.product_data.models import (
    ShopProductDataGeneration, ShopProductDataMetricSnapshot, ShopProductDataProduct, ShopProductDataSeries,
)
from app.modules.product_data.source import freeze_native_slice
from app.modules.access.models import Team  # Register the FK target in isolated test runs.
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.douyin.product_data import PRODUCT_METRICS
from tests.product_data_pg_support import guarded_feature_engine


pytestmark = pytest.mark.integration


@pytest.fixture
def engine():
    # This test never substitutes SQLite or another Feature database.
    result, facts = guarded_feature_engine()
    assert facts["database"] == "control_center_feat_shop_product_data"
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
            series_row = ShopProductDataSeries(shop_id=scope.shop_id, rolling_series_hash=scope.rolling_series_hash,
                period=scope.period, sale_type="1", content_type="1", request_contract=scope.request_contract,
                metric_contract=scope.metric_contract, next_sequence=2, published_sequence=0)
            product = ShopProductDataProduct(shop_id=scope.shop_id, platform="douyin", platform_product_id=str(9000000000000000001 + index))
            session.add_all([series_row, product]); session.flush()
            generation = ShopProductDataGeneration(series_id=series_row.series_id, shop_id=scope.shop_id, sequence=1,
                requested_by_user_id=user.user_id, requested_team_id=None, submission_key=uuid4(),
                period=scope.period, date_type=scope.date_type, start_date=scope.start_date, end_date=scope.end_date,
                source_scope_hash=scope.source_scope_hash, request_scope=scope.model_dump(mode="json"),
                status="running", stage="session_preparation", lease_id=uuid4(),
                lease_until=datetime.now(UTC)+timedelta(minutes=5), started_at=datetime.now(UTC))
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
    with pytest.raises(IntegrityError) as error:
        with session.begin_nested():
            generations[1].submission_key = generations[0].submission_key
            session.flush()
    assert error.value.orig.diag.constraint_name == "uq_spd_generation_actor_key"


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


def test_new_empty_tables_downgrade_and_upgrade_keep_existing_marker(engine):
    cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    marker = uuid4()
    with Session(engine) as session:
        assert all(session.scalar(text("SELECT count(*) FROM " + table)) == 0 for table in (
            "shop_product_data_metric_snapshots", "shop_product_data_generations", "shop_product_data_series", "shop_product_data_products"))
        session.add(User(user_id=marker, display_name="stage-2a1-spd-migration-marker", enabled=True))
        session.commit()
    try:
        checked, _ = guarded_feature_engine(); checked.dispose()
        command.downgrade(cfg, "20261015_0046")
        assert not any(name.startswith("shop_product_data_") for name in inspect(engine).get_table_names())
        with Session(engine) as session:
            assert session.get(User, marker) is not None
        checked, _ = guarded_feature_engine(); checked.dispose()
        command.upgrade(cfg, "20261017_0047")
        with Session(engine) as session:
            assert list(session.scalars(text("SELECT version_num FROM alembic_version"))) == ["20261017_0047"]
            assert session.get(User, marker) is not None
    finally:
        with Session(engine) as session:
            session.execute(delete(User).where(User.user_id == marker)); session.commit()
