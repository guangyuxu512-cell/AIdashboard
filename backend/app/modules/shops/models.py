from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.shops.enums import ShopPlatform, enum_values
from app.shared.identifiers import generate_id


class Shop(TimestampMixin, Base):
    __tablename__ = "shops"
    __table_args__ = (
        CheckConstraint("length(trim(display_name)) > 0", name="display_name_not_blank"),
        CheckConstraint(
            "(operating_start_date IS NULL "
            "AND operating_start_date_source IS NULL "
            "AND operating_start_date_set_by_user_id IS NULL "
            "AND operating_start_date_set_at IS NULL) "
            "OR (operating_start_date IS NOT NULL "
            "AND operating_start_date_source IS NOT NULL "
            "AND operating_start_date_set_by_user_id IS NOT NULL "
            "AND operating_start_date_set_at IS NOT NULL)",
            name="operating_start_date_audit_complete",
        ),
        UniqueConstraint(
            "platform",
            "platform_shop_id",
            name="uq_shops_platform_identity",
        ),
    )

    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    platform: Mapped[ShopPlatform] = mapped_column(
        SqlEnum(
            ShopPlatform,
            name="shop_platform",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    platform_shop_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # This is a deliberately optional, manager-confirmed coverage boundary.
    # It is not inferred from Control Center onboarding, first collection, or
    # first order.  The audit fields make the source of an explicit boundary
    # visible without storing any platform-session material on the Shop.
    operating_start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    operating_start_date_source: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    operating_start_date_set_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=True,
    )
    operating_start_date_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )


class ShopDeviceBinding(TimestampMixin, Base):
    __tablename__ = "shop_device_bindings"

    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
