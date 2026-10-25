"""Read-only human APIs over invisible terminal fixtures; no dispatch or task creation API."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import HumanPrincipal
from app.modules.access.models import Team, TeamMembership, TeamModuleAccess
from app.modules.access.module_access import ModuleCode
from app.modules.product_collection.api import get_product_library_actor
from app.modules.product_collection.models import (
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionRequest as CollectionRequest,
    ProductLibraryGroup as LibraryGroup,
    ProductLibraryProduct as Product,
)
from app.modules.users.models import User
from tests.integration.test_postgresql_collection_media_budget import isolated_collection


pytestmark = pytest.mark.integration


@pytest.fixture
def read_world(isolated_collection):
    application, client, sessions = isolated_collection
    team_a, team_b, super_id, member_a, member_b = (uuid4() for _ in range(5))
    request_ids = [uuid4() for _ in range(3)]
    group_ids = [uuid4() for _ in range(2)]
    product_ids = [uuid4() for _ in range(3)]
    item_ids = []
    with sessions() as session:
        baseline = session.scalar(select(func.count()).select_from(CollectionRequest))
        library_product_baseline = session.scalar(select(func.count()).select_from(Product))
        existing_super = session.scalar(select(User).where(User.is_super_account.is_(True)))
        if existing_super is not None:
            assert existing_super.enabled
            super_id = existing_super.user_id
        session.add_all([
            Team(team_id=team, name=f"stage-2a1-read-scope-{team}", enabled=True)
            for team in (team_a, team_b)
        ])
        session.add_all([
            User(user_id=user, display_name="stage-2a1-read-scope", enabled=True,
                 is_super_account=(user == super_id))
            for user in ((member_a, member_b) if existing_super is not None else (super_id, member_a, member_b))
        ])
        session.flush()
        for team, member in ((team_a, member_a), (team_b, member_b)):
            session.add(TeamModuleAccess(team_id=team, module_code=ModuleCode.PRODUCT_LIBRARY.value))
            session.add(TeamMembership(membership_id=uuid4(), team_id=team, user_id=member,
                                       enabled=True, role_code="member", data_scope="team"))
        session.flush()
        for index, (group_id, team) in enumerate(zip(group_ids, (team_a, team_b), strict=True)):
            session.add(LibraryGroup(
                group_id=group_id, team_id=team, name=f"stage-2a1-library-group-{index}",
                normalized_name=f"stage-2a1-library-group-{index}", created_by_user_id=super_id,
            ))
        session.flush()
        product_specs = (
            (product_ids[0], team_a, group_ids[0], "stage-2a1-library-scope-alpha", "scope-a-grouped"),
            (product_ids[1], team_b, group_ids[1], "stage-2a1-library-scope-beta", "scope-b-grouped"),
            (product_ids[2], team_a, None, "stage-2a1-library-scope-ungrouped", "scope-a-ungrouped"),
        )
        for index, (product_id, team, group_id, title, source_id) in enumerate(product_specs):
            at = datetime(2090, 1, 2, tzinfo=UTC) - timedelta(minutes=index)
            session.add(Product(
                product_id=product_id, team_id=team, platform="douyin",
                source_product_id=source_id, group_id=group_id, title=title,
                created_by_user_id=super_id, manual_revision=0,
                created_at=at, updated_at=at,
            ))
        session.flush()
        # Terminal, uncommitted fixtures cannot be claimed by any consumer.
        for index, (request_id, team) in enumerate(zip(request_ids, (team_a, team_b, team_a), strict=True)):
            at = datetime(2090, 1, 1, tzinfo=UTC) - timedelta(minutes=index)
            state = "canceled" if index == 1 else "failed"
            count = 2 if index == 0 else 1
            session.add(CollectionRequest(
                request_id=request_id, team_id=team, requested_by_user_id=super_id,
                submission_key=uuid4(), source_kind="manual", canonical_request_hash="a" * 64,
                status=state, item_count=count, created_at=at, updated_at=at, finished_at=at,
            ))
            session.flush()
            product_indexes = ((0, 2), (1,), (0,))[index]
            for product_index in product_indexes:
                item_id = uuid4()
                item_ids.append(item_id)
                product = product_specs[product_index]
                session.add(Item(
                    item_id=item_id, team_id=team, request_id=request_id, platform="douyin",
                    source_product_id=product[4], collection_mode="auto_gateway",
                    state=state, library_product_id=product[0], attempt_count=0,
                    created_at=at, updated_at=at, finished_at=at,
                    last_error_message="合成读取权限样本" if state == "failed" else None,
                ))
        session.commit()
    # Keep the real ActorContext resolver and module guard. Only authentication
    # identity is synthetic; X-Team-ID must pass normal database authorization.
    application.dependency_overrides.pop(get_product_library_actor)
    identity = {"user_id": super_id}
    application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
        identity["user_id"], "stage-2a1-read-scope",
    )
    settings = get_settings().model_copy(update={"product_collection_gateway_id": "synthetic-read-scope"})
    application.dependency_overrides[get_settings] = lambda: settings
    yield (
        client,
        sessions,
        identity,
        (team_a, team_b),
        (super_id, member_a, member_b),
        request_ids,
        item_ids,
        baseline,
        {
            "group_ids": group_ids,
            "product_ids": product_ids,
            "product_baseline": library_product_baseline,
        },
    )


@pytest.mark.parametrize("identity_index,team_index,expected_indices", [
    (0, None, [0, 1, 2]), (0, 0, [0, 2]), (0, 1, [1]), (1, None, [0, 2]), (2, None, [1]),
])
def test_list_count_pagination_and_details_share_the_same_scope(read_world, identity_index, team_index, expected_indices):
    client, _, identity, teams, users, requests, _, baseline, _ = read_world
    identity["user_id"] = users[identity_index]
    headers = {"X-Team-ID": str(teams[team_index])} if team_index is not None else {}
    expected = [str(requests[index]) for index in expected_indices]
    global_view = identity_index == 0 and team_index is None
    response = client.get("/api/v1/product-collection/requests?page_size=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == len(expected) + (baseline if global_view else 0)
    found = []
    for page in range(1, len(expected) + 1):
        result = client.get(f"/api/v1/product-collection/requests?page={page}&page_size=1", headers=headers).json()
        found.append(result["items"][0]["request_id"])
        assert result["total"] == response.json()["total"]
    assert found == expected
    for index, request_id in enumerate(requests):
        detail = client.get(f"/api/v1/product-collection/requests/{request_id}", headers=headers)
        if str(request_id) not in expected:
            assert detail.status_code == 404
            continue
        assert detail.status_code == 200
        body = detail.json()
        assert body["item_count"] == (2 if index == 0 else 1)
        assert len(body["items"]) == body["item_count"]
        assert body["failed_count"] == (0 if index == 1 else body["item_count"])
        assert body["canceled_count"] == (1 if index == 1 else 0)
        assert body["pending_count"] == body["running_count"] == body["succeeded_count"] == 0


@pytest.mark.parametrize(
    "identity_index,team_index,expected_product_indexes,expected_group_indexes",
    [
        (0, None, [0, 1, 2], [0, 1]),
        (0, 0, [0, 2], [0]),
        (0, 1, [1], [1]),
        (1, None, [0, 2], [0]),
        (2, None, [1], [1]),
    ],
)
def test_library_groups_list_total_search_filter_and_detail_share_scope(
    read_world,
    identity_index,
    team_index,
    expected_product_indexes,
    expected_group_indexes,
):
    client, _, identity, teams, users, _, _, _, library = read_world
    identity["user_id"] = users[identity_index]
    headers = {"X-Team-ID": str(teams[team_index])} if team_index is not None else {}
    product_ids = library["product_ids"]
    group_ids = library["group_ids"]
    expected_products = [str(product_ids[index]) for index in expected_product_indexes]
    expected_groups = {str(group_ids[index]) for index in expected_group_indexes}
    global_view = identity_index == 0 and team_index is None

    groups = client.get("/api/v1/product-library/groups", headers=headers)
    assert groups.status_code == 200
    returned_groups = {row["group_id"] for row in groups.json()}
    assert expected_groups <= returned_groups
    if not global_view:
        assert returned_groups == expected_groups

    products = client.get(
        "/api/v1/product-library/products?search=stage-2a1-library-scope&page_size=1",
        headers=headers,
    )
    assert products.status_code == 200
    assert products.json()["total"] == len(expected_products)
    found = []
    for page in range(1, len(expected_products) + 1):
        response = client.get(
            f"/api/v1/product-library/products?search=stage-2a1-library-scope&page={page}&page_size=1",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == len(expected_products)
        found.append(response.json()["items"][0]["product_id"])
    assert found == expected_products

    unfiltered = client.get("/api/v1/product-library/products", headers=headers)
    assert unfiltered.status_code == 200
    expected_total = len(expected_products)
    if global_view:
        expected_total += library["product_baseline"]
    assert unfiltered.json()["total"] == expected_total

    for index, product_id in enumerate(product_ids):
        detail = client.get(
            f"/api/v1/product-library/products/{product_id}",
            headers=headers,
        )
        if str(product_id) not in expected_products:
            assert detail.status_code == 404
            continue
        assert detail.status_code == 200
        assert detail.json()["versions"] == []
        assert detail.json()["latest_collection_state"] == (
            "canceled" if index == 1 else "failed"
        )

    visible_group = group_ids[expected_group_indexes[0]]
    filtered = client.get(
        f"/api/v1/product-library/products?group_id={visible_group}",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1


def test_library_group_filter_cannot_cross_selected_team(read_world):
    client, _, identity, teams, users, _, _, _, library = read_world
    identity["user_id"] = users[0]
    result = client.get(
        f"/api/v1/product-library/products?group_id={library['group_ids'][1]}",
        headers={"X-Team-ID": str(teams[0])},
    )
    assert result.status_code == 404


def test_member_cannot_select_other_team_or_read_cross_team_detail(read_world):
    client, _, identity, teams, users, requests, _, _, _ = read_world
    identity["user_id"] = users[1]
    for path in ("/api/v1/product-collection/requests", f"/api/v1/product-collection/requests/{requests[1]}"):
        assert client.get(path, headers={"X-Team-ID": str(teams[1])}).status_code == 403
    assert client.get(f"/api/v1/product-collection/requests/{requests[1]}").status_code == 404


def test_revoked_module_still_blocks_list_and_detail(read_world):
    client, sessions, identity, teams, users, requests, _, _, _ = read_world
    with sessions() as session:
        session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == teams[0]))
        session.commit()
    identity["user_id"] = users[1]
    for path in ("/api/v1/product-collection/requests", f"/api/v1/product-collection/requests/{requests[0]}"):
        result = client.get(path)
        assert result.status_code == 403
        assert result.json()["code"] == "MODULE_ACCESS_DENIED"


@pytest.mark.parametrize("action", ["create", "cancel", "retry", "recapture"])
def test_global_read_does_not_grant_writes_or_create_queue_work(read_world, action):
    client, sessions, _, _, _, requests, items, _, _ = read_world
    def counts(session):
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (CollectionRequest, Item, Dispatch))
    with sessions() as session:
        before = counts(session)
    paths = {
        "create": "/api/v1/product-collection/requests",
        "cancel": f"/api/v1/product-collection/requests/{requests[0]}/cancel",
        "retry": f"/api/v1/product-collection/items/{items[0]}/retry",
        "recapture": f"/api/v1/product-collection/items/{items[0]}/recapture",
    }
    # The create call must be rejected before persistence, not create a test task.
    body = {"submission_key": str(uuid4()), "source": {"kind": "manual", "targets": [
        {"platform": "douyin", "product_id_or_supported_url": "3832497447662387684"},
    ]}} if action == "create" else None
    result = client.post(paths[action], json=body)
    assert result.status_code == 409
    assert result.json()["code"] == "TEAM_CONTEXT_REQUIRED"
    with sessions() as session:
        assert counts(session) == before


@pytest.mark.parametrize("identity_index", [0, 1])
def test_selected_team_write_cannot_target_other_team(read_world, identity_index):
    client, _, identity, teams, users, requests, items, _, _ = read_world
    identity["user_id"] = users[identity_index]
    headers = {"X-Team-ID": str(teams[1])}
    for path in (f"/api/v1/product-collection/requests/{requests[0]}/cancel",
                 f"/api/v1/product-collection/items/{items[0]}/retry",
                 f"/api/v1/product-collection/items/{items[0]}/recapture"):
        result = client.post(path, headers=headers)
        assert result.status_code == (404 if identity_index == 0 else 403)
