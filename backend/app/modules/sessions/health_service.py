from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.sessions.auth_context import (
    ShopSessionAccessor,
    ShopSessionAuthContext,
    StoredSessionCookie,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.schemas import (
    ShopSessionHealthRead,
    StoreShopSessionCommand,
)
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.repository import ShopRepository
from app.platforms.base import PlatformConnector
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
    PlatformNotSupportedError,
)


class ShopSessionHealthService:
    """Authoritative, request-driven ShopSession validation boundary."""

    def __init__(
        self,
        session: Session,
        session_accessor: ShopSessionAccessor,
        connectors: dict[ShopPlatform, PlatformConnector],
        *,
        session_service: ShopSessionService | None = None,
        shop_repository: ShopRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session_accessor = session_accessor
        self.connectors = connectors
        self.session_service = session_service or ShopSessionService(session)
        self.shop_repository = shop_repository or ShopRepository(session)
        self.settings = settings or get_settings()

    def check(
        self,
        shop_id: UUID,
        *,
        force: bool,
    ) -> ShopSessionHealthRead:
        shop = self.shop_repository.get(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        metadata = self.session_service.get_metadata(shop_id)
        now = datetime.now(UTC)
        if (
            not force
            and metadata.status is ShopSessionStatus.VALID
            and metadata.validated_at is not None
            and metadata.validated_at
            >= now
            - timedelta(
                seconds=self.settings.shop_session_validation_freshness_seconds,
            )
            and shop.platform_shop_id is not None
        ):
            return ShopSessionHealthRead(
                shop_id=shop_id,
                platform=shop.platform,
                platform_shop_id=shop.platform_shop_id,
                shop_display_name=shop.display_name,
                status=metadata.status,
                version=metadata.version,
                validated_at=metadata.validated_at,
                used_cached_validation=True,
                cookie_updates_applied=0,
            )

        connector = self.connectors.get(shop.platform)
        if connector is None:
            raise PlatformNotSupportedError()
        auth_context = self.session_accessor.get_auth_context(shop_id, shop.platform)
        try:
            identity = connector.fetch_shop_identity(shop_id, auth_context)
        except PlatformAuthenticationInvalidError:
            self.session_accessor.mark_validation_status(
                shop_id,
                auth_context.session_version,
                ShopSessionStatus.INVALID,
            )
            raise
        if (
            shop.platform_shop_id is not None
            and identity.platform_shop_id != shop.platform_shop_id
        ):
            raise PlatformIdentityMismatchError()

        updates_applied = self.apply_response_cookie_updates(
            auth_context,
            identity.cookie_updates,
        )
        if updates_applied:
            metadata = self.session_service.get_metadata(shop_id)
        else:
            self.session_accessor.mark_validation_status(
                shop_id,
                auth_context.session_version,
                ShopSessionStatus.VALID,
            )
            metadata = self.session_service.get_metadata(shop_id)

        return ShopSessionHealthRead(
            shop_id=shop_id,
            platform=shop.platform,
            platform_shop_id=identity.platform_shop_id,
            shop_display_name=identity.shop_display_name,
            status=metadata.status,
            version=metadata.version,
            validated_at=metadata.validated_at or now,
            used_cached_validation=False,
            cookie_updates_applied=updates_applied,
        )

    def apply_response_cookie_updates(
        self,
        auth_context: ShopSessionAuthContext,
        cookie_updates: tuple[StoredSessionCookie, ...],
    ) -> int:
        """Persist explicit platform Set-Cookie updates through the Session boundary.

        Platform business connectors may use this after a successful request;
        they never decrypt or write a Session payload directly.  A version
        conflict remains explicit so an older in-flight request cannot replace
        a newly captured browser session.
        """

        if not cookie_updates:
            return 0
        payload, updates_applied = self.session_accessor.merge_response_cookies(
            auth_context.shop_id,
            cookie_updates,
        )
        if not updates_applied:
            return 0
        metadata = self.session_service.get_metadata(auth_context.shop_id)
        now = datetime.now(UTC)
        self.session_service.store_payload(
            StoreShopSessionCommand(
                shop_id=auth_context.shop_id,
                expected_version=auth_context.session_version,
                status=ShopSessionStatus.VALID,
                source_device_id=metadata.source_device_id,
                captured_at=metadata.captured_at or now,
                validated_at=now,
                expires_at=metadata.expires_at,
            ),
            payload,
        )
        return updates_applied
