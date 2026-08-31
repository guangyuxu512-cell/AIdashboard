from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, delete, inspect, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.access.models import Team, TeamMembership
from app.modules.human_auth.models import HumanSession
from app.modules.human_auth.passwords import PasswordService
from app.modules.users.models import User


pytestmark = pytest.mark.integration


def test_postgresql_human_auth_schema_and_cookie_identity_chain(
    postgresql_engine: Engine,
) -> None:
    inspector = inspect(postgresql_engine)
    assert "human_sessions" in inspector.get_table_names()
    assert {"login_name", "password_hash"} <= {
        column["name"] for column in inspector.get_columns("users")
    }
    assert {index["name"] for index in inspector.get_indexes("human_sessions")} >= {
        "ix_human_sessions_token_hash",
        "ix_human_sessions_user_id",
    }
    assert {
        constraint["name"] for constraint in inspector.get_unique_constraints("users")
    } >= {
        "uq_users_login_name",
    }

    password_service = PasswordService()
    user_id = uuid4()
    team_id = uuid4()
    membership_id = uuid4()
    with Session(postgresql_engine) as session:
        session.add_all(
            [
                User(
                    user_id=user_id,
                    display_name="PostgreSQL认证用户",
                    login_name="postgresql-auth-user",
                    password_hash=password_service.hash_password(
                        "postgresql-safe-password",
                    ),
                    enabled=True,
                ),
                Team(team_id=team_id, name="PostgreSQL认证团队", enabled=True),
            ],
        )
        session.flush()
        session.add(
            TeamMembership(
                membership_id=membership_id,
                team_id=team_id,
                user_id=user_id,
                role_code="member",
                data_scope="team",
                enabled=True,
            ),
        )
        session.commit()

    async def exercise() -> None:
        transport = ASGITransport(app=create_app())
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={
                    "login_name": "POSTGRESQL-AUTH-USER",
                    "password": "postgresql-safe-password",
                },
            )
            assert login.status_code == 200
            assert "siyu_human_session" in login.cookies
            assert (await client.get("/api/v1/auth/me")).status_code == 200
            actor = await client.get("/api/v1/access/me")
            assert actor.status_code == 200
            assert actor.json()["team_id"] == str(team_id)
            assert (await client.post("/api/v1/auth/logout")).status_code == 204
            assert (await client.get("/api/v1/auth/me")).status_code == 401

    try:
        asyncio.run(exercise())
        with Session(postgresql_engine) as session:
            stored = session.scalar(
                select(HumanSession).where(HumanSession.user_id == user_id),
            )
            assert stored is not None
            assert len(stored.token_hash) == 64
            assert stored.revoked_at is not None
    finally:
        with Session(postgresql_engine) as session:
            session.execute(delete(HumanSession).where(HumanSession.user_id == user_id))
            session.execute(
                delete(TeamMembership).where(
                    TeamMembership.membership_id == membership_id,
                ),
            )
            session.execute(delete(Team).where(Team.team_id == team_id))
            session.execute(delete(User).where(User.user_id == user_id))
            session.commit()
