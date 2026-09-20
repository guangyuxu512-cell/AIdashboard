from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, delete, inspect, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import HumanPrincipal
from app.modules.access.enums import DataScope
from app.modules.access.models import (
    Team,
    TeamDeviceAccess,
    TeamMembership,
    TeamModuleAccess,
    TeamShopAccess,
)
from app.modules.access.module_access import ModuleCode
from app.modules.access.schemas import (
    AccessMemberCreate,
    AccessMemberTeamUpdate,
    TeamAuthorizationUpdate,
    TeamCreate,
)
from app.modules.access.service import (
    AccessManagementService,
    ActorContextService,
)
from app.modules.users.models import User
from app.modules.human_auth.passwords import PasswordService


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
        if team_ids:
            session.execute(
                delete(TeamModuleAccess).where(
                    TeamModuleAccess.team_id.in_(team_ids),
                ),
            )
            session.execute(
                delete(TeamDeviceAccess).where(
                    TeamDeviceAccess.team_id.in_(team_ids),
                ),
            )
            session.execute(
                delete(TeamShopAccess).where(
                    TeamShopAccess.team_id.in_(team_ids),
                ),
            )
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


def _cleanup_stale_fixture_rows(engine: Engine) -> None:
    """Recover only this test's rows if a previous assertion aborted cleanup."""

    with Session(engine) as session:
        team_ids = set(
            session.scalars(
                select(Team.team_id).where(Team.name.like(f"{TEST_PREFIX}%")),
            ),
        )
        user_ids = set(
            session.scalars(
                select(User.user_id).where(
                    User.display_name.like(f"{TEST_PREFIX}%"),
                ),
            ),
        )
        membership_ids = set(
            session.scalars(
                select(TeamMembership.membership_id).where(
                    TeamMembership.team_id.in_(team_ids),
                ),
            ),
        ) if team_ids else set()
    _cleanup(
        engine,
        membership_ids=membership_ids,
        team_ids=team_ids,
        user_ids=user_ids,
    )


def _member_input(team_id: UUID, *, login_name: str) -> AccessMemberCreate:
    return AccessMemberCreate(
        display_name=f"{TEST_PREFIX}-{login_name}",
        login_name=login_name,
        password="correct-horse-battery",
        team_id=team_id,
    )


def test_postgresql_access_schema_constraints_and_services(
    postgresql_engine: Engine,
) -> None:
    _cleanup_stale_fixture_rows(postgresql_engine)
    inspector = inspect(postgresql_engine)
    assert {
        "teams",
        "team_memberships",
        "team_module_accesses",
        "team_device_accesses",
        "team_shop_accesses",
    } <= set(inspector.get_table_names())

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
    assert "uq_team_memberships_one_active_user" in membership_indexes
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
            service = AccessManagementService(session, PasswordService())
            first_team = service.create_team(
                TeamCreate(name=f"{TEST_PREFIX}-first"),
            )
            second_team = service.create_team(
                TeamCreate(name=f"{TEST_PREFIX}-second"),
            )
            third_team = service.create_team(
                TeamCreate(name=f"{TEST_PREFIX}-third"),
            )
            team_ids.update(
                {first_team.team_id, second_team.team_id, third_team.team_id},
            )
            service.update_team_authorization(
                first_team.team_id,
                TeamAuthorizationUpdate(module_codes=[ModuleCode.DEVICE]),
            )
            member = service.create_member(
                _member_input(
                    first_team.team_id,
                    login_name=f"{TEST_PREFIX}-user",
                ),
            )
            user_ids.add(member.user_id)
            membership_ids.add(member.memberships[0].membership_id)
            moved = service.move_member_to_team(
                member.user_id,
                AccessMemberTeamUpdate(team_id=second_team.team_id),
            )
            membership_ids.update(item.membership_id for item in moved.memberships)

            actor = ActorContextService(session).resolve(
                user_id=member.user_id,
                requested_team_id=second_team.team_id,
            )
            assert actor.team_id == second_team.team_id
            assert actor.role_code == "member"
            assert actor.data_scope is DataScope.TEAM

        duplicate = TeamMembership(
            membership_id=uuid4(),
            team_id=third_team.team_id,
            user_id=member.user_id,
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
                        user_id=member.user_id,
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
                        user_id=member.user_id,
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
    _cleanup_stale_fixture_rows(postgresql_engine)
    user_ids: set[UUID] = set()
    team_ids: set[UUID] = set()
    membership_ids: set[UUID] = set()
    with Session(postgresql_engine, expire_on_commit=False) as session:
        service = AccessManagementService(session, PasswordService())
        team = service.create_team(TeamCreate(name=f"{TEST_PREFIX}-api"))
        team_ids.add(team.team_id)
        member = service.create_member(
            _member_input(team.team_id, login_name=f"{TEST_PREFIX}-api-user"),
        )
        user_ids.add(member.user_id)
        membership_ids.add(member.memberships[0].membership_id)

    async def exercise() -> None:
        application = create_app()
        application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
            user_id=member.user_id,
            display_name=member.display_name,
        )
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            resolved_context = await client.get("/api/v1/access/me")
            selected_context = await client.get(
                "/api/v1/access/me",
                headers={"X-Team-ID": str(team.team_id)},
            )
            invalid_context = await client.get(
                "/api/v1/access/me",
                headers={"X-Team-ID": str(uuid4())},
            )
            my_teams = await client.get("/api/v1/access/me/teams")

        assert resolved_context.status_code == 200
        assert resolved_context.json()["team_id"] == str(team.team_id)
        assert selected_context.status_code == 200
        assert selected_context.json()["team_id"] == str(team.team_id)
        assert invalid_context.status_code == 403
        assert invalid_context.json()["code"] == "TEAM_ACCESS_DENIED"
        assert my_teams.status_code == 200
        assert {item["team_id"] for item in my_teams.json()} == {str(team.team_id)}

    try:
        asyncio.run(exercise())
    finally:
        _cleanup(
            postgresql_engine,
            membership_ids=membership_ids,
            team_ids=team_ids,
            user_ids=user_ids,
        )
