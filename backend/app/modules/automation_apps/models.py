from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class AutomationApplicationConfig(TimestampMixin, Base):
    __tablename__ = "automation_application_configs"
    __table_args__ = (
        CheckConstraint(
            "length(trim(provider_code)) > 0",
            name="provider_code_not_blank",
        ),
        CheckConstraint("length(trim(app_id)) > 0", name="app_id_not_blank"),
        CheckConstraint("schema_source IN ('manual', 'provider')", name="schema_source"),
        CheckConstraint("jsonb_typeof(input_schema) = 'object'", name="input_schema_object"),
        CheckConstraint("jsonb_typeof(default_values) = 'object'", name="default_values_object"),
        CheckConstraint("version > 0", name="positive_version"),
        UniqueConstraint(
            "provider_code",
            "app_id",
            name="uq_automation_app_provider_app",
        ),
    )

    config_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    app_id: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="manual",
    )
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    default_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
