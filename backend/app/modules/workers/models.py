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


class DeviceSkillCapability(TimestampMixin, Base):
    __tablename__ = "device_skill_capabilities"
    __table_args__ = (
        CheckConstraint(
            "runtime IN ('python', 'rpa', 'discovery')",
            name="runtime",
        ),
        CheckConstraint(
            "length(trim(skill_id)) > 0",
            name="skill_id_not_blank",
        ),
        CheckConstraint(
            "length(trim(display_name)) > 0",
            name="display_name_not_blank",
        ),
        CheckConstraint(
            "length(trim(skill_version)) > 0",
            name="skill_version_not_blank",
        ),
        CheckConstraint(
            "classification IS NULL OR classification IN ('internal', 'business')",
            name="classification",
        ),
        CheckConstraint(
            "input_schema IS NULL OR jsonb_typeof(input_schema) = 'object'",
            name="input_schema_object",
        ),
    )

    device_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("devices.device_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    skill_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    runtime: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skill_version: Mapped[str] = mapped_column(String(64), nullable=False)
    classification: Mapped[str | None] = mapped_column(String(16), nullable=True)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )
