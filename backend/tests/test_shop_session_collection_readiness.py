from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.sessions.auth_context import ShopSessionAuthContext
from app.modules.sessions.collection_readiness import (
    ShopSessionCollectionReadiness,
    bind_collection_auth_context,
    classify_collection_readiness,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import SessionVersionConflictError
from app.modules.sessions.schemas import ShopSessionHealthRead, ShopSessionMetadataRead
from app.modules.shops.enums import ShopPlatform
from app.platforms.exceptions import PlatformIdentityMismatchError


NOW = datetime(2026, 10, 18, 0, 0, tzinfo=UTC)


def _metadata(
    status: ShopSessionStatus,
    *,
    configured: bool = True,
    captured_at: datetime | None = None,
    validated_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> ShopSessionMetadataRead:
    return ShopSessionMetadataRead(
        session_id=uuid4() if configured else None,
        configured=configured,
        status=status,
        version=3 if configured else 0,
        source_device_id=None,
        captured_at=captured_at,
        validated_at=validated_at,
        expires_at=expires_at,
    )


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (
            _metadata(ShopSessionStatus.NOT_CONFIGURED, configured=False),
            ShopSessionCollectionReadiness.NOT_CONFIGURED,
        ),
        (
            _metadata(ShopSessionStatus.CAPTURED, captured_at=NOW),
            ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED,
        ),
        (
            _metadata(
                ShopSessionStatus.VALID,
                captured_at=NOW - timedelta(minutes=10),
                validated_at=None,
            ),
            ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED,
        ),
        (
            _metadata(
                ShopSessionStatus.VALID,
                captured_at=NOW - timedelta(minutes=10),
                validated_at=NOW - timedelta(minutes=6),
            ),
            ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED,
        ),
        (
            _metadata(
                ShopSessionStatus.VALID,
                captured_at=NOW,
                validated_at=NOW - timedelta(seconds=1),
            ),
            ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED,
        ),
        (
            _metadata(
                ShopSessionStatus.VALID,
                captured_at=NOW - timedelta(minutes=10),
                validated_at=NOW + timedelta(seconds=1),
            ),
            ShopSessionCollectionReadiness.AUTHORITATIVE_VALIDATION_REQUIRED,
        ),
        (
            _metadata(
                ShopSessionStatus.VALID,
                captured_at=NOW - timedelta(minutes=10),
                validated_at=NOW - timedelta(minutes=1),
                expires_at=NOW - timedelta(days=1),
            ),
            ShopSessionCollectionReadiness.READY,
        ),
        (
            _metadata(ShopSessionStatus.INVALID, captured_at=NOW),
            ShopSessionCollectionReadiness.REAUTHENTICATION_REQUIRED,
        ),
        (
            _metadata(ShopSessionStatus.REFRESH_REQUIRED, captured_at=NOW),
            ShopSessionCollectionReadiness.REAUTHENTICATION_REQUIRED,
        ),
    ],
)
def test_collection_readiness_is_a_pure_status_and_freshness_decision(
    metadata: ShopSessionMetadataRead,
    expected: ShopSessionCollectionReadiness,
) -> None:
    assert classify_collection_readiness(
        metadata,
        now=NOW,
        validation_freshness=timedelta(minutes=5),
    ) is expected


def _health(shop_id, *, version: int = 3) -> ShopSessionHealthRead:
    return ShopSessionHealthRead(
        shop_id=shop_id,
        platform=ShopPlatform.DOUYIN,
        platform_shop_id="platform-shop-1",
        shop_display_name="HuanYu",
        status=ShopSessionStatus.VALID,
        version=version,
        validated_at=NOW,
        used_cached_validation=True,
        cookie_updates_applied=0,
    )


def _context(shop_id, *, version: int = 3) -> ShopSessionAuthContext:
    return ShopSessionAuthContext(
        shop_id=shop_id,
        platform=ShopPlatform.DOUYIN,
        session_version=version,
        cookies=(),
    )


def test_collection_context_rejects_a_version_changed_after_validation() -> None:
    shop_id = uuid4()
    with pytest.raises(SessionVersionConflictError):
        bind_collection_auth_context(
            _health(shop_id, version=3),
            _context(shop_id, version=4),
            expected_platform=ShopPlatform.DOUYIN,
        )


def test_collection_context_rejects_a_different_shop_identity() -> None:
    with pytest.raises(PlatformIdentityMismatchError):
        bind_collection_auth_context(
            _health(uuid4()),
            _context(uuid4()),
            expected_platform=ShopPlatform.DOUYIN,
        )
