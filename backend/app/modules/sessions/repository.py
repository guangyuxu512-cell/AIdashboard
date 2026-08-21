from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession


class ShopSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_shop(self, shop_id: UUID) -> ShopSession | None:
        return self.session.scalar(
            select(ShopSession).where(ShopSession.shop_id == shop_id),
        )

    def add(self, shop_session: ShopSession) -> None:
        self.session.add(shop_session)

    def set_validation_status(
        self,
        *,
        shop_id: UUID,
        expected_version: int,
        status: ShopSessionStatus,
        validated_at: datetime,
    ) -> bool:
        result = self.session.execute(
            update(ShopSession)
            .where(
                ShopSession.shop_id == shop_id,
                ShopSession.version == expected_version,
            )
            .values(status=status, validated_at=validated_at, updated_at=func.now()),
        )
        return result.rowcount == 1

    def update_if_version(
        self,
        *,
        shop_id: UUID,
        expected_version: int,
        status: ShopSessionStatus,
        source_device_id: UUID | None,
        captured_at: datetime,
        validated_at: datetime | None,
        expires_at: datetime | None,
        payload_encrypted: bytes,
    ) -> bool:
        statement = (
            update(ShopSession)
            .where(
                ShopSession.shop_id == shop_id,
                ShopSession.version == expected_version,
            )
            .values(
                version=ShopSession.version + 1,
                status=status,
                source_device_id=source_device_id,
                captured_at=captured_at,
                validated_at=validated_at,
                expires_at=expires_at,
                payload_encrypted=payload_encrypted,
                updated_at=func.now(),
            )
        )
        result = self.session.execute(statement)
        return result.rowcount == 1

    def acquire_refresh_lease(
        self,
        *,
        shop_id: UUID,
        lease_id: UUID,
        now: datetime,
        expires_at: datetime,
    ) -> bool:
        result = self.session.execute(
            update(ShopSession)
            .where(
                ShopSession.shop_id == shop_id,
                or_(
                    ShopSession.refresh_lease_id.is_(None),
                    ShopSession.refresh_lease_expires_at <= now,
                ),
            )
            .values(
                refresh_lease_id=lease_id,
                refresh_lease_expires_at=expires_at,
                updated_at=func.now(),
            ),
        )
        return result.rowcount == 1

    def has_active_refresh_lease(
        self,
        *,
        shop_id: UUID,
        lease_id: UUID,
        now: datetime,
    ) -> bool:
        return (
            self.session.scalar(
                select(ShopSession.session_id).where(
                    ShopSession.shop_id == shop_id,
                    ShopSession.refresh_lease_id == lease_id,
                    ShopSession.refresh_lease_expires_at > now,
                ),
            )
            is not None
        )

    def release_refresh_lease(self, *, shop_id: UUID, lease_id: UUID) -> bool:
        result = self.session.execute(
            update(ShopSession)
            .where(
                ShopSession.shop_id == shop_id,
                ShopSession.refresh_lease_id == lease_id,
            )
            .values(
                refresh_lease_id=None,
                refresh_lease_expires_at=None,
                updated_at=func.now(),
            ),
        )
        return result.rowcount == 1
