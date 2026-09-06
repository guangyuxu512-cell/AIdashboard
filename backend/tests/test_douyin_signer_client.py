import json

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.integrations.douyin_signer import (
    DouyinSignerAuthenticationError,
    DouyinSignerClient,
    DouyinSignerConfigurationError,
    DouyinSignerResponseError,
    DouyinSignRequest,
)


TEST_API_KEY = "test-only-signer-key"


def settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        douyin_signer_api_key=SecretStr(TEST_API_KEY),
        **overrides,
    )


def sign_request() -> DouyinSignRequest:
    return DouyinSignRequest(
        host="example.invalid",
        full_url="https://example.invalid/compass_api/test?item=1",
        method="GET",
        user_agent="Douyin Signer Foundation Test",
    )


def test_client_sends_internal_authenticated_sign_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://127.0.0.1:8787/sign"
        assert request.headers["x-api-key"] == TEST_API_KEY
        assert json.loads(request.content) == {
            "host": "example.invalid",
            "full_url": "https://example.invalid/compass_api/test?item=1",
            "method": "GET",
            "user_agent": "Douyin Signer Foundation Test",
        }
        return httpx.Response(
            200,
            request=request,
            json={
                "ok": True,
                "a_bogus": "synthetic-signature",
                "msToken": "synthetic-ms-token",
                "duration_ms": 12,
                "version": "abogus-node-env-1",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        result = DouyinSignerClient(
            settings=settings(),
            client=http_client,
        ).sign(sign_request())

    assert result.a_bogus.get_secret_value() == "synthetic-signature"
    assert result.ms_token is not None
    assert result.ms_token.get_secret_value() == "synthetic-ms-token"


def test_client_fails_closed_when_api_key_is_not_configured() -> None:
    with pytest.raises(DouyinSignerConfigurationError):
        DouyinSignerClient(
            settings=Settings(_env_file=None, douyin_signer_api_key=""),
        ).sign(sign_request())


@pytest.mark.parametrize(
    ("status_code", "exception"),
    [
        (401, DouyinSignerAuthenticationError),
        (400, DouyinSignerResponseError),
        (200, DouyinSignerResponseError),
    ],
)
def test_client_classifies_unsafe_or_invalid_responses(
    status_code: int,
    exception: type[Exception],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {"ok": False} if status_code == 200 else {"ok": False}
        return httpx.Response(status_code, request=request, json=payload)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(exception):
            DouyinSignerClient(settings=settings(), client=http_client).sign(
                sign_request(),
            )


def test_settings_allow_internal_loopback_or_service_dns_and_mask_api_key() -> None:
    assert Settings(_env_file=None).douyin_signer_url == "http://127.0.0.1:8787"

    configured = settings(douyin_signer_url="http://127.0.0.1:8787/")
    docker_service = settings(douyin_signer_url="http://douyin-signer:8787/")

    assert configured.douyin_signer_url == "http://127.0.0.1:8787"
    assert docker_service.douyin_signer_url == "http://douyin-signer:8787"
    assert TEST_API_KEY not in repr(configured)
    with pytest.raises(ValidationError):
        settings(douyin_signer_url="http://douyin-signer:8787/sign")
