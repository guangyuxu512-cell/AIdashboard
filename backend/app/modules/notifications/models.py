from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, LargeBinary, String, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class NotificationChannel(TimestampMixin, Base):
    __tablename__ = "notification_channels"
    __table_args__ = (
        CheckConstraint(
            "channel_type IN ('feishu_webhook', 'wecom_webhook')",
            name="channel_type",
        ),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )

    channel_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    webhook_url_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    device_offline_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    device_recovered_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
