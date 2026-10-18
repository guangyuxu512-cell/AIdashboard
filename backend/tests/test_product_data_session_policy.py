"""Product Data consumer expectations for the shared Session authority.

These tests exercise the consumer boundary without a database, cipher, signer,
or network. The expected matrix is deliberately fixed here instead of being
derived from the shared Session implementation that owns the decision.
"""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.modules.product_data.platform_io as platform_io
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionVersionConflictError,
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
)
from app.modules.shops.enums import ShopPlatform
from app.platforms.douyin.product_data import CompassProductDataBusinessError
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
    PlatformRequestFailedError,
    PlatformRequestTimeoutError,
    PlatformResponseInvalidError,
    PlatformSignerFailedError,
)


FIXED_NOW = datetime(2026, 10, 18, 1, 30, tzinfo=UTC)
FIXED_FRESHNESS_SECONDS = 300


def _metadata(
    *,
    configured: bool = True,
    status: ShopSessionStatus = ShopSessionStatus.VALID,
    captured_at: datetime | None = FIXED_NOW - timedelta(minutes=10),
    validated_at: datetime | None = FIXED_NOW,
    expires_at: datetime | None = None,
    version: int = 7,
):
    return SimpleNamespace(
        configured=configured,
        status=status,
        captured_at=captured_at,
        validated_at=validated_at,
        expires_at=expires_at,
        version=version,
    )


@pytest.fixture
def consumer(monkeypatch):
    shop_id = uuid4()
    health_connectors = {ShopPlatform.DOUYIN: object()}
    state = SimpleNamespace(
        metadata=_metadata(),
        context=SimpleNamespace(
            scope=SimpleNamespace(shop_id=shop_id),
            platform_shop_id="synthetic-shop-1",
        ),
        auth=SimpleNamespace(
            shop_id=shop_id,
            platform=ShopPlatform.DOUYIN,
            session_version=7,
        ),
        page=object(),
        cookie_updates=(),
        connector_calls=[],
        prepare_calls=[],
        auth_context_calls=[],
        health_calls=[],
        identity_calls=[],
        health_marked=[],
        marked=[],
        applied_cookie_updates=[],
        registry_calls=[],
        rollbacks=[],
        events=[],
        connector_behavior=None,
        health_error=None,
        authoritative_validation=False,
    )
    state.health = SimpleNamespace(
        shop_id=shop_id,
        platform=ShopPlatform.DOUYIN,
        platform_shop_id="synthetic-shop-1",
        status=ShopSessionStatus.VALID,
        version=7,
    )

    class FakeSession:
        new = ()
        dirty = ()
        deleted = ()

        def rollback(self):
            state.rollbacks.append("authoritative-validation-boundary")

    class FakeProductDataService:
        def __init__(self, _session, *, settings):
            del settings

        def prepare_execution(self, generation_id, lease_id):
            state.prepare_calls.append((generation_id, lease_id))
            return state.context

    class FakeSessionService:
        def __init__(self, *_args, **_kwargs):
            pass

        def get_metadata(self, requested_shop_id):
            assert requested_shop_id == shop_id
            return state.metadata

    class FakeAccessor:
        def __init__(self, *_args, **_kwargs):
            self.cipher = object()

        def get_auth_context(self, requested_shop_id, expected_platform):
            state.events.append("auth-context")
            state.auth_context_calls.append((requested_shop_id, expected_platform))
            return state.auth

        def mark_validation_status(self, requested_shop_id, expected_version, status):
            if state.metadata.version != expected_version:
                raise SessionVersionConflictError()
            state.marked.append((requested_shop_id, expected_version, status))
            state.metadata.status = status

    class FakeHealthService:
        def __init__(self, _session, _accessor, connectors, **kwargs):
            self.before_platform_io = kwargs.get("before_platform_io")
            if self.before_platform_io is not None:
                assert connectors is health_connectors
            else:
                assert connectors == {}

        def check(self, requested_shop_id, *, force):
            state.events.append("health-check")
            state.health_calls.append((requested_shop_id, force))
            assert requested_shop_id == shop_id
            assert force is False
            if state.authoritative_validation:
                self.before_platform_io()
                state.identity_calls.append(requested_shop_id)
            if state.health_error is not None:
                if isinstance(state.health_error, PlatformAuthenticationInvalidError):
                    state.health_marked.append(
                        (shop_id, state.metadata.version, ShopSessionStatus.INVALID),
                    )
                    state.metadata.status = ShopSessionStatus.INVALID
                raise state.health_error
            return state.health

        def apply_response_cookie_updates(self, auth, updates):
            state.applied_cookie_updates.append((auth, updates))
            return len(updates)

    class FakeConnector:
        def page(self, auth, scope, platform_shop_id, page_no):
            state.events.append("business-page")
            state.connector_calls.append((auth, scope, platform_shop_id, page_no))
            if state.connector_behavior is not None:
                return state.connector_behavior()
            return SimpleNamespace(page=state.page, cookie_updates=state.cookie_updates)

    @contextmanager
    def session_factory():
        yield FakeSession()

    def connector_registry():
        state.registry_calls.append(True)
        return health_connectors

    monkeypatch.setattr(platform_io, "ProductDataService", FakeProductDataService)
    monkeypatch.setattr(platform_io, "ShopSessionService", FakeSessionService)
    monkeypatch.setattr(platform_io, "ShopSessionAccessor", FakeAccessor)
    monkeypatch.setattr(platform_io, "ShopSessionHealthService", FakeHealthService)
    monkeypatch.setattr(platform_io, "create_platform_connectors", connector_registry)
    stored_io = platform_io.ProductDataStoredSessionIO(
        session_factory,
        SimpleNamespace(
            shop_session_validation_freshness_seconds=FIXED_FRESHNESS_SECONDS,
        ),
        connector=FakeConnector(),
        cipher_factory=lambda: object(),
    )
    return state, stored_io


@pytest.mark.parametrize(
    (
        "metadata",
        "health_error",
        "authoritative_validation",
        "expected_error",
    ),
    [
        (
            _metadata(
                configured=False,
                status=ShopSessionStatus.NOT_CONFIGURED,
                captured_at=None,
                validated_at=None,
            ),
            ShopSessionNotConfiguredError(),
            False,
            ShopSessionNotConfiguredError,
        ),
        (
            _metadata(
                status=ShopSessionStatus.CAPTURED,
                captured_at=FIXED_NOW,
                validated_at=None,
            ),
            None,
            True,
            None,
        ),
        (
            _metadata(status=ShopSessionStatus.REFRESH_REQUIRED),
            ShopSessionAuthenticationInvalidError(),
            False,
            ShopSessionAuthenticationInvalidError,
        ),
        (
            _metadata(status=ShopSessionStatus.INVALID),
            ShopSessionAuthenticationInvalidError(),
            False,
            ShopSessionAuthenticationInvalidError,
        ),
        (
            _metadata(validated_at=None),
            None,
            True,
            None,
        ),
        (
            _metadata(
                validated_at=FIXED_NOW
                - timedelta(seconds=FIXED_FRESHNESS_SECONDS + 1),
            ),
            None,
            True,
            None,
        ),
        (
            _metadata(validated_at=FIXED_NOW + timedelta(microseconds=1)),
            None,
            True,
            None,
        ),
        (
            _metadata(
                captured_at=FIXED_NOW - timedelta(minutes=5),
                validated_at=FIXED_NOW - timedelta(minutes=6),
            ),
            None,
            True,
            None,
        ),
        (
            _metadata(
                validated_at=FIXED_NOW
                - timedelta(seconds=FIXED_FRESHNESS_SECONDS),
            ),
            None,
            False,
            None,
        ),
        (
            _metadata(
                validated_at=FIXED_NOW,
                expires_at=FIXED_NOW - timedelta(days=1),
            ),
            None,
            False,
            None,
        ),
    ],
    ids=[
        "not-configured-does-not-request",
        "captured-validates-once",
        "refresh-required-reauth-without-request",
        "explicit-invalid-reauth-without-request",
        "valid-without-validation-time-validates-once",
        "stale-by-one-second-validates-once",
        "future-validation-time-validates-once",
        "validation-before-capture-validates-once",
        "inclusive-freshness-boundary-uses-cache",
        "expired-cookie-metadata-is-warning-only",
    ],
)
def test_consumer_uses_shared_health_result_with_independent_fixed_expectations(
    consumer,
    metadata,
    health_error,
    authoritative_validation,
    expected_error,
):
    state, stored_io = consumer
    state.metadata = metadata
    state.auth.session_version = metadata.version
    state.health.version = metadata.version
    state.health_error = health_error
    state.authoritative_validation = authoritative_validation

    if expected_error is not None:
        with pytest.raises(expected_error):
            stored_io.page("generation-1", "lease-1", 1)
        assert state.connector_calls == []
        assert state.auth_context_calls == []
        assert state.events == ["health-check"]
    else:
        assert stored_io.page("generation-1", "lease-1", 1) is state.page
        assert len(state.connector_calls) == 1
        assert state.auth_context_calls == [
            (state.auth.shop_id, ShopPlatform.DOUYIN),
        ]
        assert state.events[:3] == [
            "health-check",
            "auth-context",
            "business-page",
        ]

    assert state.health_calls == [(state.auth.shop_id, False)]
    assert state.registry_calls == [True]
    assert len(state.identity_calls) == int(authoritative_validation)
    assert len(state.rollbacks) == int(authoritative_validation)


def test_binder_rejects_health_for_a_different_shop_before_business_page(consumer):
    state, stored_io = consumer
    state.health.shop_id = uuid4()

    with pytest.raises(PlatformIdentityMismatchError):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.health_calls == [(state.auth.shop_id, False)]
    assert state.auth_context_calls == [
        (state.auth.shop_id, ShopPlatform.DOUYIN),
    ]
    assert state.connector_calls == []
    assert state.marked == []


def test_binder_rejects_version_changed_after_health_check(consumer):
    state, stored_io = consumer
    state.health.version = state.auth.session_version + 1

    with pytest.raises(SessionVersionConflictError):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.connector_calls == []
    assert state.marked == []


@pytest.mark.parametrize(
    "error",
    [
        PlatformIdentityMismatchError(),
        PlatformRequestTimeoutError(),
        PlatformRequestFailedError(),
        PlatformSignerFailedError(),
        PlatformResponseInvalidError(),
        CompassProductDataBusinessError(details={"business_code": 100008}),
    ],
    ids=[
        "wrong-shop",
        "network-timeout",
        "network-failure",
        "signer-failure",
        "response-parse",
        "business-rejection",
    ],
)
def test_non_auth_business_failures_never_mark_session_invalid(consumer, error):
    state, stored_io = consumer
    state.connector_behavior = lambda: (_ for _ in ()).throw(error)

    with pytest.raises(type(error)):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.marked == []
    assert state.applied_cookie_updates == []


@pytest.mark.parametrize(
    "error",
    [
        PlatformIdentityMismatchError(),
        PlatformRequestTimeoutError(),
        PlatformRequestFailedError(),
        PlatformSignerFailedError(),
        PlatformResponseInvalidError(),
    ],
)
def test_authoritative_validation_failure_does_not_start_business_page_or_mark(
    consumer,
    error,
):
    state, stored_io = consumer
    state.authoritative_validation = True
    state.health_error = error

    with pytest.raises(type(error)):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.identity_calls == [state.auth.shop_id]
    assert state.connector_calls == []
    assert state.health_marked == []
    assert state.marked == []


def test_authoritative_auth_invalid_stops_before_business_page(consumer):
    state, stored_io = consumer
    state.authoritative_validation = True
    state.health_error = PlatformAuthenticationInvalidError()

    with pytest.raises(PlatformAuthenticationInvalidError):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.health_marked == [
        (state.auth.shop_id, state.auth.session_version, ShopSessionStatus.INVALID),
    ]
    assert state.connector_calls == []
    assert state.marked == []


def test_session_version_change_rejects_late_cookie_writeback(consumer):
    state, stored_io = consumer
    state.cookie_updates = (object(),)

    def change_session_version():
        state.metadata.version += 1
        return SimpleNamespace(page=state.page, cookie_updates=state.cookie_updates)

    state.connector_behavior = change_session_version
    with pytest.raises(SessionVersionConflictError):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.applied_cookie_updates == []
    assert state.metadata.status is ShopSessionStatus.VALID


def test_explicit_business_auth_failure_marks_only_the_observed_version(consumer):
    state, stored_io = consumer
    state.connector_behavior = lambda: (_ for _ in ()).throw(
        PlatformAuthenticationInvalidError(),
    )

    with pytest.raises(PlatformAuthenticationInvalidError):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.marked == [
        (state.auth.shop_id, state.auth.session_version, ShopSessionStatus.INVALID),
    ]


def test_late_auth_failure_cannot_invalidate_a_newer_session(consumer):
    state, stored_io = consumer

    def replace_session_then_fail():
        state.metadata.version += 1
        raise PlatformAuthenticationInvalidError()

    state.connector_behavior = replace_session_then_fail
    with pytest.raises(SessionVersionConflictError):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.marked == []
    assert state.metadata.status is ShopSessionStatus.VALID
