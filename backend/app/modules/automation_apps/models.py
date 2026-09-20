from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
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


class AutomationParameterPreset(TimestampMixin, Base):
    """Team-scoped reusable parameters for one Yingdao application.

    Shop overrides intentionally remain JSON because the application schema owns
    parameter names.  Shop relationships continue to be validated through the
    existing Shop and Task boundaries rather than being made a second ownership
    model here.
    """

    __tablename__ = "automation_parameter_presets"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint("length(trim(app_id)) > 0", name="app_id_not_blank"),
        CheckConstraint(
            "jsonb_typeof(common_parameters) = 'object'",
            name="common_parameters_object",
        ),
        CheckConstraint(
            "jsonb_typeof(shop_overrides) = 'object'",
            name="shop_overrides_object",
        ),
        CheckConstraint(
            "jsonb_typeof(input_schema_snapshot) = 'object'",
            name="input_schema_snapshot_object",
        ),
        CheckConstraint("version > 0", name="positive_version"),
        Index(
            "uq_automation_preset_team_app_name",
            "team_id",
            "app_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_automation_preset_team_app_created",
            "team_id",
            "app_id",
            "created_at",
            "preset_id",
        ),
        Index(
            "ix_automation_preset_team_creator_created",
            "team_id",
            "created_by_user_id",
            "created_at",
            "preset_id",
        ),
    )

    preset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    app_id: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    common_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    shop_overrides: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
    )
    # A preset owns its field contract.  The application configuration is only
    # the initial template for a newly-created preset; changing that template
    # must not reinterpret a saved preset, Task snapshot, or Schedule run.
    input_schema_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {"fields": []},
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Keep the durable Task/Schedule foreign-key history intact while removing
    # the preset from all new configuration reads and selections.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def input_schema(self) -> dict[str, Any]:
        """Read-model compatibility name for the persisted schema snapshot."""
        return self.input_schema_snapshot
