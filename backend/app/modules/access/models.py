from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.modules.access.enums import DataScope
from app.modules.access.roles import DEFAULT_ROLE_CODE
from app.shared.identifiers import generate_id


class Team(TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),)

    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )


class TeamMembership(TimestampMixin, Base):
    __tablename__ = "team_memberships"
    __table_args__ = (
        CheckConstraint(
            "length(trim(role_code)) > 0",
            name="role_code_not_blank",
        ),
        CheckConstraint(
            "data_scope IN ('self', 'team', 'all')",
            name="data_scope",
        ),
        UniqueConstraint(
            "team_id",
            "user_id",
            name="uq_team_memberships_team_user",
        ),
        Index("ix_team_memberships_user_id", "user_id"),
        Index(
            "ix_team_memberships_active_user",
            "user_id",
            postgresql_where=text("enabled"),
        ),
        Index(
            "ix_team_memberships_active_team",
            "team_id",
            postgresql_where=text("enabled"),
        ),
    )

    membership_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=generate_id,
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.team_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    role_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_ROLE_CODE,
        server_default=DEFAULT_ROLE_CODE,
    )
    data_scope: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
        default=DataScope.TEAM,
        server_default=DataScope.TEAM.value,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )


class MembershipModuleAccess(Base):
    """One allowed PC module for one TeamMembership."""

    __tablename__ = "membership_module_accesses"

    membership_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("team_memberships.membership_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    module_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
