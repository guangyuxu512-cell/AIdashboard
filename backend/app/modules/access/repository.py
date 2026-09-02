from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.access.models import Team, TeamMembership


MembershipWithTeam = tuple[TeamMembership, Team]


class TeamRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, team_id: UUID) -> Team | None:
        return self.session.get(Team, team_id)

    def get_by_name(self, name: str) -> Team | None:
        return self.session.scalar(select(Team).where(Team.name == name))

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

    def add(self, membership: TeamMembership) -> None:
        self.session.add(membership)
