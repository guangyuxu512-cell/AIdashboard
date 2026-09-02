from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.access.enums import DataScope


@dataclass(frozen=True, slots=True)
class HumanPrincipal:
    """Authenticated management-plane identity before Team resolution."""

    user_id: UUID
    display_name: str


@dataclass(frozen=True, slots=True)
class ActorContext:
    """Small, request-scoped authorization context passed to business services."""

    user_id: UUID
    user_display_name: str
    team_id: UUID
    membership_id: UUID
    role_code: str
    data_scope: DataScope


@dataclass(frozen=True, slots=True)
class TeamMembershipSummary:
    membership_id: UUID
    team_id: UUID
    team_name: str
    team_enabled: bool
    role_code: str
    data_scope: DataScope
    membership_enabled: bool


@dataclass(frozen=True, slots=True)
class ManagedMembership:
    membership_id: UUID
    team_id: UUID
    team_name: str
    team_enabled: bool
    role_code: str
    data_scope: DataScope
    enabled: bool
    module_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManagedMember:
    user_id: UUID
    display_name: str
    login_name: str | None
    enabled: bool
    memberships: tuple[ManagedMembership, ...]
    created_at: datetime
    updated_at: datetime
