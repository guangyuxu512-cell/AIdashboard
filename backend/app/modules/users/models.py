from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.shared.identifiers import generate_id


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(trim(display_name)) > 0", name="display_name_not_blank"),
        CheckConstraint(
            "login_name IS NULL OR (length(trim(login_name)) > 0 AND "
            "login_name = lower(trim(login_name)))",
            name="login_name_normalized",
        ),
        UniqueConstraint("login_name", name="uq_users_login_name"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    login_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
