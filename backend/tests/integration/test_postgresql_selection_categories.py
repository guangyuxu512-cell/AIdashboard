"""Real Feature authorization/transactions, synthetic categories; zero platform I/O."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import delete

from app.modules.access.models import TeamShopAccess
from app.modules.product_selection.category_service import SelectionCategoryService
from app.modules.product_selection.category_cache import SelectionCategoryCache
from app.modules.product_selection.exceptions import SelectionShopUnavailableError
from app.modules.shops.models import Shop
from app.platforms.douyin.product_selection import CompassCategoryTree, CompassCategoryNode
from app.platforms.exceptions import PlatformIdentityMismatchError
from tests.integration.test_postgresql_product_selection import selection_context, _api_client


pytestmark = pytest.mark.integration


def _service(context, before_return=None, mismatch=False, cache=None, tree=None):
    open_sessions, calls = [], []

    @contextmanager
    def factory():
        with Session(context[0]) as session:
            open_sessions.append(session)
            try:
                yield session
            finally:
                open_sessions.remove(session)

    class Platform:
        def session_context(self, shop_id):
            assert not open_sessions
            assert context[0].pool.checkedout() == 0
            calls.append("session")
            return SimpleNamespace(shop_id=uuid4() if mismatch else shop_id)

        def categories(self, auth_context):
            assert not open_sessions  # Network boundary has no open DB session.
            assert context[0].pool.checkedout() == 0
            calls.append("categories")
            if before_return:
                before_return()
            return tree or CompassCategoryTree((CompassCategoryNode("7", "行业", ()),), "7", "行业", None)

    return SelectionCategoryService(factory, platform=Platform(), cache=cache or SelectionCategoryCache()), calls


def test_category_api_uses_authorized_shop_and_keeps_io_outside_transactions(selection_context):
    from app.modules.product_selection.api import get_selection_category_service
    context = selection_context
    service, calls = _service(context)
    with _api_client(context) as client:
        client.app.dependency_overrides[get_selection_category_service] = lambda: service
        response = client.get("/api/v1/product-selection/categories", params={"shop_id": str(context[3][0])}, headers={"X-Team-ID": str(context[1][0])})
    assert response.status_code == 200
    assert response.json() == {
        "shop_id": str(context[3][0]), "nodes": [{"category_id": "7", "name": "行业", "children": []}],
        "industry_id": "7", "industry_name": "行业", "selected_category_id": None,
    }
    assert calls == ["session", "categories"]


def test_category_rejects_unauthorized_and_disabled_shop_before_any_session_or_platform(selection_context):
    context = selection_context
    service, calls = _service(context)
    with pytest.raises(SelectionShopUnavailableError):
        service.read(context[4][1], context[3][1])
    with Session(context[0]) as session:
        session.get(Shop, context[3][0]).enabled = False
        session.commit()
    with pytest.raises(SelectionShopUnavailableError):
        service.read(context[4][0], context[3][0])
    assert calls == []


def test_category_rechecks_revoked_shop_after_io_and_rejects_context_mismatch(selection_context):
    context = selection_context

    def revoke():
        with Session(context[0]) as session:
            session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0], TeamShopAccess.shop_id == context[3][0]))
            session.commit()

    service, calls = _service(context, before_return=revoke)
    with pytest.raises(SelectionShopUnavailableError):
        service.read(context[4][0], context[3][0])
    assert calls == ["session", "categories"]
    service, calls = _service(context, mismatch=True)
    with pytest.raises(PlatformIdentityMismatchError):
        service.read(context[4][1], context[3][0])
    assert calls == ["session"]


def test_category_cache_hit_refresh_and_current_permissions(selection_context):
    from app.modules.product_selection.api import get_selection_category_service
    context = selection_context
    service, calls = _service(context)
    with _api_client(context) as client:
        client.app.dependency_overrides[get_selection_category_service] = lambda: service
        params = {"shop_id": str(context[3][0])}
        headers = {"X-Team-ID": str(context[1][0])}
        assert client.get("/api/v1/product-selection/categories", params=params, headers=headers).status_code == 200
        assert client.get("/api/v1/product-selection/categories", params=params, headers=headers).status_code == 200
        assert calls == ["session", "categories"]
        assert client.get("/api/v1/product-selection/categories", params={**params, "refresh": True}, headers=headers).status_code == 200
        assert calls == ["session", "categories"] * 2
        with Session(context[0]) as session:
            session.execute(delete(TeamShopAccess).where(TeamShopAccess.team_id == context[1][0], TeamShopAccess.shop_id == context[3][0]))
            session.commit()
        denied = client.get("/api/v1/product-selection/categories", params=params, headers=headers)
        assert denied.status_code == 409
        assert denied.json()["code"] == SelectionShopUnavailableError.code
    assert calls == ["session", "categories"] * 2


def test_cache_shared_across_services_but_never_authorizes_a_team(selection_context):
    context, cache = selection_context, SelectionCategoryCache()
    display, display_calls = _service(context, cache=cache)
    validation, validation_calls = _service(context, cache=cache)
    tree = display.read(context[4][0], context[3][0])
    assert validation.read(context[4][0], context[3][0]) == tree
    assert display_calls == ["session", "categories"]
    assert validation_calls == []
    assert validation.read(context[4][1], context[3][0]) == tree
    with pytest.raises(SelectionShopUnavailableError):
        validation.read(context[4][1], context[3][1])
    with Session(context[0]) as session:
        session.get(Shop, context[3][0]).enabled = False
        session.commit()
    with pytest.raises(SelectionShopUnavailableError):
        validation.read(context[4][0], context[3][0])
    assert validation_calls == []


def test_display_and_formal_submit_share_the_process_cache(selection_context, monkeypatch):
    from app.modules.product_selection import category_service
    from app.modules.product_selection.run_service import SelectionRunService
    from tests.integration.test_postgresql_selection_runs import SETTINGS, _input

    context = selection_context
    tree = CompassCategoryTree((CompassCategoryNode("7", "行业", (
        CompassCategoryNode("1000009092", "父级", (
            CompassCategoryNode("1000009142", "三级", ()),
        )),
    )),), "7", "行业", None)
    display, calls = _service(context, tree=tree)
    monkeypatch.setattr(category_service, "get_selection_category_cache", lambda: display.cache)
    monkeypatch.setattr(category_service, "SelectionStoredSessionIO", lambda factory: display.platform)
    display.read(context[4][0], context[3][0])
    command = _input(context)
    with Session(context[0]) as session:
        # Default production resolver + default category reader; only I/O is synthetic.
        run_service = SelectionRunService(session, settings=SETTINGS)
        receipt = run_service.submit(context[4][0], command)
        assert receipt.execution.status == "pending"
        assert run_service.submit(context[4][0], command).receipt_id == receipt.receipt_id
    assert calls == ["session", "categories"]


def test_cached_tree_does_not_bypass_revoked_module(selection_context):
    from app.modules.access.exceptions import ModuleAccessDeniedError
    from app.modules.access.models import TeamModuleAccess
    from app.modules.access.module_access import ModuleCode
    context = selection_context
    service, calls = _service(context)
    service.read(context[4][0], context[3][0])
    with Session(context[0]) as session:
        session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id == context[1][0], TeamModuleAccess.module_code == ModuleCode.PRODUCT_SELECTION.value))
        session.commit()
    with pytest.raises(ModuleAccessDeniedError):
        service.read(context[4][0], context[3][0])
    assert calls == ["session", "categories"]
