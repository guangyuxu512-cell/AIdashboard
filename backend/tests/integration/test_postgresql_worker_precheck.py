from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.modules.access.models import Team
from app.modules.devices.models import Device
from app.modules.sessions.application_auth import ApplicationPrincipal, ApplicationShopNotFoundError, ClientGrant, DeviceShopGrant
from app.modules.tasks.models import Task
from app.modules.users.models import User
from app.modules.workers.models import DeviceRuntime, DeviceSkillCapability
from app.modules.workers.precheck_contract import PrecheckSubmission, PrecheckTerminal
from app.modules.workers.precheck_contract import PrecheckSignInput
from app.modules.workers.precheck_models import ApplicationWorkerPrecheck, WorkerRpaShopInventory
from app.modules.workers.precheck_service import PrecheckConflict, PrecheckInvalidResult, PrecheckNotFound, WorkerPrecheckService, accept_precheck_terminal, sign_current_precheck
from app.integrations.douyin_signer.schemas import DouyinSignResult


pytestmark = pytest.mark.integration


class StubAuthorizer:
    def __init__(self, grant):
        self.grant = grant

    def authenticate(self, client_id, token):
        assert client_id == self.grant.client_id
        return ApplicationPrincipal(self.grant, token)

    def reauthorize_shop(self, shop_id):
        if shop_id not in self.grant.shop_ids:
            raise ApplicationShopNotFoundError()

    def current_grant(self, client_id):
        assert client_id == self.grant.client_id
        return self.grant


@pytest.fixture
def ready_precheck(postgresql_engine):
    with postgresql_engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT current_database()").scalar_one() == "control_center_feat_worker_capability_precheck"
    user_id, team_id, device_id, install_id = (uuid4() for _ in range(4))
    now = datetime.now(UTC)
    with Session(postgresql_engine) as session:
        session.add_all([
            User(user_id=user_id, display_name="isolated precheck test", enabled=True, is_super_account=True),
            Team(team_id=team_id, name="isolated precheck test", enabled=True),
        ])
        session.flush()
        session.add(Device(device_id=device_id, team_id=team_id, display_name="precheck", enabled=True))
        session.flush()
        session.add_all([
            DeviceRuntime(device_id=device_id, worker_version="test", started_at=now, last_seen_at=now, connection_status="online"),
            DeviceSkillCapability(device_id=device_id, skill_id="douyin.category_schema", display_name="test", runtime="python", skill_version="1", classification="internal"),
            WorkerRpaShopInventory(device_id=device_id, installation_id=install_id, available=True, last_discovered_at=now,
                shops=[{"localShopId": "local-1", "platformShopId": "123", "shopName": "fixture", "platform": "douyin", "browserOpen": True}]),
        ])
        session.commit()
    grant = ClientGrant(client_id="pdc-test", token_sha256="a" * 64, authorized_by_user_id=user_id,
                        enabled=True, worker_precheck_enabled=True, device_ids=(device_id,),
                        device_shops=(DeviceShopGrant(device_id=device_id, local_shop_id="local-1", platform_shop_id="123"),))
    principal = ApplicationPrincipal(grant, "synthetic-token")
    yield postgresql_engine, principal, StubAuthorizer(grant), device_id
    with Session(postgresql_engine) as session:
        tasks = session.scalars(select(ApplicationWorkerPrecheck.task_id).where(ApplicationWorkerPrecheck.client_id == "pdc-test")).all()
        session.execute(delete(ApplicationWorkerPrecheck).where(ApplicationWorkerPrecheck.client_id == "pdc-test"))
        session.execute(delete(Task).where(Task.task_id.in_(tasks)))
        session.execute(delete(WorkerRpaShopInventory).where(WorkerRpaShopInventory.device_id == device_id))
        session.execute(delete(DeviceSkillCapability).where(DeviceSkillCapability.device_id == device_id))
        session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id))
        session.execute(delete(Device).where(Device.device_id == device_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.execute(delete(User).where(User.user_id == user_id))
        session.commit()


def submission(*, product="product-a", revision=1, attempt=1, title="fixture"):
    return PrecheckSubmission.model_validate({"kind": "douyin.category_schema",
        "context": {"product_id": product, "revision": revision, "attempt": attempt},
        "input": {"category_id": "1000005146", "title": title}})


def test_concurrent_claim_reuses_one_task_and_checks_changed_request(ready_precheck):
    engine, principal, auth, device_id = ready_precheck
    barrier = Barrier(4)

    def create(attempt):
        with Session(engine) as session:
            barrier.wait()
            return WorkerPrecheckService(session, auth).submit(principal, submission(attempt=attempt)).task_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(create, range(1, 5)))
    assert len(set(ids)) == 1
    with Session(engine) as session:
        runtime = session.get(DeviceRuntime, device_id)
        runtime.connection_status = "offline"
        session.commit()
        service = WorkerPrecheckService(session, auth)
        assert service.submit(principal, submission(attempt=5)).task_id == ids[0]
        with pytest.raises(PrecheckConflict):
            service.submit(principal, submission(title="different"))
        session.rollback()
        assert len(session.scalars(select(ApplicationWorkerPrecheck)).all()) == 1
    assert auth.grant.shop_ids == ()
    with pytest.raises(ApplicationShopNotFoundError):
        auth.reauthorize_shop(uuid4())


def test_lost_result_replay_large_payload_and_revision_fence(ready_precheck):
    engine, principal, auth, device_id = ready_precheck
    with Session(engine) as session:
        service = WorkerPrecheckService(session, auth)
        task = service.submit(principal, submission())
        task_id = task.task_id
        task.status = "lost"
        session.commit()
        result = {"kind": "douyin.category_schema", "category_id": "1000005146",
                  "device_id": str(device_id), "local_shop_id": "local-1", "platform_shop_id": "123",
                  "http_status": 200, "platform_code": 0,
                  "items": [{"id": 1, "options": [{"id": i, "name": "颜色" * 8} for i in range(2000)]}]}
        data = PrecheckTerminal(status="success", result=result)
        with pytest.raises(PrecheckNotFound):
            accept_precheck_terminal(session, uuid4(), task_id, data)
        assert accept_precheck_terminal(session, device_id, task_id, data).result_json == result
        assert accept_precheck_terminal(session, device_id, task_id, data).status == "success"
        assert service.get(principal, task_id).result_json["items"][0]["options"][-1]["id"] == 1999
        bad = dict(result, cookies="must-not-persist")
        with pytest.raises(PrecheckInvalidResult):
            accept_precheck_terminal(session, device_id, task_id, PrecheckTerminal(status="success", result=bad))

        old = service.submit(principal, submission(product="another", revision=1))
        old_id = old.task_id
        old.status = "lost"
        session.commit()
        service.submit(principal, submission(product="another", revision=2))
        with pytest.raises(PrecheckConflict):
            accept_precheck_terminal(session, device_id, old_id, data)


def test_signer_is_scoped_to_current_device_and_task(ready_precheck):
    engine, principal, auth, device_id = ready_precheck

    class Signer:
        requests = []

        def sign(self, request):
            self.requests.append(request)
            return DouyinSignResult(ok=True, a_bogus="synthetic-signature", duration_ms=1)

    signer = Signer()
    headers = PrecheckSignInput(cookie="session=synthetic-cookie", user_agent="synthetic-agent")
    with pytest.raises(ValidationError):
        PrecheckSignInput.model_validate({"cookie": "synthetic-cookie", "user_agent": "test",
                                          "url": "https://wrong.invalid/path"})
    with Session(engine) as session:
        task = WorkerPrecheckService(session, auth).submit(principal, submission())
        task.status = "running"
        task.lease_until = datetime.now(UTC) + timedelta(minutes=1)
        session.commit()
        with pytest.raises(PrecheckNotFound):
            sign_current_precheck(session, auth, signer, uuid4(), task.task_id, headers)
        assert signer.requests == []
        signed = sign_current_precheck(session, auth, signer, device_id, task.task_id, headers)
        assert signed["url"].startswith("https://fxg.jinritemai.com/product/tproduct/getSchema?")
        assert len(signer.requests) == 1
        assert signer.requests[0].cookie.get_secret_value() == "session=synthetic-cookie"
        assert "synthetic-cookie" not in str(task.input_json)
        task.lease_until = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        with pytest.raises(PrecheckNotFound):
            sign_current_precheck(session, auth, signer, device_id, task.task_id, headers)
        assert len(signer.requests) == 1


def test_safe_string_business_code_survives_failure_and_replay(ready_precheck):
    engine, principal, auth, device_id = ready_precheck
    with Session(engine) as session:
        task = WorkerPrecheckService(session, auth).submit(principal, submission())
        task.status = "running"
        task.lease_until = datetime.now(UTC) + timedelta(minutes=1)
        session.commit()
        result = {"kind": "douyin.category_schema", "category_id": "1000005146",
                  "device_id": str(device_id), "local_shop_id": "local-1", "platform_shop_id": "123",
                  "http_status": 200, "platform_code": "TEST_600.2-A",
                  "error_stage": "platform", "safe_error_code": "PLATFORM_BUSINESS_REJECTED"}
        data = PrecheckTerminal(status="failed", result=result,
                                error_code="PLATFORM_BUSINESS_REJECTED", error_message="safe")
        assert accept_precheck_terminal(session, device_id, task.task_id, data).result_json["platform_code"] == "TEST_600.2-A"
        assert accept_precheck_terminal(session, device_id, task.task_id, data).status == "failed"


def test_all_mapped_shops_rotate_and_new_open_shop_needs_no_regrant(ready_precheck):
    engine, principal, auth, device_id = ready_precheck
    grant = auth.grant.model_copy(update={"all_mapped_shops": (device_id,), "device_shops": ()})
    auth, principal = StubAuthorizer(grant), ApplicationPrincipal(grant, "synthetic-token")
    with Session(engine) as session:
        inventory = session.get(WorkerRpaShopInventory, device_id)
        inventory.shops = [*inventory.shops,
            {"localShopId": "local-2", "platformShopId": "456", "shopName": "second", "platform": "douyin", "browserOpen": True},
            {"localShopId": "local-3", "platformShopId": "789", "shopName": "closed", "platform": "douyin", "browserOpen": False}]
        session.commit()
        service = WorkerPrecheckService(session, auth)
        assigned = []
        for index in range(4):
            task = service.submit(principal, submission(product=f"rotation-{index}"))
            assigned.append(task.input_json["local_shop_id"])
            task.status = "success"
            session.commit()
        assert assigned == ["local-1", "local-2", "local-1", "local-2"]
        # A newly opened local shop appears through the next inventory report,
        # not through a central shop record or a new application grant.
        inventory.shops = [*inventory.shops,
            {"localShopId": "local-4", "platformShopId": "000", "shopName": "new", "platform": "douyin", "browserOpen": True}]
        session.commit()
        assert service.submit(principal, submission(product="new-shop")).input_json["local_shop_id"] == "local-4"
        assert not service._authorized_shop(grant, uuid4(), "local-4", "000")


def test_concurrent_distinct_products_rotate_across_open_shops(ready_precheck):
    engine, _, auth, device_id = ready_precheck
    grant = auth.grant.model_copy(update={"all_mapped_shops": (device_id,), "device_shops": ()})
    auth, principal = StubAuthorizer(grant), ApplicationPrincipal(grant, "synthetic-token")
    with Session(engine) as session:
        inventory = session.get(WorkerRpaShopInventory, device_id)
        inventory.shops = [*inventory.shops, {"localShopId": "local-2", "platformShopId": "456",
            "shopName": "second", "platform": "douyin", "browserOpen": True}]
        session.commit()
    barrier = Barrier(4)

    def create(index):
        with Session(engine) as session:
            barrier.wait()
            return WorkerPrecheckService(session, auth).submit(principal, submission(product=f"parallel-{index}")).input_json["local_shop_id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        assigned = list(pool.map(create, range(4)))
    assert assigned.count("local-1") == 2
    assert assigned.count("local-2") == 2


def test_application_precheck_and_legacy_session_switches_are_independent(ready_precheck, tmp_path):
    import hashlib
    import json

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from cryptography.fernet import Fernet
    from app.core.config import Settings, get_settings
    from app.core.database import get_database_session
    from app.core.exceptions import install_exception_handlers
    from app.core.security import SecretCipher, get_secret_cipher
    from app.modules.sessions.application_api import router as session_router
    from app.modules.workers.precheck_api import application_router

    engine, principal, _, device_id = ready_precheck
    token = "synthetic_application_token_1234567890"
    grant = principal.grant.model_dump(mode="json")
    grant["token_sha256"] = hashlib.sha256(token.encode()).hexdigest()
    path = tmp_path / "application-grants.json"
    path.write_text(json.dumps({"version": 1, "clients": [grant]}), encoding="utf-8")
    application = FastAPI()
    install_exception_handlers(application)
    application.include_router(session_router)
    application.include_router(application_router)
    state = {"settings": Settings(application_worker_precheck_enabled=True,
                                   application_worker_precheck_clients_file=path,
                                   application_shop_session_enabled=False)}
    application.dependency_overrides[get_settings] = lambda: state["settings"]
    application.dependency_overrides[get_secret_cipher] = lambda: SecretCipher(Fernet.generate_key().decode())

    def database():
        with Session(engine) as session:
            yield session
    application.dependency_overrides[get_database_session] = database
    headers = {"Authorization": f"Bearer {token}", "X-Application-ID": grant["client_id"]}
    with TestClient(application, base_url="https://integration.test") as client:
        assert client.post("/internal/applications/v1/worker-prechecks", json=submission().model_dump(), headers=headers).status_code == 202
        assert client.get("/internal/applications/v1/shops", headers=headers).status_code == 503
        state["settings"] = Settings(application_worker_precheck_enabled=False,
            application_shop_session_enabled=True, application_shop_session_clients_file=path)
        assert client.post("/internal/applications/v1/worker-prechecks", json=submission().model_dump(), headers=headers).status_code == 503
        assert client.get("/internal/applications/v1/shops", headers=headers).json() == []
        assert client.get(f"/internal/applications/v1/shops/{uuid4()}/session", headers=headers).status_code == 404


def test_migration_refuses_to_drop_nonempty_feature_records(ready_precheck):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    engine, _, _, device_id = ready_precheck
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "migrations"))
    with pytest.raises(RuntimeError, match="retain schema and audit data"):
        command.downgrade(config, "20261020_0049")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261110_0050"
        assert connection.scalar(select(WorkerRpaShopInventory.device_id).where(
            WorkerRpaShopInventory.device_id == device_id)) == device_id


def test_synthetic_http_chain_uses_signed_capability_and_real_postgres(ready_precheck, tmp_path, monkeypatch):
    import asyncio
    import base64
    import hashlib
    import io
    import json
    from pathlib import Path
    import zipfile

    import app
    import httpx
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from fastapi import FastAPI
    from app.core.config import Settings, get_settings
    from app.core.database import get_database_session
    from app.core.exceptions import install_exception_handlers
    from app.core.security import SecretCipher, get_secret_cipher
    from app.modules.tasks.worker_api import router as task_router
    from app.modules.workers import precheck_api
    from app.modules.workers.api import router as worker_router
    from app.modules.workers.auth import get_worker_principal
    from app.modules.workers.capability_package_api import build_capability_package_router
    from app.modules.workers.service import WorkerPrincipal

    # Both packages deliberately use the project's `app` name; for this
    # in-process synthetic test add only the local Worker source path.
    worker_root = Path(__file__).resolve().parents[3] / "worker"
    app.__path__.append(str(worker_root / "app"))
    import app.shared
    app.shared.__path__.append(str(worker_root / "app/shared"))
    from app.capability_host import CapabilityHost
    from app.capability_runtime import CapabilityRuntime
    from app.capability_updates import CapabilityUpdater
    from app.client import WorkerApiClient
    from app.config import WorkerSettings
    from app.rpa_session_bridge import LocalSession
    from app.worker import Worker

    engine, principal, auth, device_id = ready_precheck
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    code = (worker_root / "capabilities/douyin_category_schema/capability.py").read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("capability.py", code)
    blob = buffer.getvalue()
    digest = hashlib.sha256(blob).hexdigest()
    manifest = json.dumps({"schema_version": 1, "sequence": 1, "packages": [{
        "skill_id": "douyin.category_schema", "version": "1.0", "entrypoint": "capability.py",
        "host_api_version": 1, "sha256": digest, "size": len(blob)}]}, separators=(",", ":")).encode()
    artifacts = tmp_path / "server-artifacts"
    (artifacts / "packages").mkdir(parents=True)
    (artifacts / "manifest.json").write_bytes(manifest)
    (artifacts / "manifest.sig").write_bytes(private.sign(manifest))
    (artifacts / "packages" / f"{digest}.zip").write_bytes(blob)
    application = FastAPI()
    install_exception_handlers(application)
    application.include_router(precheck_api.application_router)
    application.include_router(precheck_api.worker_router)
    application.include_router(task_router)
    application.include_router(worker_router)
    application.include_router(build_capability_package_router(artifacts))
    settings = Settings(application_worker_precheck_enabled=True)
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[precheck_api.require_precheck_application] = lambda: principal
    application.dependency_overrides[precheck_api._precheck_authenticator] = lambda: auth
    application.dependency_overrides[get_worker_principal] = lambda: WorkerPrincipal(device_id=device_id)
    application.dependency_overrides[get_secret_cipher] = lambda: SecretCipher(Fernet.generate_key().decode())

    def database():
        with Session(engine) as session:
            yield session
    application.dependency_overrides[get_database_session] = database

    class SyntheticSigner:
        def __init__(self, **kwargs):
            pass

        def sign(self, request):
            assert request.cookie.get_secret_value() == "session=synthetic-cookie"
            return DouyinSignResult(ok=True, a_bogus="synthetic-signature", duration_ms=1)
    monkeypatch.setattr(precheck_api, "DouyinSignerClient", SyntheticSigner)
    platform_calls = []

    def platform(request):
        platform_calls.append(request.url.path)
        assert request.headers["cookie"] == "session=synthetic-cookie"
        return httpx.Response(200, json={"code": "0", "data": {"model": {"category_properties": {
            "items": [{"id": "large", "options": [{"id": index, "name": "选项" * 8} for index in range(2500)]}]
        }}}})

    class FakeRpa:
        async def read_session(self, local_shop_id, platform_shop_id):
            assert (local_shop_id, platform_shop_id) == ("local-1", "123")
            return LocalSession(localShopId=local_shop_id, platformShopId=platform_shop_id, platform="douyin",
                userAgent="synthetic-agent", cookies=[{"name": "session", "value": "synthetic-cookie",
                                                       "domain": ".jinritemai.com", "path": "/"}])

    class NoopExecutor:
        def can_claim(self):
            return True

        async def execute(self, task):
            raise AssertionError("signed capability should handle the task")

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application), base_url="https://integration.test") as http:
            worker_settings = WorkerSettings(server_url="https://integration.test", device_id=device_id,
                                             device_token="synthetic-device-token", runtime_root=tmp_path / "runtime")
            client = WorkerApiClient(worker_settings, client=http)
            updater = CapabilityUpdater((tmp_path / "installed-capabilities").resolve(), public, 1)
            runtime = CapabilityRuntime(updater, CapabilityHost(device_id, client, FakeRpa(), transport=httpx.MockTransport(platform)))
            worker = Worker(worker_settings, client, NoopExecutor(), capability_runtime=runtime)
            await worker._refresh_capabilities_if_due()
            assert runtime.descriptors()[0].skill_id == "douyin.category_schema"
            await worker._heartbeat_once()
            created = await http.post("/internal/applications/v1/worker-prechecks", json=submission().model_dump())
            assert created.status_code == 202
            task = await client.claim()
            assert task is not None and str(task.task_id) == created.json()["task_id"]
            await worker._execute_task(task)
            status = await http.get(f"/internal/applications/v1/worker-prechecks/{task.task_id}")
            assert status.status_code == 200
            result = status.json()
            assert result["status"] == "success"
            assert result["result"]["platform_code"] == 0
            assert result["result"]["items"][0]["options"][-1]["id"] == 2499
            assert "synthetic-cookie" not in status.text and "synthetic-signature" not in status.text
            assert len(status.content) > 64 * 1024
            assert worker.result_outbox.pending() == []
            assert platform_calls == ["/product/tproduct/getSchema"]
            assert (await client.claim()) is None
    try:
        asyncio.run(exercise())
    finally:
        app.__path__.remove(str(worker_root / "app"))
        app.shared.__path__.remove(str(worker_root / "app/shared"))
