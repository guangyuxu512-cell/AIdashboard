from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from app.core.security import SecretCipher
from app.modules.devices.models import Device
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import SessionVersionConflictError
from app.modules.sessions.models import ShopSession
from app.modules.sessions.schemas import StoreShopSessionCommand
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from tests.support import FakeSession


class FakeEntityRepository:
    def __init__(self, items: dict[UUID, object]) -> None:
        self.items = items

    def get(self, identifier: UUID) -> object | None:
        return self.items.get(identifier)


class FakeShopSessionRepository:
    def __init__(self) -> None:
        self.item: ShopSession | None = None

    def get_by_shop(self, shop_id: UUID) -> ShopSession | None:
        return self.item if self.item and self.item.shop_id == shop_id else None

    def add(self, shop_session: ShopSession) -> None:
        shop_session.session_id = uuid4()
        shop_session.created_at = datetime.now(UTC)
        shop_session.updated_at = shop_session.created_at
        self.item = shop_session

    def update_if_version(self, **changes: object) -> bool:
        if self.item is None or self.item.version != changes["expected_version"]:
            return False
        self.item.version += 1
        for field in (
            "status",
            "source_device_id",
            "captured_at",
            "validated_at",
            "expires_at",
            "payload_encrypted",
        ):
            setattr(self.item, field, changes[field])
        self.item.updated_at = datetime.now(UTC)
        return True


def test_session_payload_is_encrypted_and_version_checked() -> None:
    shop_id = uuid4()
    device_id = uuid4()
    shop = Shop(
        shop_id=shop_id,
        display_name="Session 店铺",
        platform=ShopPlatform.DOUYIN,
        enabled=True,
    )
    device = Device(device_id=device_id, display_name="PC-A", enabled=True)
    repository = FakeShopSessionRepository()
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    service = ShopSessionService(
        FakeSession(),  # type: ignore[arg-type]
        cipher,
        repository,  # type: ignore[arg-type]
        FakeEntityRepository({shop_id: shop}),  # type: ignore[arg-type]
        FakeEntityRepository({device_id: device}),  # type: ignore[arg-type]
    )
    payload = b"cookie=stage-3a-session"
    now = datetime.now(UTC)

    created = service.store_payload(
        StoreShopSessionCommand(
            shop_id=shop_id,
            expected_version=0,
            status=ShopSessionStatus.VALID,
            source_device_id=device_id,
            captured_at=now,
            validated_at=now,
        ),
        payload,
    )

    assert created.version == 1
    assert repository.item is not None
    assert payload not in repository.item.payload_encrypted
    assert cipher.decrypt_bytes(repository.item.payload_encrypted) == payload

    with pytest.raises(SessionVersionConflictError):
        service.store_payload(
            StoreShopSessionCommand(
                shop_id=shop_id,
                expected_version=0,
                status=ShopSessionStatus.REFRESH_REQUIRED,
                source_device_id=device_id,
                captured_at=now,
            ),
            b"new-session",
        )

    updated = service.store_payload(
        StoreShopSessionCommand(
            shop_id=shop_id,
            expected_version=1,
            status=ShopSessionStatus.REFRESH_REQUIRED,
            source_device_id=device_id,
            captured_at=now,
        ),
        b"new-session",
    )
    assert updated.version == 2
