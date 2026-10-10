from dataclasses import replace
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import Barrier, Thread
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.exceptions import ModuleAccessDeniedError, TeamContextRequiredError
from app.modules.access.models import Team, TeamMembership, TeamModuleAccess, TeamShopAccess
from app.modules.access.module_access import ModuleCode
from app.modules.access.repository import AccessManagementRepository
from app.modules.access.service import ActorContextService
from app.modules.audit.models import AuditLog
from app.modules.product_selection.exceptions import (
    SelectionObservationNotFoundError, SelectionShopUnavailableError,
)
from app.modules.product_selection.models import (
    ProductSelectionCandidate as Candidate, ProductSelectionObservation as Observation,
)
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.product_selection.source import SelectionSourceScope
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.douyin.product_selection import (
    CompassBadCommentRate, CompassBasicInfo, CompassMerchant, CompassMetricRange,
    CompassRangeEndpoint, CompassRankPage, CompassRankProduct, FieldObservation,
)
from app.platforms.exceptions import PlatformRequestFailedError


pytestmark = pytest.mark.integration
START = datetime(2026, 10, 10, 8, tzinfo=UTC)
PRODUCT_ID = "9000000000000000001"


def _scope(**changes) -> SelectionSourceScope:
    values = {
        "industry_id": "7", "category_id": "1000009092,1000009142",
        "brand_type": "-1", "price_bin": "不限", "search_info": "",
        "rank_data_type": "1", "begin_date": "2026/10/02 00:00:00",
        "end_date": "2026/10/08 00:00:00", "date_type": "21", "activity_id": "",
    }
    return SelectionSourceScope(**(values | changes))


def _product(product_id=PRODUCT_ID, rank=11) -> CompassRankProduct:
    zero = FieldObservation("available", CompassMetricRange((
        CompassRangeEndpoint(Decimal(0), "int", "price"),
        CompassRangeEndpoint(Decimal(0), "int", "price"),
    )))
    return CompassRankProduct(
        product_id, "stage-2a1 合成候选", None, rank, "¥9-¥23",
        (CompassMerchant("synthetic-merchant", "商品所属商家"),),
        None, None, zero, FieldObservation("missing"),
        FieldObservation("null"), FieldObservation("invalid"),
    )


def _page(*products, page_no=2) -> CompassRankPage:
    return CompassRankPage(tuple(products or (_product(),)), page_no, 10, 200)


@pytest.fixture
def selection_context(postgresql_engine):
    engine = postgresql_engine
    teams, users, shops = [uuid4() for _ in range(2)], [uuid4() for _ in range(2)], [uuid4() for _ in range(2)]
    with Session(engine) as session:
        session.add_all([Team(team_id=key, name=f"stage-2a1-selection-{key}") for key in teams])
        session.add_all([User(user_id=key, display_name=f"stage-2a1-selection-{key}") for key in users])
        session.add_all([Shop(shop_id=key, display_name=f"stage-2a1-selection-{key}", platform=ShopPlatform.DOUYIN) for key in shops])
        session.flush()
        session.add_all([TeamMembership(team_id=team, user_id=user) for team, user in zip(teams, users)])
        session.add_all([TeamModuleAccess(team_id=key, module_code=ModuleCode.PRODUCT_SELECTION.value) for key in teams])
        session.add_all([TeamShopAccess(team_id=key, shop_id=shops[0]) for key in teams])
        session.add(TeamShopAccess(team_id=teams[0], shop_id=shops[1]))
        session.commit()
        actors = [ActorContextService(session).resolve(user_id=user, requested_team_id=team) for team, user in zip(teams, users)]
    try:
        yield engine, teams, users, shops, actors
    finally:
        with Session(engine) as session:
            session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(users)))
            candidate_ids = select(Candidate.candidate_id).where(Candidate.team_id.in_(teams))
            session.execute(delete(Observation).where(Observation.candidate_id.in_(candidate_ids)))
            session.execute(delete(Candidate).where(Candidate.team_id.in_(teams)))
            session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id.in_(teams)))
            session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id.in_(teams)))
            session.execute(delete(TeamMembership).where(TeamMembership.team_id.in_(teams)))
            session.execute(delete(Shop).where(Shop.shop_id.in_(shops)))
            session.execute(delete(Team).where(Team.team_id.in_(teams)))
            session.execute(delete(User).where(User.user_id.in_(users)))
            session.commit()


def _save(context, *, actor_index=0, shop_index=0, scope=None, page=None, started_at=START):
    engine, _, _, shops, actors = context
    with Session(engine) as session:
        return ProductSelectionFactService(session).persist_rank_page(
            actor=actors[actor_index], shop_id=shops[shop_index], scope=scope or _scope(),
            page=page or _page(), started_at=started_at, retrieved_at=started_at + timedelta(seconds=1),
        )


@contextmanager
def _api_client(context, actor_index=0):
    # Inject only the authenticated identity and registered Feature DB. Actual
    # ActorContext, Module and Shop authorization dependencies remain active.
    # Do not enter TestClient: no application scheduler/executor is started.
    from app.core.database import get_database_session
    from app.main import create_app
    from app.modules.access.auth import get_human_principal
    from app.modules.access.contracts import HumanPrincipal

    engine, _, users, _, _ = context
    application = create_app()

    def session_dependency():
        with Session(engine) as session:
            yield session

    application.dependency_overrides[get_database_session] = session_dependency
    application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
        user_id=users[actor_index], display_name="stage-2a1-selection-api",
    )
    client = TestClient(application)
    try:
        yield client
    finally:
        client.close()


def test_read_api_keeps_raw_ranges_units_and_distinct_source_times(selection_context):
    row_id = _save(selection_context)[0]
    engine, _, _, shops, actors = selection_context
    basic_at = START + timedelta(seconds=5)
    with Session(engine) as session:
        ProductSelectionFactService(session).persist_basic_info(
            actor=actors[0], observation_id=row_id, rank_started_at=START,
            retrieved_at=basic_at,
            basic=CompassBasicInfo(
                PRODUCT_ID, FieldObservation("available", ("厨具", "储物")),
                FieldObservation("available", date(2025, 8, 17)),
                FieldObservation("available", CompassBadCommentRate(
                    Decimal("0.00205018686599039"), "float", 4,
                )),
            ),
        )
    with _api_client(selection_context) as client:
        response = client.get("/api/v1/product-selection/candidates", params={
            "shop_id": str(shops[0]), "page": 1, "page_size": 10,
        })
        assert response.status_code == 200
        payload = response.json()
        assert (payload["total"], payload["page"], payload["page_size"]) == (1, 1, 10)
        item = payload["items"][0]
        assert item["product_id"] == PRODUCT_ID and isinstance(item["product_id"], str)
        assert item["request_shop_id"] == str(shops[0])
        assert item["merchants"][0]["platform_shop_id"] == "synthetic-merchant"
        assert item["bad_comment_rate_raw"] == "0.00205018686599039"
        assert item["bad_comment_rate_unit"] == 4
        assert item["video_metric_ranges"]["pay_amt"]["value_range"][0]["value"] == "0"
        assert item["video_metric_ranges"]["video_cnt"]["state"] == "invalid"
        assert item["first_on_shelf_date"] == "2025-08-17"
        assert item["checked_at"] == item["metrics_retrieved_at"]
        assert item["basic_info_retrieved_at"] != item["checked_at"]
        assert item["source_context"]["business"]["date_type"] == "21"
        assert "a_bogus" not in item["source_context"]["business"]
        # Detail points to the same observation, not a newly chosen period.
        assert client.get(f"/api/v1/product-selection/observations/{row_id}").json() == item
        assert client.post("/api/v1/product-selection/candidates").status_code == 405


def test_read_api_scopes_before_sort_pagination_and_revoked_access(selection_context):
    row_ids = _save(selection_context, page=_page(
        _product("9000000000000000003", rank=3),
        _product("9000000000000000002", rank=None),
        _product(PRODUCT_ID, rank=1),
    ))
    _save(selection_context, actor_index=1)
    engine, teams, _, shops, _ = selection_context
    with _api_client(selection_context) as client:
        response = client.get("/api/v1/product-selection/candidates", params={
            "sort_field": "rank", "sort_direction": "desc", "page_size": 1,
        })
        assert response.status_code == 200
        assert response.json()["total"] == 3
        assert response.json()["items"][0]["product_id"] == "9000000000000000003"
        last = client.get("/api/v1/product-selection/candidates", params={
            "sort_field": "rank", "sort_direction": "desc", "page_size": 1, "page": 3,
        }).json()
        assert last["items"][0]["rank"] is None
        match = client.get("/api/v1/product-selection/candidates", params={
            "search": "9000000000000000002",
        }).json()
        assert match["total"] == 1
        assert match["items"][0]["product_id"] == "9000000000000000002"
        with Session(engine) as session:
            session.execute(delete(TeamShopAccess).where(
                TeamShopAccess.team_id == teams[0], TeamShopAccess.shop_id == shops[0],
            ))
            session.commit()
        assert client.get("/api/v1/product-selection/candidates").json()["total"] == 0
        assert client.get(f"/api/v1/product-selection/observations/{row_ids[0]}").status_code == 404
        with Session(engine) as session:
            session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == teams[0]))
            session.commit()
        denied = client.get("/api/v1/product-selection/candidates")
        assert denied.status_code == 403 and denied.json()["code"] == "MODULE_ACCESS_DENIED"
    with _api_client(selection_context, actor_index=1) as client:
        assert client.get(f"/api/v1/product-selection/observations/{row_ids[0]}").status_code == 404


def test_read_api_rejects_unverified_rate_sort_and_invalid_queries(selection_context):
    with _api_client(selection_context) as client:
        for query in (
            {"sort_field": "negativeReviewRate"}, {"sort_field": "bad_comment_rate_raw"},
            {"source_scope_hash": "not-a-hash"}, {"page_size": 101}, {"page": 0},
        ):
            response = client.get("/api/v1/product-selection/candidates", params=query)
            assert response.status_code == 422
            assert response.json()["code"] == "VALIDATION_ERROR"
        assert client.get("/api/v1/product-selection/candidates").json()["total"] == 0


def _remove_team_grants_and_membership(context):
    engine, teams, users, _, _ = context
    with Session(engine) as session:
        # A real super-account principal has no membership. Only these
        # synthetic fixture grants/membership are removed, never facts.
        session.get(User, users[0]).is_super_account = True
        session.execute(delete(TeamMembership).where(TeamMembership.team_id == teams[0]))
        session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == teams[0]))
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == teams[0]))
        session.commit()


def test_team_delete_rejects_only_selection_facts_and_preserves_them(selection_context):
    observation_id = _save(selection_context)[0]
    engine, teams, _, _, _ = selection_context
    _remove_team_grants_and_membership(selection_context)
    with Session(engine) as session:
        for model in (TeamMembership, TeamModuleAccess, TeamShopAccess):
            assert session.scalar(select(func.count()).select_from(model).where(model.team_id == teams[0])) == 0
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == teams[0])) == 1
        assert AccessManagementRepository(session).team_has_references(teams[0]) is True
    with _api_client(selection_context) as client:
        response = client.delete(f"/api/v1/access-management/teams/{teams[0]}")
        assert response.status_code == 409
        assert response.json()["code"] == "TEAM_IN_USE"
    with Session(engine) as session:
        assert session.get(Team, teams[0]) is not None
        assert session.get(Observation, observation_id) is not None
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == teams[0])) == 1
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.target_id == teams[0])) == 0


def test_empty_team_without_selection_or_old_references_remains_deletable(selection_context):
    engine, teams, _, _, _ = selection_context
    _remove_team_grants_and_membership(selection_context)
    with Session(engine) as session:
        assert AccessManagementRepository(session).team_has_references(teams[0]) is False
    with _api_client(selection_context) as client:
        response = client.delete(f"/api/v1/access-management/teams/{teams[0]}")
        assert response.status_code == 204 and not response.content
    with Session(engine) as session:
        assert session.get(Team, teams[0]) is None
        assert session.get(Team, teams[1]) is not None


def test_postgresql_unique_identity_idempotent_source_and_raw_values(selection_context):
    first = _save(selection_context)[0]
    second = _save(selection_context, page=_page(_product(rank=9), page_no=3), started_at=START + timedelta(minutes=1))[0]
    assert second == first
    engine, teams, users, shops, actors = selection_context
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == teams[0])) == 1
        row = ProductSelectionFactService(session).get_observation(actor=actors[0], observation_id=first)
        candidate = session.get(Candidate, row.candidate_id)
        assert candidate.platform_product_id == PRODUCT_ID
        assert (row.rank, row.previous_rank, row.request_shop_id) == (9, 11, shops[0])
        assert row.merchant_snapshot[0]["platform_shop_id"] == "synthetic-merchant"
        assert row.video_metric_ranges["pay_amt"]["value_range"][0] == {"value": "0", "value_type": "int", "unit": "price"}
        assert row.video_metric_ranges["pay_combo_cnt"]["state"] == "missing"
        assert row.first_on_shelf_date is None and row.bad_comment_rate_raw is None
        session.add(Candidate(team_id=teams[0], created_by_user_id=users[0], platform="douyin", platform_product_id=PRODUCT_ID))
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


def test_sources_and_shared_shop_are_not_cross_team_facts(selection_context):
    original = _save(selection_context)[0]
    other_period = _save(selection_context, scope=_scope(begin_date="2026/10/01 00:00:00"))[0]
    other_shop = _save(selection_context, shop_index=1)[0]
    other_team = _save(selection_context, actor_index=1)[0]
    assert len({original, other_period, other_shop, other_team}) == 4
    engine, teams, _, _, actors = selection_context
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id.in_(teams))) == 2
        rows, total = ProductSelectionFactService(session).list_latest(actor=actors[1])
        assert total == 1 and rows[0].observation_id == other_team
        with pytest.raises(SelectionObservationNotFoundError):
            ProductSelectionFactService(session).get_observation(actor=actors[1], observation_id=original)


def test_older_rank_and_enrichment_cannot_overwrite_a_newer_run(selection_context):
    row_id = _save(selection_context)[0]
    newer = START + timedelta(minutes=2)
    _save(selection_context, page=_page(_product(rank=8)), started_at=newer)
    assert _save(selection_context, page=_page(_product(rank=99)), started_at=START) == ()
    engine, _, _, _, actors = selection_context
    with Session(engine) as session:
        service = ProductSelectionFactService(session)
        basic = CompassBasicInfo(PRODUCT_ID, FieldObservation("available", ("旧来源",)), FieldObservation("missing"), FieldObservation("null"))
        assert not service.persist_basic_info(actor=actors[0], observation_id=row_id, rank_started_at=START, retrieved_at=newer + timedelta(seconds=3), basic=basic)
        row = service.get_observation(actor=actors[0], observation_id=row_id)
        assert row.rank == 8 and row.category_path is None


def test_basic_info_partial_or_failure_preserves_successful_facts(selection_context):
    row_id = _save(selection_context)[0]
    engine, _, _, _, actors = selection_context
    with Session(engine) as session:
        service = ProductSelectionFactService(session)
        basic = CompassBasicInfo(
            PRODUCT_ID, FieldObservation("available", ("厨具", "储物")),
            FieldObservation("available", date(2025, 8, 17)),
            FieldObservation("available", CompassBadCommentRate(Decimal("0.00205018686599039"), "float", 4)),
        )
        assert service.persist_basic_info(actor=actors[0], observation_id=row_id, rank_started_at=START, retrieved_at=START + timedelta(seconds=2), basic=basic)
        partial = CompassBasicInfo(PRODUCT_ID, FieldObservation("null"), FieldObservation("missing"), FieldObservation("invalid"))
        assert service.persist_basic_info(actor=actors[0], observation_id=row_id, rank_started_at=START, retrieved_at=START + timedelta(seconds=3), basic=partial)
        assert service.record_basic_info_failure(actor=actors[0], observation_id=row_id, rank_started_at=START, at=START + timedelta(seconds=4), error=PlatformRequestFailedError("untrusted message must not be stored"))
        row = service.get_observation(actor=actors[0], observation_id=row_id)
        assert row.first_on_shelf_date == date(2025, 8, 17)
        assert row.category_path == ["厨具", "储物"]
        assert row.bad_comment_rate_raw == Decimal("0.00205018686599039") and row.bad_comment_rate_unit == 4
        assert row.last_error_code == "PLATFORM_REQUEST_FAILED"
        assert row.basic_info_retrieved_at == START + timedelta(seconds=2)
        assert "untrusted" not in str(row.source_context)


def test_older_partial_basic_attempt_cannot_replace_a_later_attempt(selection_context):
    row_id = _save(selection_context)[0]
    engine, _, _, _, actors = selection_context
    with Session(engine) as session:
        service = ProductSelectionFactService(session)
        newer = CompassBasicInfo(
            PRODUCT_ID, FieldObservation("available", ("当前有效类目",)),
            FieldObservation("missing"), FieldObservation("null"),
        )
        assert service.persist_basic_info(
            actor=actors[0], observation_id=row_id, rank_started_at=START,
            retrieved_at=START + timedelta(seconds=5), basic=newer,
        )
        assert not service.persist_basic_info(
            actor=actors[0], observation_id=row_id, rank_started_at=START,
            retrieved_at=START + timedelta(seconds=3),
            basic=replace(newer, category_path=FieldObservation("available", ("过期类目",))),
        )
        row = service.get_observation(actor=actors[0], observation_id=row_id)
        assert row.category_path == ["当前有效类目"]
        assert row.last_attempt_at == START + timedelta(seconds=5)


def test_missing_new_metric_does_not_clear_a_known_zero(selection_context):
    row_id = _save(selection_context)[0]
    _save(selection_context, page=_page(replace(_product(), pay_amt=FieldObservation("null"))), started_at=START + timedelta(minutes=1))
    engine, _, _, _, actors = selection_context
    with Session(engine) as session:
        row = ProductSelectionFactService(session).get_observation(actor=actors[0], observation_id=row_id)
        assert row.video_metric_ranges["pay_amt"]["state"] == "available"
        assert row.video_metric_ranges["pay_amt"]["value_range"][0]["value"] == "0"
        assert row.video_metric_ranges["pay_amt"]["retrieved_at"] == (START + timedelta(seconds=1)).isoformat()


def test_revoked_shop_and_module_access_are_rechecked(selection_context):
    row_id = _save(selection_context)[0]
    engine, teams, _, shops, actors = selection_context
    with Session(engine) as session:
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == teams[0], TeamShopAccess.shop_id == shops[0]))
        session.commit()
        service = ProductSelectionFactService(session)
        assert service.list_latest(actor=actors[0])[1] == 0
        with pytest.raises(SelectionObservationNotFoundError):
            service.get_observation(actor=actors[0], observation_id=row_id)
    with pytest.raises(SelectionShopUnavailableError):
        _save(selection_context, started_at=START + timedelta(minutes=1))
    with Session(engine) as session:
        session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == teams[1]))
        session.commit()
        with pytest.raises(ModuleAccessDeniedError):
            ProductSelectionFactService(session).list_latest(actor=actors[1])


def test_permission_filter_precedes_latest_source_and_disabled_history_is_readable(selection_context):
    visible = _save(selection_context)[0]
    _save(selection_context, shop_index=1, page=_page(_product(rank=2)), started_at=START + timedelta(minutes=2))
    engine, teams, _, shops, actors = selection_context
    with Session(engine) as session:
        session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == teams[0], TeamShopAccess.shop_id == shops[1]))
        session.get(Shop, shops[0]).enabled = False
        session.commit()
        rows, total = ProductSelectionFactService(session).list_latest(actor=actors[0])
        assert total == 1 and rows[0].observation_id == visible and rows[0].rank == 11
    with pytest.raises(SelectionShopUnavailableError):
        _save(selection_context, started_at=START + timedelta(minutes=3))
    with Session(engine) as session:
        session.get(Shop, shops[0]).deleted_at = START
        session.commit()
        assert ProductSelectionFactService(session).list_latest(actor=actors[0])[1] == 0


def test_sort_all_visible_candidates_then_paginate_nulls_last(selection_context):
    products = [_product(str(int(PRODUCT_ID) + index), rank) for index, rank in enumerate((10, None, 1))]
    _save(selection_context, page=_page(*products))
    engine, _, _, _, actors = selection_context
    with Session(engine) as session:
        service = ProductSelectionFactService(session)
        page_one, total = service.list_latest(actor=actors[0], sort="rank", descending=False, limit=2)
        page_two, _ = service.list_latest(actor=actors[0], sort="rank", descending=False, offset=2, limit=2)
        assert total == 3 and [row.rank for row in page_one + page_two] == [1, 10, None]
        assert [row.rank for row in service.list_latest(actor=actors[0], sort="rank", limit=3)[0]] == [10, 1, None]


def test_two_database_sessions_upsert_without_duplicate_identity(selection_context):
    barrier, results, errors = Barrier(2), [], []
    def write(index):
        try:
            barrier.wait(timeout=10)
            results.append(_save(selection_context, started_at=START + timedelta(seconds=index)))
        except Exception as error:
            errors.append(type(error).__name__)
    threads = [Thread(target=write, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)
    assert not any(thread.is_alive() for thread in threads) and not errors
    engine, teams, _, _, _ = selection_context
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == teams[0])) == 1
        row = session.scalar(select(Observation).join(Candidate).where(Candidate.team_id == teams[0]))
        assert row.last_successful_request_started_at == START + timedelta(seconds=1)


def test_empty_success_does_not_invent_candidate_or_fake_persisted_run(selection_context):
    assert _save(selection_context, page=CompassRankPage((), 1, 10, 0)) == ()
    engine, teams, _, _, _ = selection_context
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Candidate).where(Candidate.team_id == teams[0])) == 0
    # Queryable empty/failed run state is deliberately not claimed by these
    # two fact tables; it still requires the separately reviewed run contract.


def test_explicit_zero_rate_is_not_missing_and_partial_attempt_is_visible(selection_context):
    row_id = _save(selection_context)[0]
    engine, _, _, _, actors = selection_context
    with Session(engine) as session:
        service = ProductSelectionFactService(session)
        basic = CompassBasicInfo(
            PRODUCT_ID, FieldObservation("missing"), FieldObservation("null"),
            FieldObservation("available", CompassBadCommentRate(Decimal(0), "int", 4)),
        )
        assert service.persist_basic_info(actor=actors[0], observation_id=row_id, rank_started_at=START, retrieved_at=START + timedelta(seconds=2), basic=basic)
        row = service.get_observation(actor=actors[0], observation_id=row_id)
        assert row.bad_comment_rate_raw == 0 and row.bad_comment_rate_unit == 4
        assert row.category_path is None and row.first_on_shelf_date is None
        assert row.last_error_code == "PRODUCT_SELECTION_BASIC_INFO_PARTIAL"
        assert row.basic_info_retrieved_at is None


def test_super_account_write_needs_explicit_team_and_actor_flags_are_not_trusted(selection_context):
    first = _save(selection_context)[0]
    _save(selection_context, actor_index=1)
    engine, _, users, shops, actors = selection_context
    with Session(engine) as session:
        service = ProductSelectionFactService(session)
        forged = replace(actors[1], is_super_account=True)
        with pytest.raises(SelectionObservationNotFoundError):
            service.get_observation(actor=forged, observation_id=first)
        session.get(User, users[0]).is_super_account = True
        session.commit()
        no_team = ActorContextService(session).resolve(user_id=users[0], requested_team_id=None)
        assert service.list_latest(actor=no_team)[1] == 2
        with pytest.raises(TeamContextRequiredError):
            service.persist_rank_page(actor=no_team, shop_id=shops[0], scope=_scope(), page=_page(), started_at=START, retrieved_at=START + timedelta(seconds=1))


def test_membership_revocation_after_request_prevents_fact_write(selection_context):
    engine, teams, _, _, _ = selection_context
    with Session(engine) as session:
        membership = session.scalar(select(TeamMembership).where(TeamMembership.team_id == teams[0]))
        membership.enabled = False
        session.commit()
    from app.modules.access.exceptions import TeamAccessDeniedError
    with pytest.raises(TeamAccessDeniedError):
        _save(selection_context)


def test_platform_product_identity_is_checked_again_before_basic_write(selection_context):
    row_id = _save(selection_context)[0]
    engine, _, _, _, actors = selection_context
    from app.platforms.douyin.product_selection import CompassSelectionIdentityError
    with Session(engine) as session:
        wrong = CompassBasicInfo("9000000000000000002", FieldObservation("missing"), FieldObservation("missing"), FieldObservation("missing"))
        with pytest.raises(CompassSelectionIdentityError):
            ProductSelectionFactService(session).persist_basic_info(actor=actors[0], observation_id=row_id, rank_started_at=START, retrieved_at=START + timedelta(seconds=2), basic=wrong)
        assert session.get(Observation, row_id).basic_info_retrieved_at is None
