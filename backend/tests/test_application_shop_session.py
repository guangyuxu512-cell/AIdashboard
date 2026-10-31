import hashlib
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.exceptions import install_exception_handlers
from app.core.security import SecretCipher
from app.modules.sessions.application_api import (
    authenticator as api_authenticator,
    get_application_session_service,
    router,
)
from app.modules.sessions.application_auth import (
    ApplicationAuthenticationError,
    ApplicationAuthenticator,
    ApplicationSessionUnavailableError,
    ApplicationShopNotFoundError,
)
from app.modules.sessions.application_service import ApplicationSessionService
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import ShopSessionAuthenticationInvalidError, ShopSessionPayloadInvalidError
from app.modules.shops.enums import ShopPlatform


TOKEN = "integration_test_token_abcdefghijklmnopqrstuvwxyz0123456789"
COOKIE = "synthetic-shop-cookie-do-not-log"


class FakeDatabase:
    def __init__(self):
        self.commits = 0
        self.on_commit = None

    def commit(self):
        self.commits += 1
        if self.on_commit:
            self.on_commit()

    def rollback(self):
        pass


class FakeRepository:
    def __init__(self, user, shops, stored):
        self.user, self.shops, self.stored = user, shops, stored

    def lock_authorizer(self, user_id):
        return self.user if self.user.user_id == user_id else None

    def list_shops(self, shop_ids):
        return [(shop, self.stored.status) for shop in self.shops.values() if shop.shop_id in shop_ids]

    def lock_shop(self, shop_id):
        return self.shops.get(shop_id)

    def lock_session(self, shop_id):
        return self.stored if self.stored.shop_id == shop_id else None

    def get_by_shop(self, shop_id):
        return self.lock_session(shop_id)


class FakeAudit:
    def __init__(self):
        self.events = []

    def record_access_management_action(self, **kwargs):
        self.events.append(kwargs)


@pytest.fixture
def setup(tmp_path):
    shop_id, owner_id, other_id = uuid4(), uuid4(), uuid4()
    config_path = tmp_path / "grants.json"
    grant = {
        "client_id": "product-library", "token_sha256": hashlib.sha256(TOKEN.encode()).hexdigest(),
        "authorized_by_user_id": str(owner_id), "enabled": True, "shop_ids": [str(shop_id)],
    }

    def save(grant_value=grant):
        config_path.write_text(json.dumps({"version": 1, "clients": [grant_value]}))

    save()
    auth = ApplicationAuthenticator(enabled=True, path=config_path)
    principal = auth.authenticate("product-library", TOKEN)
    cipher = SecretCipher(Fernet.generate_key().decode())
    payload = {
        "schema": "management-login.session.v1", "platform": "douyin",
        "identity": {"platform": "douyin", "platformShopId": "shop-123", "shopDisplayName": "Test"},
        "cookies": [{"name": "sessionid", "value": COOKIE, "domain": ".jinritemai.com"}],
    }
    stored = SimpleNamespace(
        shop_id=shop_id, status=ShopSessionStatus.VALID, version=7,
        payload_encrypted=cipher.encrypt_bytes(json.dumps(payload).encode()),
    )
    shop = SimpleNamespace(
        shop_id=shop_id, display_name="Test", platform=ShopPlatform.DOUYIN,
        platform_shop_id="shop-123", enabled=True,
    )
    user = SimpleNamespace(user_id=owner_id, display_name="Authorized administrator", enabled=True, is_super_account=True)
    db = FakeDatabase()
    repo = FakeRepository(user, {shop_id: shop}, stored)
    audit = FakeAudit()
    accessor = ShopSessionAccessor(db, cipher, repo)
    service = ApplicationSessionService(db, auth, repository=repo, accessor=accessor, audit=audit)
    return SimpleNamespace(
        shop_id=shop_id, owner_id=owner_id, other_id=other_id, grant=grant, save=save,
        auth=auth, principal=principal, db=db, repo=repo, audit=audit, service=service,
        cipher=cipher, payload=payload, config_path=config_path,
    )


def test_independent_application_reads_only_authorized_shop_with_durable_audit(setup):
    assert [x.shop_id for x in setup.service.list_shops(setup.principal)] == [setup.shop_id]
    result = setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    assert result.session_version == 7
    assert result.cookies[0].value.get_secret_value() == COOKIE
    assert COOKIE not in repr(result) and TOKEN not in repr(setup.principal)
    assert setup.db.commits == 1
    event = setup.audit.events[0]
    assert event["actor"].user_id == setup.owner_id
    assert event["details"]["actor_kind"] == "application"
    assert event["details"]["application_id"] == "product-library"
    assert COOKIE not in repr(event) and TOKEN not in repr(event)


def test_other_shop_is_not_authorized(setup):
    with pytest.raises(ApplicationShopNotFoundError):
        setup.service.read_session(setup.principal, shop_id=setup.other_id, request_id=str(uuid4()))
    assert setup.db.commits == 0 and setup.audit.events == []


@pytest.mark.parametrize("field,value", [("enabled", False), ("is_super_account", False)])
def test_revoked_authorizer_blocks_access(setup, field, value):
    setattr(setup.repo.user, field, value)
    with pytest.raises(ApplicationAuthenticationError):
        setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    assert setup.db.commits == 0


def test_revocation_during_commit_prevents_delivery(setup):
    def revoke():
        setup.grant["enabled"] = False
        setup.save()
    setup.db.on_commit = revoke
    with pytest.raises(ApplicationAuthenticationError):
        setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    assert setup.db.commits == 1 and len(setup.audit.events) == 1


def test_audit_commit_failure_prevents_delivery(setup):
    def fail():
        raise RuntimeError("database failure")
    setup.db.on_commit = fail
    with pytest.raises(RuntimeError):
        setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))


def test_store_identity_mismatch_and_invalid_session_fail_closed(setup):
    setup.repo.shops[setup.shop_id].platform_shop_id = "different-shop"
    with pytest.raises(ShopSessionPayloadInvalidError):
        setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    setup.repo.shops[setup.shop_id].platform_shop_id = "shop-123"
    setup.repo.stored.status = ShopSessionStatus.INVALID
    with pytest.raises(ShopSessionAuthenticationInvalidError):
        setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    assert setup.db.commits == 0


def test_auth_config_is_fail_closed_and_reread(setup):
    with pytest.raises(ApplicationAuthenticationError):
        setup.auth.authenticate("product-library", "wrong-token-abcdefghijklmnopqrstuvwxyz0123456")
    setup.grant["shop_ids"] = [str(setup.other_id)]
    setup.save()
    with pytest.raises(ApplicationShopNotFoundError):
        setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    setup.config_path.write_text("invalid json")
    with pytest.raises(ApplicationSessionUnavailableError):
        setup.auth.authenticate("product-library", TOKEN)


def test_atomic_grant_replacement_is_seen_before_next_session_read(setup, tmp_path):
    assert len(setup.service.list_shops(setup.principal)) == 1
    replacement = tmp_path / "grants-next.json"
    replacement.write_text(json.dumps({"version": 1, "clients": [{**setup.grant, "enabled": False}]}))
    os.replace(replacement, setup.config_path)
    with pytest.raises(ApplicationAuthenticationError):
        setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    assert setup.db.commits == 0


def test_shared_token_between_applications_is_rejected(setup):
    other = dict(setup.grant, client_id="other-software")
    setup.config_path.write_text(json.dumps({"version": 1, "clients": [setup.grant, other]}))
    with pytest.raises(ApplicationSessionUnavailableError):
        setup.auth.authenticate("product-library", TOKEN)


def test_default_disabled_even_if_client_is_configured(setup):
    disabled = ApplicationAuthenticator(enabled=False, path=setup.config_path)
    with pytest.raises(ApplicationSessionUnavailableError):
        disabled.authenticate("product-library", TOKEN)


def test_second_platform_session_uses_its_own_checked_identity(setup):
    setup.payload["platform"] = "pdd"
    setup.payload["identity"]["platform"] = "pdd"
    setup.repo.shops[setup.shop_id].platform = ShopPlatform.PDD
    setup.repo.stored.payload_encrypted = setup.cipher.encrypt_bytes(json.dumps(setup.payload).encode())
    result = setup.service.read_session(setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()))
    assert result.platform is ShopPlatform.PDD


def test_https_api_needs_no_worker_and_rejects_spoofed_proxy_header(setup):
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[api_authenticator] = lambda: setup.auth
    app.dependency_overrides[get_application_session_service] = lambda: setup.service
    headers = {"X-Application-ID": "product-library", "Authorization": f"Bearer {TOKEN}"}
    with TestClient(app, base_url="https://service.test") as client:
        listed = client.get("/internal/applications/v1/shops", headers=headers)
        assert listed.status_code == 200 and len(listed.json()) == 1
        result = client.get(f"/internal/applications/v1/shops/{setup.shop_id}/session", headers=headers)
        assert result.status_code == 200
        assert result.headers["cache-control"] == "no-store"
        assert result.json()["cookies"][0]["value"] == COOKIE
        assert client.get(f"/internal/applications/v1/shops/{setup.shop_id}/session").status_code == 401
    with TestClient(app, base_url="http://service.test") as client:
        result = client.get(
            "/internal/applications/v1/shops", headers={**headers, "X-Forwarded-Proto": "https"},
        )
        assert result.status_code == 403
