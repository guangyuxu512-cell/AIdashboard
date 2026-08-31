from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import (
    ActorContext,
    HumanPrincipal,
    TeamMembershipSummary,
)
from app.modules.access.dependencies import get_actor_context_service
from app.modules.access.enums import DataScope


USER_ID = uuid4()
TEAM_ID = uuid4()
MEMBERSHIP_ID = uuid4()


class ApiActorContextService:
    requested_team_id: UUID | None = None

    def resolve(
        self,
        *,
        user_id: UUID,
        requested_team_id: UUID | None,
    ) -> ActorContext:
        type(self).requested_team_id = requested_team_id
        return ActorContext(
            user_id=user_id,
            user_display_name="API 用户",
            team_id=requested_team_id or TEAM_ID,
            membership_id=MEMBERSHIP_ID,
            role_code="member",
            data_scope=DataScope.TEAM,
        )

    def list_my_teams(self, user_id: UUID) -> list[TeamMembershipSummary]:
        return [
            TeamMembershipSummary(
                membership_id=MEMBERSHIP_ID,
                team_id=TEAM_ID,
                team_name="默认团队",
                team_enabled=True,
                role_code="member",
                data_scope=DataScope.TEAM,
                membership_enabled=True,
            ),
        ]


def request(
    method: str,
    path: str,
    *,
    authenticated: bool,
    headers: dict[str, str] | None = None,
) -> Response:
    application = create_app()
    if authenticated:
        application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
            user_id=USER_ID,
            display_name="API 用户",
        )
        application.dependency_overrides[get_actor_context_service] = (
            ApiActorContextService
        )

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, headers=headers)

    return asyncio.run(send())


def test_access_api_fails_closed_without_human_authentication() -> None:
    response = request("GET", "/api/v1/access/me", authenticated=False)

    assert response.status_code == 401
    assert response.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"


def test_current_actor_uses_validated_team_context_header() -> None:
    selected_team_id = uuid4()
    response = request(
        "GET",
        "/api/v1/access/me",
        authenticated=True,
        headers={"X-Team-ID": str(selected_team_id)},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(USER_ID)
    assert response.json()["team_id"] == str(selected_team_id)
    assert response.json()["data_scope"] == "team"
    assert ApiActorContextService.requested_team_id == selected_team_id


def test_my_teams_does_not_require_an_active_team_selection() -> None:
    response = request(
        "GET",
        "/api/v1/access/me/teams",
        authenticated=True,
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "membership_id": str(MEMBERSHIP_ID),
            "team_id": str(TEAM_ID),
            "team_name": "默认团队",
            "team_enabled": True,
            "role_code": "member",
            "data_scope": "team",
            "membership_enabled": True,
        },
    ]
