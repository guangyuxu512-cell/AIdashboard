from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    LargeBinary,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.shops.enums import enum_values
from app.shared.identifiers import generate_id


class ShopSession(TimestampMixin, Base):
    __tablename__ = "shop_sessions"
    __table_args__ = (
        UniqueConstraint("shop_id", name="uq_shop_sessions_shop_id"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "(refresh_lease_id IS NULL) = (refresh_lease_expires_at IS NULL)",
            name="refresh_lease_pair",
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[ShopSessionStatus] = mapped_column(
        SqlEnum(
            ShopSessionStatus,
            name="shop_session_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    source_device_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        nullable=True,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    refresh_lease_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    refresh_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    payload_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
