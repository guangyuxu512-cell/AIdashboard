from __future__ import annotations

from base64 import b64decode

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import SecretCipher, mask_login_identifier
from app.modules.authentication.exceptions import (
    InvalidSessionPayloadError,
    ShopOnboardingConflictError,
)
from app.modules.authentication.schemas import (
    CompleteManagementOnboardingCommand,
    ManagementOnboardingResult,
)
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.credentials.schemas import CredentialStatusRead
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession
from app.modules.sessions.schemas import ShopSessionMetadataRead
from app.modules.shops.models import Shop
from app.modules.shops.repository import ShopRepository
from app.modules.shops.schemas import ShopRead


class ManagementOnboardingService:
    """Atomically persist adapter-confirmed Shop, Credential and ShopSession facts."""

    def __init__(
        self,
        session: Session,
        cipher: SecretCipher,
        shop_repository: ShopRepository | None = None,
    ) -> None:
        self.session = session
        self.cipher = cipher
        self.shop_repository = shop_repository or ShopRepository(session)

    def complete(
        self,
        command: CompleteManagementOnboardingCommand,
    ) -> ManagementOnboardingResult:
        if command.expected_version != 0:
            raise ShopOnboardingConflictError("首次接入的 Session 版本必须从 0 开始")
        if self.shop_repository.get_by_platform_identity(
            command.platform,
            command.platform_shop_id,
        ) is not None:
            raise ShopOnboardingConflictError()

        payload = self._decode_payload(command.session_payload_base64)
        shop = Shop(
            display_name=command.shop_display_name,
            platform=command.platform,
            platform_shop_id=command.platform_shop_id,
            enabled=True,
        )
        credential = PlatformCredential(
            platform_code=command.platform,
            login_identifier=command.login_identifier,
            secret_encrypted=self.cipher.encrypt_text(
                command.secret.get_secret_value(),
            ),
            preferred_verification_channel=command.preferred_verification_channel,
            enabled=True,
        )

        try:
            self.session.add_all([shop, credential])
            self.session.flush()
            credential_binding = ShopCredentialBinding(
                shop_id=shop.shop_id,
                credential_id=credential.credential_id,
                enabled=True,
            )
            shop_session = ShopSession(
                shop_id=shop.shop_id,
                version=1,
                status=ShopSessionStatus.CAPTURED,
                source_device_id=None,
                captured_at=command.session_captured_at,
                validated_at=None,
                expires_at=None,
                payload_encrypted=self.cipher.encrypt_bytes(payload),
            )
            self.session.add_all([credential_binding, shop_session])
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ShopOnboardingConflictError() from error

        self.session.refresh(shop)
        self.session.refresh(credential)
        self.session.refresh(shop_session)
        return ManagementOnboardingResult(
            shop=ShopRead.model_validate(shop),
            credential=CredentialStatusRead(
                credential_id=credential.credential_id,
                platform=credential.platform_code,
                masked_identifier=mask_login_identifier(
                    credential.login_identifier,
                ),
                configured=True,
                enabled=True,
                preferred_verification_channel=credential.preferred_verification_channel,
                updated_at=credential.updated_at,
            ),
            session=ShopSessionMetadataRead(
                session_id=shop_session.session_id,
                configured=True,
                status=shop_session.status,
                version=shop_session.version,
                source_device_id=None,
                captured_at=shop_session.captured_at,
                validated_at=None,
                expires_at=None,
            ),
        )

    @staticmethod
    def _decode_payload(value: SecretStr) -> bytes:
        try:
            payload = b64decode(value.get_secret_value(), validate=True)
        except ValueError as error:
            raise InvalidSessionPayloadError() from error
        if not payload:
            raise InvalidSessionPayloadError()
        return payload
