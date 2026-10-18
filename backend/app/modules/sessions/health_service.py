from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID
from typing import Callable

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.modules.sessions.auth_context import (
    ShopSessionAccessor,
    ShopSessionAuthContext,
    StoredManagementSessionPayload,
    StoredSessionCookie,
)
from app.modules.sessions.collection_readiness import (
    ShopSessionCollectionReadiness,
    classify_collection_readiness,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
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


@dataclass(frozen=True)
class ValidatedSessionCandidate:
    payload: bytes = field(repr=False)
    platform_shop_id: str
    shop_display_name: str
    validated_at: datetime
    cookie_updates_applied: int


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
        before_platform_io: Callable[[], None] | None = None,
    ) -> None:
        self.session_accessor = session_accessor
        self.connectors = connectors
        self.session_service = session_service or ShopSessionService(session)
        self.shop_repository = shop_repository or ShopRepository(session)
        self.settings = settings or get_settings()
        # Only an owner of an exclusive read Session may opt in. Ordinary
        # health/login callers keep their original transaction semantics.
        self.before_platform_io = before_platform_io

    def validate_candidate(
        self,
        shop_id: UUID,
        platform: ShopPlatform,
        platform_shop_id: str | None,
        version: int,
        payload: bytes,
        parsed: StoredManagementSessionPayload,
    ) -> ValidatedSessionCandidate:
        """Fresh authoritative check without any stored validation/payload writes.

        An invalid replacement does not prove the previous Session is invalid.
        Keep the existing ``check`` path for validating that stored Session.
        """
        connector = self.connectors.get(platform)
        if connector is None:
            raise PlatformNotSupportedError()
        try:
            context = self.session_accessor.context_from_payload(shop_id, platform, version, parsed)
        except ShopSessionPayloadInvalidError as error:
            error.details = {
                "refresh_stage": "candidate_validation", "validation_step": "context_validation",
            }
            raise
        try:
            identity = connector.fetch_shop_identity(shop_id, context)
        except ShopSessionPayloadInvalidError as error:
            error.details = {
                "refresh_stage": "candidate_validation", "validation_step": "identity_connector",
            }
            raise
        if platform_shop_id is None or identity.platform_shop_id != platform_shop_id:
            raise PlatformIdentityMismatchError()
        merged, count = (payload, 0)
        if identity.cookie_updates:
            try:
                merged, count = self.session_accessor.merge_payload_cookies(payload, identity.cookie_updates)
            except ShopSessionPayloadInvalidError as error:
                error.details = {
                    "refresh_stage": "candidate_validation", "validation_step": "cookie_merge",
                }
                raise
        return ValidatedSessionCandidate(
            payload=merged,
            platform_shop_id=identity.platform_shop_id,
            shop_display_name=identity.shop_display_name,
            validated_at=datetime.now(UTC),
            cookie_updates_applied=count,
        )

    def check(
        self,
        shop_id: UUID,
        *,
        force: bool,
    ) -> ShopSessionHealthRead:
        shop = self.shop_repository.get(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        platform, platform_shop_id, shop_display_name = (
            shop.platform, shop.platform_shop_id, shop.display_name,
        )
        metadata = self.session_service.get_metadata(shop_id)
        now = datetime.now(UTC)
        readiness = classify_collection_readiness(
            metadata,
            now=now,
            validation_freshness=timedelta(
                seconds=self.settings.shop_session_validation_freshness_seconds,
            ),
        )
        if readiness is ShopSessionCollectionReadiness.NOT_CONFIGURED:
            raise ShopSessionNotConfiguredError()
        if readiness is ShopSessionCollectionReadiness.REAUTHENTICATION_REQUIRED:
            raise ShopSessionAuthenticationInvalidError()
        if (
            not force
            and readiness is ShopSessionCollectionReadiness.READY
            and platform_shop_id is not None
        ):
            return ShopSessionHealthRead(
                shop_id=shop_id,
                platform=platform,
                platform_shop_id=platform_shop_id,
                shop_display_name=shop_display_name,
                status=metadata.status,
                version=metadata.version,
                validated_at=metadata.validated_at,
                used_cached_validation=True,
                cookie_updates_applied=0,
            )

        connector = self.connectors.get(platform)
        if connector is None:
            raise PlatformNotSupportedError()
        auth_context = self.session_accessor.get_auth_context(shop_id, platform)
        if self.before_platform_io is not None:
            self.before_platform_io()
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
            platform_shop_id is not None
            and identity.platform_shop_id != platform_shop_id
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
            platform=platform,
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
