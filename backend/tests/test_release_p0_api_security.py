from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from app.core.database import get_database_session
from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_actor_context, get_module_access_service
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import ModuleAccessDeniedError
from app.modules.access.module_access import ModuleCode
from app.modules.notifications.api import get_notification_service, get_settings_authorized_actor, router as notifications_router
from tests.support import FakeSession

CHANNEL_ID = uuid4()
ACTOR = ActorContext(user_id=uuid4(), user_display_name="test", team_id=uuid4(),
                     membership_id=uuid4(), role_code="member", data_scope=DataScope.TEAM)


class ModuleAccessProbe:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed
        self.checked: list[ModuleCode] = []

    def require_module_access(self, actor: ActorContext, module_code: ModuleCode) -> None:
        assert actor == ACTOR
        self.checked.append(module_code)
        if not self.allowed:
            raise ModuleAccessDeniedError()


class NotificationServiceStub:
    def send_test(self, channel_id: UUID, *, now: datetime) -> None:
        assert channel_id == CHANNEL_ID
        assert now.tzinfo is not None


def request(method: str, path: str, *, access: ModuleAccessProbe | None = None):
    app = create_app()
    app.dependency_overrides[get_database_session] = lambda: FakeSession()
    app.dependency_overrides[get_notification_service] = NotificationServiceStub
    if access is not None:
        app.dependency_overrides[get_actor_context] = lambda: ACTOR
        app.dependency_overrides[get_module_access_service] = lambda: access

    async def send():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            return await client.request(method, path)
    return asyncio.run(send())


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v1/shops"),
    ("POST", "/api/v1/shops"),
    ("GET", "/api/v1/credentials"),
    ("GET", "/api/v1/automation-app-configs/yingdao/applications"),
    ("GET", "/api/v1/automation-parameter-presets"),
])
def test_retired_management_routes_return_404(method: str, path: str) -> None:
    assert request(method, path).status_code == 404


def test_notification_management_retains_auth_and_module_guard() -> None:
    path = f"/api/v1/notification-channels/{CHANNEL_ID}/test"
    assert request("POST", path).status_code == 401
    denied = ModuleAccessProbe(False)
    assert request("POST", path, access=denied).status_code == 403
    assert denied.checked == [ModuleCode.SETTINGS]
    allowed = ModuleAccessProbe(True)
    assert request("POST", path, access=allowed).status_code == 200
    assert allowed.checked == [ModuleCode.SETTINGS]


def test_notification_router_uses_settings_guard() -> None:
    routes = [route for route in notifications_router.routes if isinstance(route, APIRoute)]
    assert len(routes) == 4
    assert all(any(dep.call is get_settings_authorized_actor for dep in route.dependant.dependencies)
               for route in routes)
