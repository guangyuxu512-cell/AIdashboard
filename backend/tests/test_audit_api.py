from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_actor_context, get_super_account
from app.modules.access.enums import DataScope
from app.modules.audit.api import get_audit_log_service
from app.modules.audit.enums import AuditAction, AuditTargetType
from app.modules.audit.schemas import AuditLogRead
from app.shared.pagination import Page


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="审计管理员",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="access_admin",
    data_scope=DataScope.ALL,
    is_super_account=True,
)


class ApiAuditLogService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list_logs(self, **kwargs: object) -> Page[AuditLogRead]:
        self.calls.append(kwargs)
        return Page(
            items=[
                AuditLogRead(
                    audit_log_id=uuid4(),
                    request_id="request-audit-list",
                    actor_user_id=ACTOR.user_id,
                    actor_display_name=ACTOR.user_display_name,
                    team_id=ACTOR.team_id,
                    action=AuditAction.UPDATE_MEMBERSHIP,
                    target_type=AuditTargetType.MEMBERSHIP,
                    target_id=uuid4(),
                    details={"changes": {"data_scope": {"from": "team", "to": "self"}}},
                    created_at=datetime(2026, 9, 4, tzinfo=UTC),
                ),
            ],
            total=1,
            page=kwargs["page"],  # type: ignore[arg-type]
            page_size=kwargs["page_size"],  # type: ignore[arg-type]
        )


def _request(application: object, path: str) -> Response:
    async def send() -> Response:
        transport = ASGITransport(app=application)  # type: ignore[arg-type]
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(send())


def test_access_administrator_can_list_paginated_audit_logs() -> None:
    service = ApiAuditLogService()
    application = create_app()
    application.dependency_overrides[get_super_account] = lambda: ACTOR
    application.dependency_overrides[get_audit_log_service] = lambda: service
    actor_user_id = uuid4()

    response = _request(
        application,
        "/api/v1/access-management/audit-logs?"
        f"page=2&page_size=10&actor_user_id={actor_user_id}&"
        "action=access_management.update_membership&"
        "created_from=2026-09-01T00%3A00%3A00Z&"
        "created_to=2026-09-05T00%3A00%3A00Z",
    )

    assert response.status_code == 200
    assert response.json()["page"] == 2
    assert response.json()["items"][0]["request_id"] == "request-audit-list"
    assert service.calls == [
        {
            "page": 2,
            "page_size": 10,
            "created_from": datetime(2026, 9, 1, tzinfo=UTC),
            "created_to": datetime(2026, 9, 5, tzinfo=UTC),
            "actor_user_id": actor_user_id,
            "action": AuditAction.UPDATE_MEMBERSHIP,
        },
    ]


def test_audit_log_list_rejects_non_administrator() -> None:
    application = create_app()
    application.dependency_overrides[get_actor_context] = lambda: ActorContext(
        user_id=uuid4(),
        user_display_name="普通成员",
        team_id=uuid4(),
        membership_id=uuid4(),
        role_code="member",
        data_scope=DataScope.TEAM,
    )

    response = _request(application, "/api/v1/access-management/audit-logs")

    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_ADMINISTRATION_FORBIDDEN"
