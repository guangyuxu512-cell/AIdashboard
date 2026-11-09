import hashlib
import asyncio
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
import httpx
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
    ApplicationSessionBusyError,
    ApplicationMerchantIdentityUnverifiedError,
    ApplicationMerchantValidationUnavailableError,
    ApplicationShopNotFoundError,
)
from app.modules.sessions.application_service import ApplicationSessionService
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import ShopSessionAuthenticationInvalidError, ShopSessionPayloadInvalidError
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.merchant_identity import (
    MerchantIdentityUnverified,
    MerchantValidationUnavailable,
    verify_merchant_session,
)


TOKEN = "integration_test_token_abcdefghijklmnopqrstuvwxyz0123456789"
COOKIE = "synthetic-shop-cookie-do-not-log"


class FakeDatabase:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.on_commit = None

    def commit(self):
        self.commits += 1
        if self.on_commit:
            self.on_commit()

    def rollback(self):
        self.rollbacks += 1


class FakeRepository:
    def __init__(self, user, shops, stored):
        self.user, self.shops, self.stored = user, shops, stored

    def lock_authorizer(self, user_id):
        return self.user if self.user.user_id == user_id else None

    def list_shops(self, shop_ids):
        return [(shop, self.stored.status if self.stored else None,
                 self.stored.version if self.stored else None) for shop in self.shops.values()
                if shop.shop_id in shop_ids and shop.enabled]

    def lock_shop(self, shop_id):
        shop = self.shops.get(shop_id)
        return shop if shop and shop.enabled else None

    def lock_session(self, shop_id):
        return self.stored if self.stored and self.stored.shop_id == shop_id else None

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


def test_merchant_access_releases_locks_before_probe_then_rechecks_snapshot(setup):
    calls = []

    async def verify(context, target):
        assert setup.db.rollbacks == 1
        assert context.session_version == 7
        assert target == "shop-123"
        calls.append("verified")

    setup.service.merchant_verifier = verify
    result = setup.service.read_session(
        setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()), merchant=True,
    )
    assert calls == ["verified"]
    assert result.session_version == 7
    assert setup.db.commits == 1
    assert len(setup.audit.events) == 1


@pytest.mark.parametrize("error", [MerchantIdentityUnverified(), MerchantValidationUnavailable()])
def test_merchant_unverified_or_unavailable_never_delivers_or_writes(setup, error):
    async def verify(_context, _target):
        assert setup.db.rollbacks == 1
        raise error

    setup.service.merchant_verifier = verify
    expected = (
        ApplicationMerchantIdentityUnverifiedError
        if isinstance(error, MerchantIdentityUnverified)
        else ApplicationMerchantValidationUnavailableError
    )
    with pytest.raises(expected):
        setup.service.read_session(
            setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()), merchant=True,
        )
    assert setup.db.commits == 0
    assert setup.audit.events == []


@pytest.mark.parametrize("change", ["version", "status", "payload", "identity", "disabled", "revoked"])
def test_merchant_read_rejects_concurrent_changes_before_release(setup, change):
    async def verify(_context, _target):
        assert setup.db.rollbacks == 1
        if change == "version":
            setup.repo.stored.version += 1
        elif change == "status":
            setup.repo.stored.status = ShopSessionStatus.INVALID
        elif change == "payload":
            setup.repo.stored.payload_encrypted = b"different-ciphertext"
        elif change == "identity":
            setup.repo.shops[setup.shop_id].platform_shop_id = "changed-shop"
        elif change == "disabled":
            setup.repo.shops[setup.shop_id].enabled = False
        else:
            setup.grant["enabled"] = False
            setup.save()

    setup.service.merchant_verifier = verify
    expected = (
        ApplicationShopNotFoundError if change == "disabled"
        else ApplicationAuthenticationError if change == "revoked"
        else ApplicationSessionBusyError
    )
    with pytest.raises(expected):
        setup.service.read_session(
            setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()), merchant=True,
        )
    assert setup.db.commits == 0
    assert setup.audit.events == []


def test_unrequested_merchant_purpose_never_calls_platform(setup):
    async def unexpected(_context, _target):
        raise AssertionError("unexpected merchant request")

    setup.service.merchant_verifier = unexpected
    assert setup.service.read_session(
        setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()),
    ).session_version == 7
    assert setup.db.rollbacks == 0


@pytest.mark.parametrize("identity", [None, "different-shop"])
def test_missing_or_wrong_stored_identity_is_unverified_before_probe(setup, identity):
    if identity is None:
        setup.payload["identity"] = None
    else:
        setup.payload["identity"]["platformShopId"] = identity
    setup.repo.stored.payload_encrypted = setup.cipher.encrypt_bytes(json.dumps(setup.payload).encode())

    async def unexpected(*_args):
        raise AssertionError("unverified stored identity must not call platform")

    setup.service.merchant_verifier = unexpected
    with pytest.raises(ApplicationMerchantIdentityUnverifiedError):
        setup.service.read_session(
            setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()), merchant=True,
        )
    assert setup.db.commits == 0


def test_merchant_total_deadline_stops_slow_probe_without_delivery(setup, monkeypatch):
    async def slow(_context, _target):
        await asyncio.sleep(0.2)

    setup.service.merchant_verifier = slow
    monkeypatch.setattr("app.modules.sessions.application_service.MERCHANT_VERIFICATION_TOTAL_SECONDS", 0.02)
    with pytest.raises(ApplicationMerchantValidationUnavailableError):
        setup.service.read_session(
            setup.principal, shop_id=setup.shop_id, request_id=str(uuid4()), merchant=True,
        )
    assert setup.db.commits == 0


def test_merchant_header_contract_and_fail_closed_with_old_or_invalid_purpose(setup):
    async def verified(_context, _target):
        return None

    setup.service.merchant_verifier = verified
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[api_authenticator] = lambda: setup.auth
    app.dependency_overrides[get_application_session_service] = lambda: setup.service
    headers = {"X-Application-ID": "product-library", "Authorization": f"Bearer {TOKEN}"}
    path = f"/internal/applications/v1/shops/{setup.shop_id}/session"
    with TestClient(app, base_url="https://service.test") as client:
        generic = client.get(path, headers=headers)
        assert generic.status_code == 200
        assert "X-Merchant-Identity-Verified" not in generic.headers
        assert setup.db.rollbacks == 0
        checked = client.get(path, headers={**headers, "X-Session-Purpose": "merchant"})
        assert checked.status_code == 200
        assert checked.headers["X-Merchant-Identity-Verified"] == "1"
        assert checked.json().keys() == generic.json().keys()
        assert "no-store" in checked.headers["Cache-Control"].lower()
        invalid = client.get(path, headers={**headers, "X-Session-Purpose": "other"})
        assert invalid.status_code == 400
        assert "X-Merchant-Identity-Verified" not in invalid.headers


@pytest.mark.parametrize("failure,status,code", [
    (MerchantIdentityUnverified(), 409, "APPLICATION_MERCHANT_IDENTITY_UNVERIFIED"),
    (MerchantValidationUnavailable(), 503, "APPLICATION_MERCHANT_VALIDATION_UNAVAILABLE"),
])
def test_merchant_http_failures_do_not_issue_success_marker_or_session(setup, failure, status, code):
    async def verify(_context, _target):
        raise failure

    setup.service.merchant_verifier = verify
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[api_authenticator] = lambda: setup.auth
    app.dependency_overrides[get_application_session_service] = lambda: setup.service
    headers = {"X-Application-ID": "product-library", "Authorization": f"Bearer {TOKEN}",
               "X-Session-Purpose": "merchant"}
    with TestClient(app, base_url="https://service.test") as client:
        response = client.get(f"/internal/applications/v1/shops/{setup.shop_id}/session", headers=headers)
    assert response.status_code == status
    assert response.json()["code"] == code
    assert "X-Merchant-Identity-Verified" not in response.headers
    assert COOKIE not in response.text
    assert setup.db.commits == 0


@pytest.mark.parametrize("merchant,status", [
    ({"code": 0, "data": {"id": "shop-123"}}, 200),
    ({"code": 0, "data": {"id": "other-shop"}}, 409),
    ({"code": 10008}, 409),
])
def test_legacy_unmarked_snapshot_is_checked_through_merchant_http_path(setup, merchant, status):
    paths = []

    def platform(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        body = {"st": 0, "data": {"shop_id": "shop-123"}} if request.url.host.startswith("compass.") else merchant
        return httpx.Response(200, request=request, json=body)

    async def verify(context, target):
        await verify_merchant_session(context, target, transport=httpx.MockTransport(platform))

    setup.service.merchant_verifier = verify
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[api_authenticator] = lambda: setup.auth
    app.dependency_overrides[get_application_session_service] = lambda: setup.service
    headers = {"X-Application-ID": "product-library", "Authorization": f"Bearer {TOKEN}",
               "X-Session-Purpose": "merchant"}
    with TestClient(app, base_url="https://service.test") as client:
        response = client.get(f"/internal/applications/v1/shops/{setup.shop_id}/session", headers=headers)
    assert response.status_code == status
    assert paths == ["/compass_api/shop/mall/common/shop_info_v2", "/common/index/index"]
    if status == 200:
        assert response.headers["X-Merchant-Identity-Verified"] == "1"
    else:
        assert response.json()["code"] == "APPLICATION_MERCHANT_IDENTITY_UNVERIFIED"
        assert "X-Merchant-Identity-Verified" not in response.headers
        assert COOKIE not in response.text


@pytest.mark.parametrize("status,version,expected", [
    (ShopSessionStatus.VALID, 7, 7),
    (ShopSessionStatus.INVALID, 7, 7),
    (ShopSessionStatus.NOT_CONFIGURED, 1, None),
    (None, None, None),
])
def test_merchant_shop_list_only_exposes_authorized_version_metadata(setup, status, version, expected):
    if status is None:
        setup.repo.stored = None
    else:
        setup.repo.stored.status = status
        setup.repo.stored.version = version

    class ForbiddenAccessor:
        def get_auth_context(self, *_args):
            raise AssertionError("metadata must not read the Session")

    async def forbidden_probe(*_args):
        raise AssertionError("metadata must not request the platform")

    setup.service.accessor = ForbiddenAccessor()
    setup.service.merchant_verifier = forbidden_probe
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[api_authenticator] = lambda: setup.auth
    app.dependency_overrides[get_application_session_service] = lambda: setup.service
    headers = {"X-Application-ID": "product-library", "Authorization": f"Bearer {TOKEN}"}
    with TestClient(app, base_url="https://service.test") as client:
        generic = client.get("/internal/applications/v1/shops", headers=headers)
        assert generic.status_code == 200
        assert "session_version" not in generic.json()[0]
        assert "X-Session-Metadata-Version" not in generic.headers
        merchant = client.get("/internal/applications/v1/shops", headers={**headers, "X-Session-Purpose": "merchant"})
        assert merchant.status_code == 200
        assert merchant.headers["X-Session-Metadata-Version"] == "1"
        assert merchant.json()[0]["session_version"] == expected
        assert merchant.json()[0]["session_status"] == (status.value if status else None)
        assert set(merchant.json()[0]) == set(generic.json()[0]) | {"session_version"}
        assert setup.db.rollbacks == 0
        invalid = client.get("/internal/applications/v1/shops", headers={**headers, "X-Session-Purpose": "other"})
        assert invalid.status_code == 400
        assert "X-Session-Metadata-Version" not in invalid.headers


def test_merchant_version_list_filters_shop_revoked_before_response(setup):
    original_list = setup.repo.list_shops

    def revoke_after_query(shop_ids):
        rows = original_list(shop_ids)
        setup.grant["shop_ids"] = [str(setup.other_id)]
        setup.save()
        return rows

    setup.repo.list_shops = revoke_after_query
    assert setup.service.list_shops(setup.principal, merchant=True) == []


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
