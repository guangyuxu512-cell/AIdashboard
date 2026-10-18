"""Product Data consumer expectations for the shared Session authority.

These tests exercise the consumer boundary without a database, cipher, signer,
or network.  The expected matrix is deliberately fixed here instead of being
derived from the shared Session implementation that will own the decision.
"""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.modules.product_data.platform_io as platform_io
from app.modules.product_data.exceptions import (
    ProductDataSessionValidationRequiredError,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionVersionConflictError,
    ShopSessionAuthenticationInvalidError,
    ShopSessionNotConfiguredError,
)
from app.platforms.exceptions import (
    PlatformAuthenticationInvalidError,
    PlatformIdentityMismatchError,
)


FIXED_NOW = datetime(2026, 10, 18, 1, 30, tzinfo=UTC)
FIXED_FRESHNESS_SECONDS = 300


def _metadata(
    *,
    configured: bool = True,
    status: ShopSessionStatus = ShopSessionStatus.VALID,
    validated_at: datetime | None = FIXED_NOW,
    version: int = 7,
):
    return SimpleNamespace(
        configured=configured,
        status=status,
        validated_at=validated_at,
        version=version,
    )


@pytest.fixture
def consumer(monkeypatch):
    shop_id = uuid4()
    state = SimpleNamespace(
        metadata=_metadata(),
        context=SimpleNamespace(
            scope=SimpleNamespace(shop_id=shop_id),
            platform_shop_id="synthetic-shop-1",
        ),
        auth=SimpleNamespace(shop_id=shop_id, session_version=7),
        page=object(),
        cookie_updates=(),
        connector_calls=[],
        prepare_calls=[],
        auth_context_calls=[],
        marked=[],
        applied_cookie_updates=[],
        connector_behavior=None,
    )

    class FakeProductDataService:
        def __init__(self, _session, *, settings):
            del settings
            self.repository = SimpleNamespace(now=lambda: FIXED_NOW)

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
            state.auth_context_calls.append((requested_shop_id, expected_platform))
            return state.auth

        def mark_validation_status(self, requested_shop_id, expected_version, status):
            if state.metadata.version != expected_version:
                raise SessionVersionConflictError()
            state.marked.append((requested_shop_id, expected_version, status))
            state.metadata.status = status

    class FakeHealthService:
        def __init__(self, *_args, **_kwargs):
            pass

        def apply_response_cookie_updates(self, auth, updates):
            state.applied_cookie_updates.append((auth, updates))
            return len(updates)

    class FakeConnector:
        def page(self, auth, scope, platform_shop_id, page_no):
            state.connector_calls.append((auth, scope, platform_shop_id, page_no))
            if state.connector_behavior is not None:
                return state.connector_behavior()
            return SimpleNamespace(page=state.page, cookie_updates=state.cookie_updates)

    @contextmanager
    def session_factory():
        yield object()

    monkeypatch.setattr(platform_io, "ProductDataService", FakeProductDataService)
    monkeypatch.setattr(platform_io, "ShopSessionService", FakeSessionService)
    monkeypatch.setattr(platform_io, "ShopSessionAccessor", FakeAccessor)
    monkeypatch.setattr(platform_io, "ShopSessionHealthService", FakeHealthService)
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
    ("metadata", "expected_error"),
    [
        (
            _metadata(
                configured=False,
                status=ShopSessionStatus.NOT_CONFIGURED,
                validated_at=None,
            ),
            ShopSessionNotConfiguredError,
        ),
        (
            _metadata(status=ShopSessionStatus.CAPTURED, validated_at=None),
            ProductDataSessionValidationRequiredError,
        ),
        (
            _metadata(status=ShopSessionStatus.REFRESH_REQUIRED),
            ProductDataSessionValidationRequiredError,
        ),
        (
            _metadata(status=ShopSessionStatus.INVALID),
            ShopSessionAuthenticationInvalidError,
        ),
        (
            _metadata(validated_at=None),
            ProductDataSessionValidationRequiredError,
        ),
        (
            _metadata(
                validated_at=FIXED_NOW
                - timedelta(seconds=FIXED_FRESHNESS_SECONDS + 1),
            ),
            ProductDataSessionValidationRequiredError,
        ),
        (
            _metadata(validated_at=FIXED_NOW + timedelta(microseconds=1)),
            ProductDataSessionValidationRequiredError,
        ),
        (
            _metadata(
                validated_at=FIXED_NOW
                - timedelta(seconds=FIXED_FRESHNESS_SECONDS),
            ),
            None,
        ),
        (_metadata(validated_at=FIXED_NOW), None),
    ],
    ids=[
        "not-configured",
        "captured-needs-validation",
        "refresh-required-needs-validation",
        "explicit-invalid",
        "valid-without-validation-time",
        "stale-by-one-second",
        "future-validation-time",
        "inclusive-freshness-boundary",
        "fresh-valid",
    ],
)
def test_consumer_preflight_has_independent_fixed_expectations(
    consumer,
    metadata,
    expected_error,
):
    state, stored_io = consumer
    state.metadata = metadata

    if expected_error is not None:
        with pytest.raises(expected_error):
            stored_io.page("generation-1", "lease-1", 1)
        assert state.connector_calls == []
        return

    assert stored_io.page("generation-1", "lease-1", 1) is state.page
    assert len(state.connector_calls) == 1


def test_wrong_shop_failure_is_not_reclassified_as_auth_invalid(consumer):
    state, stored_io = consumer
    state.connector_behavior = lambda: (_ for _ in ()).throw(
        PlatformIdentityMismatchError(),
    )

    with pytest.raises(PlatformIdentityMismatchError):
        stored_io.page("generation-1", "lease-1", 1)

    assert state.marked == []
    assert state.applied_cookie_updates == []


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


def test_explicit_auth_failure_marks_only_the_observed_version(consumer):
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
