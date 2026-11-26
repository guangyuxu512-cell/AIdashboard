import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.dependencies import get_super_account
from app.modules.access.exceptions import AccessAdministrationForbiddenError
from app.modules.api_tokens.api import require_human_administrator
from app.modules.api_tokens.catalog import permissions_catalog
from app.modules.token_management.api import get_token_management_service
from app.modules.token_management.service import TokenManagementService


BASE = "/api/v1/token-management"
IDENTIFIER = "a" * 32


@pytest.fixture
def app_client(tmp_path):
    credentials = tmp_path / "credentials.json"
    credentials.write_text(json.dumps({
        "product": "synthetic-product-credential",
        "operations": "synthetic-operations-credential",
        "collector": "synthetic-collector-credential",
    }), encoding="utf-8")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"items": []}, headers={"Set-Cookie": "private=ignored"})

    settings = Settings(_env_file=None, runtime_environment="test")
    bridge = TokenManagementService("http://127.0.0.1:18080", credentials, transport=httpx.MockTransport(handler))
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_token_management_service] = lambda: bridge
    app.dependency_overrides[require_human_administrator] = lambda: SimpleNamespace(user_id="synthetic")
    with TestClient(app) as client:
        yield client, calls, app, credentials


def test_each_service_uses_its_own_server_credential_and_returns_no_cookie(app_client):
    client, calls, _, _ = app_client
    for service, path in (
        ("product", "api/v1/tokens/permissions"),
        ("operations", "api/v1/tokens"),
        ("collector", "collector-api/v1/admin/browsers"),
    ):
        response = client.get(f"{BASE}/{service}/{path}")
        assert response.status_code == 200
        assert response.json() == {"items": []}
        assert response.headers["cache-control"] == "no-store"
        assert "set-cookie" not in response.headers
        assert calls[-1].headers["authorization"] == f"Bearer synthetic-{service}-credential"
        assert "cookie" not in calls[-1].headers
        assert f"synthetic-{service}-credential" not in response.text


def test_sourcing_overview_reuses_operations_credential_without_exposing_it(app_client):
    client, calls, _, _ = app_client
    response = client.get('/api/v1/devices/sourcing-account-overview')
    assert response.status_code == 200 and response.json() == {'items': []}
    assert calls[-1].url.path.endswith('/_operations/api/v1/sourcing/worker/overview')
    assert calls[-1].headers['authorization'] == 'Bearer synthetic-operations-credential'
    assert 'set-cookie' not in response.headers


def test_cross_origin_mutations_and_unlisted_paths_never_reach_upstream(app_client):
    client, calls, _, _ = app_client
    target = f"{BASE}/product/api/v1/tokens"
    assert client.post(target, json={"name": "test"}).status_code == 403
    assert client.post(target, json={"name": "test"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post(target, json={"name": "test"}, headers={"Origin": "http://testserver", "Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.get(f"{BASE}/product/api/v1/other").status_code == 404
    assert client.get(target + "?target=elsewhere").status_code == 404
    assert client.patch(f"{target}/{IDENTIFIER}/reveal", headers={"Origin": "http://testserver"}).status_code == 404
    assert calls == []
    assert client.post(target, json={"name": "test"}, headers={"Origin": "http://testserver"}).status_code == 200
    assert json.loads(calls[-1].content) == {"name": "test"}


def test_service_auth_failure_is_not_mistaken_for_human_session_expiry(app_client):
    client, _, app, credentials = app_client
    bridge = TokenManagementService(
        "http://127.0.0.1:18080", credentials,
        transport=httpx.MockTransport(lambda request: httpx.Response(401, text="secret from upstream")),
    )
    app.dependency_overrides[get_token_management_service] = lambda: bridge
    response = client.get(f"{BASE}/product/api/v1/tokens")
    assert response.status_code == 503
    assert "secret" not in response.text
    credentials.unlink()
    assert client.get(f"{BASE}/product/api/v1/tokens").status_code == 503


def test_missing_human_session_is_denied_and_bridge_is_not_an_ai_permission(app_client):
    client, calls, app, _ = app_client
    del app.dependency_overrides[require_human_administrator]
    assert client.get(f"{BASE}/product/api/v1/tokens").status_code == 401
    assert client.get('/api/v1/devices/sourcing-account-overview').status_code == 401
    assert not any("/token-management/" in item["id"] for item in permissions_catalog(app))
    assert calls == []


def test_api_token_and_non_super_account_are_denied(app_client):
    client, calls, app, _ = app_client
    del app.dependency_overrides[require_human_administrator]
    app.dependency_overrides[get_human_principal] = lambda: SimpleNamespace(api_token_id="synthetic-token")
    app.dependency_overrides[get_super_account] = lambda: SimpleNamespace()
    assert client.get(f"{BASE}/product/api/v1/tokens").status_code == 403
    assert client.get('/api/v1/devices/sourcing-account-overview').status_code == 403
    app.dependency_overrides[get_human_principal] = lambda: SimpleNamespace(api_token_id=None)

    def deny_member():
        raise AccessAdministrationForbiddenError()

    app.dependency_overrides[get_super_account] = deny_member
    assert client.get(f"{BASE}/product/api/v1/tokens").status_code == 403
    assert client.get('/api/v1/devices/sourcing-account-overview').status_code == 403
    assert calls == []


def test_proxy_configuration_cannot_point_at_nonlocal_host():
    with pytest.raises(ValueError):
        Settings(_env_file=None, token_manager_proxy_origin="https://example.com")
