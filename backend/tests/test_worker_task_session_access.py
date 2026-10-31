import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings
from app.core.database import get_database_session
from app.core.exceptions.handlers import install_exception_handlers
from app.core.security import SecretCipher
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.repository import ExecutionAuthorizationLockRepository
from app.modules.access.exceptions import TeamResourceAccessDeniedError
from app.modules.sessions.auth_context import (
    ShopSessionAccessor,
    ShopSessionAuthContext,
    StoredSessionCookie,
    StoredSessionIdentity,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    ShopSessionReadBusyError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions import worker_task_service as worker_task_service_module
from app.modules.sessions.worker_task_service import WorkerTaskSessionService
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.repository import ShopDeviceBindingRepository, ShopRepository
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.repository import TaskRepository
from app.modules.tasks.worker_api import (
    claim_task, get_worker_task_service, get_worker_task_session_service, router,
)
from app.modules.workers import auth as worker_auth
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.exceptions import WorkerAuthenticationError
from app.modules.workers.security import hash_worker_token
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.service import WorkerPrincipal, WorkerService
from tests.support import FakeSession


class Fixture:
    def __init__(self) -> None:
        self.device_id, self.task_id, self.shop_id = uuid4(), uuid4(), uuid4()
        self.user_id, self.team_id = uuid4(), uuid4()
        self.token_hash = hash_worker_token("ccw_synthetic_fixture_token")
        self.principal = WorkerPrincipal(
            device_id=self.device_id, credential_hash=self.token_hash,
        )
        self.worker_credential = SimpleNamespace(enabled=True, token_hash=self.token_hash)
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
        self.locked_grants = SimpleNamespace(
            user=True, team=True, membership=True, module=True, device=True, shop=True,
        )
        self.task_shop_locked = True
        self.audit = []
        self.settings = Settings(worker_precheck_session_access_enabled=True)
        self.service = WorkerTaskSessionService(
            self.session, SecretCipher(Fernet.generate_key().decode()),
            settings=self.settings, task_repository=self, shop_repository=self,
            binding_repository=self, session_repository=self, accessor=self,
            actor_service=self, module_service=self, team_service=self,
            audit_service=self, authorization_locks=self, worker_repository=self,
        )

    def get_enabled_device(self, device_id):
        return object() if self.enabled and device_id == self.device_id else None

    def set_lock_timeout(self):
        pass

    def get_enabled_device_for_session_read(self, device_id):
        return self.get_enabled_device(device_id)

    def lock_shop_for_session_read(self, *, task_id, shop_id):
        return (self.task_shop_locked and task_id == self.task_id
                and shop_id == self.shop_id and shop_id in self.task.shop_ids)

    def get_credential_for_session_read(self, device_id):
        return self.worker_credential if device_id == self.device_id else None

    def get_running_for_device_for_session_read(self, *, task_id, device_id, now):
        if (task_id == self.task_id and device_id == self.task.target_device_id
                and self.task.status == "running" and self.task.lease_until
                and self.task.lease_until > now):
            return self.task
        return None

    def get_for_session_read(self, *args):
        if len(args) == 1:
            return self.shop if args[0] == self.shop_id else None
        return self.binding if args == (self.shop_id, self.device_id) else None

    def get_by_shop_for_session_read(self, shop_id):
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
        return self.locked_grants

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


def test_authorized_read_decrypts_real_stored_payload_with_matching_identity():
    f = Fixture()
    cipher = SecretCipher(Fernet.generate_key().decode())
    f.stored.status = ShopSessionStatus.CAPTURED
    f.stored.version = 4
    f.stored.payload_encrypted = cipher.encrypt_bytes(json.dumps({
        "schema": "management-login.session.v1",
        "platform": "douyin",
        "identity": {"platform": "douyin", "platformShopId": "shop-1",
                     "shopDisplayName": "Test store"},
        "cookies": [{"name": "sessionid", "value": "synthetic-encrypted-cookie"}],
    }).encode())
    repository = SimpleNamespace(get_by_shop=lambda shop_id: f.stored)
    f.service.accessor = ShopSessionAccessor(f.session, cipher, repository)
    result = f.read()
    assert result.session_version == 4
    assert result.cookies[0].value.get_secret_value() == "synthetic-encrypted-cookie"
    assert "synthetic-encrypted-cookie" not in repr(result)
    assert "synthetic-encrypted-cookie" not in repr(f.audit)


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


@pytest.mark.parametrize("missing", ["user", "team", "membership", "module", "device", "shop"])
def test_missing_locked_authorization_row_fails_closed(missing):
    f = Fixture()
    setattr(f.locked_grants, missing, False)
    with pytest.raises((TaskNotFoundError, TeamResourceAccessDeniedError)):
        f.read()
    assert not f.audit and f.session.commits == 0


def test_missing_locked_task_shop_link_fails_closed():
    f = Fixture()
    f.task_shop_locked = False
    with pytest.raises(TaskNotFoundError):
        f.read()
    assert not f.audit and f.session.commits == 0


def test_super_account_does_not_require_membership_or_team_module_rows():
    f = Fixture()
    f.actor = replace(f.actor, is_super_account=True)
    f.locked_grants.membership = False
    f.locked_grants.module = False
    assert f.read().shop_id == f.shop_id


@pytest.mark.parametrize("missing", ["device", "shop"])
def test_super_account_still_requires_locked_team_resource_grants(missing):
    f = Fixture()
    f.actor = replace(f.actor, is_super_account=True)
    setattr(f.locked_grants, missing, False)
    with pytest.raises(TeamResourceAccessDeniedError):
        f.read()
    assert not f.audit and f.session.commits == 0


def test_authorization_lock_contention_rolls_back_without_releasing_session():
    f = Fixture()

    class LockBusy(Exception):
        sqlstate = "55P03"

    def unavailable(**kwargs):
        raise DBAPIError("SELECT synthetic lock", {}, LockBusy(), False)

    f.service.authorization_locks = SimpleNamespace(set_lock_timeout=lambda: None, lock=unavailable)
    with pytest.raises(ShopSessionReadBusyError):
        f.read()
    assert f.session.rollbacks == 1 and not f.audit and f.session.commits == 0


def test_unrelated_database_errors_are_not_classified_as_lock_contention():
    f = Fixture()

    class OtherDatabaseError(Exception):
        sqlstate = "23505"

    def fail(**kwargs):
        raise DBAPIError("SELECT synthetic query", {}, OtherDatabaseError(), False)

    f.service.authorization_locks = SimpleNamespace(set_lock_timeout=lambda: None, lock=fail)
    with pytest.raises(DBAPIError) as error:
        f.read()
    assert error.value.orig.sqlstate == "23505"
    assert not f.audit and f.session.commits == 0


@pytest.mark.parametrize("change", ["revoked", "rotated"])
def test_worker_credential_change_after_authentication_blocks_session(change):
    f = Fixture()
    token = "ccw_synthetic_worker_token"
    credential = SimpleNamespace(enabled=True, token_hash=hash_worker_token(token))
    repository = SimpleNamespace(
        get_device=lambda device_id: object(),
        get_credential=lambda device_id: credential,
        get_credential_for_session_read=lambda device_id: credential,
    )
    f.principal = WorkerService(f.session, repository=repository).authenticate(
        f.device_id, token,
    )
    assert token not in repr(f.principal)
    assert hash_worker_token(token) not in repr(f.principal)
    f.service.worker_credentials = repository
    if change == "revoked":
        credential.enabled = False
    else:
        credential.token_hash = hash_worker_token("ccw_synthetic_rotated_token")

    with pytest.raises(WorkerAuthenticationError):
        f.read()
    assert not f.audit and f.session.commits == 0


@pytest.mark.parametrize("missing", ["authentication_snapshot", "credential"])
def test_missing_worker_credential_proof_fails_closed(missing):
    f = Fixture()
    if missing == "authentication_snapshot":
        f.principal = WorkerPrincipal(device_id=f.device_id)
    else:
        f.worker_credential = None
    with pytest.raises(WorkerAuthenticationError):
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


def test_expired_lease_during_audit_commit_does_not_release_session(monkeypatch):
    f = Fixture()
    start = datetime.now(UTC)
    f.task.lease_until = start + timedelta(seconds=1)

    class Clock:
        calls = 0

        @classmethod
        def now(cls, timezone):
            assert timezone is UTC
            cls.calls += 1
            return start if cls.calls <= 2 else start + timedelta(seconds=2)

    monkeypatch.setattr(worker_task_service_module, "datetime", Clock)
    with pytest.raises(TaskNotFoundError):
        f.read()
    # The authorized read was audited before the lease expired, but no
    # session was returned to the caller after the delayed audit commit.
    assert f.session.commits == 1 and len(f.audit) == 1


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


def test_http_reports_lock_contention_without_sensitive_data():
    f = Fixture()

    class LockBusy(Exception):
        sqlstate = "55P03"

    def unavailable(**kwargs):
        raise DBAPIError("SELECT synthetic lock", {}, LockBusy(), False)

    f.service.authorization_locks = SimpleNamespace(set_lock_timeout=lambda: None, lock=unavailable)
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_worker_task_session_service] = lambda: f.service
    app.dependency_overrides[get_worker_principal] = lambda: f.principal
    with TestClient(app) as client:
        response = client.post(f"/api/v1/worker/tasks/{f.task_id}/shop-sessions/{f.shop_id}")
    assert response.status_code == 409
    assert response.json()["code"] == "PRECHECK_SESSION_AUTHORIZATION_BUSY"
    assert "test-secret" not in response.text
    assert f.session.rollbacks == 1 and not f.audit


@pytest.mark.parametrize("change", ["revoked", "rotated"])
def test_http_rechecks_worker_credential_before_releasing_session(monkeypatch, change):
    f = Fixture()
    token = "ccw_synthetic_http_token"
    credential = SimpleNamespace(enabled=True, token_hash=hash_worker_token(token))

    def lock_credential(device_id):
        assert device_id == f.device_id
        if change == "revoked":
            credential.enabled = False
        else:
            credential.token_hash = hash_worker_token("ccw_synthetic_new_token")
        return credential

    repository = SimpleNamespace(
        get_device=lambda device_id: object(),
        get_credential=lambda device_id: credential,
        get_credential_for_session_read=lock_credential,
    )
    f.service.worker_credentials = repository
    monkeypatch.setattr(
        worker_auth, "WorkerService",
        lambda session: WorkerService(session, repository=repository),
    )
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_database_session] = lambda: f.session
    app.dependency_overrides[get_worker_task_session_service] = lambda: f.service
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/worker/tasks/{f.task_id}/shop-sessions/{f.shop_id}",
            headers={"Authorization": f"Bearer {token}", "X-Device-ID": str(f.device_id)},
        )
    assert response.status_code == 401
    assert "test-secret" not in response.text
    assert not f.audit and f.session.commits == 0


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


@pytest.mark.parametrize("populated", [False, True])
def test_ordinary_claim_http_response_is_accepted_by_baseline_worker(populated):
    # Wire contract copied from dev 877f131's Worker before shop_ids existed.
    # Exercise the FastAPI route, not only Pydantic model_dump in isolation.
    class LegacyAccount(BaseModel):
        model_config = ConfigDict(extra="forbid")
        shop_id: UUID
        shop_name: str | None = None
        platform_code: str
        login_identifier: str
        secret: str = Field(repr=False)
        preferred_verification_channel: str | None = None

    class LegacyAsset(BaseModel):
        model_config = ConfigDict(extra="forbid")
        asset_id: UUID
        filename: str
        position: int = Field(ge=0)
        content_type: str
        size_bytes: int = Field(gt=0)
        sha256: str = Field(min_length=64, max_length=64)
        download_path: str

    class LegacyTask(BaseModel):
        model_config = ConfigDict(extra="forbid")
        task_id: UUID
        skill_id: str
        input: dict[str, Any]
        lease_until: datetime
        accounts: list[LegacyAccount] = Field(default_factory=list, repr=False)
        assets: list[LegacyAsset] = Field(default_factory=list)

    # Local classes under postponed annotations may need explicit rebuilding.
    LegacyTask.model_rebuild(_types_namespace={
        "LegacyAccount": LegacyAccount, "LegacyAsset": LegacyAsset,
    })
    f = Fixture()
    task = SimpleNamespace(
        task_id=f.task_id, skill_id="system.echo", input_json={"message": "test"},
        lease_until=f.task.lease_until, shop_ids=[f.shop_id],
    )
    accounts = [{
        "shop_id": f.shop_id, "platform_code": "douyin", "login_identifier": "synthetic",
        "secret": "synthetic", "preferred_verification_channel": "manual",
    }] if populated else []
    assets = [SimpleNamespace(
        asset_id=uuid4(), original_filename="test.jpg", content_type="image/jpeg",
        size_bytes=1, sha256="a" * 64,
    )] if populated else []
    service = SimpleNamespace(claim_with_account=lambda principal: SimpleNamespace(
        task=task, accounts=accounts, assets=assets,
    ))
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_worker_principal] = lambda: f.principal
    app.dependency_overrides[get_worker_task_service] = lambda: service
    with TestClient(app) as client:
        response = client.post("/api/v1/worker/tasks/claim")
    assert response.status_code == 200
    payload = response.json()
    assert "shop_ids" not in payload
    parsed = LegacyTask.model_validate(payload)
    assert parsed.task_id == f.task_id
    assert len(parsed.accounts) == len(accounts) and len(parsed.assets) == len(assets)


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
    assert all("FOR SHARE NOWAIT" in statement for statement in session.statements)
    for table, statement in zip(("users", "teams", "team_memberships", "team_module_accesses",
                                 "team_device_accesses", "team_shop_accesses"), session.statements):
        assert f"FROM {table}" in statement


def test_sensitive_resource_reads_use_nonblocking_shared_locks():
    class RecordingSession:
        def __init__(self):
            self.statements = []
        def scalar(self, statement):
            self.statements.append(statement)
            return None

    session = RecordingSession()
    task_id, device_id, shop_id = uuid4(), uuid4(), uuid4()
    tasks = TaskRepository(session)
    tasks.get_enabled_device_for_session_read(device_id)
    tasks.get_running_for_device_for_session_read(
        task_id=task_id, device_id=device_id, now=datetime.now(UTC),
    )
    tasks.lock_shop_for_session_read(task_id=task_id, shop_id=shop_id)
    WorkerRepository(session).get_credential_for_session_read(device_id)
    ShopRepository(session).get_for_session_read(shop_id)
    ShopDeviceBindingRepository(session).get_for_session_read(shop_id, device_id)
    ShopSessionRepository(session).get_by_shop_for_session_read(shop_id)

    assert len(session.statements) == 7
    assert all("FOR SHARE NOWAIT" in str(stmt.compile(dialect=postgresql.dialect()))
               for stmt in session.statements)
    for index in (0, 1, 3, 4, 5, 6):
        assert session.statements[index].get_execution_options()["populate_existing"] is True
