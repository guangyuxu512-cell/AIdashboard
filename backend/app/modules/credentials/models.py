from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Uuid,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.credentials.enums import VerificationChannel
from app.modules.shops.enums import ShopPlatform, enum_values
from app.shared.identifiers import generate_id


class PlatformCredential(TimestampMixin, Base):
    __tablename__ = "platform_credentials"
    __table_args__ = (
        CheckConstraint(
            "length(trim(login_identifier)) > 0",
            name="login_identifier_not_blank",
        ),
    )

    credential_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    platform_code: Mapped[ShopPlatform] = mapped_column(
        SqlEnum(
            ShopPlatform,
            name="credential_platform_code",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    login_identifier: Mapped[str] = mapped_column(String(320), nullable=False)
    secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    preferred_verification_channel: Mapped[VerificationChannel] = mapped_column(
        SqlEnum(
            VerificationChannel,
            name="verification_channel",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
        default=VerificationChannel.MANUAL,
        server_default=VerificationChannel.MANUAL.value,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )


class ShopCredentialBinding(TimestampMixin, Base):
    __tablename__ = "shop_credential_bindings"
    __table_args__ = (
        Index(
            "uq_shop_credential_bindings_enabled_shop",
            "shop_id",
            unique=True,
            postgresql_where=text("enabled"),
        ),
        Index(
            "ix_shop_credential_bindings_credential_id",
            "credential_id",
        ),
    )

    shop_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shops.shop_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    credential_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("platform_credentials.credential_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
