from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.sessions.auth_context import (
    ShopSessionAuthContext,
    StoredSessionCookie,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.schemas import ShopSessionMetadataRead
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
)
from app.platforms.schemas import PlatformShopIdentity
from tests.support import FakeSession


class FakeShopRepository:
    def __init__(self, shop: Shop) -> None:
        self.shop = shop

    def get(self, shop_id: UUID) -> Shop | None:
        return self.shop if self.shop.shop_id == shop_id else None


class FakeSessionService:
    def __init__(self, metadata: ShopSessionMetadataRead) -> None:
        self.metadata = metadata
        self.store_calls = 0

    def get_metadata(self, shop_id: UUID) -> ShopSessionMetadataRead:
        del shop_id
        return self.metadata

    def store_payload(self, command, payload: bytes) -> ShopSessionMetadataRead:
        del payload
        self.store_calls += 1
        self.metadata = self.metadata.model_copy(
            update={
                "version": command.expected_version + 1,
                "status": command.status,
                "validated_at": command.validated_at,
            },
        )
        return self.metadata


class FakeAccessor:
    def __init__(self) -> None:
        self.marked: list[ShopSessionStatus] = []

    def get_auth_context(
        self,
        shop_id: UUID,
        platform: ShopPlatform,
    ) -> ShopSessionAuthContext:
        return ShopSessionAuthContext(
            shop_id=shop_id,
            platform=platform,
            session_version=1,
            cookies=(),
        )

    def mark_validation_status(
        self,
        shop_id: UUID,
        expected_version: int,
        status: ShopSessionStatus,
    ) -> None:
        del shop_id, expected_version
        self.marked.append(status)

    def merge_response_cookies(self, shop_id: UUID, updates):
        del shop_id
        return b"merged", len(updates)


class FakeConnector:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls = 0

    def fetch_shop_identity(self, shop_id: UUID, auth_context: object):
        del shop_id, auth_context
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def metadata(*, validated_at: datetime | None = None) -> ShopSessionMetadataRead:
    now = datetime.now(UTC)
    return ShopSessionMetadataRead(
        session_id=uuid4(),
        configured=True,
        status=ShopSessionStatus.VALID,
        version=1,
        source_device_id=None,
        captured_at=now,
        validated_at=validated_at,
        expires_at=now - timedelta(minutes=1),
    )


def make_service(result: object, *, validated_at: datetime | None = None):
    shop_id = uuid4()
    shop = Shop(
        shop_id=shop_id,
        display_name="HuanYu",
        platform=ShopPlatform.DOUYIN,
        platform_shop_id="platform-shop-1",
        enabled=True,
    )
    accessor = FakeAccessor()
    connector = FakeConnector(result)
    session_service = FakeSessionService(metadata(validated_at=validated_at))
    service = ShopSessionHealthService(
        FakeSession(),  # type: ignore[arg-type]
        accessor,  # type: ignore[arg-type]
        {ShopPlatform.DOUYIN: connector},  # type: ignore[dict-item]
        session_service=session_service,  # type: ignore[arg-type]
        shop_repository=FakeShopRepository(shop),  # type: ignore[arg-type]
        settings=Settings(
            _env_file=None,
            shop_session_validation_freshness_seconds=300,
        ),
    )
    return service, shop_id, accessor, connector, session_service


def identity(*, cookie_update: bool = False) -> PlatformShopIdentity:
    updates = ()
    if cookie_update:
        updates = (
            StoredSessionCookie(
                name="sessionid",
                value=SecretStr("rotated-secret"),
                domain=".jinritemai.com",
            ),
        )
    return PlatformShopIdentity(
        platform_shop_id="platform-shop-1",
        shop_display_name="HuanYu",
        cookie_updates=updates,
    )


def test_health_check_marks_valid_and_updates_version_only_for_set_cookie() -> None:
    service, shop_id, accessor, _, session_service = make_service(
        identity(cookie_update=True),
    )

    result = service.check(shop_id, force=True)

    assert result.status is ShopSessionStatus.VALID
    assert result.version == 2
    assert result.cookie_updates_applied == 1
    assert accessor.marked == []
    assert session_service.store_calls == 1


def test_health_check_without_set_cookie_only_updates_validation_metadata() -> None:
    service, shop_id, accessor, _, session_service = make_service(identity())

    result = service.check(shop_id, force=True)

    assert result.status is ShopSessionStatus.VALID
    assert result.version == 1
    assert result.cookie_updates_applied == 0
    assert accessor.marked == [ShopSessionStatus.VALID]
    assert session_service.store_calls == 0


@pytest.mark.parametrize(
    "failure",
    [
        PlatformRequestTimeoutError(),
        PlatformRequestFailedError(details={"platform_http_status": 503}),
        PlatformResponseInvalidError(),
    ],
)
def test_transient_or_invalid_response_does_not_mark_session_invalid(
    failure: Exception,
) -> None:
    service, shop_id, accessor, _, _ = make_service(failure)

    with pytest.raises(type(failure)):
        service.check(shop_id, force=True)

    assert accessor.marked == []


def test_only_explicit_auth_failure_marks_session_invalid() -> None:
    service, shop_id, accessor, _, _ = make_service(
        PlatformAuthenticationInvalidError(),
    )

    with pytest.raises(PlatformAuthenticationInvalidError):
        service.check(shop_id, force=True)

    assert accessor.marked == [ShopSessionStatus.INVALID]


def test_recent_validation_skips_remote_request() -> None:
    service, shop_id, accessor, connector, _ = make_service(
        identity(),
        validated_at=datetime.now(UTC),
    )

    result = service.check(shop_id, force=False)

    assert result.used_cached_validation is True
    assert connector.calls == 0
    assert accessor.marked == []
