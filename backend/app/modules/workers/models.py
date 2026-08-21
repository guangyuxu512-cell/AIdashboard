from datetime import datetime
from uuid import UUID

from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Uuid,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class WorkerDeviceCredential(TimestampMixin, Base):
    __tablename__ = "worker_device_credentials"

    credential_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )


class DeviceRuntime(TimestampMixin, Base):
    __tablename__ = "device_runtime"
    __table_args__ = (
        CheckConstraint(
            "connection_status IN ('online', 'offline')",
            name="connection_status",
        ),
    )

    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    worker_version: Mapped[str] = mapped_column(String(64), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    connection_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="online",
    )
    offline_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class DeviceProviderInventory(TimestampMixin, Base):
    __tablename__ = "device_provider_inventory"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(inventory_payload) = 'object'",
            name="inventory_payload_object",
        ),
    )

    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    provider_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    account_display: Mapped[str | None] = mapped_column(String(200), nullable=True)
    account_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enterprise_account: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    last_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    inventory_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
