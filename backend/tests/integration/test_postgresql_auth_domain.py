from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.modules.access.models import Team
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.credentials.schemas import CredentialCreate
from app.modules.credentials.service import CredentialService
from app.modules.devices.models import Device
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import SessionVersionConflictError
from app.modules.sessions.models import ShopSession
from app.modules.sessions.schemas import StoreShopSessionCommand
from app.modules.sessions.service import ShopSessionService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop


pytestmark = pytest.mark.integration
TEST_PREFIX = "stage-3a"


def _cleanup(
    engine: Engine,
    *,
    shop_ids: set[UUID],
    credential_ids: set[UUID],
    device_ids: set[UUID],
    team_id: UUID,
) -> None:
    with Session(engine) as session:
        if shop_ids:
            session.execute(delete(ShopSession).where(ShopSession.shop_id.in_(shop_ids)))
            session.execute(
                delete(ShopCredentialBinding).where(
                    ShopCredentialBinding.shop_id.in_(shop_ids),
                ),
            )
        if credential_ids:
            session.execute(
                delete(ShopCredentialBinding).where(
                    ShopCredentialBinding.credential_id.in_(credential_ids),
                ),
            )
            session.execute(
                delete(PlatformCredential).where(
                    PlatformCredential.credential_id.in_(credential_ids),
                ),
            )
        if shop_ids:
            session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
        if device_ids:
            session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def test_credential_binding_encryption_and_session_version(
    postgresql_engine: Engine,
) -> None:
    shop_ids = {uuid4(), uuid4()}
    device_ids = {uuid4()}
    team_id = uuid4()
    credential_ids: set[UUID] = set()
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    plaintext_password = "stage-3a-real-password"
    plaintext_payload = b"stage-3a-cookie-session-payload"
    now = datetime.now(UTC)

    try:
        with Session(postgresql_engine) as session:
            session.add(Team(team_id=team_id, name="Credential Integration Team"))
            session.flush()
            session.add_all(
                [
                    Shop(
                        shop_id=shop_id,
                        display_name=f"{TEST_PREFIX}-shop-{index}",
                        platform=ShopPlatform.DOUYIN,
                        enabled=True,
                    )
                    for index, shop_id in enumerate(shop_ids, start=1)
                ],
            )
            session.add(
                Device(
                    device_id=next(iter(device_ids)),
                    team_id=team_id,
                    display_name=f"{TEST_PREFIX}-device",
                    enabled=True,
                ),
            )
            session.commit()

        first_shop_id, second_shop_id = tuple(shop_ids)
        device_id = next(iter(device_ids))
        with Session(postgresql_engine, expire_on_commit=False) as session:
            credential_service = CredentialService(session, cipher)
            status = credential_service.create(
                CredentialCreate(
                    shop_id=first_shop_id,
                    login_identifier="13812348888",
                    secret=SecretStr(plaintext_password),
                ),
            )
            assert status.credential_id is not None
            credential_ids.add(status.credential_id)
            credential_service.bind(second_shop_id, status.credential_id)

            stored_secret = session.scalar(
                select(PlatformCredential.secret_encrypted).where(
                    PlatformCredential.credential_id == status.credential_id,
                ),
            )
            assert stored_secret is not None
            assert plaintext_password.encode() not in stored_secret
            assert cipher.decrypt_text(stored_secret) == plaintext_password

            bindings = list(
                session.scalars(
                    select(ShopCredentialBinding).where(
                        ShopCredentialBinding.credential_id == status.credential_id,
                    ),
                ),
            )
            assert {binding.shop_id for binding in bindings} == shop_ids

        with Session(postgresql_engine, expire_on_commit=False) as session:
            session_service = ShopSessionService(session, cipher)
            created = session_service.store_payload(
                StoreShopSessionCommand(
                    shop_id=first_shop_id,
                    expected_version=0,
                    status=ShopSessionStatus.VALID,
                    source_device_id=device_id,
                    captured_at=now,
                    validated_at=now,
                ),
                plaintext_payload,
            )
            assert created.version == 1

            stored_payload = session.scalar(
                select(ShopSession.payload_encrypted).where(
                    ShopSession.shop_id == first_shop_id,
                ),
            )
            assert stored_payload is not None
            assert plaintext_payload not in stored_payload
            assert cipher.decrypt_bytes(stored_payload) == plaintext_payload

            with pytest.raises(SessionVersionConflictError):
                session_service.store_payload(
                    StoreShopSessionCommand(
                        shop_id=first_shop_id,
                        expected_version=0,
                        status=ShopSessionStatus.INVALID,
                        source_device_id=device_id,
                        captured_at=now,
                    ),
                    b"stale-payload",
                )

            updated = session_service.store_payload(
                StoreShopSessionCommand(
                    shop_id=first_shop_id,
                    expected_version=1,
                    status=ShopSessionStatus.REFRESH_REQUIRED,
                    source_device_id=device_id,
                    captured_at=now,
                ),
                b"new-payload",
            )
            assert updated.version == 2
    finally:
        _cleanup(
            postgresql_engine,
            shop_ids=shop_ids,
            credential_ids=credential_ids,
            device_ids=device_ids,
            team_id=team_id,
        )
