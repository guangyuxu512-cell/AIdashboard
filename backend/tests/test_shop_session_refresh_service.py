import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.config import Settings
from app.core.security import SecretCipher
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionRefreshLeaseConflictError,
    SessionVersionConflictError,
)
from app.modules.sessions.models import ShopSession
from app.modules.sessions.refresh_service import ShopSessionRefreshService
from app.modules.sessions.schemas import (
    CompleteShopSessionRefreshCommand,
    ShopSessionHealthRead,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from tests.support import FakeSession


class FakeShopRepository:
    def __init__(self, shop: Shop) -> None:
        self.shop = shop

    def get(self, shop_id: UUID) -> Shop | None:
        return self.shop if self.shop.shop_id == shop_id else None


class FakeRepository:
    def __init__(self, stored: ShopSession) -> None:
        self.stored = stored

    def get_by_shop(self, shop_id: UUID) -> ShopSession | None:
        return self.stored if self.stored.shop_id == shop_id else None

    def acquire_refresh_lease(
        self,
        *,
        shop_id: UUID,
        lease_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> bool:
        del shop_id
        if (
            self.stored.refresh_lease_id is not None
            and self.stored.refresh_lease_expires_at is not None
            and self.stored.refresh_lease_expires_at > now
        ):
            return False
        self.stored.refresh_lease_id = lease_id
        self.stored.refresh_lease_expires_at = expires_at
        return True

    def has_active_refresh_lease(
        self,
        *,
        shop_id: UUID,
        lease_id: UUID,
        now: datetime,
    ) -> bool:
        del shop_id
        return (
            self.stored.refresh_lease_id == lease_id
            and self.stored.refresh_lease_expires_at is not None
            and self.stored.refresh_lease_expires_at > now
        )

    def release_refresh_lease(self, *, shop_id: UUID, lease_id: UUID) -> bool:
        del shop_id
        if self.stored.refresh_lease_id != lease_id:
            return False
        self.stored.refresh_lease_id = None
        self.stored.refresh_lease_expires_at = None
        return True


class FakeSessionService:
    def __init__(self, stored: ShopSession) -> None:
        self.stored = stored
        self.payload: bytes | None = None

    def store_payload(self, command, payload: bytes):
        if self.stored.version != command.expected_version:
            raise SessionVersionConflictError()
        self.stored.version += 1
        self.stored.status = command.status
        self.payload = payload


class FakeHealthService:
    def __init__(
        self,
        stored: ShopSession,
        *,
        status: ShopSessionStatus = ShopSessionStatus.VALID,
    ) -> None:
        self.stored = stored
        self.status = status

    def check(self, shop_id: UUID, *, force: bool) -> ShopSessionHealthRead:
        assert force is True
        self.stored.status = self.status
        return ShopSessionHealthRead(
            shop_id=shop_id,
            platform=ShopPlatform.DOUYIN,
            platform_shop_id="shop-1",
            shop_display_name="HuanYu",
            status=self.status,
            version=self.stored.version,
            validated_at=datetime.now(UTC),
            used_cached_validation=False,
            cookie_updates_applied=0,
        )


def make_service(
    *,
    health_status: ShopSessionStatus = ShopSessionStatus.VALID,
    collection_resume=None,
):
    shop_id = uuid4()
    now = datetime.now(UTC)
    shop = Shop(
        shop_id=shop_id,
        display_name="HuanYu",
        platform=ShopPlatform.DOUYIN,
        platform_shop_id="shop-1",
        enabled=True,
    )
    stored = ShopSession(
        session_id=uuid4(),
        shop_id=shop_id,
        version=3,
        status=ShopSessionStatus.INVALID,
        source_device_id=None,
        captured_at=now,
        validated_at=now,
        expires_at=None,
        payload_encrypted=b"encrypted",
    )
    repository = FakeRepository(stored)
    session_service = FakeSessionService(stored)
    service = ShopSessionRefreshService(
        FakeSession(),  # type: ignore[arg-type]
        SecretCipher(Fernet.generate_key().decode()),
        FakeHealthService(stored, status=health_status),  # type: ignore[arg-type]
        repository=repository,  # type: ignore[arg-type]
        shop_repository=FakeShopRepository(shop),  # type: ignore[arg-type]
        session_service=session_service,  # type: ignore[arg-type]
        collection_resume=collection_resume or (lambda _shop_id: 0),
        settings=Settings(_env_file=None, shop_session_refresh_lease_seconds=60),
    )
    return service, stored, session_service


def captured_payload() -> bytes:
    return json.dumps(
        {
            "schema": "management-login.session.v1",
            "platform": "douyin",
            "identity": {
                "platform": "douyin",
                "platformShopId": "shop-1",
                "shopDisplayName": "HuanYu",
            },
            "cookies": [{"name": "sessionid", "value": "secret"}],
        },
    ).encode()


def test_refresh_lease_blocks_concurrent_attempt_and_recovers_after_expiry() -> None:
    service, stored, _ = make_service()

    first = service.acquire(stored.shop_id)
    with pytest.raises(SessionRefreshLeaseConflictError):
        service.acquire(stored.shop_id)

    stored.refresh_lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    second = service.acquire(stored.shop_id)

    assert second.lease_id != first.lease_id


def test_cancel_releases_lease_and_complete_uses_expected_version() -> None:
    service, stored, session_service = make_service()
    cancelled = service.acquire(stored.shop_id)
    service.release(stored.shop_id, cancelled.lease_id)
    assert stored.refresh_lease_id is None

    lease = service.acquire(stored.shop_id)
    result = service.complete(
        stored.shop_id,
        CompleteShopSessionRefreshCommand(
            lease_id=lease.lease_id,
            expected_version=lease.expected_version,
            session_payload_base64=SecretStr(
                base64.b64encode(captured_payload()).decode(),
            ),
            captured_at=datetime.now(UTC),
        ),
    )

    assert result.status is ShopSessionStatus.VALID
    assert result.version == 4
    assert session_service.payload == captured_payload()
    assert stored.refresh_lease_id is None


def test_version_conflict_rejects_overwrite_and_releases_lease() -> None:
    service, stored, session_service = make_service()
    lease = service.acquire(stored.shop_id)
    stored.version += 1

    with pytest.raises(SessionVersionConflictError):
        service.complete(
            stored.shop_id,
            CompleteShopSessionRefreshCommand(
                lease_id=lease.lease_id,
                expected_version=lease.expected_version,
                session_payload_base64=SecretStr(
                    base64.b64encode(captured_payload()).decode(),
                ),
                captured_at=datetime.now(UTC),
            ),
        )

    assert session_service.payload is None
    assert stored.refresh_lease_id is None


def test_refresh_does_not_resume_operating_collection_until_health_is_valid() -> None:
    resumed_shop_ids: list[UUID] = []
    service, stored, _ = make_service(
        health_status=ShopSessionStatus.CAPTURED,
        collection_resume=resumed_shop_ids.append,
    )
    lease = service.acquire(stored.shop_id)

    result = service.complete(
        stored.shop_id,
        CompleteShopSessionRefreshCommand(
            lease_id=lease.lease_id,
            expected_version=lease.expected_version,
            session_payload_base64=SecretStr(
                base64.b64encode(captured_payload()).decode(),
            ),
            captured_at=datetime.now(UTC),
        ),
    )

    assert result.status is ShopSessionStatus.CAPTURED
    assert resumed_shop_ids == []
