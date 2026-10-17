"""Synthetic encrypted Session/CAS integration; connector never accesses network."""

from contextlib import contextmanager
from datetime import timedelta
import json
from types import SimpleNamespace

from cryptography.fernet import Fernet
from pydantic import SecretStr
import pytest
from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.modules.product_data.exceptions import ProductDataSessionValidationRequiredError
from app.modules.product_data.platform_io import ProductDataStoredSessionIO
from app.modules.sessions.auth_context import StoredSessionCookie
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import SessionVersionConflictError
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.sessions.schemas import StoreShopSessionCommand
from app.modules.sessions.service import ShopSessionService
from app.platforms.douyin.product_data import CompassProductDataBusinessError, CompassProductDataPage
from app.platforms.douyin.product_data_connector import ProductDataFetchResult
from app.platforms.exceptions import PlatformAuthenticationInvalidError
from tests.test_product_data_service_postgres import graph, submit, complete


pytestmark = pytest.mark.integration


@pytest.fixture
def session_graph(graph):
    # New ephemeral test key and fabricated cookie, never real configuration.
    cipher = SecretCipher(Fernet.generate_key().decode())
    now = graph.service.repository.now()
    graph.session.commit()
    command = StoreShopSessionCommand(shop_id=graph.shops[0].shop_id, expected_version=0, status=ShopSessionStatus.VALID,
        source_device_id=None, captured_at=now-timedelta(seconds=20), validated_at=now,
        expires_at=now-timedelta(seconds=1)) # cookie expiry is only a warning
    payload = json.dumps({"schema": "management-login.session.v1", "platform": "douyin",
        "cookies": [{"name": "sessionid", "value": "synthetic-only-cookie", "domain": ".jinritemai.com"}]}).encode()
    ShopSessionService(graph.session, cipher).store_payload(command, payload)
    receipt, lease = submit(graph)
    active = [0]
    @contextmanager
    def factory():
        active[0] += 1
        try:
            with Session(graph.session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            active[0] -= 1
    graph.cipher, graph.command, graph.payload = cipher, command, payload
    graph.receipt, graph.lease, graph.factory, graph.active = receipt, lease, factory, active
    return graph


def io(graph, connector):
    return ProductDataStoredSessionIO(graph.factory, graph.settings, connector=connector, cipher_factory=lambda: graph.cipher)


def test_closed_session_during_io_and_real_cookie_update_uses_existing_cas(session_graph):
    graph = session_graph
    def page(auth, scope, shop_id, number):
        assert graph.active[0] == 0
        assert auth.session_version == 1 and auth.shop_id == graph.shops[0].shop_id
        assert scope == graph.receipt.scope and shop_id == graph.shops[0].platform_shop_id and number == 1
        rows = complete(graph.receipt, graph.shops[0], 1).products
        return ProductDataFetchResult(CompassProductDataPage(rows, 1, 10, 1), (
            StoredSessionCookie(name="sessionid", value=SecretStr("synthetic-new-cookie"), domain=".jinritemai.com"),))
    assert io(graph, SimpleNamespace(page=page)).page(graph.receipt.generation_id, graph.lease, 1).total == 1
    graph.session.expire_all()
    stored = ShopSessionRepository(graph.session).get_by_shop(graph.shops[0].shop_id)
    assert stored.version == 2 and stored.status == ShopSessionStatus.VALID
    assert b"synthetic-new-cookie" in graph.cipher.decrypt_bytes(stored.payload_encrypted)


def test_stale_validation_is_not_auth_invalid_and_does_not_call_platform(session_graph):
    graph = session_graph
    stored = ShopSessionRepository(graph.session).get_by_shop(graph.shops[0].shop_id)
    stored.validated_at -= timedelta(seconds=graph.settings.shop_session_validation_freshness_seconds + 60)
    graph.session.commit()
    with pytest.raises(ProductDataSessionValidationRequiredError):
        io(graph, SimpleNamespace(page=lambda *_: pytest.fail("no hidden identity/page request"))).page(
            graph.receipt.generation_id, graph.lease, 1)
    graph.session.expire_all()
    assert stored.status == ShopSessionStatus.VALID and stored.version == 1


@pytest.mark.parametrize("auth_invalid", [True, False])
def test_only_explicit_auth_invalid_marks_current_version(session_graph, auth_invalid):
    graph = session_graph
    def page(*_):
        assert graph.active[0] == 0
        if auth_invalid:
            raise PlatformAuthenticationInvalidError()
        raise CompassProductDataBusinessError(details={"business_code": 100008})
    with pytest.raises(PlatformAuthenticationInvalidError if auth_invalid else CompassProductDataBusinessError):
        io(graph, SimpleNamespace(page=page)).page(graph.receipt.generation_id, graph.lease, 1)
    graph.session.expire_all()
    stored = ShopSessionRepository(graph.session).get_by_shop(graph.shops[0].shop_id)
    assert stored.status == (ShopSessionStatus.INVALID if auth_invalid else ShopSessionStatus.VALID)
    assert stored.version == 1


@pytest.mark.parametrize("auth_invalid", [True, False])
def test_late_response_never_overwrites_new_session_version(session_graph, auth_invalid):
    graph = session_graph
    def page(*_):
        with graph.factory() as session:
            ShopSessionService(session, graph.cipher).store_payload(graph.command.model_copy(update={"expected_version": 1}), graph.payload)
        if auth_invalid:
            raise PlatformAuthenticationInvalidError()
        return ProductDataFetchResult(CompassProductDataPage(complete(graph.receipt, graph.shops[0], 1).products, 1, 10, 1), ())
    with pytest.raises(SessionVersionConflictError):
        io(graph, SimpleNamespace(page=page)).page(graph.receipt.generation_id, graph.lease, 1)
    graph.session.expire_all()
    stored = ShopSessionRepository(graph.session).get_by_shop(graph.shops[0].shop_id)
    assert stored.version == 2 and stored.status == ShopSessionStatus.VALID


def test_actor_disabled_during_http_prevents_cookie_writeback(session_graph):
    graph = session_graph
    from app.modules.access.exceptions import HumanUserDisabledError
    def page(*_):
        graph.users[0].enabled = False
        graph.session.commit()
        return ProductDataFetchResult(CompassProductDataPage(complete(graph.receipt, graph.shops[0], 1).products, 1, 10, 1), (
            StoredSessionCookie(name="sessionid", value=SecretStr("synthetic-late-cookie"), domain=".jinritemai.com"),))
    with pytest.raises(HumanUserDisabledError):
        io(graph, SimpleNamespace(page=page)).page(graph.receipt.generation_id, graph.lease, 1)
    graph.session.expire_all()
    stored = ShopSessionRepository(graph.session).get_by_shop(graph.shops[0].shop_id)
    assert stored.version == 1 and b"synthetic-late-cookie" not in graph.cipher.decrypt_bytes(stored.payload_encrypted)
