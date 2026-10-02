from base64 import b64encode
from datetime import UTC, datetime
import json

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.security import SecretCipher
from app.modules.access.models import Team
from app.modules.authentication.exceptions import ShopOnboardingConflictError
from app.modules.authentication.schemas import (
    CompleteManagementOnboardingCommand,
    VerifyPddManagementLoginCommand,
)
from app.modules.authentication.service import ManagementOnboardingService
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.devices.models import Device
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession
from app.modules.operating_dashboard.models import (
    OperatingDataCollectionItem,
    OperatingDataCollectionJob,
    ShopOperatingDailyMetric,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from app.platforms.exceptions import PlatformRequestFailedError
from app.platforms.schemas import PlatformShopIdentity

_REFERENCED_MODELS = (Device, Team, User)


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
            ShopOperatingDailyMetric.__table__,
            OperatingDataCollectionJob.__table__,
            OperatingDataCollectionItem.__table__,
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


class PddConnectorStub:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.cookies = None

    def fetch_identity_from_cookies(self, cookies):  # type: ignore[no-untyped-def]
        self.cookies = cookies
        if self.error:
            raise self.error
        return PlatformShopIdentity(
            platform_shop_id="pdd-mall-1",
            shop_display_name="真实拼多多店铺",
        )


def pdd_command() -> CompleteManagementOnboardingCommand:
    payload = {
        "schema": "management-login.session.v1",
        "platform": "pdd",
        "cookies": [
            {
                "name": "pdd_user_id",
                "value": "test-session-cookie",
                "domain": ".pinduoduo.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            },
        ],
    }
    return CompleteManagementOnboardingCommand(
        platform=ShopPlatform.PDD,
        login_identifier="pdd-login@example.com",
        secret=SecretStr("plain-password"),
        session_payload_base64=SecretStr(
            b64encode(json.dumps(payload).encode()).decode(),
        ),
        session_captured_at=datetime.now(UTC),
        expected_version=0,
        source="management_console",
    )


def pdd_identity_command() -> VerifyPddManagementLoginCommand:
    return VerifyPddManagementLoginCommand(
        session_payload_base64=pdd_command().session_payload_base64,
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
        collection_job = session.scalar(select(OperatingDataCollectionJob))
        assert collection_job is None
        assert (
            session.scalar(select(func.count()).select_from(OperatingDataCollectionItem))
            == 0
        )

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


def test_pdd_onboarding_derives_identity_before_the_atomic_write() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    connector = PddConnectorStub()
    with create_test_session() as session:
        result = ManagementOnboardingService(
            session,
            cipher,
            pdd_connector=connector,  # type: ignore[arg-type]
        ).complete(pdd_command())

        assert result.shop.platform is ShopPlatform.PDD
        assert result.shop.platform_shop_id == "pdd-mall-1"
        assert result.shop.display_name == "真实拼多多店铺"
        assert connector.cookies is not None
        assert connector.cookies[0].name == "pdd_user_id"
        assert (
            session.scalar(select(func.count()).select_from(ShopCredentialBinding))
            == 1
        )


def test_pdd_identity_preflight_uses_fixed_identity_and_writes_nothing() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    connector = PddConnectorStub()
    with create_test_session() as session:
        result = ManagementOnboardingService(
            session,
            cipher,
            pdd_connector=connector,  # type: ignore[arg-type]
        ).verify_pdd_identity(pdd_identity_command())

        assert result.platform_shop_id == "pdd-mall-1"
        assert result.shop_display_name == "真实拼多多店铺"
        assert connector.cookies is not None
        assert connector.cookies[0].name == "pdd_user_id"
        assert session.scalar(select(func.count()).select_from(Shop)) == 0
        assert (
            session.scalar(select(func.count()).select_from(PlatformCredential))
            == 0
        )
        assert session.scalar(select(func.count()).select_from(ShopSession)) == 0


def test_pdd_identity_failure_creates_no_partial_onboarding_records() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    connector = PddConnectorStub(error=PlatformRequestFailedError())
    with create_test_session() as session:
        service = ManagementOnboardingService(
            session,
            cipher,
            pdd_connector=connector,  # type: ignore[arg-type]
        )
        with pytest.raises(PlatformRequestFailedError):
            service.complete(pdd_command())

        assert session.scalar(select(func.count()).select_from(Shop)) == 0
        assert (
            session.scalar(select(func.count()).select_from(PlatformCredential))
            == 0
        )
        assert session.scalar(select(func.count()).select_from(ShopSession)) == 0


def test_pdd_onboarding_rejects_client_supplied_shop_identity() -> None:
    values = pdd_command().model_dump()
    values["platform_shop_id"] = "untrusted-client-id"
    with pytest.raises(ValidationError):
        CompleteManagementOnboardingCommand(**values)
