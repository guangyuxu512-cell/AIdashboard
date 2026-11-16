from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.core.security import SecretCipher, get_secret_cipher
from app.main import create_app
from app.modules.access.models import Team, TeamDeviceAccess, TeamModuleAccess
from app.modules.api_tokens.models import ApiToken, ApiTokenEvent
from app.modules.audit.models import AuditLog
from app.modules.devices.models import Device
from app.modules.human_auth.models import HumanSession
from app.modules.human_auth.passwords import PasswordService
from app.modules.tasks.models import Task
from app.modules.users.models import User

pytestmark = pytest.mark.integration


@pytest.fixture
def token_environment(postgresql_engine):
    with postgresql_engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == "control_center_feat_ai_token_management"
    user_id, team_a, team_b, device_a, device_b, task_a, task_b = [uuid4() for _ in range(7)]
    password = "integration-only-test-password"
    with Session(postgresql_engine) as session:
        session.add_all([
            User(user_id=user_id, display_name="Token test operator", login_name="token_test_operator", password_hash=PasswordService().hash_password(password), enabled=True, is_super_account=True),
            Team(team_id=team_a, name="Token test A", enabled=True),
            Team(team_id=team_b, name="Token test B", enabled=True),
        ])
        session.flush()
        session.add_all([
            TeamModuleAccess(team_id=team_a, module_code="task"),
            TeamModuleAccess(team_id=team_b, module_code="task"),
            TeamModuleAccess(team_id=team_a, module_code="device"),
            TeamModuleAccess(team_id=team_b, module_code="device"),
            Device(device_id=device_a, team_id=team_a, display_name="Token test A", enabled=True),
            Device(device_id=device_b, team_id=team_b, display_name="Token test B", enabled=True),
        ])
        session.flush()
        session.add_all([
            TeamDeviceAccess(team_id=team_a, device_id=device_a),
            TeamDeviceAccess(team_id=team_b, device_id=device_b),
            Task(task_id=task_a, team_id=team_a, created_by_user_id=user_id, target_device_id=device_a, skill_id="test.skill", execution_display_name="A", status="pending", input_json={}),
            Task(task_id=task_b, team_id=team_b, created_by_user_id=user_id, target_device_id=device_b, skill_id="test.skill", execution_display_name="B", status="pending", input_json={}),
        ])
        session.commit()

    app = create_app()
    settings = Settings(runtime_environment="test", encryption_key=Fernet.generate_key().decode("ascii"))
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_secret_cipher] = lambda: SecretCipher(settings.encryption_key)

    def database():
        with Session(postgresql_engine) as session:
            yield session

    app.dependency_overrides[get_database_session] = database
    # No lifespan: this test must not start scheduler or other background loops.
    client = TestClient(app, raise_server_exceptions=True)
    login = client.post("/api/v1/auth/login", json={"login_name": "token_test_operator", "password": password})
    assert login.status_code == 200
    yield client, postgresql_engine, (user_id, team_a, team_b, task_a, task_b)
    client.close()

    with Session(postgresql_engine) as session:
        session.execute(delete(ApiTokenEvent).where(ApiTokenEvent.actor_user_id == user_id))
        session.execute(delete(ApiToken).where(ApiToken.owner_user_id == user_id))
        session.execute(delete(HumanSession).where(HumanSession.user_id == user_id))
        session.execute(delete(Task).where(Task.task_id.in_([task_a, task_b])))
        session.execute(delete(TeamDeviceAccess).where(TeamDeviceAccess.device_id.in_([device_a, device_b])))
        session.execute(delete(Device).where(Device.device_id.in_([device_a, device_b])))
        session.execute(delete(TeamModuleAccess).where(TeamModuleAccess.team_id.in_([team_a, team_b])))
        session.execute(delete(Team).where(Team.team_id.in_([team_a, team_b])))
        session.execute(delete(User).where(User.user_id == user_id))
        session.commit()


def test_scoped_token_is_enforced_and_revocation_is_immediate(token_environment):
    client, engine, (user_id, team_a, team_b, task_a, task_b) = token_environment
    catalog = client.get("/api/v1/api-tokens/permissions")
    assert catalog.status_code == 200
    permissions = {entry["id"] for entry in catalog.json()}
    assert {"GET /api/v1/tasks", "GET /api/v1/devices", "GET /api/v1/schedules"} <= permissions
    assert not any("/worker/" in permission for permission in permissions)

    created = client.post("/api/v1/api-tokens", json={
        "name": "read team A", "permissions": ["GET /api/v1/tasks", "GET /api/v1/tasks/{task_id}"],
        "team_ids": [str(team_a)], "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
    })
    assert created.status_code == 201
    assert created.headers["cache-control"] == "no-store"
    token_id, value = created.json()["token"]["token_id"], created.json()["value"]
    headers = {"Authorization": "Bearer " + value, "X-Team-ID": str(team_a)}
    with Session(engine) as session:
        stored = session.get(ApiToken, UUID(token_id))
        assert stored.token_hash != value and value not in str(stored.__dict__)

    # The existing administrator cookie must not elevate a restricted Bearer.
    assert client.get("/api/v1/devices", headers=headers).status_code == 403
    rows = client.get("/api/v1/tasks", headers=headers)
    assert rows.status_code == 200
    assert rows.json()["total"] == 1
    assert rows.json()["items"][0]["task_id"] == str(task_a)
    assert client.get(f"/api/v1/tasks/{task_b}", headers=headers).status_code == 404
    assert client.get("/api/v1/tasks", headers={**headers, "X-Team-ID": str(team_b)}).status_code == 403
    assert client.get("/api/v1/tasks", headers={"Authorization": "Bearer " + value}).status_code == 409
    assert client.get("/api/v1/api-tokens", headers=headers).status_code == 403

    updated = client.put(f"/api/v1/api-tokens/{token_id}", json={
        "name": "read team A", "permissions": ["GET /api/v1/tasks/{task_id}"], "team_ids": [str(team_a)],
    })
    assert updated.status_code == 200
    assert client.get("/api/v1/tasks", headers=headers).status_code == 403
    assert client.get(f"/api/v1/tasks/{task_a}", headers=headers).status_code == 200
    paused = client.patch(f"/api/v1/api-tokens/{token_id}/enabled", json={"enabled": False})
    assert paused.status_code == 200
    assert client.get(f"/api/v1/tasks/{task_a}", headers=headers).status_code == 401
    resumed = client.patch(f"/api/v1/api-tokens/{token_id}/enabled", json={"enabled": True})
    assert resumed.status_code == 200
    assert client.get(f"/api/v1/tasks/{task_a}", headers=headers).status_code == 200
    assert client.delete(f"/api/v1/api-tokens/{token_id}").status_code == 204
    assert client.get(f"/api/v1/tasks/{task_a}", headers=headers).status_code == 401
    events = client.get(f"/api/v1/api-tokens/{token_id}/events")
    assert events.status_code == 200
    assert {"create", "update", "revoke"} <= {event["action"] for event in events.json()}
    with Session(engine) as session:
        # Older releases must still be able to parse their existing audit log.
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.actor_user_id == user_id)) == 0


def test_unknown_permission_and_global_operations_cannot_be_team_scoped(token_environment):
    client, _engine, (_, team_a, _, _, _) = token_environment
    assert client.post("/api/v1/api-tokens", json={"name": "bad", "permissions": ["GET /invented"]}).status_code == 422
    assert client.post("/api/v1/api-tokens", json={"name": "bad", "permissions": ["POST /api/v1/devices"], "team_ids": [str(team_a)]}).status_code == 422
    assert client.post("/api/v1/api-tokens", json={"name": "expired", "permissions": ["GET /api/v1/tasks"], "expires_at": "2020-01-01T00:00:00Z"}).status_code == 422


def test_team_token_device_reads_respect_existing_device_grants(token_environment):
    client, _engine, (_, team_a, team_b, _, _) = token_environment
    created = client.post("/api/v1/api-tokens", json={
        "name": "team devices", "permissions": ["GET /api/v1/devices"], "team_ids": [str(team_a)],
    })
    assert created.status_code == 201
    headers = {"Authorization": "Bearer " + created.json()["value"], "X-Team-ID": str(team_a)}
    response = client.get("/api/v1/devices", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["display_name"] == "Token test A"
    assert client.get("/api/v1/devices", headers={**headers, "X-Team-ID": str(team_b)}).status_code == 403


def test_all_teams_token_can_read_only_its_granted_operations(token_environment):
    client, engine, (user_id, _, _, _, _) = token_environment
    created = client.post("/api/v1/api-tokens", json={
        "name": "devices only", "permissions": ["GET /api/v1/devices", "GET /api/v1/auth/me"],
    })
    assert created.status_code == 201
    value = created.json()["value"]
    headers = {"Authorization": "Bearer " + value}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.get("/api/v1/devices", headers=headers).status_code == 200
    assert client.get("/api/v1/tasks", headers=headers).status_code == 403
    assert client.post("/api/v1/devices", headers=headers, json={}).status_code == 403
    with Session(engine) as session:
        owner = session.get(User, user_id)
        owner.enabled = False
        session.commit()
    assert client.get("/api/v1/devices", headers=headers).status_code == 401


def test_existing_worker_migration_guard_still_rejects_data(token_environment, monkeypatch):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.modules.workers.precheck_models import WorkerRpaShopInventory

    _client, engine, (_, team_a, _, _, _) = token_environment
    with Session(engine) as session:
        device_id = session.scalar(select(Device.device_id).where(Device.team_id == team_a))
        session.add(WorkerRpaShopInventory(device_id=device_id, available=False, shops=[], last_discovered_at=datetime.now(UTC)))
        session.commit()
    try:
        migration = importlib.import_module("migrations.versions.20261110_0050_worker_rpa_precheck_v1")
        # The test uses this Feature's disposable DB, never the old Feature DB.
        monkeypatch.setattr(migration, "FEATURE_DATABASE", "control_center_feat_ai_token_management")
        with engine.connect() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                with pytest.raises(RuntimeError, match="retain schema and audit data"):
                    migration.downgrade()
            connection.rollback()
            assert connection.scalar(text("select version_num from alembic_version")) == "20261113_0051"
    finally:
        with Session(engine) as session:
            session.execute(delete(WorkerRpaShopInventory).where(WorkerRpaShopInventory.device_id == device_id))
            session.commit()


def test_token_migration_will_not_discard_existing_credentials(token_environment):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    client, engine, _ = token_environment
    created = client.post("/api/v1/api-tokens", json={"name": "preserved", "permissions": ["GET /api/v1/tasks"]})
    assert created.status_code == 201
    migration = importlib.import_module("migrations.versions.20261113_0051_api_tokens")
    with engine.connect() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            with pytest.raises(RuntimeError, match="retain schema and audit records"):
                migration.downgrade()
        connection.rollback()
        assert connection.scalar(text("select version_num from alembic_version")) == "20261113_0051"
