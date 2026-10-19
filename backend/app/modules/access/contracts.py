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
    """Small, request-scoped authorization context passed to business services.

    A super account deliberately has no membership.  It may optionally select
    a Team as business view/write context through ``X-Team-ID``; an omitted
    context means a cross-Team read, never an implicit default Team.
    """

    user_id: UUID
    user_display_name: str
    team_id: UUID | None
    membership_id: UUID | None
    role_code: str
    data_scope: DataScope
    is_super_account: bool = False

    def require_team_id(self) -> UUID:
        """Return an explicit Team context for a new Team-owned object."""

        if self.team_id is None:
            from app.modules.access.exceptions import TeamContextRequiredError

            raise TeamContextRequiredError()
        return self.team_id

    def can_access_team(self, team_id: UUID) -> bool:
        return self.is_super_account or self.team_id == team_id


@dataclass(frozen=True, slots=True)
class TeamMembershipSummary:
    membership_id: UUID | None
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
    is_super_account: bool
    memberships: tuple[ManagedMembership, ...]
    created_at: datetime
    updated_at: datetime
