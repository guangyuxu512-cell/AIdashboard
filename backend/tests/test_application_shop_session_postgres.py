"""Only a disposable, explicitly named CI PostgreSQL database is used."""
import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.modules.sessions.application_auth import ApplicationAuthenticator, ApplicationSessionBusyError
from app.modules.sessions.application_service import ApplicationSessionService


@pytest.fixture
def database():
    raw_url = os.environ.get("BACKEND_DATABASE_URL")
    if not raw_url:
        pytest.skip("disposable PostgreSQL CI database not available")
    url = make_url(raw_url)
    if (url.get_backend_name() != "postgresql" or url.database != "control_center_ci"
            or url.username != "control_center_ci" or url.host not in {"127.0.0.1", "localhost"}):
        pytest.skip("database is not the explicitly guarded CI fixture")
    schema = "app_session_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={
        "options": f"-csearch_path={schema} -cstatement_timeout=10000",
    })

    @event.listens_for(engine, "connect")
    def guard_connection(dbapi_connection, _record):
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_schema()")
            assert cursor.fetchone() == ("control_center_ci", schema)
        dbapi_connection.rollback()

    try:
        with engine.begin() as connection:
            for statement in (
                """CREATE TABLE users (user_id uuid PRIMARY KEY, display_name text NOT NULL,
                    login_name text, password_hash text, enabled boolean NOT NULL,
                    is_super_account boolean NOT NULL, created_at timestamptz DEFAULT now(),
                    updated_at timestamptz DEFAULT now())""",
                """CREATE TABLE shops (shop_id uuid PRIMARY KEY, display_name text NOT NULL,
                    platform text NOT NULL, platform_shop_id text, enabled boolean NOT NULL,
                    owner_user_id uuid, note text, operating_start_date date,
                    operating_start_date_source text, operating_start_date_set_by_user_id uuid,
                    operating_start_date_set_at timestamptz, deleted_at timestamptz,
                    created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now())""",
                """CREATE TABLE shop_sessions (session_id uuid PRIMARY KEY, shop_id uuid NOT NULL,
                    version integer NOT NULL, status text NOT NULL, source_device_id uuid,
                    captured_at timestamptz NOT NULL, validated_at timestamptz, expires_at timestamptz,
                    refresh_lease_id uuid, refresh_lease_expires_at timestamptz,
                    payload_encrypted bytea NOT NULL, created_at timestamptz DEFAULT now(),
                    updated_at timestamptz DEFAULT now())""",
                """CREATE TABLE audit_logs (audit_log_id uuid PRIMARY KEY, request_id text NOT NULL,
                    actor_user_id uuid NOT NULL, team_id uuid, action text NOT NULL,
                    target_type text NOT NULL, target_id uuid NOT NULL, details jsonb,
                    created_at timestamptz DEFAULT now())""",
            ):
                connection.execute(text(statement))
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_authorized_direct_session_and_database_audit_and_lock(database, tmp_path):
    user_id, shop_id, session_id = uuid4(), uuid4(), uuid4()
    cipher = SecretCipher(Fernet.generate_key().decode())
    payload = {
        "schema": "management-login.session.v1", "platform": "douyin",
        "identity": {"platform": "douyin", "platformShopId": "fake-shop", "shopDisplayName": "Fixture"},
        "cookies": [{"name": "sessionid", "value": "synthetic-pg-cookie"}],
    }
    with database.begin() as connection:
        connection.execute(text("INSERT INTO users (user_id, display_name, enabled, is_super_account) "
                                "VALUES (:id, 'Owner', true, true)"), {"id": user_id})
        connection.execute(text("INSERT INTO shops (shop_id, display_name, platform, platform_shop_id, enabled) "
                                "VALUES (:id, 'Fixture', 'douyin', 'fake-shop', true)"), {"id": shop_id})
        connection.execute(text("INSERT INTO shop_sessions (session_id, shop_id, version, status, captured_at, "
                                "payload_encrypted) VALUES (:id, :shop, 1, 'valid', :now, :payload)"), {
            "id": session_id, "shop": shop_id, "now": datetime.now(UTC),
            "payload": cipher.encrypt_bytes(json.dumps(payload).encode()),
        })
    token = "synthetic_service_token_abcdefghijklmnopqrstuvwxyz0123456"
    path = tmp_path / "grants.json"
    path.write_text(json.dumps({"version": 1, "clients": [{
        "client_id": "test-app", "enabled": True, "authorized_by_user_id": str(user_id),
        "shop_ids": [str(shop_id)], "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
    }]}))
    authenticator = ApplicationAuthenticator(enabled=True, path=path)
    principal = authenticator.authenticate("test-app", token)
    with Session(database, expire_on_commit=False) as db:
        service = ApplicationSessionService(db, authenticator, cipher=cipher)
        result = service.read_session(principal, shop_id=shop_id, request_id=str(uuid4()))
        assert result.cookies[0].value.get_secret_value() == "synthetic-pg-cookie"
    with database.connect() as connection:
        record = connection.execute(text("SELECT actor_user_id, action, target_id, details FROM audit_logs")).one()
        assert record.actor_user_id == user_id and record.target_id == shop_id
        assert record.action == "application.read_shop_session"
        assert record.details["application_id"] == "test-app"
        assert "synthetic-pg-cookie" not in str(record.details)
    with Session(database) as writer, Session(database) as reader:
        writer.execute(text("UPDATE users SET enabled=false WHERE user_id=:id"), {"id": user_id})
        with pytest.raises(ApplicationSessionBusyError):
            ApplicationSessionService(reader, authenticator, cipher=cipher).read_session(
                principal, shop_id=shop_id, request_id=str(uuid4()),
            )
        writer.rollback()
