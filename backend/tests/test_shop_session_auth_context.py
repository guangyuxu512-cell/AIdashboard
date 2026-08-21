import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.security import SecretCipher
from app.modules.sessions.auth_context import ShopSessionAccessor, StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.models import ShopSession
from app.modules.shops.enums import ShopPlatform
from tests.support import FakeSession


class FakeShopSessionRepository:
    def __init__(self, item: ShopSession | None) -> None:
        self.item = item

    def get_by_shop(self, shop_id: UUID) -> ShopSession | None:
        if self.item is not None and self.item.shop_id == shop_id:
            return self.item
        return None

    def set_validation_status(
        self,
        *,
        shop_id: UUID,
        expected_version: int,
        status: ShopSessionStatus,
        validated_at: datetime,
    ) -> bool:
        if (
            self.item is None
            or self.item.shop_id != shop_id
            or self.item.version != expected_version
        ):
            return False
        self.item.status = status
        self.item.validated_at = validated_at
        return True


def session_payload(cookie_value: str = "secret-cookie") -> bytes:
    return json.dumps(
        {
            "schema": "management-login.session.v1",
            "platform": "douyin",
            "cookies": [
                {
                    "name": "sessionid",
                    "value": cookie_value,
                    "domain": ".jinritemai.com",
                    "path": "/",
                    "secure": True,
                },
            ],
        },
    ).encode()


def stored_session(
    cipher: SecretCipher,
    shop_id: UUID,
    *,
    status: ShopSessionStatus = ShopSessionStatus.CAPTURED,
    payload: bytes | None = None,
) -> ShopSession:
    now = datetime.now(UTC)
    return ShopSession(
        session_id=uuid4(),
        shop_id=shop_id,
        version=1,
        status=status,
        source_device_id=None,
        captured_at=now,
        validated_at=None,
        expires_at=now + timedelta(hours=1),
        payload_encrypted=cipher.encrypt_bytes(payload or session_payload()),
    )


def test_accessor_decrypts_and_validates_current_session() -> None:
    shop_id = uuid4()
    cipher = SecretCipher(Fernet.generate_key().decode())
    item = stored_session(cipher, shop_id)
    accessor = ShopSessionAccessor(
        FakeSession(),  # type: ignore[arg-type]
        cipher,
        FakeShopSessionRepository(item),  # type: ignore[arg-type]
    )

    context = accessor.get_auth_context(shop_id, ShopPlatform.DOUYIN)

    assert context.shop_id == shop_id
    assert context.platform is ShopPlatform.DOUYIN
    assert context.session_version == 1
    assert context.cookies[0].name == "sessionid"
    assert context.cookies[0].value.get_secret_value() == "secret-cookie"
    assert "secret-cookie" not in repr(context)


def test_accessor_classifies_missing_damaged_and_invalid_sessions() -> None:
    shop_id = uuid4()
    cipher = SecretCipher(Fernet.generate_key().decode())
    missing = ShopSessionAccessor(
        FakeSession(),  # type: ignore[arg-type]
        cipher,
        FakeShopSessionRepository(None),  # type: ignore[arg-type]
    )
    with pytest.raises(ShopSessionNotConfiguredError):
        missing.get_auth_context(shop_id, ShopPlatform.DOUYIN)

    damaged_item = stored_session(cipher, shop_id)
    damaged_item.payload_encrypted = b"not-a-fernet-payload"
    damaged = ShopSessionAccessor(
        FakeSession(),  # type: ignore[arg-type]
        cipher,
        FakeShopSessionRepository(damaged_item),  # type: ignore[arg-type]
    )
    with pytest.raises(ShopSessionPayloadInvalidError):
        damaged.get_auth_context(shop_id, ShopPlatform.DOUYIN)

    invalid_item = stored_session(
        cipher,
        shop_id,
        status=ShopSessionStatus.INVALID,
    )
    invalid = ShopSessionAccessor(
        FakeSession(),  # type: ignore[arg-type]
        cipher,
        FakeShopSessionRepository(invalid_item),  # type: ignore[arg-type]
    )
    with pytest.raises(ShopSessionAuthenticationInvalidError):
        invalid.get_auth_context(shop_id, ShopPlatform.DOUYIN)


def test_accessor_keeps_expired_cookie_for_authoritative_remote_validation() -> None:
    shop_id = uuid4()
    cipher = SecretCipher(Fernet.generate_key().decode())
    payload = json.dumps(
        {
            "schema": "management-login.session.v1",
            "platform": "douyin",
            "cookies": [
                {
                    "name": "sessionid",
                    "value": "remote-may-still-accept",
                    "domain": ".jinritemai.com",
                    "expirationDate": 1,
                },
            ],
        },
    ).encode()
    item = stored_session(cipher, shop_id, payload=payload)
    item.expires_at = datetime.now(UTC) - timedelta(days=1)
    accessor = ShopSessionAccessor(
        FakeSession(),  # type: ignore[arg-type]
        cipher,
        FakeShopSessionRepository(item),  # type: ignore[arg-type]
    )

    context = accessor.get_auth_context(shop_id, ShopPlatform.DOUYIN)

    assert context.cookies[0].name == "sessionid"


def test_response_cookie_merge_preserves_payload_and_cookie_attributes() -> None:
    shop_id = uuid4()
    cipher = SecretCipher(Fernet.generate_key().decode())
    payload = json.dumps(
        {
            "schema": "management-login.session.v1",
            "platform": "douyin",
            "identity": {
                "platform": "douyin",
                "platformShopId": "shop-1",
                "shopDisplayName": "HuanYu",
            },
            "storage": {"origin": "https://fxg.jinritemai.com"},
            "cookies": [
                {
                    "name": "sessionid",
                    "value": "old-secret",
                    "domain": ".jinritemai.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                },
            ],
        },
    ).encode()
    item = stored_session(cipher, shop_id, payload=payload)
    accessor = ShopSessionAccessor(
        FakeSession(),  # type: ignore[arg-type]
        cipher,
        FakeShopSessionRepository(item),  # type: ignore[arg-type]
    )

    merged, count = accessor.merge_response_cookies(
        shop_id,
        (
            StoredSessionCookie(
                name="sessionid",
                value=SecretStr("new-secret"),
                domain="jinritemai.com",
                path="/",
                secure=True,
                httpOnly=True,
                sameSite="Lax",
            ),
        ),
    )
    decoded = json.loads(merged)

    assert count == 1
    assert decoded["cookies"][0]["value"] == "new-secret"
    assert decoded["cookies"][0]["httpOnly"] is True
    assert decoded["cookies"][0]["sameSite"] == "Lax"
    assert decoded["storage"]["origin"] == "https://fxg.jinritemai.com"
