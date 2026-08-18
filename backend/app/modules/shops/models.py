from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.shops.enums import BindingRole, ShopPlatform, enum_values
from app.shared.identifiers import generate_id


class Shop(TimestampMixin, Base):
    __tablename__ = "shops"
    __table_args__ = (
        CheckConstraint("length(trim(display_name)) > 0", name="display_name_not_blank"),
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


class ShopDeviceBinding(TimestampMixin, Base):
    __tablename__ = "shop_device_bindings"
    __table_args__ = (
        Index(
            "uq_shop_device_bindings_enabled_primary",
            "shop_id",
            unique=True,
            postgresql_where=text("enabled AND binding_role = 'primary'"),
        ),
    )

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
    binding_role: Mapped[BindingRole] = mapped_column(
        SqlEnum(
            BindingRole,
            name="binding_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
