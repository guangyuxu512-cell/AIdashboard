import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import SecretCipher
from app.modules.sessions.auth_context import StoredManagementSessionPayload
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionRefreshLeaseConflictError,
    SessionRefreshLeaseInvalidError,
    SessionVersionConflictError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.sessions.schemas import (
    CompleteShopSessionRefreshCommand,
    ShopSessionHealthRead,
    ShopSessionRefreshLeaseRead,
    StoreShopSessionCommand,
)
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.repository import ShopRepository


class ShopSessionRefreshService:
    def __init__(
        self,
        session: Session,
        cipher: SecretCipher,
        health_service: ShopSessionHealthService,
        *,
        repository: ShopSessionRepository | None = None,
        shop_repository: ShopRepository | None = None,
        session_service: ShopSessionService | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ShopSessionRepository(session)
        self.shop_repository = shop_repository or ShopRepository(session)
        self.session_service = session_service or ShopSessionService(session, cipher)
        self.health_service = health_service
        self.settings = settings or get_settings()

    def acquire(self, shop_id: UUID) -> ShopSessionRefreshLeaseRead:
        if self.shop_repository.get(shop_id) is None:
            raise ShopNotFoundError()
        stored = self.repository.get_by_shop(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        now = datetime.now(UTC)
        lease_id = uuid4()
        expires_at = now + timedelta(
            seconds=self.settings.shop_session_refresh_lease_seconds,
        )
        if not self.repository.acquire_refresh_lease(
            shop_id=shop_id,
            lease_id=lease_id,
            now=now,
            expires_at=expires_at,
        ):
            self.session.rollback()
            raise SessionRefreshLeaseConflictError()
        self.session.commit()
        current = self.repository.get_by_shop(shop_id)
        if current is None:
            raise ShopSessionNotConfiguredError()
        return ShopSessionRefreshLeaseRead(
            shop_id=shop_id,
            lease_id=lease_id,
            expected_version=current.version,
            expires_at=expires_at,
        )

    def release(self, shop_id: UUID, lease_id: UUID) -> None:
        self.repository.release_refresh_lease(shop_id=shop_id, lease_id=lease_id)
        self.session.commit()

    def complete(
        self,
        shop_id: UUID,
        command: CompleteShopSessionRefreshCommand,
    ) -> ShopSessionHealthRead:
        now = datetime.now(UTC)
        if not self.repository.has_active_refresh_lease(
            shop_id=shop_id,
            lease_id=command.lease_id,
            now=now,
        ):
            raise SessionRefreshLeaseInvalidError()
        try:
            return self._complete_under_lease(shop_id, command)
        finally:
            self.release(shop_id, command.lease_id)

    def _complete_under_lease(
        self,
        shop_id: UUID,
        command: CompleteShopSessionRefreshCommand,
    ) -> ShopSessionHealthRead:
        stored = self.repository.get_by_shop(shop_id)
        shop = self.shop_repository.get(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        if shop is None:
            raise ShopNotFoundError()
        if stored.version != command.expected_version:
            raise SessionVersionConflictError()

        try:
            payload = base64.b64decode(
                command.session_payload_base64.get_secret_value(),
                validate=True,
            )
            parsed = StoredManagementSessionPayload.model_validate(
                json.loads(payload),
            )
        except (
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
        ) as error:
            raise ShopSessionPayloadInvalidError() from error
        if parsed.platform is not shop.platform:
            raise ShopSessionPayloadInvalidError()
        if (
            parsed.identity is not None
            and shop.platform_shop_id is not None
            and parsed.identity.platform_shop_id != shop.platform_shop_id
        ):
            raise ShopSessionPayloadInvalidError("登录身份与目标店铺不匹配")

        self.session_service.store_payload(
            StoreShopSessionCommand(
                shop_id=shop_id,
                expected_version=command.expected_version,
                status=ShopSessionStatus.CAPTURED,
                source_device_id=stored.source_device_id,
                captured_at=command.captured_at,
                validated_at=None,
                expires_at=stored.expires_at,
            ),
            payload,
        )
        return self.health_service.check(shop_id, force=True)
