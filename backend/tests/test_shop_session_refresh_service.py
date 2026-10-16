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
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.models import ShopSession
from app.modules.sessions.refresh_service import ShopSessionRefreshService
from app.modules.sessions.health_service import ValidatedSessionCandidate
from app.modules.sessions.schemas import (
    CompleteShopSessionRefreshCommand,
    ShopSessionMetadataRead,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from tests.support import FakeSession
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
)


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

    def store_payload(self, command, payload: bytes, *, refresh_lease_id=None):
        assert self.stored.refresh_lease_id == refresh_lease_id
        if self.stored.version != command.expected_version:
            raise SessionVersionConflictError()
        self.stored.version += 1
        self.stored.status = command.status
        self.stored.captured_at = command.captured_at
        self.stored.validated_at = command.validated_at
        self.payload = payload
        return ShopSessionMetadataRead(
            session_id=self.stored.session_id, configured=True,
            status=self.stored.status, version=self.stored.version,
            source_device_id=self.stored.source_device_id,
            captured_at=self.stored.captured_at, validated_at=self.stored.validated_at,
            expires_at=self.stored.expires_at,
        )


class FakeHealthService:
    def __init__(
        self,
        stored: ShopSession,
        *,
        failure: Exception | None = None,
    ) -> None:
        self.stored = stored
        self.failure = failure

    def validate_candidate(self, shop_id, platform, platform_shop_id, version, payload, parsed):
        del shop_id, platform, version, parsed
        assert platform_shop_id == "shop-1"
        if self.failure:
            raise self.failure
        return ValidatedSessionCandidate(
            payload=payload,
            platform_shop_id="shop-1",
            shop_display_name="HuanYu",
            validated_at=datetime.now(UTC),
            cookie_updates_applied=0,
        )


def make_service(
    *,
    failure: Exception | None = None,
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
        FakeHealthService(stored, failure=failure),  # type: ignore[arg-type]
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


@pytest.mark.parametrize(("encoded", "stage"), [
    ("not base64!", "candidate_encoding"),
    (base64.b64encode(b"not json").decode(), "candidate_json"),
    (base64.b64encode(b'{"cookies": []}').decode(), "candidate_schema"),
])
def test_rejected_payload_reports_only_a_safe_stage_and_preserves_old_session(encoded, stage) -> None:
    service, stored, session_service = make_service()
    lease = service.acquire(stored.shop_id)
    before = (stored.payload_encrypted, stored.version, stored.status, stored.captured_at, stored.validated_at)
    with pytest.raises(ShopSessionPayloadInvalidError) as failure:
        service.complete(stored.shop_id, CompleteShopSessionRefreshCommand(
            lease_id=lease.lease_id,
            expected_version=lease.expected_version,
            session_payload_base64=SecretStr(encoded),
            captured_at=datetime.now(UTC),
        ))
    assert failure.value.details == {"refresh_stage": stage}
    assert encoded not in str(failure.value)
    assert session_service.payload is None
    assert stored.refresh_lease_id is None
    assert before == (stored.payload_encrypted, stored.version, stored.status, stored.captured_at, stored.validated_at)


@pytest.mark.parametrize(("field", "replacement", "stage"), [
    ("platform", "pdd", "candidate_platform"),
    ("identity", {"platform": "douyin", "platformShopId": "another-test-shop", "shopDisplayName": "Other"}, "candidate_identity"),
])
def test_refresh_still_rejects_a_wrong_platform_or_target_identity(field, replacement, stage) -> None:
    service, stored, session_service = make_service()
    lease = service.acquire(stored.shop_id)
    document = json.loads(captured_payload())
    document[field] = replacement
    with pytest.raises(ShopSessionPayloadInvalidError) as failure:
        service.complete(stored.shop_id, CompleteShopSessionRefreshCommand(
            lease_id=lease.lease_id, expected_version=lease.expected_version,
            session_payload_base64=SecretStr(base64.b64encode(json.dumps(document).encode()).decode()),
            captured_at=datetime.now(UTC),
        ))
    assert failure.value.details == {"refresh_stage": stage}
    assert session_service.payload is None
    assert stored.version == 3
    assert stored.refresh_lease_id is None


def test_fresh_lease_can_validate_a_corrected_candidate_after_payload_rejection() -> None:
    service, stored, session_service = make_service()
    lease = service.acquire(stored.shop_id)
    with pytest.raises(ShopSessionPayloadInvalidError):
        service.complete(stored.shop_id, CompleteShopSessionRefreshCommand(
            lease_id=lease.lease_id, expected_version=lease.expected_version,
            session_payload_base64=SecretStr("invalid fixture"), captured_at=datetime.now(UTC),
        ))
    fresh = service.acquire(stored.shop_id)
    assert fresh.lease_id != lease.lease_id
    result = service.complete(stored.shop_id, CompleteShopSessionRefreshCommand(
        lease_id=fresh.lease_id, expected_version=fresh.expected_version,
        session_payload_base64=SecretStr(base64.b64encode(captured_payload()).decode()),
        captured_at=datetime.now(UTC),
    ))
    assert result.status is ShopSessionStatus.VALID
    assert result.version == 4
    assert session_service.payload == captured_payload()


@pytest.mark.parametrize("changed_target", [False, True])
def test_validation_stage_and_changed_target_remain_rejected_before_store(changed_target) -> None:
    service, stored, session_service = make_service(
        failure=None if changed_target else ShopSessionPayloadInvalidError(),
    )
    lease = service.acquire(stored.shop_id)

    def recheck() -> None:
        assert changed_target
        service.shop_repository.shop.platform_shop_id = "changed-test-target"

    with pytest.raises(ShopSessionPayloadInvalidError) as failure:
        service.complete(stored.shop_id, CompleteShopSessionRefreshCommand(
            lease_id=lease.lease_id, expected_version=lease.expected_version,
            session_payload_base64=SecretStr(base64.b64encode(captured_payload()).decode()),
            captured_at=datetime.now(UTC),
        ), recheck_authorization=recheck)
    assert failure.value.details == {"refresh_stage": "target_changed" if changed_target else "candidate_validation"}
    assert session_service.payload is None
    assert stored.version == 3
    assert stored.refresh_lease_id is None


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


@pytest.mark.parametrize("failure", [
    PlatformAuthenticationInvalidError(), PlatformIdentityMismatchError(),
    PlatformRequestFailedError(), PlatformRequestTimeoutError(), PlatformResponseInvalidError(),
])
def test_failed_candidate_preserves_old_valid_session_and_does_not_resume(failure) -> None:
    resumed_shop_ids: list[UUID] = []
    service, stored, _ = make_service(
        failure=failure,
        collection_resume=resumed_shop_ids.append,
    )
    lease = service.acquire(stored.shop_id)
    stored.status = ShopSessionStatus.VALID
    before = (stored.payload_encrypted, stored.version, stored.status, stored.captured_at, stored.validated_at)

    with pytest.raises(type(failure)):
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
    assert before == (stored.payload_encrypted, stored.version, stored.status, stored.captured_at, stored.validated_at)
    assert stored.refresh_lease_id is None
    assert resumed_shop_ids == []
