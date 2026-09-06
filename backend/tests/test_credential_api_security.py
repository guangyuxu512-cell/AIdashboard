from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.credentials.api import get_credential_service, get_shop_authorized_actor
from app.modules.credentials.enums import VerificationChannel
from app.modules.credentials.schemas import CredentialStatusRead
from app.modules.sessions.api import (
    get_shop_authorized_actor as get_session_shop_authorized_actor,
    get_shop_session_service,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.schemas import ShopSessionMetadataRead
from app.modules.shops.enums import ShopPlatform


SHOP_ID = uuid4()
CREDENTIAL_ID = uuid4()
API_ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="Credential API operator",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)


class ApiCredentialService:
    @staticmethod
    def _status() -> CredentialStatusRead:
        return CredentialStatusRead(
            credential_id=CREDENTIAL_ID,
            platform=ShopPlatform.DOUYIN,
            masked_identifier="138****8888",
            configured=True,
            enabled=True,
            preferred_verification_channel=VerificationChannel.MANUAL,
            updated_at=datetime.now(UTC),
        )

    def get_status_for_shop(self, shop_id: UUID) -> CredentialStatusRead:
        return self._status()

    def create(self, data: object) -> CredentialStatusRead:
        return self._status()

    def update(self, credential_id: UUID, data: object) -> CredentialStatusRead:
        return self._status()

    def disable(self, credential_id: UUID) -> CredentialStatusRead:
        status = self._status()
        return status.model_copy(update={"enabled": False})


class ApiSessionService:
    def get_metadata(self, shop_id: UUID) -> ShopSessionMetadataRead:
        return ShopSessionMetadataRead(
            session_id=None,
            configured=False,
            status=ShopSessionStatus.NOT_CONFIGURED,
            version=0,
            source_device_id=None,
            captured_at=None,
            validated_at=None,
            expires_at=None,
        )


def request(method: str, path: str, **kwargs: object) -> Response:
    application = create_app()
    application.dependency_overrides[get_credential_service] = ApiCredentialService
    application.dependency_overrides[get_shop_session_service] = ApiSessionService
    application.dependency_overrides[get_shop_authorized_actor] = lambda: API_ACTOR
    application.dependency_overrides[get_session_shop_authorized_actor] = (
        lambda: API_ACTOR
    )

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_credential_and_session_reads_never_return_sensitive_payloads() -> None:
    credential_response = request("GET", f"/api/v1/shops/{SHOP_ID}/credential")
    session_response = request("GET", f"/api/v1/shops/{SHOP_ID}/session")

    assert credential_response.status_code == 200
    assert credential_response.json()["masked_identifier"] == "138****8888"
    assert "secret" not in credential_response.text.lower()
    assert "password" not in credential_response.text.lower()

    assert session_response.status_code == 200
    assert session_response.json()["status"] == "not_configured"
    assert "payload" not in session_response.text.lower()
    assert "cookie" not in session_response.text.lower()


def test_validation_errors_and_logs_redact_secret(caplog: object) -> None:
    plaintext = "sensitive-stage-3a-" + "x" * 1000
    response = request(
        "POST",
        "/api/v1/credentials",
        json={
            "shop_id": str(SHOP_ID),
            "login_identifier": "13812348888",
            "secret": plaintext,
        },
    )

    assert response.status_code == 422
    assert plaintext not in response.text
    assert "[REDACTED]" in response.text
    assert plaintext not in caplog.text  # type: ignore[attr-defined]


def test_openapi_has_write_only_secret_and_safe_read_schemas() -> None:
    schema = create_app().openapi()
    components = schema["components"]["schemas"]

    create_secret = components["CredentialCreate"]["properties"]["secret"]
    credential_read = components["CredentialStatusRead"]["properties"]
    session_read = components["ShopSessionMetadataRead"]["properties"]

    assert create_secret["format"] == "password"
    assert create_secret["writeOnly"] is True
    assert "secret" not in credential_read
    assert "secret_encrypted" not in credential_read
    assert not any("password" in field for field in credential_read)
    assert "payload" not in session_read
    assert "payload_encrypted" not in session_read
