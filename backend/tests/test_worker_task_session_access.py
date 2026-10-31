from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.core.database import get_database_session
from app.core.exceptions.handlers import install_exception_handlers
from app.core.security import SecretCipher
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.repository import ExecutionAuthorizationLockRepository
from app.modules.access.exceptions import TeamResourceAccessDeniedError
from app.modules.sessions.auth_context import (
    ShopSessionAuthContext,
    StoredSessionCookie,
    StoredSessionIdentity,
)
from app.modules.sessions.exceptions import (
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.worker_task_service import WorkerTaskSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.worker_api import claim_task, get_worker_task_session_service, router
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.service import WorkerPrincipal
from tests.support import FakeSession


class Fixture:
    def __init__(self) -> None:
        self.device_id, self.task_id, self.shop_id = uuid4(), uuid4(), uuid4()
        self.user_id, self.team_id = uuid4(), uuid4()
        self.principal = WorkerPrincipal(device_id=self.device_id)
        self.session = FakeSession()
        self.enabled = True
        self.task = SimpleNamespace(
            skill_id="product.precheck", created_by_user_id=self.user_id,
            team_id=self.team_id, shop_ids=[self.shop_id],
            lease_until=datetime.now(UTC) + timedelta(minutes=5),
            status="running", target_device_id=self.device_id,
        )
        self.shop = SimpleNamespace(
            enabled=True, platform=ShopPlatform.DOUYIN, platform_shop_id="shop-1",
        )
        self.binding = SimpleNamespace(enabled=True)
        self.stored = SimpleNamespace(expires_at=datetime.now(UTC) + timedelta(hours=1))
        self.context = ShopSessionAuthContext(
            shop_id=self.shop_id, platform=ShopPlatform.DOUYIN, session_version=2,
            identity=StoredSessionIdentity(
                platform=ShopPlatform.DOUYIN, platformShopId="shop-1",
                shopDisplayName="Test store",
            ),
            cookies=(StoredSessionCookie(name="sessionid", value=SecretStr("test-secret")),),
        )
        self.actor = ActorContext(
            user_id=self.user_id, user_display_name="Test", team_id=self.team_id,
            membership_id=uuid4(), role_code="member", data_scope=DataScope.TEAM,
        )
        self.granted = True
        self.locked = False
        self.audit = []
        self.settings = Settings(worker_precheck_session_access_enabled=True)
        self.service = WorkerTaskSessionService(
            self.session, SecretCipher(Fernet.generate_key().decode()),
            settings=self.settings, task_repository=self, shop_repository=self,
            binding_repository=self, session_repository=self, accessor=self,
            actor_service=self, module_service=self, team_service=self,
            audit_service=self, authorization_locks=self,
        )

    def get_enabled_device(self, device_id):
        return object() if self.enabled and device_id == self.device_id else None

    def get_running_for_device_for_update(self, *, task_id, device_id, now):
        if (task_id == self.task_id and device_id == self.task.target_device_id
                and self.task.status == "running" and self.task.lease_until
                and self.task.lease_until > now):
            return self.task
        return None

    def get_for_update(self, *args):
        if len(args) == 1:
            return self.shop if args[0] == self.shop_id else None
        return self.binding if args == (self.shop_id, self.device_id) else None

    def get_by_shop_for_update(self, shop_id):
        return self.stored if shop_id == self.shop_id else None

    def get_auth_context(self, shop_id, platform):
        assert shop_id == self.shop_id and platform == ShopPlatform.DOUYIN
        return self.context

    def resolve(self, *, user_id, requested_team_id):
        assert self.locked
        assert user_id == self.user_id and requested_team_id == self.team_id
        return self.actor

    def lock(self, *, user_id, team_id, device_id, shop_id):
        assert (user_id, team_id, device_id, shop_id) == (
            self.user_id, self.team_id, self.device_id, self.shop_id,
        )
        self.locked = True

    def require_module_access(self, actor, module):
        assert actor == self.actor and module.value == "task"

    def require_execution_resources(self, *, team_id, device_id, shop_ids):
        assert (team_id, device_id, shop_ids) == (self.team_id, self.device_id, [self.shop_id])
        if not self.granted:
            raise TeamResourceAccessDeniedError()

    def record_worker_session_access(self, **details):
        self.audit.append(details)

    def read(self):
        return self.service.read(
            self.principal, task_id=self.task_id, shop_id=self.shop_id, request_id="test",
        )


def test_only_authorized_session_is_returned_and_audited_without_secret():
    f = Fixture()
    result = f.read()
    assert result.shop_id == f.shop_id and result.session_version == 2
    assert "test-secret" not in repr(result)
    assert "test-secret" not in repr(f.audit)
    assert result.model_dump_json().count("test-secret") == 1
    assert f.audit[0]["task_id"] == f.task_id
    assert f.audit[0]["device_id"] == f.device_id
    assert f.session.commits == 1


@pytest.mark.parametrize("change", [
    lambda f: setattr(f.settings, "worker_precheck_session_access_enabled", False),
    lambda f: setattr(f, "enabled", False),
    lambda f: setattr(f.task, "target_device_id", uuid4()),
    lambda f: setattr(f.task, "skill_id", "system.echo"),
    lambda f: setattr(f.task, "created_by_user_id", None),
    lambda f: setattr(f.task, "shop_ids", [uuid4()]),
    lambda f: setattr(f.task, "status", "success"),
    lambda f: setattr(f.task, "lease_until", datetime.now(UTC) - timedelta(seconds=1)),
    lambda f: setattr(f.shop, "enabled", False),
    lambda f: setattr(f.binding, "enabled", False),
    lambda f: setattr(f.shop, "platform", ShopPlatform.PDD),
])
def test_unrelated_or_inactive_task_and_resources_cannot_receive_session(change):
    f = Fixture()
    change(f)
    with pytest.raises(TaskNotFoundError):
        f.read()
    assert not f.audit and f.session.commits == 0


def test_revoked_team_access_is_denied():
    f = Fixture()
    f.granted = False
    with pytest.raises(TeamResourceAccessDeniedError):
        f.read()
    assert not f.audit and f.session.commits == 0


@pytest.mark.parametrize("case", ["missing", "wrong_identity", "no_identity"])
def test_unavailable_or_ambiguous_shop_session_is_not_returned(case):
    f = Fixture()
    if case == "missing":
        f.stored = None
        error = ShopSessionNotConfiguredError
    else:
        if case == "wrong_identity":
            f.shop.platform_shop_id = "different-shop"
        else:
            f.context = f.context.model_copy(update={"identity": None})
        error = ShopSessionPayloadInvalidError
    with pytest.raises(error):
        f.read()
    assert not f.audit and f.session.commits == 0


def test_session_expiration_metadata_does_not_replace_platform_authentication():
    f = Fixture()
    f.stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert f.read().shop_id == f.shop_id


def test_audit_commit_failure_does_not_release_session():
    f = Fixture()
    def fail_commit():
        raise RuntimeError("commit failed")
    f.session.commit = fail_commit
    with pytest.raises(RuntimeError, match="commit failed"):
        f.read()


def test_http_response_reveals_cookie_only_on_authenticated_wire_without_caching():
    f = Fixture()
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_worker_task_session_service] = lambda: f.service
    app.dependency_overrides[get_worker_principal] = lambda: f.principal
    with TestClient(app) as client:
        response = client.post(f"/api/v1/worker/tasks/{f.task_id}/shop-sessions/{f.shop_id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    assert response.headers["pragma"] == "no-cache"
    assert response.json()["cookies"][0]["value"] == "test-secret"


def test_http_without_worker_authentication_is_rejected():
    f = Fixture()
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_database_session] = lambda: f.session
    app.dependency_overrides[get_worker_task_session_service] = lambda: f.service
    with TestClient(app) as client:
        response = client.post(f"/api/v1/worker/tasks/{f.task_id}/shop-sessions/{f.shop_id}")
    assert response.status_code == 401
    assert "test-secret" not in response.text
    assert not f.audit


@pytest.mark.parametrize("is_precheck", [True, False])
def test_claim_exposes_nonsecret_shop_ids_only_for_precheck(is_precheck):
    f = Fixture()
    task = SimpleNamespace(
        task_id=f.task_id, skill_id="product.precheck" if is_precheck else "system.echo",
        input_json={}, lease_until=f.task.lease_until, shop_ids=[f.shop_id],
    )
    service = SimpleNamespace(claim_with_account=lambda principal: SimpleNamespace(
        task=task, accounts=[], assets=[],
    ))
    result = claim_task(f.principal, service)
    payload = result.model_dump(mode="json", exclude_defaults=True)
    if is_precheck:
        assert payload["shop_ids"] == [str(f.shop_id)]
    else:
        assert "shop_ids" not in payload


def test_sensitive_authorization_checks_lock_all_existing_grant_rows():
    class RecordingSession:
        def __init__(self):
            self.statements = []
        def scalar(self, statement):
            self.statements.append(str(statement.compile(dialect=postgresql.dialect())))
    session = RecordingSession()
    ExecutionAuthorizationLockRepository(session).lock(
        user_id=uuid4(), team_id=uuid4(), device_id=uuid4(), shop_id=uuid4(),
    )
    assert len(session.statements) == 6
    assert all("FOR UPDATE" in statement for statement in session.statements)
    for table, statement in zip(("users", "teams", "team_memberships", "team_module_accesses",
                                 "team_device_accesses", "team_shop_accesses"), session.statements):
        assert f"FROM {table}" in statement
