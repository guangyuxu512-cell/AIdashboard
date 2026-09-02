from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership
from app.modules.access.roles import ACCESS_ADMIN_ROLE_CODE
from app.modules.users.models import User


MembershipWithTeam = tuple[TeamMembership, Team]


class TeamRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, team_id: UUID) -> Team | None:
        return self.session.get(Team, team_id)

    def get_by_name(self, name: str) -> Team | None:
        return self.session.scalar(select(Team).where(Team.name == name))

    def list(self) -> list[Team]:
        return list(
            self.session.scalars(
                select(Team).order_by(Team.name.asc(), Team.team_id.asc()),
            ),
        )

    def add(self, team: Team) -> None:
        self.session.add(team)


class MembershipRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, membership_id: UUID) -> TeamMembership | None:
        return self.session.get(TeamMembership, membership_id)

    def get_for_user_and_team(
        self,
        *,
        user_id: UUID,
        team_id: UUID,
    ) -> MembershipWithTeam | None:
        statement = (
            select(TeamMembership, Team)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == user_id,
                TeamMembership.team_id == team_id,
            )
        )
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    def list_for_user(self, user_id: UUID) -> list[MembershipWithTeam]:
        statement = (
            select(TeamMembership, Team)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(TeamMembership.user_id == user_id)
            .order_by(Team.name.asc(), Team.team_id.asc())
        )
        return [(row[0], row[1]) for row in self.session.execute(statement)]

    def list_active_for_user(self, user_id: UUID) -> list[MembershipWithTeam]:
        statement = (
            select(TeamMembership, Team)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == user_id,
                TeamMembership.enabled.is_(True),
                Team.enabled.is_(True),
            )
            .order_by(Team.name.asc(), Team.team_id.asc())
        )
        return [(row[0], row[1]) for row in self.session.execute(statement)]

    def list_for_users(self, user_ids: Sequence[UUID]) -> list[MembershipWithTeam]:
        if not user_ids:
            return []
        statement = (
            select(TeamMembership, Team)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(TeamMembership.user_id.in_(user_ids))
            .order_by(
                TeamMembership.user_id.asc(),
                Team.name.asc(),
                Team.team_id.asc(),
            )
        )
        return [(row[0], row[1]) for row in self.session.execute(statement)]

    def add(self, membership: TeamMembership) -> None:
        self.session.add(membership)


class MembershipModuleAccessRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_codes_for_memberships(
        self,
        membership_ids: Sequence[UUID],
    ) -> dict[UUID, list[str]]:
        if not membership_ids:
            return {}
        rows = self.session.execute(
            select(
                MembershipModuleAccess.membership_id,
                MembershipModuleAccess.module_code,
            )
            .where(MembershipModuleAccess.membership_id.in_(membership_ids))
            .order_by(
                MembershipModuleAccess.membership_id.asc(),
                MembershipModuleAccess.module_code.asc(),
            ),
        )
        result: dict[UUID, list[str]] = {}
        for membership_id, module_code in rows:
            result.setdefault(membership_id, []).append(module_code)
        return result

    def replace_codes(
        self,
        membership_id: UUID,
        module_codes: Sequence[str],
    ) -> None:
        self.session.execute(
            delete(MembershipModuleAccess).where(
                MembershipModuleAccess.membership_id == membership_id,
            ),
        )
        self.session.add_all(
            [
                MembershipModuleAccess(
                    membership_id=membership_id,
                    module_code=module_code,
                )
                for module_code in module_codes
            ],
        )

    def has_module_access(
        self,
        membership_id: UUID,
        module_code: str,
    ) -> bool:
        statement = select(MembershipModuleAccess.membership_id).where(
            MembershipModuleAccess.membership_id == membership_id,
            MembershipModuleAccess.module_code == module_code,
        )
        return self.session.scalar(statement) is not None


class AccessManagementRepository:
    """Persistence queries for the access-management control plane."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_users(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None,
    ) -> list[User]:
        statement = select(User)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    User.display_name.ilike(pattern),
                    User.login_name.ilike(pattern),
                ),
            )
        return list(
            self.session.scalars(
                statement.order_by(User.created_at.desc(), User.user_id.desc())
                .offset(offset)
                .limit(limit),
            ),
        )

    def count_users(self, *, search: str | None) -> int:
        statement = select(func.count()).select_from(User)
        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    User.display_name.ilike(pattern),
                    User.login_name.ilike(pattern),
                ),
            )
        return self.session.scalar(statement) or 0

    def count_active_access_administrators(
        self,
        *,
        excluding_user_id: UUID | None = None,
        excluding_membership_id: UUID | None = None,
        excluding_team_id: UUID | None = None,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(TeamMembership)
            .join(User, User.user_id == TeamMembership.user_id)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.role_code == ACCESS_ADMIN_ROLE_CODE,
                TeamMembership.enabled.is_(True),
                Team.enabled.is_(True),
                User.enabled.is_(True),
            )
        )
        if excluding_user_id is not None:
            statement = statement.where(TeamMembership.user_id != excluding_user_id)
        if excluding_membership_id is not None:
            statement = statement.where(
                TeamMembership.membership_id != excluding_membership_id,
            )
        if excluding_team_id is not None:
            statement = statement.where(TeamMembership.team_id != excluding_team_id)
        return self.session.scalar(statement) or 0

    def membership_is_active_access_administrator(
        self,
        membership_id: UUID,
    ) -> bool:
        statement = (
            select(TeamMembership.membership_id)
            .join(User, User.user_id == TeamMembership.user_id)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.membership_id == membership_id,
                TeamMembership.role_code == ACCESS_ADMIN_ROLE_CODE,
                TeamMembership.enabled.is_(True),
                Team.enabled.is_(True),
                User.enabled.is_(True),
            )
        )
        return self.session.scalar(statement) is not None

    def user_has_active_access_administrator_membership(self, user_id: UUID) -> bool:
        statement = (
            select(TeamMembership.membership_id)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == user_id,
                TeamMembership.role_code == ACCESS_ADMIN_ROLE_CODE,
                TeamMembership.enabled.is_(True),
                Team.enabled.is_(True),
            )
        )
        return self.session.scalar(statement) is not None

    def team_has_active_access_administrator_membership(self, team_id: UUID) -> bool:
        statement = (
            select(TeamMembership.membership_id)
            .join(User, User.user_id == TeamMembership.user_id)
            .where(
                TeamMembership.team_id == team_id,
                TeamMembership.role_code == ACCESS_ADMIN_ROLE_CODE,
                TeamMembership.enabled.is_(True),
                User.enabled.is_(True),
            )
        )
        return self.session.scalar(statement) is not None
