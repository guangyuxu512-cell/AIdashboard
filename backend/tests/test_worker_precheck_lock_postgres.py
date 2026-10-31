"""Concurrency check against the explicitly disposable GitHub CI database only."""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, load_only

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.security import SecretCipher
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import Team, TeamMembership
from app.modules.access.module_access import ModuleCode
from app.modules.access.repository import (
    ExecutionAuthorizationLockRepository, MembershipRepository, TeamModuleAccessRepository,
)
from app.modules.access.schemas import TeamAuthorizationUpdate
from app.modules.access.service import AccessManagementService
from app.modules.sessions.exceptions import ShopSessionReadBusyError
from app.modules.sessions.worker_task_service import WorkerTaskSessionService
from app.modules.users.models import User
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.security import hash_worker_token
from app.modules.workers.service import WorkerService


@pytest.fixture
def isolated_engine():
    raw_url = os.environ.get("BACKEND_DATABASE_URL")
    if not raw_url:
        pytest.skip("only the disposable PostgreSQL CI database is supported")
    url = make_url(raw_url)
    if (url.get_backend_name() != "postgresql"
            or url.database != "control_center_ci"
            or url.username != "control_center_ci"
            or url.host not in {"127.0.0.1", "localhost"}):
        pytest.skip("database is not the explicitly guarded CI fixture")

    schema = "precheck_lock_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})

    @event.listens_for(engine, "connect")
    def verify_connection_isolation(dbapi_connection, _connection_record):
        # Connection-level options persist across the service's own commits.
        # Do not include public as a fallback schema for synthetic test data.
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_schema()")
            assert cursor.fetchone() == ("control_center_ci", schema)
        dbapi_connection.rollback()

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


def _foreign_keys(conn, schema, tables):
    return conn.execute(text("""
        SELECT source.relname::text AS source_table,
               ARRAY(SELECT att.attname::text
                     FROM unnest(con.conkey) WITH ORDINALITY AS item(attnum, pos)
                     JOIN pg_attribute att ON att.attrelid=source.oid AND att.attnum=item.attnum
                     ORDER BY item.pos) AS source_columns,
               target_ns.nspname::text AS target_schema, target.relname::text AS target_table,
               ARRAY(SELECT att.attname::text
                     FROM unnest(con.confkey) WITH ORDINALITY AS item(attnum, pos)
                     JOIN pg_attribute att ON att.attrelid=target.oid AND att.attnum=item.attnum
                     ORDER BY item.pos) AS target_columns,
               con.confdeltype, con.confupdtype, con.confmatchtype,
               con.condeferrable, con.condeferred, con.convalidated
        FROM pg_constraint con
        JOIN pg_class source ON source.oid=con.conrelid
        JOIN pg_namespace source_ns ON source_ns.oid=source.relnamespace
        JOIN pg_class target ON target.oid=con.confrelid
        JOIN pg_namespace target_ns ON target_ns.oid=target.relnamespace
        WHERE con.contype='f' AND source_ns.nspname=:schema
          AND source.relname::text = ANY(:tables)
    """), {"schema": schema, "tables": list(tables)}).mappings().all()


def _foreign_key_signature(row):
    return (
        row["source_table"], tuple(row["source_columns"]), row["target_table"],
        tuple(row["target_columns"]), row["confdeltype"], row["confupdtype"],
        row["confmatchtype"], row["condeferrable"], row["condeferred"], row["convalidated"],
    )


def _identifier(value):
    assert re.fullmatch(r"[a-z_][a-z0-9_]*", value)
    return f'"{value}"'


def _session_audit_count(session, task_id):
    return session.scalar(text("""
        SELECT count(*) FROM audit_logs
        WHERE action='session.read_for_task' AND details->>'task_id'=:task_id
    """), {"task_id": str(task_id)})


def _synthetic_actor(ids):
    return ActorContext(
        user_id=ids["user_id"], user_display_name="Synthetic user",
        team_id=ids["team_id"], membership_id=ids["membership_id"],
        role_code="member", data_scope=DataScope.TEAM,
    )


@pytest.fixture
def real_service_fixture(isolated_engine):
    """Clone the guarded CI schema's FK closure; no triggers or real data."""
    engine = isolated_engine
    tables = (
        "users", "teams", "team_memberships", "team_module_accesses",
        "devices", "shops", "team_device_accesses", "team_shop_accesses",
        "shop_device_bindings", "worker_device_credentials", "shop_sessions",
        "tasks", "task_shops", "audit_logs", "human_sessions",
        "automation_parameter_presets",
    )
    ids = {name: uuid4() for name in (
        "user_id", "team_id", "membership_id", "device_id", "shop_id",
        "worker_credential_id", "shop_session_id", "task_id",
    )}
    token = "ccw_synthetic_ci_token"
    secret = "synthetic-ci-cookie"
    cipher = SecretCipher(Fernet.generate_key().decode())
    captured_at = datetime.now(UTC)
    payload = cipher.encrypt_bytes(json.dumps({
        "schema": "management-login.session.v1",
        "platform": "douyin",
        "identity": {
            "platform": "douyin", "platformShopId": "synthetic-platform-shop",
            "shopDisplayName": "Synthetic shop",
        },
        "cookies": [{"name": "sessionid", "value": secret}],
    }).encode())
    values = ids | {
        "token_hash": hash_worker_token(token),
        "payload": payload,
        "captured_at": captured_at,
        "lease_until": captured_at + timedelta(minutes=5),
    }
    with engine.begin() as conn:
        schema = conn.scalar(text("SELECT current_schema()"))
        assert schema and schema.startswith("precheck_lock_")
        defaults = conn.execute(text("""
            SELECT pg_get_expr(def.adbin, def.adrelid) AS expression
            FROM pg_attrdef def
            JOIN pg_class rel ON rel.oid=def.adrelid
            JOIN pg_namespace ns ON ns.oid=rel.relnamespace
            WHERE ns.nspname='public' AND rel.relname::text = ANY(:tables)
        """), {"tables": list(tables)}).scalars().all()
        for expression in defaults:
            assert "public." not in expression.lower()
            calls = re.findall(r"([a-zA-Z_][a-zA-Z0-9_.]*)\s*\(", expression)
            assert all(call.lower() in {"now", "pg_catalog.now"} for call in calls), expression

        source_fks = _foreign_keys(conn, "public", tables)
        assert len(source_fks) == 27
        assert all(row["target_schema"] == "public" and row["target_table"] in tables
                   for row in source_fks)
        for table in tables:
            conn.execute(text(
                f'CREATE TABLE {_identifier(schema)}.{_identifier(table)} '
                f'(LIKE public.{_identifier(table)} INCLUDING ALL)',
            ))
        actions = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE",
                   "n": "SET NULL", "d": "SET DEFAULT"}
        for row in source_fks:
            assert row["confmatchtype"] in {"s", "f"}
            source_columns = ", ".join(_identifier(c) for c in row["source_columns"])
            target_columns = ", ".join(_identifier(c) for c in row["target_columns"])
            match = "SIMPLE" if row["confmatchtype"] == "s" else "FULL"
            deferred = (" DEFERRABLE INITIALLY DEFERRED" if row["condeferred"]
                        else " DEFERRABLE INITIALLY IMMEDIATE")
            deferrability = deferred if row["condeferrable"] else " NOT DEFERRABLE"
            validation = "" if row["convalidated"] else " NOT VALID"
            conn.execute(text(
                f'ALTER TABLE {_identifier(schema)}.{_identifier(row["source_table"])} '
                f'ADD FOREIGN KEY ({source_columns}) REFERENCES '
                f'{_identifier(schema)}.{_identifier(row["target_table"])} ({target_columns}) '
                f'MATCH {match} ON UPDATE {actions[row["confupdtype"]]} '
                f'ON DELETE {actions[row["confdeltype"]]}{deferrability}{validation}',
            ))
        cloned_fks = _foreign_keys(conn, schema, tables)
        assert all(row["target_schema"] == schema for row in cloned_fks)
        assert sorted(map(_foreign_key_signature, source_fks)) == sorted(
            map(_foreign_key_signature, cloned_fks),
        )
        for statement in (
            "INSERT INTO users (user_id, display_name, enabled, is_super_account) "
            "VALUES (:user_id, 'Synthetic user', true, false)",
            "INSERT INTO teams (team_id, name, enabled) VALUES (:team_id, 'Synthetic team', true)",
            "INSERT INTO team_memberships (membership_id, user_id, team_id, role_code, data_scope, enabled) "
            "VALUES (:membership_id, :user_id, :team_id, 'member', 'team', true)",
            "INSERT INTO team_module_accesses (team_id, module_code) VALUES (:team_id, 'task')",
            "INSERT INTO devices (device_id, team_id, created_by_user_id, display_name, enabled) "
            "VALUES (:device_id, :team_id, :user_id, 'Synthetic device', true)",
            "INSERT INTO shops (shop_id, display_name, platform, platform_shop_id, enabled) "
            "VALUES (:shop_id, 'Synthetic shop', 'douyin', 'synthetic-platform-shop', true)",
            "INSERT INTO team_device_accesses (team_id, device_id) VALUES (:team_id, :device_id)",
            "INSERT INTO team_shop_accesses (team_id, shop_id) VALUES (:team_id, :shop_id)",
            "INSERT INTO shop_device_bindings (shop_id, device_id, enabled) VALUES (:shop_id, :device_id, true)",
            "INSERT INTO worker_device_credentials (credential_id, device_id, token_hash, enabled) "
            "VALUES (:worker_credential_id, :device_id, :token_hash, true)",
            "INSERT INTO shop_sessions (session_id, shop_id, version, status, captured_at, payload_encrypted) "
            "VALUES (:shop_session_id, :shop_id, 1, 'captured', :captured_at, :payload)",
            "INSERT INTO tasks (task_id, team_id, created_by_user_id, target_device_id, skill_id, "
            "execution_display_name, status, input_json, lease_until) "
            "VALUES (:task_id, :team_id, :user_id, :device_id, 'product.precheck', "
            "'Synthetic precheck', 'running', CAST('{}' AS jsonb), :lease_until)",
            "INSERT INTO task_shops (task_id, shop_id, position) VALUES (:task_id, :shop_id, 0)",
        ):
            conn.execute(text(statement), values)
    return ids, token, secret, cipher


def test_real_service_commits_audit_with_foreign_keys_before_return(
    isolated_engine, real_service_fixture,
):
    ids, token, secret, cipher = real_service_fixture
    with Session(isolated_engine) as session:
        principal = WorkerService(session).authenticate(ids["device_id"], token)
        result = WorkerTaskSessionService(
            session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
        ).read(principal, task_id=ids["task_id"], shop_id=ids["shop_id"], request_id="synthetic-ci")
        assert result.cookies[0].value.get_secret_value() == secret
        # The real service committed before returning; the same connection
        # must stay inside the disposable schema after that commit.
        assert session.scalar(text("SELECT current_schema()")).startswith("precheck_lock_")
    with isolated_engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT action, target_id, actor_user_id, team_id, details::text
            FROM audit_logs
        """)).mappings().all()
    assert len(rows) == 1
    assert rows[0]["action"] == "session.read_for_task"
    assert rows[0]["target_id"] == ids["shop_id"] and rows[0]["actor_user_id"] == ids["user_id"]
    assert rows[0]["team_id"] == ids["team_id"]
    assert secret not in str(rows[0]) and token not in str(rows[0])


def test_real_audit_failure_never_returns_session(isolated_engine, real_service_fixture):
    ids, token, _secret, cipher = real_service_fixture
    with isolated_engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE audit_logs ADD CONSTRAINT synthetic_reject_session_audit
            CHECK (action <> 'session.read_for_task')
        """))
    with Session(isolated_engine) as session:
        principal = WorkerService(session).authenticate(ids["device_id"], token)
        service = WorkerTaskSessionService(
            session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
        )
        with pytest.raises(DBAPIError):
            service.read(
                principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
                request_id="synthetic-reject-audit",
            )
        session.rollback()
        assert _session_audit_count(session, ids["task_id"]) == 0


def test_real_session_read_before_revoke_is_audited_and_later_read_is_denied(
    isolated_engine, real_service_fixture,
):
    ids, token, secret, cipher = real_service_fixture
    with Session(isolated_engine) as session:
        principal = WorkerService(session).authenticate(ids["device_id"], token)
        service = WorkerTaskSessionService(
            session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
        )
        result = service.read(
            principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
            request_id="synthetic-before-revoke",
        )
        assert result.cookies[0].value.get_secret_value() == secret
        assert _session_audit_count(session, ids["task_id"]) == 1

    with Session(isolated_engine) as session:
        AccessManagementService(session, password_service=None).update_team_authorization(
            ids["team_id"],
            TeamAuthorizationUpdate(
                module_codes=[ModuleCode.TASK], device_ids=[ids["device_id"]], shop_ids=[],
            ),
            actor=_synthetic_actor(ids), request_id="synthetic-revoke",
        )

    with Session(isolated_engine) as session:
        principal = WorkerService(session).authenticate(ids["device_id"], token)
        service = WorkerTaskSessionService(
            session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
        )
        with pytest.raises(AppError):
            service.read(
                principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
                request_id="synthetic-after-revoke",
            )
        assert _session_audit_count(session, ids["task_id"]) == 1


def test_real_team_archive_and_session_read_do_not_deadlock(
    isolated_engine, real_service_fixture,
):
    ids, token, _secret, cipher = real_service_fixture
    ready, proceed = Event(), Event()

    class PausingMembershipRepository(MembershipRepository):
        def disable_active_for_team(self, team_id):
            result = super().disable_active_for_team(team_id)
            ready.set()
            if not proceed.wait(timeout=10):
                raise TimeoutError("synthetic archive test did not resume")
            return result

    def archive_team():
        with Session(isolated_engine) as session:
            service = AccessManagementService(
                session, password_service=None,
                membership_repository=PausingMembershipRepository(session),
            )
            return service.archive_team(
                ids["team_id"], actor=_synthetic_actor(ids), request_id="synthetic-archive",
            ).enabled

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(archive_team)
        try:
            assert ready.wait(timeout=10), "archive did not reach membership lock"
            with Session(isolated_engine) as session:
                principal = WorkerService(session).authenticate(ids["device_id"], token)
                service = WorkerTaskSessionService(
                    session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
                )
                with pytest.raises(ShopSessionReadBusyError):
                    service.read(
                        principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
                        request_id="synthetic-race",
                    )
        finally:
            proceed.set()
        assert future.result(timeout=10) is False

    with Session(isolated_engine) as session:
        principal = WorkerService(session).authenticate(ids["device_id"], token)
        service = WorkerTaskSessionService(
            session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
        )
        with pytest.raises(AppError):
            service.read(
                principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
                request_id="synthetic-archived",
            )
        assert _session_audit_count(session, ids["task_id"]) == 0


@pytest.mark.parametrize("keep_shop", [True, False])
def test_real_team_authorization_replacement_and_session_read_do_not_deadlock(
    isolated_engine, real_service_fixture, keep_shop,
):
    ids, token, secret, cipher = real_service_fixture
    ready, proceed = Event(), Event()

    class PausingTeamModuleRepository(TeamModuleAccessRepository):
        def replace_codes(self, team_id, module_codes):
            super().replace_codes(team_id, module_codes)
            ready.set()
            if not proceed.wait(timeout=10):
                raise TimeoutError("synthetic authorization test did not resume")

    def update_authorization():
        with Session(isolated_engine) as session:
            service = AccessManagementService(
                session, password_service=None,
                team_module_access_repository=PausingTeamModuleRepository(session),
            )
            return service.update_team_authorization(
                ids["team_id"],
                TeamAuthorizationUpdate(
                    module_codes=[ModuleCode.TASK],
                    device_ids=[ids["device_id"]],
                    shop_ids=[ids["shop_id"]] if keep_shop else [],
                ),
                actor=_synthetic_actor(ids), request_id="synthetic-update-authorization",
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(update_authorization)
        try:
            assert ready.wait(timeout=10), "authorization did not reach module replacement"
            with Session(isolated_engine) as session:
                principal = WorkerService(session).authenticate(ids["device_id"], token)
                service = WorkerTaskSessionService(
                    session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
                )
                with pytest.raises(ShopSessionReadBusyError):
                    service.read(
                        principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
                        request_id="synthetic-replacement-race",
                    )
        finally:
            proceed.set()
        modules, devices, shops = future.result(timeout=10)
        assert modules == [ModuleCode.TASK]
        assert devices == [ids["device_id"]]
        assert shops == ([ids["shop_id"]] if keep_shop else [])

    # Once the complete replacement commits, a fresh read may use the new grants.
    with Session(isolated_engine) as session:
        principal = WorkerService(session).authenticate(ids["device_id"], token)
        service = WorkerTaskSessionService(
            session, cipher, settings=Settings(worker_precheck_session_access_enabled=True),
        )
        if keep_shop:
            result = service.read(
                principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
                request_id="synthetic-after-replacement",
            )
            assert result.cookies[0].value.get_secret_value() == secret
        else:
            with pytest.raises(AppError):
                service.read(
                    principal, task_id=ids["task_id"], shop_id=ids["shop_id"],
                    request_id="synthetic-after-revocation",
                )
        assert _session_audit_count(session, ids["task_id"]) == int(keep_shop)
