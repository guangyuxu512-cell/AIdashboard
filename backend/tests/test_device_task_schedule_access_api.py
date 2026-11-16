from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.access.exceptions import ModuleAccessDeniedError
from app.modules.devices.api import get_device_authorized_actor
from app.core.config import get_settings
from app.modules.schedules.api import get_schedule_authorized_actor, get_schedule_service
from app.modules.tasks.api import get_task_authorized_actor
from app.shared.pagination import Page


def _request(application: object, path: str) -> Response:
    async def send() -> Response:
        transport = ASGITransport(app=application)  # type: ignore[arg-type]
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(send())


@pytest.mark.parametrize(
    "path",
    ["/api/v1/devices", "/api/v1/tasks", "/api/v1/schedules"],
)
def test_human_resource_apis_require_a_human_session(path: str) -> None:
    response = _request(create_app(), path)

    assert response.status_code == 401
    assert response.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"


@pytest.mark.parametrize(
    "dependency,path",
    [
        (get_device_authorized_actor, "/api/v1/devices"),
        (get_task_authorized_actor, "/api/v1/tasks"),
        (get_schedule_authorized_actor, "/api/v1/schedules"),
    ],
)
def test_human_resource_apis_reject_missing_module_access(
    dependency: object,
    path: str,
) -> None:
    application = create_app()

    def deny_module_access() -> object:
        raise ModuleAccessDeniedError()

    application.dependency_overrides[dependency] = deny_module_access  # type: ignore[index]
    response = _request(application, path)

    assert response.status_code == 403
    assert response.json()["code"] == "MODULE_ACCESS_DENIED"


@pytest.mark.parametrize("enabled", [False, True])
def test_schedule_list_reports_actual_worker_execution_status(monkeypatch, enabled: bool) -> None:
    monkeypatch.setenv("BACKEND_WORKER_SCHEDULE_EXECUTION_ENABLED", str(enabled).lower())
    get_settings.cache_clear()

    class EmptyScheduleService:
        def list_management(self, **kwargs):
            return Page(items=[], total=0, page=kwargs["page"], page_size=kwargs["page_size"])

    try:
        application = create_app()
        application.dependency_overrides[get_schedule_authorized_actor] = lambda: object()
        application.dependency_overrides[get_schedule_service] = lambda: EmptyScheduleService()
        response = _request(application, "/api/v1/schedules")
        assert response.status_code == 200
        assert response.json()["execution_enabled"] is enabled
    finally:
        get_settings.cache_clear()
