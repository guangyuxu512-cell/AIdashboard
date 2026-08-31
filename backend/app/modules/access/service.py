from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext, TeamMembershipSummary
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import (
    HumanAuthenticationRequiredError,
    HumanUserDisabledError,
    InvalidDataScopeError,
    TeamAccessDeniedError,
    TeamContextRequiredError,
    TeamDisabledError,
    TeamMembershipConflictError,
    TeamMembershipNotFoundError,
    TeamMembershipRequiredError,
    TeamNotFoundError,
)
from app.modules.access.models import Team, TeamMembership
from app.modules.access.repository import MembershipRepository, TeamRepository
from app.modules.access.schemas import (
    TeamCreate,
    TeamMembershipCreate,
    TeamMembershipUpdate,
    TeamUpdate,
)
from app.modules.users.exceptions import UserNotFoundError
from app.modules.users.repository import UserRepository


class TeamService:
    def __init__(
        self,
        session: Session,
        repository: TeamRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or TeamRepository(session)

    def get(self, team_id: UUID) -> Team:
        team = self.repository.get(team_id)
        if team is None:
            raise TeamNotFoundError()
        return team

    def create(self, data: TeamCreate) -> Team:
        team = Team(**data.model_dump())
        self.repository.add(team)
        self.session.commit()
        self.session.refresh(team)
        return team

    def update(self, team_id: UUID, data: TeamUpdate) -> Team:
        team = self.get(team_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(team, field, value)
        self.session.commit()
        self.session.refresh(team)
        return team


class MembershipService:
    def __init__(
        self,
        session: Session,
        *,
        repository: MembershipRepository | None = None,
        team_repository: TeamRepository | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or MembershipRepository(session)
        self.team_repository = team_repository or TeamRepository(session)
        self.user_repository = user_repository or UserRepository(session)

    def get(self, membership_id: UUID) -> TeamMembership:
        membership = self.repository.get(membership_id)
        if membership is None:
            raise TeamMembershipNotFoundError()
        return membership

    def create(self, data: TeamMembershipCreate) -> TeamMembership:
        user = self.user_repository.get(data.user_id)
        if user is None:
            raise UserNotFoundError()
        if not user.enabled:
            raise HumanUserDisabledError()

        team = self.team_repository.get(data.team_id)
        if team is None:
            raise TeamNotFoundError()
        if not team.enabled:
            raise TeamDisabledError()
        if (
            self.repository.get_for_user_and_team(
                user_id=data.user_id,
                team_id=data.team_id,
            )
            is not None
        ):
            raise TeamMembershipConflictError()

        membership = TeamMembership(**data.model_dump())
        self.repository.add(membership)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise TeamMembershipConflictError() from error
        self.session.refresh(membership)
        return membership

    def update(
        self,
        membership_id: UUID,
        data: TeamMembershipUpdate,
    ) -> TeamMembership:
        membership = self.get(membership_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(membership, field, value)
        self.session.commit()
        self.session.refresh(membership)
        return membership


class ActorContextService:
    def __init__(
        self,
        session: Session,
        *,
        membership_repository: MembershipRepository | None = None,
        user_repository: UserRepository | None = None,
    ) -> None:
        self.membership_repository = membership_repository or MembershipRepository(
            session,
        )
        self.user_repository = user_repository or UserRepository(session)

    def resolve(
        self,
        *,
        user_id: UUID,
        requested_team_id: UUID | None,
    ) -> ActorContext:
        user = self.user_repository.get(user_id)
        if user is None:
            raise HumanAuthenticationRequiredError()
        if not user.enabled:
            raise HumanUserDisabledError()

        if requested_team_id is None:
            memberships = self.membership_repository.list_active_for_user(user_id)
            if not memberships:
                raise TeamMembershipRequiredError()
            if len(memberships) > 1:
                raise TeamContextRequiredError()
            membership, team = memberships[0]
        else:
            selected = self.membership_repository.get_for_user_and_team(
                user_id=user_id,
                team_id=requested_team_id,
            )
            if selected is None:
                raise TeamAccessDeniedError()
            membership, team = selected
            if not membership.enabled or not team.enabled:
                raise TeamAccessDeniedError()

        data_scope = self._validated_scope(membership.data_scope)
        return ActorContext(
            user_id=user.user_id,
            user_display_name=user.display_name,
            team_id=team.team_id,
            membership_id=membership.membership_id,
            role_code=membership.role_code,
            data_scope=data_scope,
        )

    def list_my_teams(self, user_id: UUID) -> list[TeamMembershipSummary]:
        user = self.user_repository.get(user_id)
        if user is None:
            raise HumanAuthenticationRequiredError()
        if not user.enabled:
            raise HumanUserDisabledError()

        return [
            TeamMembershipSummary(
                membership_id=membership.membership_id,
                team_id=team.team_id,
                team_name=team.name,
                team_enabled=team.enabled,
                role_code=membership.role_code,
                data_scope=self._validated_scope(membership.data_scope),
                membership_enabled=membership.enabled,
            )
            for membership, team in self.membership_repository.list_for_user(user_id)
        ]

    @staticmethod
    def _validated_scope(value: object) -> DataScope:
        if not isinstance(value, str):
            raise InvalidDataScopeError()
        try:
            return DataScope(value)
        except ValueError as error:
            raise InvalidDataScopeError() from error
