from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from app.modules.devices.models import Device  # register the referenced table
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.sessions.service import ShopSessionService
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
