from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.repository import DeviceRepository
from app.modules.sessions.exceptions import (
    SessionEncryptionUnavailableError,
    SessionVersionConflictError,
)
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.sessions.schemas import (
    ShopSessionMetadataRead,
    StoreShopSessionCommand,
)
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.repository import ShopRepository


class ShopSessionService:
    def __init__(
        self,
        session: Session,
        cipher: SecretCipher | None = None,
        repository: ShopSessionRepository | None = None,
        shop_repository: ShopRepository | None = None,
        device_repository: DeviceRepository | None = None,
    ) -> None:
        self.session = session
        self.cipher = cipher
        self.repository = repository or ShopSessionRepository(session)
        self.shop_repository = shop_repository or ShopRepository(session)
        self.device_repository = device_repository or DeviceRepository(session)

    def _ensure_shop_exists(self, shop_id: UUID) -> None:
        if self.shop_repository.get(shop_id) is None:
            raise ShopNotFoundError()

    def get_metadata(self, shop_id: UUID) -> ShopSessionMetadataRead:
        self._ensure_shop_exists(shop_id)
        shop_session = self.repository.get_by_shop(shop_id)
        if shop_session is None:
            return ShopSessionMetadataRead(
                session_id=None,
                configured=False,
                status=ShopSessionStatus.NOT_CONFIGURED,
                version=0,
                source_device_id=None,
                captured_at=None,
                validated_at=None,
                expires_at=None,
                refresh_in_progress=False,
                refresh_lease_expires_at=None,
            )
        return self._to_metadata(shop_session)

    def reserve_for_refresh(self, shop_id: UUID, reserved_at: datetime) -> None:
        """Create only a lease carrier for a pre-existing, unconfigured Shop.

        Does not commit: the refresh service owns the reservation/lease boundary.
        Empty encrypted bytes are deliberately not a usable Session payload.
        """
        self._ensure_shop_exists(shop_id)
        if self.cipher is None:
            raise SessionEncryptionUnavailableError()
        self.repository.reserve_for_refresh(
            shop_id=shop_id,
            reserved_at=reserved_at,
            payload_encrypted=self.cipher.encrypt_bytes(b""),
        )

    def store_payload(
        self,
        command: StoreShopSessionCommand,
        payload: bytes,
        *,
        refresh_lease_id: UUID | None = None,
    ) -> ShopSessionMetadataRead:
        self._ensure_shop_exists(command.shop_id)
        if (
            command.source_device_id is not None
            and self.device_repository.get(command.source_device_id) is None
        ):
            raise DeviceNotFoundError()
        if self.cipher is None:
            raise SessionEncryptionUnavailableError()

        payload_encrypted = self.cipher.encrypt_bytes(payload)
        existing = self.repository.get_by_shop(command.shop_id)
        if existing is None:
            if command.expected_version != 0:
                raise SessionVersionConflictError()
            shop_session = ShopSession(
                shop_id=command.shop_id,
                version=1,
                status=command.status,
                source_device_id=command.source_device_id,
                captured_at=command.captured_at,
                validated_at=command.validated_at,
                expires_at=command.expires_at,
                payload_encrypted=payload_encrypted,
            )
            self.repository.add(shop_session)
            try:
                self.session.commit()
            except IntegrityError as error:
                self.session.rollback()
                raise SessionVersionConflictError() from error
            self.session.refresh(shop_session)
            return self._to_metadata(shop_session)

        if not self.repository.update_if_version(
            shop_id=command.shop_id,
            expected_version=command.expected_version,
            status=command.status,
            source_device_id=command.source_device_id,
            captured_at=command.captured_at,
            validated_at=command.validated_at,
            expires_at=command.expires_at,
            payload_encrypted=payload_encrypted,
            **({"refresh_lease_id": refresh_lease_id} if refresh_lease_id is not None else {}),
        ):
            self.session.rollback()
            raise SessionVersionConflictError()
        self.session.commit()
        updated = self.repository.get_by_shop(command.shop_id)
        if updated is None:
            raise SessionVersionConflictError()
        return self._to_metadata(updated)

    @staticmethod
    def _to_metadata(shop_session: ShopSession) -> ShopSessionMetadataRead:
        now = datetime.now(UTC)
        configured = shop_session.status is not ShopSessionStatus.NOT_CONFIGURED
        refresh_in_progress = (
            shop_session.refresh_lease_id is not None
            and shop_session.refresh_lease_expires_at is not None
            and shop_session.refresh_lease_expires_at > now
        )
        return ShopSessionMetadataRead(
            session_id=shop_session.session_id,
            configured=configured,
            status=shop_session.status,
            version=shop_session.version,
            source_device_id=shop_session.source_device_id,
            captured_at=shop_session.captured_at if configured else None,
            validated_at=shop_session.validated_at if configured else None,
            expires_at=shop_session.expires_at if configured else None,
            refresh_in_progress=refresh_in_progress,
            refresh_lease_expires_at=(
                shop_session.refresh_lease_expires_at
                if refresh_in_progress
                else None
            ),
        )
