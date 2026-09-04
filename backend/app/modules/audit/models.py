from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.identifiers import generate_id


class AuditLog(Base):
    """One immutable record for a successful administrative change."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "length(trim(request_id)) > 0",
            name="request_id_not_blank",
        ),
        CheckConstraint("length(trim(action)) > 0", name="action_not_blank"),
        CheckConstraint(
            "length(trim(target_type)) > 0",
            name="target_type_not_blank",
        ),
        CheckConstraint(
            "details IS NULL OR jsonb_typeof(details) = 'object'",
            name="details_object",
        ),
        Index("ix_audit_logs_created_log", "created_at", "audit_log_id"),
        Index(
            "ix_audit_logs_actor_created_log",
            "actor_user_id",
            "created_at",
            "audit_log_id",
        ),
        Index(
            "ix_audit_logs_action_created_log",
            "action",
            "created_at",
            "audit_log_id",
        ),
    )

    audit_log_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
