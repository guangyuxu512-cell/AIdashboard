import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.sessions.auth_context import (
    ShopSessionAccessor,
    ShopSessionAuthContext,
    StoredSessionCookie,
    StoredManagementSessionPayload,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.schemas import ShopSessionMetadataRead
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
    PlatformSignerFailedError,
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
    context_from_payload = staticmethod(ShopSessionAccessor.context_from_payload)
    merge_payload_cookies = staticmethod(ShopSessionAccessor.merge_payload_cookies)

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
        captured_at=now - timedelta(minutes=10),
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
        PlatformSignerFailedError(details={"retryable": True}),
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


@pytest.mark.parametrize(
    ("status", "configured", "error"),
    [
        (ShopSessionStatus.NOT_CONFIGURED, False, ShopSessionNotConfiguredError),
        (ShopSessionStatus.INVALID, True, ShopSessionAuthenticationInvalidError),
        (
            ShopSessionStatus.REFRESH_REQUIRED,
            True,
            ShopSessionAuthenticationInvalidError,
        ),
    ],
)
def test_terminal_readiness_states_never_issue_identity_requests(
    status: ShopSessionStatus,
    configured: bool,
    error: type[Exception],
) -> None:
    service, shop_id, accessor, connector, storage = make_service(identity())
    storage.metadata = storage.metadata.model_copy(
        update={"status": status, "configured": configured},
    )

    with pytest.raises(error):
        service.check(shop_id, force=False)

    assert connector.calls == 0
    assert accessor.marked == []


@pytest.mark.parametrize(
    ("status", "validated_at"),
    [
        (ShopSessionStatus.CAPTURED, None),
        (ShopSessionStatus.VALID, datetime.now(UTC) - timedelta(minutes=6)),
    ],
)
def test_pending_or_stale_validation_uses_one_authoritative_identity_request(
    status: ShopSessionStatus,
    validated_at: datetime | None,
) -> None:
    service, shop_id, accessor, connector, storage = make_service(
        identity(),
        validated_at=validated_at,
    )
    storage.metadata = storage.metadata.model_copy(update={"status": status})

    result = service.check(shop_id, force=False)

    assert result.used_cached_validation is False
    assert connector.calls == 1
    assert accessor.marked == [ShopSessionStatus.VALID]


def test_stored_identity_mismatch_does_not_mark_session_invalid() -> None:
    service, shop_id, accessor, connector, _ = make_service(
        PlatformShopIdentity(
            platform_shop_id="another-platform-shop",
            shop_display_name="Other",
        ),
    )

    with pytest.raises(PlatformIdentityMismatchError):
        service.check(shop_id, force=True)

    assert connector.calls == 1
    assert accessor.marked == []


def candidate_input() -> tuple[bytes, StoredManagementSessionPayload]:
    document = {
        "schema": "management-login.session.v1", "platform": "douyin",
        "cookies": [{"name": "synthetic", "value": "SYNTHETIC_PRIVATE_CANARY"}],
    }
    return json.dumps(document).encode(), StoredManagementSessionPayload.model_validate(document)


@pytest.mark.parametrize(("step", "connector_calls"), [
    ("context_validation", 0), ("identity_connector", 1), ("cookie_merge", 1),
])
def test_candidate_payload_diagnostic_identifies_call_boundary_without_writes(step, connector_calls, monkeypatch) -> None:
    service, shop_id, accessor, connector, storage = make_service(identity(cookie_update=True))
    original = ShopSessionPayloadInvalidError(details={"private": "SYNTHETIC_PRIVATE_CANARY"})

    def reject(*_args):
        raise original

    if step == "context_validation":
        monkeypatch.setattr(accessor, "context_from_payload", reject)
    elif step == "cookie_merge":
        monkeypatch.setattr(accessor, "merge_payload_cookies", reject)
    else:
        connector.result = original
    payload, parsed = candidate_input()
    before = storage.metadata.model_dump()
    with pytest.raises(ShopSessionPayloadInvalidError) as failure:
        service.validate_candidate(shop_id, ShopPlatform.DOUYIN, "platform-shop-1", 1, payload, parsed)
    assert failure.value is original
    assert failure.value.details == {"refresh_stage": "candidate_validation", "validation_step": step}
    assert connector.calls == connector_calls
    assert accessor.marked == []
    assert storage.store_calls == 0
    assert storage.metadata.model_dump() == before


@pytest.mark.parametrize("failure", [
    PlatformAuthenticationInvalidError(), PlatformIdentityMismatchError(),
    PlatformRequestFailedError(), PlatformRequestTimeoutError(), PlatformResponseInvalidError(),
])
def test_candidate_non_payload_failures_keep_original_code_and_details(failure) -> None:
    service, shop_id, accessor, connector, storage = make_service(failure)
    payload, parsed = candidate_input()
    with pytest.raises(type(failure)) as observed:
        service.validate_candidate(shop_id, ShopPlatform.DOUYIN, "platform-shop-1", 1, payload, parsed)
    assert observed.value is failure
    assert failure.details is None
    assert connector.calls == 1
    assert accessor.marked == []
    assert storage.store_calls == 0
