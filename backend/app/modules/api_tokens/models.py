from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Uuid, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.identifiers import generate_id


class ApiToken(Base):
    __tablename__ = "api_tokens"

    token_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    owner_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    team_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ApiTokenEvent(Base):
    __tablename__ = "api_token_events"

    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=generate_id)
    token_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("api_tokens.token_id", ondelete="RESTRICT"), nullable=False, index=True)
    actor_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
