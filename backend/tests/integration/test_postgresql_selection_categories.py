"""Real Feature authorization/transactions, synthetic categories; zero platform I/O."""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from sqlalchemy import delete

from app.modules.access.models import TeamShopAccess
from app.modules.product_selection.category_service import SelectionCategoryService
from app.modules.product_selection.exceptions import SelectionShopUnavailableError
from app.modules.shops.models import Shop
from app.platforms.douyin.product_selection import CompassCategoryTree, CompassCategoryNode
from app.platforms.exceptions import PlatformIdentityMismatchError
from tests.integration.test_postgresql_product_selection import selection_context, _api_client


pytestmark = pytest.mark.integration


def _service(context, before_return=None, mismatch=False):
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
            return CompassCategoryTree((CompassCategoryNode("7", "行业", ()),), "7", "行业", None)

    return SelectionCategoryService(factory, platform=Platform()), calls


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
