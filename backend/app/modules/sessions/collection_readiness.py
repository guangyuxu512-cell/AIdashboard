"""Pure collection-readiness policy shared by server-side consumers.

This module never decrypts a payload and never performs platform I/O.  A
consumer must call :meth:`ShopSessionHealthService.check` explicitly when the
decision requires authoritative validation, then bind the returned validation
to the decrypted context before issuing its business request.
"""

from datetime import datetime, timedelta
from enum import StrEnum

from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionVersionConflictError,
    ShopSessionAuthenticationInvalidError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.schemas import ShopSessionHealthRead, ShopSessionMetadataRead
from app.modules.shops.enums import ShopPlatform
from app.platforms.exceptions import PlatformIdentityMismatchError


class ShopSessionCollectionReadiness(StrEnum):
    NOT_CONFIGURED = "not_configured"
    AUTHORITATIVE_VALIDATION_REQUIRED = "authoritative_validation_required"
    READY = "ready"
    REAUTHENTICATION_REQUIRED = "reauthentication_required"


def classify_collection_readiness(
    metadata: ShopSessionMetadataRead,
    *,
    now: datetime,
    validation_freshness: timedelta,
) -> ShopSessionCollectionReadiness:
    """Classify stored metadata without decrypting or contacting a platform.

    ``expires_at`` is deliberately not an authorization gate.  Cookie expiry
    metadata can be incomplete or refreshed by the authoritative response, so
    captured and stale sessions are validated remotely instead of being
    mislabelled as invalid.
    """

    if validation_freshness < timedelta(0):
        raise ValueError("validation_freshness must not be negative")
    if not metadata.configured or metadata.status is ShopSessionStatus.NOT_CONFIGURED:
        return ShopSessionCollectionReadiness.NOT_CONFIGURED
    if metadata.status in {
        ShopSessionStatus.INVALID,
        ShopSessionStatus.REFRESH_REQUIRED,
    }:
        return ShopSessionCollectionReadiness.REAUTHENTICATION_REQUIRED
    if metadata.status is ShopSessionStatus.CAPTURED:
        return ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED
    if metadata.status is not ShopSessionStatus.VALID:
        return ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED

    captured_at = metadata.captured_at
    validated_at = metadata.validated_at
    if (
        captured_at is None
        or validated_at is None
        or captured_at.utcoffset() is None
        or validated_at.utcoffset() is None
        or now.utcoffset() is None
        or validated_at < captured_at
        or validated_at > now
        or validated_at < now - validation_freshness
    ):
        return ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED
    return ShopSessionCollectionReadiness.READY


def bind_collection_auth_context(
    health: ShopSessionHealthRead,
    context: ShopSessionAuthContext,
    *,
    expected_platform: ShopPlatform,
) -> ShopSessionAuthContext:
    """Bind a checked version/shop to its decrypted context without I/O."""

    if health.shop_id != context.shop_id:
        raise PlatformIdentityMismatchError()
    if health.platform is not expected_platform or context.platform is not expected_platform:
        raise ShopSessionPayloadInvalidError()
    if health.status is not ShopSessionStatus.VALID:
        raise ShopSessionAuthenticationInvalidError()
    if health.version != context.session_version:
        raise SessionVersionConflictError()
    return context
