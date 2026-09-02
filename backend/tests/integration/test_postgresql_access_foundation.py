from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, delete, inspect, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import HumanPrincipal
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamMembership
from app.modules.access.schemas import TeamCreate, TeamMembershipCreate
from app.modules.access.service import (
    ActorContextService,
    MembershipService,
    TeamService,
)
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate
from app.modules.users.service import UserService


pytestmark = pytest.mark.integration
TEST_PREFIX = "access-foundation-v1"


def _cleanup(
    engine: Engine,
    *,
    membership_ids: set[UUID],
    team_ids: set[UUID],
    user_ids: set[UUID],
) -> None:
    with Session(engine) as session:
        if membership_ids:
            session.execute(
                delete(TeamMembership).where(
                    TeamMembership.membership_id.in_(membership_ids),
                ),
            )
        if team_ids:
            session.execute(delete(Team).where(Team.team_id.in_(team_ids)))
        if user_ids:
            session.execute(delete(User).where(User.user_id.in_(user_ids)))
        session.commit()


def test_postgresql_access_schema_constraints_and_services(
    postgresql_engine: Engine,
) -> None:
    inspector = inspect(postgresql_engine)
    assert {"teams", "team_memberships"} <= set(inspector.get_table_names())

    membership_unique_constraints = {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints("team_memberships")
    }
    assert membership_unique_constraints["uq_team_memberships_team_user"] == [
        "team_id",
        "user_id",
    ]
    membership_indexes = {
        index["name"]: index for index in inspector.get_indexes("team_memberships")
    }
    assert "ix_team_memberships_user_id" in membership_indexes
    assert "ix_team_memberships_active_user" in membership_indexes
    assert "ix_team_memberships_active_team" in membership_indexes
    assert (
        membership_indexes["ix_team_memberships_active_user"]["dialect_options"][
            "postgresql_where"
        ]
        == "enabled"
    )
    membership_foreign_keys = {
        (tuple(key["constrained_columns"]), key["referred_table"])
        for key in inspector.get_foreign_keys("team_memberships")
    }
    assert membership_foreign_keys == {
        (("team_id",), "teams"),
        (("user_id",), "users"),
    }
    membership_checks = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("team_memberships")
    }
    assert {
        "ck_team_memberships_data_scope",
        "ck_team_memberships_role_code_not_blank",
    } <= membership_checks

    user_ids: set[UUID] = set()
    team_ids: set[UUID] = set()
    membership_ids: set[UUID] = set()
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            user = UserService(session).create(
                UserCreate(display_name=f"{TEST_PREFIX}-user"),
            )
            user_ids.add(user.user_id)
            first_team = TeamService(session).create(
                TeamCreate(name=f"{TEST_PREFIX}-first"),
            )
            second_team = TeamService(session).create(
                TeamCreate(name=f"{TEST_PREFIX}-second"),
            )
            team_ids.update({first_team.team_id, second_team.team_id})

            membership_service = MembershipService(session)
            first_membership = membership_service.create(
                TeamMembershipCreate(
                    team_id=first_team.team_id,
                    user_id=user.user_id,
                    role_code="member",
                    data_scope=DataScope.TEAM,
                ),
            )
            second_membership = membership_service.create(
                TeamMembershipCreate(
                    team_id=second_team.team_id,
                    user_id=user.user_id,
                    role_code="reviewer",
                    data_scope=DataScope.SELF,
                ),
            )
            membership_ids.update(
                {first_membership.membership_id, second_membership.membership_id},
            )

            actor = ActorContextService(session).resolve(
                user_id=user.user_id,
                requested_team_id=second_team.team_id,
            )
            assert actor.team_id == second_team.team_id
            assert actor.role_code == "reviewer"
            assert actor.data_scope is DataScope.SELF

        duplicate = TeamMembership(
            membership_id=uuid4(),
            team_id=first_team.team_id,
            user_id=user.user_id,
            role_code="member",
            data_scope=DataScope.TEAM,
        )
        with Session(postgresql_engine) as session:
            session.add(duplicate)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with Session(postgresql_engine) as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    insert(TeamMembership).values(
                        membership_id=uuid4(),
                        team_id=first_team.team_id,
                        user_id=user.user_id,
                        role_code="member",
                        data_scope="nope",
                        enabled=True,
                    ),
                )
                session.commit()
            session.rollback()

        with Session(postgresql_engine) as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    insert(TeamMembership).values(
                        membership_id=uuid4(),
                        team_id=uuid4(),
                        user_id=user.user_id,
                        role_code="member",
                        data_scope="team",
                        enabled=True,
                    ),
                )
                session.commit()
            session.rollback()
    finally:
        _cleanup(
            postgresql_engine,
            membership_ids=membership_ids,
            team_ids=team_ids,
            user_ids=user_ids,
        )


def test_postgresql_access_http_resolves_active_team(
    postgresql_engine: Engine,
) -> None:
    user_ids: set[UUID] = set()
    team_ids: set[UUID] = set()
    membership_ids: set[UUID] = set()
    with Session(postgresql_engine, expire_on_commit=False) as session:
        user = UserService(session).create(
            UserCreate(display_name=f"{TEST_PREFIX}-api-user"),
        )
        user_ids.add(user.user_id)
        teams = [
            TeamService(session).create(
                TeamCreate(name=f"{TEST_PREFIX}-api-{position}"),
            )
            for position in range(2)
        ]
        team_ids.update(team.team_id for team in teams)
        memberships = [
            MembershipService(session).create(
                TeamMembershipCreate(
                    team_id=team.team_id,
                    user_id=user.user_id,
                    data_scope=DataScope.TEAM,
                ),
            )
            for team in teams
        ]
        membership_ids.update(membership.membership_id for membership in memberships)

    async def exercise() -> None:
        application = create_app()
        application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
            user_id=user.user_id,
            display_name=user.display_name,
        )
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            missing_context = await client.get("/api/v1/access/me")
            selected_context = await client.get(
                "/api/v1/access/me",
                headers={"X-Team-ID": str(teams[1].team_id)},
            )
            invalid_context = await client.get(
                "/api/v1/access/me",
                headers={"X-Team-ID": str(uuid4())},
            )
            my_teams = await client.get("/api/v1/access/me/teams")

        assert missing_context.status_code == 409
        assert missing_context.json()["code"] == "TEAM_CONTEXT_REQUIRED"
        assert selected_context.status_code == 200
        assert selected_context.json()["team_id"] == str(teams[1].team_id)
        assert invalid_context.status_code == 403
        assert invalid_context.json()["code"] == "TEAM_ACCESS_DENIED"
        assert my_teams.status_code == 200
        assert {item["team_id"] for item in my_teams.json()} == {
            str(team.team_id) for team in teams
        }

    try:
        asyncio.run(exercise())
    finally:
        _cleanup(
            postgresql_engine,
            membership_ids=membership_ids,
            team_ids=team_ids,
            user_ids=user_ids,
        )
