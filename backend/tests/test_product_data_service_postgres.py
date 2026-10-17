"""Synthetic facts on the exact registered Feature PostgreSQL, never SQLite.

Service commits use savepoints inside a rollback-only fixture transaction.
No platform, Signer, browser, production or shared Feature database is used.
"""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.models import Team, TeamMembership, TeamModuleAccess, TeamShopAccess
from app.modules.access.service import ActorContextService
from app.modules.product_data.collection import CompleteProductDataSnapshot
from app.modules.product_data.exceptions import (
    ProductDataCollectionBusyError, ProductDataCollectionUnavailableError, ProductDataGenerationNotFoundError,
    ProductDataIdempotencyConflictError, ProductDataPublicationRejectedError,
)
from app.modules.product_data.models import (
    ShopProductDataGeneration as Generation, ShopProductDataProduct as Product,
    ShopProductDataSeries as Series, ShopProductDataMetricSnapshot as Snapshot,
)
from app.modules.product_data.schemas import ProductDataCollectionRequest, ProductDataQuery
from app.modules.product_data.service import ProductDataService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.douyin.product_data import (
    PRODUCT_METRICS, CompassProductDataPage, CompassProductDataRow, ProductMetricObservation, ProductTextObservation,
)
from tests.product_data_pg_support import guarded_feature_engine


pytestmark = pytest.mark.integration


class SyntheticGraph(SimpleNamespace):
    def __repr__(self):
        return "SyntheticProductDataGraph(configuration_not_printed)"


@pytest.fixture
def graph():
    engine, facts = guarded_feature_engine()
    assert facts["database"] == "control_center_feat_shop_product_data"
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    try:
        users = [User(display_name="stage-2a1-spd-" + str(uuid4()), enabled=True,
                      is_super_account=index == 0) for index in range(3)]
        teams = [Team(name="stage-2a1-spd-" + str(uuid4()), enabled=True) for _ in range(2)]
        shops = [Shop(display_name="stage-2a1-spd-shop-" + str(index), enabled=True, platform=ShopPlatform.DOUYIN,
                      platform_shop_id=str(900000000 + index)) for index in range(2)]
        session.add_all([*users, *teams, *shops]); session.flush()
        for index in range(2):
            session.add_all([
                TeamMembership(team_id=teams[index].team_id, user_id=users[index + 1].user_id, enabled=True),
                TeamModuleAccess(team_id=teams[index].team_id, module_code="shop"),
                TeamShopAccess(team_id=teams[index].team_id, shop_id=shops[index].shop_id),
            ])
        session.commit()
        resolver = ActorContextService(session)
        actors = [resolver.resolve(user_id=users[0].user_id, requested_team_id=None)] + [
            resolver.resolve(user_id=users[index + 1].user_id, requested_team_id=teams[index].team_id) for index in range(2)
        ]
        settings = Settings(product_data_collection_execution_enabled=True, product_data_collection_max_running=5)
        yield SyntheticGraph(session=session, users=users, teams=teams, shops=shops, actors=actors,
                              settings=settings, service=ProductDataService(session, settings=settings))
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def submit(graph, actor=0, shop=0, key=None, period="1d"):
    return graph.service.request_collection(graph.actors[actor], ProductDataCollectionRequest(
        shop_id=graph.shops[shop].shop_id, period=period, submission_key=key or uuid4()))


def complete(receipt, shop, total=25, offset=0):
    rows = tuple(CompassProductDataRow(str(9000000000000000000 + i), shop.platform_shop_id,
        ProductTextObservation("available", f"Synthetic product {i:03d}"), ProductTextObservation("missing"),
        tuple(ProductMetricObservation(metric, "available",
            Decimal(i + offset) if metric.kind == "count" else Decimal("0.103846080868261780123456789"),
            metric.observed_unit) for metric in PRODUCT_METRICS)) for i in range(total))
    return CompleteProductDataSnapshot(receipt.scope, rows, total, (total + 9) // 10)


def query(receipt, **changes):
    return ProductDataQuery(period=receipt.scope.period, start_date=receipt.scope.start_date,
                            end_date=receipt.scope.end_date, **changes)


def publish(graph, actor=0, shop=0, total=25, offset=0):
    receipt, lease = submit(graph, actor, shop)
    graph.service.publish(receipt.generation_id, lease, complete(receipt, graph.shops[shop], total, offset))
    return receipt


def test_success_precision_zero_global_pagination_and_no_unit_guess(graph):
    receipt = publish(graph)
    response = graph.service.list(graph.actors[1], query(receipt))
    assert response.total == 25 and response.page_size == len(response.items) == 20
    assert response.items[0].product_id == "9000000000000000000"
    assert response.items[0].metrics["pay_cnt"].raw_value == "0"
    assert response.items[0].metrics["pay_cnt"].unit_verified
    assert response.items[0].metrics["pay_refund_ratio"].raw_value == "0.103846080868261780123456789"
    assert response.items[0].metrics["pay_amt"].unit_verified
    assert response.coverage.unit_unconfirmed_codes == []
    second = graph.service.list(graph.actors[1], query(receipt, page=2))
    assert len(second.items) == 5
    assert not {row.product_id for row in response.items} & {row.product_id for row in second.items}
    saved = graph.service.read_generation(graph.actors[0], receipt.generation_id)
    assert saved.status == "succeeded" and saved.pages_complete and saved.raw_complete_rows == 25
    assert saved.unit_complete_rows == 25 and not saved.lease_expired


def test_failed_next_intent_preserves_old_success_and_stable_ids(graph):
    first = publish(graph, total=2)
    old = graph.service.list(graph.actors[1], query(first))
    failed, lease = submit(graph)
    assert graph.service.fail(failed.generation_id, lease, "PLATFORM_TIMEOUT", "platform_response")
    assert graph.service.list(graph.actors[1], query(first)).items == old.items
    newer = publish(graph, total=2, offset=10)
    current = graph.service.list(graph.actors[1], query(newer))
    assert [row.shop_product_id for row in current.items] == [row.shop_product_id for row in old.items]
    assert current.items[0].metrics["pay_cnt"].raw_value == "10"
    series = graph.session.get(Series, graph.session.get(Generation, newer.generation_id).series_id)
    assert series.current_generation_id == newer.generation_id and series.previous_generation_id == first.generation_id


def test_no_team_actor_key_replays_frozen_dates_without_duplicate_or_new_lease(graph, monkeypatch):
    key = uuid4()
    first, lease = submit(graph, key=key)
    def must_not_recompute(*_):
        pytest.fail("cross-day replay must not re-freeze dates")
    monkeypatch.setattr("app.modules.product_data.service.freeze_native_slice", must_not_recompute)
    replay, replay_lease = submit(graph, key=key)
    assert replay == first and replay_lease is None and lease is not None
    assert graph.session.scalar(select(func.count()).select_from(Generation)) == 1
    with pytest.raises(ProductDataIdempotencyConflictError):
        submit(graph, key=key, period="7d")


def test_replay_changed_team_rejected_even_for_super_account(graph):
    key = uuid4()
    submit(graph, key=key)
    actor = ActorContextService(graph.session).resolve(user_id=graph.users[0].user_id, requested_team_id=graph.teams[0].team_id)
    with pytest.raises(ProductDataIdempotencyConflictError):
        graph.service.request_collection(actor, ProductDataCollectionRequest(shop_id=graph.shops[0].shop_id,
            period="1d", submission_key=key))


def test_cross_team_busy_contains_no_other_receipt_and_direct_receipt_is_hidden(graph):
    receipt, _ = submit(graph, actor=1)
    graph.session.add(TeamShopAccess(team_id=graph.teams[1].team_id, shop_id=graph.shops[0].shop_id)); graph.session.commit()
    with pytest.raises(ProductDataCollectionBusyError) as error:
        submit(graph, actor=2)
    assert not error.value.details and str(receipt.generation_id) not in str(error.value)
    with pytest.raises(ProductDataGenerationNotFoundError):
        graph.service.read_generation(graph.actors[2], receipt.generation_id)


def test_current_grant_revoked_before_publish_blocks_it_and_reads(graph):
    receipt, lease = submit(graph, actor=1)
    graph.session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == graph.teams[0].team_id,
                                                       TeamShopAccess.shop_id == graph.shops[0].shop_id))
    graph.session.commit()
    with pytest.raises(ShopNotFoundError):
        graph.service.publish(receipt.generation_id, lease, complete(receipt, graph.shops[0], 1))
    assert graph.session.scalar(select(func.count()).select_from(Snapshot)) == 0
    assert graph.service.list(graph.actors[1], query(receipt)).total == 0
    with pytest.raises(ProductDataGenerationNotFoundError):
        graph.service.read_generation(graph.actors[1], receipt.generation_id)


def test_sql_scope_filters_sort_before_pagination_coverage_not_filtered(graph):
    receipt = publish(graph, shop=0)
    publish(graph, shop=1)
    response = graph.service.list(graph.actors[0], query(receipt, ranges=[{
        "metric": "product_show_cnt", "min_value": "15", "max_value": "17"}], sort_field="product_show_cnt", sort_direction="desc"))
    assert response.total == len(response.items) == 4
    assert [row.metrics["product_show_cnt"].raw_value for row in response.items] == ["16", "16", "15", "15"]
    scoped = graph.service.list(graph.actors[1], query(receipt, product_name="024"))
    assert scoped.total == 1 and scoped.items[0].shop_id == graph.shops[0].shop_id
    assert scoped.coverage.supported_shop_count == scoped.coverage.collected_shop_count == 1
    with pytest.raises(ShopNotFoundError):
        graph.service.list(graph.actors[1], query(receipt, shop_id=graph.shops[1].shop_id))


def test_official_units_enable_amount_sort_and_ratio_filter(graph):
    receipt = publish(graph, total=1)
    assert graph.service.list(graph.actors[0], query(receipt, sort_field="pay_amt", sort_direction="desc")).total == 1
    assert graph.service.list(graph.actors[0], query(receipt, ranges=[{"metric": "pay_refund_ratio", "min_value": "0"}])).total == 1


RATIO_CODES = ("product_show_click_converse_uv_rate", "product_add_show_converse_uv_ratio",
               "product_click_pay_converse_uv_rate", "pay_refund_ratio")


@pytest.mark.parametrize("code", RATIO_CODES)
def test_ratio_sql_exact_boundaries_unknowns_sorting_and_pagination(graph, code):
    receipt, lease = submit(graph)
    snapshot = complete(receipt, graph.shops[0], 11)
    values = ["0", "0.0028999999999999999999999999999999999", "0.0029",
              "0.0029000000000000000000000000000000001", "0.0100999999999999999999999999999999999",
              "0.0101", "0.1", None, "0.005", "-1", None]
    rows = []
    for index, row in enumerate(snapshot.products):
        state = "missing" if index == 7 else "invalid" if index in (8, 9) else "null" if index == 10 else "available"
        unit = None if index == 7 else 6 if index == 8 else 4
        rows.append(replace(row, metrics=tuple(replace(metric, state=state, raw_unit=unit,
            raw_value=Decimal(values[index]) if values[index] is not None else None)
            if metric.definition.code == code else metric for metric in row.metrics)))
    graph.service.publish(receipt.generation_id, lease, replace(snapshot, products=tuple(rows)))
    selected = [{"metric": code, "min_value": "0.0029", "max_value": "0.0101"}]
    first = graph.service.list(graph.actors[1], query(receipt, ranges=selected, sort_field=code,
                                                    sort_direction="desc", page_size=2))
    second = graph.service.list(graph.actors[1], query(receipt, ranges=selected, sort_field=code,
                                                     sort_direction="desc", page_size=2, page=2))
    assert first.total == second.total == 3
    assert [row.product_id for row in first.items + second.items] == [rows[index].product_id for index in (4, 3, 2)]
    assert second.items[0].metrics[code].raw_value == "0.0029"
    assert first.items[0].metrics[code].raw_value == values[4]
    zero = graph.service.list(graph.actors[1], query(receipt, ranges=[{"metric": code, "min_value": "0", "max_value": "0.0029"}]))
    assert zero.total == 2 and zero.items[0].metrics[code].raw_value == "0"
    upper_only = graph.service.list(graph.actors[1], query(receipt, ranges=[{"metric": code, "max_value": "0.0101"}]))
    lower_only = graph.service.list(graph.actors[1], query(receipt, ranges=[{"metric": code, "min_value": "0.0101"}]))
    assert upper_only.total == 5 and lower_only.total == 2


def test_all_nine_ranges_combine_in_sql_before_pagination(graph):
    receipt, lease = submit(graph)
    snapshot = complete(receipt, graph.shops[0], 25)
    rows = tuple(replace(row, metrics=tuple(replace(metric, raw_value=Decimal(index).scaleb(-3))
        if metric.definition.code in RATIO_CODES else metric for metric in row.metrics))
        for index, row in enumerate(snapshot.products))
    graph.service.publish(receipt.generation_id, lease, replace(snapshot, products=rows))
    ranges = [{"metric": code, "min_value": "10", "max_value": "20"} for code in (
        "product_show_cnt", "product_click_cnt", "click_add_to_cart_uv", "net_pay_cnt", "pay_cnt_exclude_refund")]
    ranges += [{"metric": code, "min_value": "0.012", "max_value": "0.018"} for code in RATIO_CODES]
    result = graph.service.list(graph.actors[1], query(receipt, ranges=ranges, page=2, page_size=2))
    assert result.total == 6 and [row.product_id for row in result.items] == [rows[index].product_id for index in (14, 15)]


@pytest.mark.parametrize("code", ["pay_amt", "per_user_price", "pay_refund_success_amt"])
def test_amount_sort_preserves_raw_precision_with_unknowns_last(graph, code):
    receipt, lease = submit(graph)
    snapshot = complete(receipt, graph.shops[0], 4)
    specs = [("available", "9007199254740993.005", 3), ("available", "9007199254740993.004", 3),
             ("missing", None, None), ("invalid", "1", 6)]
    rows = tuple(replace(row, metrics=tuple(replace(metric, state=state, raw_unit=unit,
        raw_value=Decimal(raw) if raw is not None else None) if metric.definition.code == code else metric
        for metric in row.metrics)) for row, (state, raw, unit) in zip(snapshot.products, specs, strict=True))
    graph.service.publish(receipt.generation_id, lease, replace(snapshot, products=rows))
    result = graph.service.list(graph.actors[1], query(receipt, sort_field=code, sort_direction="asc"))
    assert [row.product_id for row in result.items[:2]] == [rows[index].product_id for index in (1, 0)]
    assert result.items[0].metrics[code].raw_value == "9007199254740993.004"
    assert {row.metrics[code].state for row in result.items[2:]} == {"missing", "invalid"}


def test_current_unit_verification_does_not_rewrite_historical_receipt_coverage(graph):
    receipt = publish(graph, total=1)
    generation = graph.session.get(Generation, receipt.generation_id)
    generation.unit_complete_rows = 0  # Simulate the original stored receipt.
    graph.session.commit()
    listed = graph.service.list(graph.actors[1], query(receipt))
    assert all(metric.unit_verified for metric in listed.items[0].metrics.values())
    assert graph.service.read_generation(graph.actors[0], receipt.generation_id).unit_complete_rows == 0


def test_stale_lease_and_late_sequence_cannot_overwrite_success(graph):
    first, lease = submit(graph)
    graph.session.execute(update(Generation).where(Generation.generation_id == first.generation_id).values(
        lease_until=graph.service.repository.now() - timedelta(seconds=1)))
    graph.session.commit()
    assert graph.service.read_generation(graph.actors[0], first.generation_id).lease_expired
    new = publish(graph, total=1)
    with pytest.raises(ProductDataPublicationRejectedError):
        graph.service.publish(first.generation_id, lease, complete(first, graph.shops[0], 1))
    assert graph.service.list(graph.actors[0], query(new)).items[0].generation_id == new.generation_id
    assert graph.session.get(Generation, first.generation_id).failure_code == "PRODUCT_DATA_LEASE_EXPIRED"


@pytest.mark.parametrize("fault", ["short", "duplicate", "scope", "identity"])
def test_incomplete_publication_is_atomic(graph, fault):
    receipt, lease = submit(graph)
    snapshot = complete(receipt, graph.shops[0], 2)
    if fault == "short": snapshot = replace(snapshot, products=snapshot.products[:1])
    if fault == "duplicate": snapshot = replace(snapshot, products=(snapshot.products[0], snapshot.products[0]))
    if fault == "scope": snapshot = replace(snapshot, scope=snapshot.scope.model_copy(update={"shop_id": graph.shops[1].shop_id}))
    if fault == "identity": snapshot = replace(snapshot, products=(replace(snapshot.products[0], platform_shop_id="999999999"), snapshot.products[1]))
    from app.platforms.exceptions import PlatformIdentityMismatchError
    with pytest.raises((ProductDataPublicationRejectedError, PlatformIdentityMismatchError)):
        graph.service.publish(receipt.generation_id, lease, snapshot)
    graph.session.rollback()
    assert graph.session.scalar(select(func.count()).select_from(Snapshot)) == 0
    assert graph.session.scalar(select(Series.current_generation_id)) is None


def test_disabled_execution_has_no_generation_side_effect(graph):
    disabled = ProductDataService(graph.session, settings=Settings(product_data_collection_execution_enabled=False))
    with pytest.raises(ProductDataCollectionUnavailableError):
        disabled.request_collection(graph.actors[0], ProductDataCollectionRequest(shop_id=graph.shops[0].shop_id,
            period="1d", submission_key=uuid4()))
    assert graph.session.scalar(select(func.count()).select_from(Generation)) == 0


def test_still_live_older_window_cannot_replace_newer_series_publication(graph, monkeypatch):
    first, lease = submit(graph)
    shifted = first.scope.model_copy(update={"start_date": first.scope.start_date + timedelta(days=1),
                                            "end_date": first.scope.end_date + timedelta(days=1)})
    monkeypatch.setattr("app.modules.product_data.service.freeze_native_slice", lambda *_: shifted)
    new = publish(graph, total=1)
    with pytest.raises(ProductDataPublicationRejectedError):
        graph.service.publish(first.generation_id, lease, complete(first, graph.shops[0], 1))
    assert graph.service.list(graph.actors[0], query(new)).items[0].generation_id == new.generation_id
