"""Concurrency check against the explicitly disposable GitHub CI database only."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, load_only

from app.modules.access.models import Team, TeamMembership
from app.modules.access.repository import ExecutionAuthorizationLockRepository
from app.modules.users.models import User
from app.modules.workers.repository import WorkerRepository


@pytest.fixture
def isolated_engine():
    raw_url = os.environ.get("BACKEND_DATABASE_URL")
    if not raw_url:
        pytest.skip("only the disposable PostgreSQL CI database is supported")
    url = make_url(raw_url)
    if (url.get_backend_name() != "postgresql"
            or url.database != "control_center_ci"
            or url.host not in {"127.0.0.1", "localhost"}):
        pytest.skip("database is not the explicitly guarded CI fixture")

    schema = "precheck_lock_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def seed_authorization(engine):
    user_id, team_id, device_id, shop_id, membership_id = [uuid4() for _ in range(5)]
    with engine.begin() as conn:
        for statement in (
            """CREATE TABLE users (user_id uuid PRIMARY KEY, display_name text DEFAULT 'test',
                   enabled boolean DEFAULT true, is_super_account boolean DEFAULT false)""",
            "CREATE TABLE teams (team_id uuid PRIMARY KEY, enabled boolean DEFAULT true)",
            """CREATE TABLE team_memberships (membership_id uuid PRIMARY KEY,
                   user_id uuid, team_id uuid REFERENCES teams(team_id), enabled boolean DEFAULT true)""",
            "CREATE TABLE team_module_accesses (team_id uuid REFERENCES teams(team_id), module_code text)",
            "CREATE TABLE team_device_accesses (team_id uuid REFERENCES teams(team_id), device_id uuid)",
            "CREATE TABLE team_shop_accesses (team_id uuid REFERENCES teams(team_id), shop_id uuid)",
        ):
            conn.execute(text(statement))
        values = dict(user_id=user_id, team_id=team_id, device_id=device_id,
                      shop_id=shop_id, membership_id=membership_id)
        for statement in (
            "INSERT INTO users (user_id) VALUES (:user_id)",
            "INSERT INTO teams (team_id) VALUES (:team_id)",
            "INSERT INTO team_memberships (membership_id, user_id, team_id) VALUES (:membership_id, :user_id, :team_id)",
            "INSERT INTO team_module_accesses VALUES (:team_id, 'task')",
            "INSERT INTO team_device_accesses VALUES (:team_id, :device_id)",
            "INSERT INTO team_shop_accesses VALUES (:team_id, :shop_id)",
        ):
            conn.execute(text(statement), values)
    return values


def test_authorization_row_cannot_be_revoked_during_sensitive_read(isolated_engine):
    engine = isolated_engine
    values = seed_authorization(engine)
    user_id, team_id, device_id, shop_id = (
        values["user_id"], values["team_id"], values["device_id"], values["shop_id"],
    )

    with Session(engine) as reader, Session(engine) as revoker:
        ExecutionAuthorizationLockRepository(reader).lock(
            user_id=user_id, team_id=team_id, device_id=device_id, shop_id=shop_id,
        )
        revoker.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(DBAPIError) as blocked:
            revoker.execute(text(
                "DELETE FROM team_shop_accesses WHERE team_id=:team_id AND shop_id=:shop_id"
            ), {"team_id": team_id, "shop_id": shop_id})
        assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
        revoker.rollback()
        reader.commit()
        result = revoker.execute(text(
            "DELETE FROM team_shop_accesses WHERE team_id=:team_id AND shop_id=:shop_id"
        ), {"team_id": team_id, "shop_id": shop_id})
        assert result.rowcount == 1
        revoker.commit()


@pytest.mark.parametrize("target", ["membership", "module", "device", "shop"])
def test_sensitive_read_does_not_wait_on_permission_update(isolated_engine, target):
    engine = isolated_engine
    values = seed_authorization(engine)
    sql = {
        "membership": "UPDATE team_memberships SET enabled=false WHERE membership_id=:membership_id",
        "module": "DELETE FROM team_module_accesses WHERE team_id=:team_id",
        "device": "DELETE FROM team_device_accesses WHERE team_id=:team_id",
        "shop": "DELETE FROM team_shop_accesses WHERE team_id=:team_id",
    }[target]
    with Session(engine) as editor, Session(engine) as reader:
        editor.execute(text(sql), values)
        repository = ExecutionAuthorizationLockRepository(reader)
        repository.set_lock_timeout()
        with pytest.raises(DBAPIError) as blocked:
            repository.lock(
                user_id=values["user_id"], team_id=values["team_id"],
                device_id=values["device_id"], shop_id=values["shop_id"],
            )
        assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
        reader.rollback()
        # The rejected read releases its Team lock, allowing the existing
        # archive/authorization transaction to finish.
        editor.execute(text("UPDATE teams SET enabled=false WHERE team_id=:team_id"), values)
        editor.commit()


def test_parallel_read_locks_and_newly_inserted_grant_are_distinguished(isolated_engine):
    engine = isolated_engine
    values = seed_authorization(engine)
    kwargs = dict(user_id=values["user_id"], team_id=values["team_id"],
                  device_id=values["device_id"], shop_id=values["shop_id"])
    with Session(engine) as first, Session(engine) as second:
        assert ExecutionAuthorizationLockRepository(first).lock(**kwargs).shop
        assert ExecutionAuthorizationLockRepository(second).lock(**kwargs).shop
        first.commit()
        second.commit()

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM team_shop_accesses WHERE team_id=:team_id"), values)
    with Session(engine) as reader, Session(engine) as writer:
        locked = ExecutionAuthorizationLockRepository(reader).lock(**kwargs)
        assert not locked.shop
        writer.execute(text("INSERT INTO team_shop_accesses VALUES (:team_id, :shop_id)"), values)
        writer.commit()
        assert reader.scalar(text("""
            SELECT count(*) FROM team_shop_accesses WHERE team_id=:team_id AND shop_id=:shop_id
        """), values) == 1
        # Even though a later unlocked query sees the new grant, the caller
        # must deny because this transaction never locked that grant row.
        assert not locked.shop
        reader.rollback()


def test_locked_authorization_refreshes_previously_loaded_orm_objects(isolated_engine):
    engine = isolated_engine
    values = seed_authorization(engine)
    with Session(engine) as reader, Session(engine) as revoker:
        user = reader.scalar(select(User).options(load_only(
            User.user_id, User.display_name, User.enabled, User.is_super_account,
        )).where(User.user_id == values["user_id"]))
        team = reader.scalar(select(Team).options(load_only(
            Team.team_id, Team.enabled,
        )).where(Team.team_id == values["team_id"]))
        membership = reader.scalar(select(TeamMembership).options(load_only(
            TeamMembership.membership_id, TeamMembership.user_id,
            TeamMembership.team_id, TeamMembership.enabled,
        )).where(TeamMembership.membership_id == values["membership_id"]))
        assert user.enabled and team.enabled and membership.enabled
        revoker.execute(text("UPDATE users SET enabled=false WHERE user_id=:user_id"), values)
        revoker.execute(text("UPDATE teams SET enabled=false WHERE team_id=:team_id"), values)
        revoker.execute(text("""
            UPDATE team_memberships SET enabled=false WHERE membership_id=:membership_id
        """), values)
        revoker.commit()
        ExecutionAuthorizationLockRepository(reader).lock(
            user_id=values["user_id"], team_id=values["team_id"],
            device_id=values["device_id"], shop_id=values["shop_id"],
        )
        assert not user.enabled and not team.enabled and not membership.enabled
        reader.rollback()


def test_table_lock_wait_is_bounded_by_transaction_timeout(isolated_engine):
    engine = isolated_engine
    values = seed_authorization(engine)
    with Session(engine) as ddl, Session(engine) as reader:
        ddl.execute(text("LOCK TABLE teams IN ACCESS EXCLUSIVE MODE"))
        repository = ExecutionAuthorizationLockRepository(reader)
        repository.set_lock_timeout()
        with pytest.raises(DBAPIError) as blocked:
            repository.lock(
                user_id=values["user_id"], team_id=values["team_id"],
                device_id=values["device_id"], shop_id=values["shop_id"],
            )
        assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
        reader.rollback()
        ddl.rollback()


def test_worker_credential_lock_refreshes_and_blocks_concurrent_changes(isolated_engine):
    engine = isolated_engine
    device_id, credential_id = uuid4(), uuid4()
    old_hash, rotated_hash = "a" * 64, "b" * 64
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE worker_device_credentials (
                credential_id uuid PRIMARY KEY, device_id uuid NOT NULL UNIQUE,
                token_hash varchar(64) NOT NULL UNIQUE, enabled boolean NOT NULL,
                created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now()
            )
        """))
        conn.execute(text("""
            INSERT INTO worker_device_credentials
                (credential_id, device_id, token_hash, enabled)
            VALUES (:credential_id, :device_id, :token_hash, true)
        """), {"credential_id": credential_id, "device_id": device_id, "token_hash": old_hash})

    # Authentication has already loaded an ORM object before revocation commits.
    with Session(engine) as reader, Session(engine) as revoker:
        repository = WorkerRepository(reader)
        authenticated = repository.get_credential(device_id)
        assert authenticated.enabled is True
        revoker.execute(text("""
            UPDATE worker_device_credentials SET enabled=false WHERE device_id=:device_id
        """), {"device_id": device_id})
        revoker.commit()
        locked = repository.get_credential_for_session_read(device_id)
        assert locked is authenticated and locked.enabled is False
        reader.commit()

    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE worker_device_credentials SET enabled=true WHERE device_id=:device_id
        """), {"device_id": device_id})
    with Session(engine) as reader, Session(engine) as rotator:
        repository = WorkerRepository(reader)
        authenticated = repository.get_credential(device_id)
        assert authenticated.token_hash == old_hash
        rotator.execute(text("""
            UPDATE worker_device_credentials SET token_hash=:token_hash WHERE device_id=:device_id
        """), {"device_id": device_id, "token_hash": rotated_hash})
        rotator.commit()
        locked = repository.get_credential_for_session_read(device_id)
        assert locked is authenticated and locked.token_hash == rotated_hash
        reader.commit()

    # A revocation cannot commit between the locked recheck and audit commit.
    with Session(engine) as reader, Session(engine) as revoker:
        assert WorkerRepository(reader).get_credential_for_session_read(device_id).enabled is True
        revoker.execute(text("SET LOCAL lock_timeout = '200ms'"))
        with pytest.raises(DBAPIError) as blocked:
            revoker.execute(text("""
                UPDATE worker_device_credentials SET enabled=false WHERE device_id=:device_id
            """), {"device_id": device_id})
        assert getattr(blocked.value.orig, "sqlstate", None) == "55P03"
        revoker.rollback()
        reader.commit()
        result = revoker.execute(text("""
            UPDATE worker_device_credentials SET enabled=false WHERE device_id=:device_id
        """), {"device_id": device_id})
        assert result.rowcount == 1
        revoker.commit()
