from base64 import b64encode
from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import SecretCipher
from app.modules.authentication.exceptions import ShopOnboardingConflictError
from app.modules.authentication.schemas import CompleteManagementOnboardingCommand
from app.modules.authentication.service import ManagementOnboardingService
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.devices.models import Device
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User

_REFERENCED_MODELS = (Device, User)


def create_test_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Device.__table__,
            Shop.__table__,
            PlatformCredential.__table__,
            ShopCredentialBinding.__table__,
            ShopSession.__table__,
        ],
    )
    return Session(engine, expire_on_commit=False)


def command() -> CompleteManagementOnboardingCommand:
    return CompleteManagementOnboardingCommand(
        platform=ShopPlatform.DOUYIN,
        platform_shop_id="987654321",
        shop_display_name="真实抖店",
        login_identifier="login@example.com",
        secret=SecretStr("plain-password"),
        session_payload_base64=SecretStr(
            b64encode(b'{"schema":"management-login.session.v1"}').decode(),
        ),
        session_captured_at=datetime.now(UTC),
        expected_version=0,
        source="management_console",
    )


def test_management_onboarding_is_atomic_and_encrypts_sensitive_data() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    with create_test_session() as session:
        result = ManagementOnboardingService(session, cipher).complete(command())

        assert result.shop.platform_shop_id == "987654321"
        assert result.session.status == ShopSessionStatus.CAPTURED
        assert result.session.version == 1
        assert result.session.source_device_id is None
        assert result.session.validated_at is None
        assert session.scalar(select(func.count()).select_from(Shop)) == 1
        assert (
            session.scalar(select(func.count()).select_from(PlatformCredential))
            == 1
        )
        assert (
            session.scalar(select(func.count()).select_from(ShopCredentialBinding))
            == 1
        )
        assert session.scalar(select(func.count()).select_from(ShopSession)) == 1

        credential = session.scalar(select(PlatformCredential))
        shop_session = session.scalar(select(ShopSession))
        assert credential is not None
        assert shop_session is not None
        assert b"plain-password" not in credential.secret_encrypted
        assert cipher.decrypt_text(credential.secret_encrypted) == "plain-password"
        assert b"management-login.session.v1" not in shop_session.payload_encrypted
        assert b"management-login.session.v1" in cipher.decrypt_bytes(
            shop_session.payload_encrypted,
        )


def test_duplicate_platform_identity_does_not_create_partial_records() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    with create_test_session() as session:
        service = ManagementOnboardingService(session, cipher)
        service.complete(command())

        with pytest.raises(ShopOnboardingConflictError):
            service.complete(command())

        assert session.scalar(select(func.count()).select_from(Shop)) == 1
        assert (
            session.scalar(select(func.count()).select_from(PlatformCredential))
            == 1
        )
        assert session.scalar(select(func.count()).select_from(ShopSession)) == 1
