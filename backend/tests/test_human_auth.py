from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.core.database import Base, get_database_session
from app.main import create_app
from app.modules.access.exceptions import HumanUserDisabledError
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamMembership
from app.modules.human_auth.exceptions import (
    HumanBootstrapNotAllowedError,
    HumanLoginFailedError,
    HumanSessionInvalidError,
)
from app.modules.human_auth.api import _set_session_cookie
from app.modules.human_auth.models import HumanSession
from app.modules.human_auth.passwords import PasswordPolicyError, PasswordService
from app.modules.human_auth.schemas import HumanLoginRequest
from app.modules.human_auth.service import HumanAuthService
from app.modules.users.models import User


TEST_PASSWORD = "correct-horse-battery"


@pytest.fixture()
def database() -> tuple[sessionmaker[Session], Settings, PasswordService]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Team.__table__,
            TeamMembership.__table__,
            HumanSession.__table__,
        ],
    )
    return (
        sessionmaker(bind=engine, expire_on_commit=False),
        Settings(runtime_environment="test"),
        PasswordService(),
    )


def seed_user(
    factory: sessionmaker[Session],
    password_service: PasswordService,
    *,
    login_name: str = "operator",
    enabled: bool = True,
    credential: bool = True,
) -> tuple[User, Team]:
    user = User(
        user_id=uuid4(),
        display_name="测试人员",
        login_name=login_name,
        password_hash=(
            password_service.hash_password(TEST_PASSWORD) if credential else None
        ),
        enabled=enabled,
    )
    team = Team(team_id=uuid4(), name="默认团队", enabled=True)
    membership = TeamMembership(
        membership_id=uuid4(),
        team_id=team.team_id,
        user_id=user.user_id,
        role_code="member",
        data_scope=DataScope.TEAM.value,
        enabled=True,
    )
    with factory() as session:
        session.add_all([user, team, membership])
        session.commit()
    return user, team


def test_password_hash_uses_argon2_salt_and_rejects_invalid_values() -> None:
    service = PasswordService()
    first = service.hash_password(TEST_PASSWORD)
    second = service.hash_password(TEST_PASSWORD)

    assert first.startswith("$argon2")
    assert first != TEST_PASSWORD
    assert first != second
    assert service.verify_and_update(TEST_PASSWORD, first)[0] is True
    assert service.verify_and_update("wrong-password", first)[0] is False
    assert service.verify_and_update(TEST_PASSWORD, "not-a-valid-hash")[0] is False
    with pytest.raises(PasswordPolicyError):
        service.hash_password("")
    with pytest.raises(PasswordPolicyError):
        service.hash_password("short")
    with pytest.raises(PasswordPolicyError):
        service.hash_password("x" * 257)


def test_login_normalizes_case_and_never_persists_raw_token_or_password(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
    caplog: pytest.LogCaptureFixture,
) -> None:
    factory, settings, password_service = database
    user, _ = seed_user(factory, password_service)

    with factory() as session:
        service = HumanAuthService(session, settings, password_service)
        command = HumanLoginRequest(
            login_name="  OPERATOR ",
            password=TEST_PASSWORD,
        )
        result = service.login(command)
        second_result = service.login(
            HumanLoginRequest(login_name="operator", password=TEST_PASSWORD),
        )
        stored = session.scalar(select(HumanSession))

        assert stored is not None
        assert stored.user_id == user.user_id
        assert stored.token_hash == service.hash_token(result.raw_session_token)
        assert result.raw_session_token not in stored.token_hash
        assert len(result.raw_session_token) >= 64
        assert result.raw_session_token != second_result.raw_session_token
        assert TEST_PASSWORD not in (user.password_hash or "")
        assert result.principal.display_name == "测试人员"
        assert TEST_PASSWORD not in repr(command)
        assert result.raw_session_token not in repr(result)
        assert result.raw_session_token not in caplog.text
        assert TEST_PASSWORD not in caplog.text


def test_disabled_user_cannot_login(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
) -> None:
    factory, settings, password_service = database
    seed_user(factory, password_service, enabled=False)

    with factory() as session, pytest.raises(HumanUserDisabledError):
        HumanAuthService(session, settings, password_service).login(
            HumanLoginRequest(login_name="operator", password=TEST_PASSWORD),
        )


@pytest.mark.parametrize(
    ("login_name", "password", "credential"),
    [
        ("missing", TEST_PASSWORD, True),
        ("operator", "wrong-password", True),
        ("operator", TEST_PASSWORD, False),
    ],
)
def test_login_failure_has_one_public_error_semantic(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
    login_name: str,
    password: str,
    credential: bool,
) -> None:
    factory, settings, password_service = database
    if login_name == "operator":
        seed_user(factory, password_service, credential=credential)

    with factory() as session, pytest.raises(HumanLoginFailedError) as captured:
        HumanAuthService(session, settings, password_service).login(
            HumanLoginRequest(login_name=login_name, password=password),
        )
    assert captured.value.message == "登录账号或密码错误"
    assert password not in captured.value.message


def test_session_rejects_unknown_expired_revoked_missing_user_and_disabled_user(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
) -> None:
    factory, settings, password_service = database
    user, _ = seed_user(factory, password_service)
    now = datetime.now(UTC)

    with factory() as session:
        service = HumanAuthService(session, settings, password_service)
        with pytest.raises(HumanSessionInvalidError):
            service.resolve_principal("unknown-token", now=now)

        expired_token = "expired-token"
        revoked_token = "revoked-token"
        missing_user_token = "missing-user-token"
        session.add_all(
            [
                HumanSession(
                    session_id=uuid4(),
                    user_id=user.user_id,
                    token_hash=service.hash_token(expired_token),
                    expires_at=now - timedelta(seconds=1),
                    created_at=now - timedelta(hours=1),
                ),
                HumanSession(
                    session_id=uuid4(),
                    user_id=user.user_id,
                    token_hash=service.hash_token(revoked_token),
                    expires_at=now + timedelta(hours=1),
                    revoked_at=now,
                    created_at=now - timedelta(minutes=1),
                ),
                HumanSession(
                    session_id=uuid4(),
                    user_id=uuid4(),
                    token_hash=service.hash_token(missing_user_token),
                    expires_at=now + timedelta(hours=1),
                    created_at=now - timedelta(minutes=1),
                ),
            ],
        )
        session.commit()

        for token in (expired_token, revoked_token, missing_user_token):
            with pytest.raises(HumanSessionInvalidError):
                service.resolve_principal(token, now=now)

        result = service.login(
            HumanLoginRequest(login_name="operator", password=TEST_PASSWORD),
            now=now,
        )
        persisted_user = session.get(User, user.user_id)
        assert persisted_user is not None
        persisted_user.enabled = False
        session.commit()
        with pytest.raises(HumanUserDisabledError):
            service.resolve_principal(result.raw_session_token, now=now)


def test_password_reset_revokes_existing_sessions(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
) -> None:
    factory, settings, password_service = database
    user, _ = seed_user(factory, password_service)
    with factory() as session:
        service = HumanAuthService(session, settings, password_service)
        login = service.login(
            HumanLoginRequest(login_name="operator", password=TEST_PASSWORD),
        )
        service.set_credentials(
            user_id=user.user_id,
            login_name="New.Operator",
            password="new-correct-password",
        )

        with pytest.raises(HumanSessionInvalidError):
            service.resolve_principal(login.raw_session_token)
        assert session.get(User, user.user_id).login_name == "new.operator"


def test_bootstrap_only_works_for_zero_users_and_creates_a_super_account(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
) -> None:
    factory, settings, password_service = database
    with factory() as session:
        service = HumanAuthService(session, settings, password_service)
        user = service.bootstrap_first_user(
            display_name="首位人员",
            login_name="First.User",
            password=TEST_PASSWORD,
        )
        membership = session.scalar(
            select(TeamMembership).where(TeamMembership.user_id == user.user_id),
        )

        assert user.login_name == "first.user"
        assert user.is_super_account is True
        assert membership is None
        with pytest.raises(HumanBootstrapNotAllowedError):
            service.bootstrap_first_user(
                display_name="第二位",
                login_name="second",
                password=TEST_PASSWORD,
            )


def test_bootstrap_does_not_depend_on_a_default_team(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
) -> None:
    factory, settings, password_service = database
    with factory() as session:
        session.add(Team(team_id=uuid4(), name="默认团队", enabled=False))
        session.commit()

        user = HumanAuthService(session, settings, password_service).bootstrap_first_user(
            display_name="首位人员",
            login_name="first.user",
            password=TEST_PASSWORD,
        )

        assert user.is_super_account is True


def test_human_auth_api_cookie_restore_single_team_and_logout(
    database: tuple[sessionmaker[Session], Settings, PasswordService],
) -> None:
    factory, settings, password_service = database
    user, first_team = seed_user(factory, password_service)
    application = create_app()

    def override_database_session():
        with factory() as session:
            yield session

    application.dependency_overrides[get_database_session] = override_database_session
    application.dependency_overrides[get_settings] = lambda: settings

    async def exercise() -> None:
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"login_name": "OPERATOR", "password": TEST_PASSWORD},
            )
            assert login.status_code == 200
            assert login.json() == {
                "user_id": str(user.user_id),
                "display_name": "测试人员",
            }
            assert "password" not in login.text
            cookie = login.headers["set-cookie"]
            assert "HttpOnly" in cookie
            assert "SameSite=lax" in cookie
            assert "Path=/api/v1" in cookie
            assert "Secure" not in cookie

            current = await client.get("/api/v1/auth/me")
            teams = await client.get("/api/v1/access/me/teams")
            default_team = await client.get("/api/v1/access/me")
            selected_team = await client.get(
                "/api/v1/access/me",
                headers={"X-Team-ID": str(first_team.team_id)},
            )
            assert current.status_code == 200
            assert teams.status_code == 200
            assert len(teams.json()) == 1
            assert default_team.status_code == 200
            assert default_team.json()["team_id"] == str(first_team.team_id)
            assert selected_team.status_code == 200
            assert selected_team.json()["team_id"] == str(first_team.team_id)

            logout = await client.post("/api/v1/auth/logout")
            assert logout.status_code == 204
            assert "Max-Age=0" in logout.headers["set-cookie"]
            assert (await client.post("/api/v1/auth/logout")).status_code == 204
            anonymous = await client.get("/api/v1/auth/me")
            assert anonymous.status_code == 401
            assert anonymous.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"

    asyncio.run(exercise())


def test_settings_reject_insecure_production_and_wildcard_credential_cors() -> None:
    with pytest.raises(ValueError):
        Settings(runtime_environment="production", human_session_cookie_secure=False)
    with pytest.raises(ValueError):
        Settings(cors_allowed_origins=["*"])
    with pytest.raises(ValueError):
        Settings(cors_allowed_origins=["https://console.example.com/path"])
    with pytest.raises(ValueError):
        Settings(cors_allowed_origins=["file:///local-console"])
    with pytest.raises(ValueError):
        Settings(
            human_session_cookie_samesite="none",
            human_session_cookie_secure=False,
        )
    production = Settings(
        runtime_environment="production",
        human_session_cookie_secure=True,
        cors_allowed_origins=["https://console.example.com/"],
    )
    assert production.cors_allowed_origins == ["https://console.example.com"]


def test_production_session_cookie_is_http_only_secure_and_scoped_to_api() -> None:
    from fastapi import Response

    response = Response()
    settings = Settings(
        runtime_environment="production",
        human_session_cookie_secure=True,
    )
    _set_session_cookie(
        response,
        raw_token="test-session-token",
        settings=settings,
    )

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1" in cookie
    assert "Max-Age=604800" in cookie


def test_credential_cors_only_allows_the_explicit_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = Settings(
        runtime_environment="test",
        cors_allowed_origins=["https://console.example.com"],
    )
    monkeypatch.setattr("app.main.get_settings", lambda: configured)
    application = create_app()

    async def exercise() -> None:
        transport = ASGITransport(app=application)
        async with AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            allowed = await client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "https://console.example.com",
                    "Access-Control-Request-Method": "POST",
                },
            )
            rejected = await client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "https://evil.example.com",
                    "Access-Control-Request-Method": "POST",
                },
            )

            assert allowed.status_code == 200
            assert allowed.headers["access-control-allow-origin"] == (
                "https://console.example.com"
            )
            assert allowed.headers["access-control-allow-credentials"] == "true"
            assert "access-control-allow-origin" not in rejected.headers

    asyncio.run(exercise())
