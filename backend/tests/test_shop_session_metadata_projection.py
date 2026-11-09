import base64
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import SecretCipher
from app.modules.devices.models import Device  # register the referenced table
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import SessionVersionConflictError
from app.modules.sessions.health_service import ValidatedSessionCandidate
from app.modules.sessions.models import ShopSession
from app.modules.sessions.refresh_service import ShopSessionRefreshService
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.sessions.schemas import CompleteShopSessionRefreshCommand
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop  # register the referenced table


@pytest.mark.parametrize("status", [ShopSessionStatus.VALID, ShopSessionStatus.NOT_CONFIGURED])
def test_metadata_never_selects_encrypted_payload_and_full_reader_still_can(status):
    _ = (Device, Shop)  # imports above register the referenced tables
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ShopSession.__table__.create(engine)
    shop_id, session_id = uuid4(), uuid4()
    blob = b"synthetic-encrypted-payload" * 60_000
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(ShopSession(
            session_id=session_id, shop_id=shop_id, version=3, status=status,
            captured_at=now, validated_at=now, payload_encrypted=blob,
        ))
        session.commit()

    statements: list[str] = []
    event.listen(
        engine, "before_cursor_execute",
        lambda _conn, _cursor, statement, _params, _ctx, _many: statements.append(statement),
    )

    class ExistingShop:
        def get(self, identifier):
            return object() if identifier == shop_id else None

    with Session(engine) as session:
        repository = ShopSessionRepository(session)
        service = ShopSessionService(session, repository=repository, shop_repository=ExistingShop())
        metadata = service.get_metadata(shop_id)
        assert metadata.session_id == session_id
        assert metadata.status is status and metadata.version == 3
        assert metadata.configured is (status is ShopSessionStatus.VALID)
        assert metadata.refresh_in_progress is False
        assert (metadata.captured_at is not None) is metadata.configured
        selects = [statement for statement in statements if "FROM shop_sessions" in statement]
        assert len(selects) == 1
        assert "payload_encrypted" not in selects[0].lower()

        partial = repository.get_metadata_by_shop(shop_id)
        assert partial is not None and "payload_encrypted" in inspect(partial).unloaded
        with pytest.raises(InvalidRequestError):
            _ = partial.payload_encrypted
        full = repository.get_by_shop(shop_id)
        assert full is partial and full.payload_encrypted == blob
        assert "payload_encrypted" in statements[-1].lower()
    engine.dispose()


def test_postgresql_metadata_statement_omits_encrypted_payload():
    class CaptureStatement:
        statement = None

        def scalar(self, statement):
            self.statement = statement
            return None

    session = CaptureStatement()
    assert ShopSessionRepository(session).get_metadata_by_shop(uuid4()) is None
    sql = str(session.statement.compile(dialect=postgresql.dialect())).lower()
    assert "shop_sessions.payload_encrypted" not in sql
    assert "shop_sessions.refresh_lease_expires_at" in sql


@pytest.mark.parametrize("conflict", [False, True])
def test_refresh_avoids_old_payload_select_and_keeps_version_cas(conflict):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    ShopSession.__table__.create(engine)
    shop_id = uuid4()
    old_encrypted = b"synthetic-encrypted-payload" * 60_000
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    now = datetime.now(UTC)
    with Session(engine) as session:
        session.add(ShopSession(
            shop_id=shop_id, version=3, status=ShopSessionStatus.VALID,
            captured_at=now, validated_at=now, payload_encrypted=old_encrypted,
        ))
        session.commit()

    statements: list[str] = []

    def observe(_conn, _cursor, statement, _params, _ctx, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    shop = SimpleNamespace(platform=ShopPlatform.DOUYIN, platform_shop_id="synthetic-shop")

    class ExistingShop:
        def get(self, identifier):
            return shop if identifier == shop_id else None

    class Health:
        def validate_candidate(self, candidate_shop, platform, platform_shop_id, version, payload, parsed):
            assert not session.in_transaction()
            assert candidate_shop == shop_id and platform is ShopPlatform.DOUYIN
            assert platform_shop_id == "synthetic-shop" and version == 3
            assert parsed.identity.platform_shop_id == platform_shop_id
            return ValidatedSessionCandidate(
                payload=payload, platform_shop_id=platform_shop_id,
                shop_display_name="fixture", validated_at=now, cookie_updates_applied=0,
            )

    payload = json.dumps({
        "schema": "management-login.session.v1", "platform": "douyin",
        "identity": {"platform": "douyin", "platformShopId": "synthetic-shop", "shopDisplayName": "fixture"},
        "cookies": [{"name": "synthetic", "value": "synthetic"}],
    }).encode()
    with Session(engine) as session:
        repository = ShopSessionRepository(session)
        shops = ExistingShop()
        store = ShopSessionService(session, cipher, repository=repository, shop_repository=shops)
        refresh = ShopSessionRefreshService(
            session, cipher, Health(), repository=repository, shop_repository=shops,
            session_service=store, collection_resume=lambda _shop_id: 0,
            settings=Settings(_env_file=None, shop_session_refresh_lease_seconds=60),
        )
        lease = refresh.acquire(shop_id)
        assert lease.expected_version == 3
        command = CompleteShopSessionRefreshCommand(
            lease_id=lease.lease_id, expected_version=4 if conflict else 3,
            session_payload_base64=SecretStr(base64.b64encode(payload).decode()), captured_at=now,
        )
        rechecked: list[bool] = []
        if conflict:
            with pytest.raises(SessionVersionConflictError):
                refresh.complete(shop_id, command, recheck_authorization=lambda: rechecked.append(True))
            assert rechecked == []
        else:
            result = refresh.complete(shop_id, command, recheck_authorization=lambda: rechecked.append(True))
            assert result.version == 4 and rechecked == [True]

        selects = [statement.lower() for statement in statements
                   if statement.lstrip().lower().startswith("select") and "shop_sessions" in statement.lower()]
        assert selects and all("payload_encrypted" not in statement for statement in selects)
        event.remove(engine, "before_cursor_execute", observe)
        session.expire_all()
        full = repository.get_by_shop(shop_id)
        assert full is not None and full.refresh_lease_id is None
        assert full.version == (3 if conflict else 4)
        if conflict:
            assert full.payload_encrypted == old_encrypted
        else:
            assert cipher.decrypt_bytes(full.payload_encrypted) == payload
    engine.dispose()
