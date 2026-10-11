import base64
import json
import logging
from collections.abc import Callable
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
from app.modules.operating_dashboard.service import OperatingDashboardService
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.repository import ShopRepository

logger = logging.getLogger(__name__)


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
        collection_resume: Callable[[UUID], int] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ShopSessionRepository(session)
        self.shop_repository = shop_repository or ShopRepository(session)
        self.session_service = session_service or ShopSessionService(session, cipher)
        self.collection_resume = collection_resume or (
            lambda shop_id: OperatingDashboardService(
                self.session,
            ).resume_after_session_refresh(shop_id)
        )
        self.health_service = health_service
        self.settings = settings or get_settings()

    def acquire(self, shop_id: UUID) -> ShopSessionRefreshLeaseRead:
        if self.shop_repository.get(shop_id) is None:
            raise ShopNotFoundError()
        now = datetime.now(UTC)
        if self.repository.get_by_shop(shop_id) is None:
            self.session_service.reserve_for_refresh(shop_id, now)
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
        *,
        recheck_authorization: Callable[[], None] | None = None,
    ) -> ShopSessionHealthRead:
        now = datetime.now(UTC)
        if not self.repository.has_active_refresh_lease(
            shop_id=shop_id,
            lease_id=command.lease_id,
            now=now,
        ):
            raise SessionRefreshLeaseInvalidError()
        try:
            return self._complete_under_lease(shop_id, command, recheck_authorization)
        finally:
            # A failed write must not leave the transaction unusable for release.
            self.session.rollback()
            try:
                self.release(shop_id, command.lease_id)
            except Exception:
                self.session.rollback()
                # A successful CAS already clears the lease atomically. Failed
                # attempts also have the existing timeout recovery boundary.
                logger.warning("Session refresh lease release incomplete")

    def _complete_under_lease(
        self,
        shop_id: UUID,
        command: CompleteShopSessionRefreshCommand,
        recheck_authorization: Callable[[], None] | None,
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

        platform = shop.platform
        platform_shop_id = shop.platform_shop_id
        source_device_id = stored.source_device_id
        expires_at = stored.expires_at
        # No transaction/row lock stays open during platform I/O. Nothing has
        # been changed yet; a failed candidate preserves every old Session field.
        self.session.rollback()
        candidate = self.health_service.validate_candidate(
            shop_id, platform, platform_shop_id, command.expected_version, payload, parsed,
        )
        if recheck_authorization is not None:
            recheck_authorization()
        shop = self.shop_repository.get(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        if shop.platform is not platform or shop.platform_shop_id != platform_shop_id:
            raise ShopSessionPayloadInvalidError("目标店铺身份已改变，请重新登录")
        metadata = self.session_service.store_payload(
            StoreShopSessionCommand(
                shop_id=shop_id,
                expected_version=command.expected_version,
                status=ShopSessionStatus.VALID,
                source_device_id=source_device_id,
                captured_at=command.captured_at,
                validated_at=candidate.validated_at,
                expires_at=expires_at,
            ),
            candidate.payload,
            refresh_lease_id=command.lease_id,
        )
        try:
            self.collection_resume(shop_id)
        except Exception:
            self.session.rollback()
            # The Session has already committed. A queue error must never make
            # the client resubmit a valid capture or misreport authentication.
            logger.warning("Session updated; paused collection resume incomplete")
        return ShopSessionHealthRead(
            shop_id=shop_id,
            platform=platform,
            platform_shop_id=candidate.platform_shop_id,
            shop_display_name=candidate.shop_display_name,
            status=metadata.status,
            version=metadata.version,
            validated_at=candidate.validated_at,
            used_cached_validation=False,
            cookie_updates_applied=candidate.cookie_updates_applied,
        )
