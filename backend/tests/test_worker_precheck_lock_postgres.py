"""Concurrency check against the explicitly disposable GitHub CI database only."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modules.access.repository import ExecutionAuthorizationLockRepository


def test_authorization_row_cannot_be_revoked_during_sensitive_read():
    raw_url = os.environ.get("BACKEND_DATABASE_URL")
    if not raw_url:
        pytest.skip("only the disposable PostgreSQL CI database is supported")
    url = make_url(raw_url)
    if url.database != "control_center_ci" or url.host not in {"127.0.0.1", "localhost"}:
        pytest.skip("database is not the explicitly guarded CI fixture")

    schema = "precheck_lock_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    user_id, team_id, device_id, shop_id, membership_id = [uuid4() for _ in range(5)]
    try:
        with engine.begin() as conn:
            for statement in (
                "CREATE TABLE users (user_id uuid PRIMARY KEY)",
                "CREATE TABLE teams (team_id uuid PRIMARY KEY)",
                "CREATE TABLE team_memberships (membership_id uuid PRIMARY KEY, user_id uuid, team_id uuid)",
                "CREATE TABLE team_module_accesses (team_id uuid, module_code text)",
                "CREATE TABLE team_device_accesses (team_id uuid, device_id uuid)",
                "CREATE TABLE team_shop_accesses (team_id uuid, shop_id uuid)",
            ):
                conn.execute(text(statement))
            values = dict(user_id=user_id, team_id=team_id, device_id=device_id,
                          shop_id=shop_id, membership_id=membership_id)
            for statement in (
                "INSERT INTO users VALUES (:user_id)",
                "INSERT INTO teams VALUES (:team_id)",
                "INSERT INTO team_memberships VALUES (:membership_id, :user_id, :team_id)",
                "INSERT INTO team_module_accesses VALUES (:team_id, 'task')",
                "INSERT INTO team_device_accesses VALUES (:team_id, :device_id)",
                "INSERT INTO team_shop_accesses VALUES (:team_id, :shop_id)",
            ):
                conn.execute(text(statement), values)

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
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
