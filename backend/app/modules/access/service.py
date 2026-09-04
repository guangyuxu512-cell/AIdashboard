from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import (
    ActorContext,
    ManagedMember,
    ManagedMembership,
    TeamMembershipSummary,
)
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import (
    AccessAdministratorMembershipUnavailableError,
    AccessMemberCredentialNotConfiguredError,
    HumanAuthenticationRequiredError,
    HumanUserDisabledError,
    InvalidDataScopeError,
    InvalidModuleAccessError,
    LastAccessAdministratorRequiredError,
    ModuleAccessDeniedError,
    TeamAccessDeniedError,
    TeamContextRequiredError,
    TeamDisabledError,
    TeamMembershipConflictError,
    TeamMembershipNotFoundError,
    TeamMembershipRequiredError,
    TeamNotFoundError,
)
from app.modules.access.models import Team, TeamMembership
from app.modules.access.module_access import ModuleCode
from app.modules.access.repository import (
    AccessManagementRepository,
    MembershipModuleAccessRepository,
    MembershipRepository,
    TeamRepository,
)
from app.modules.access.roles import ACCESS_ADMIN_ROLE_CODE
from app.modules.access.schemas import (
    AccessMemberCreate,
    AccessMemberUpdate,
    AccessMembershipCreate,
    AccessMembershipUpdate,
    TeamCreate,
    TeamMembershipCreate,
    TeamMembershipUpdate,
    TeamUpdate,
)
from app.modules.audit.enums import AuditAction, AuditTargetType
from app.modules.audit.service import AuditLogService
from app.modules.human_auth.passwords import PasswordService
from app.modules.human_auth.repository import HumanSessionRepository
from app.modules.human_auth.exceptions import HumanLoginNameConflictError
from app.modules.users.exceptions import UserNotFoundError
from app.modules.users.models import User
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


class ModuleAccessService:
    def __init__(
        self,
        session: Session,
        repository: MembershipModuleAccessRepository | None = None,
    ) -> None:
        self.repository = repository or MembershipModuleAccessRepository(session)

    def list_for_membership(self, membership_id: UUID) -> list[ModuleCode]:
        codes = self.repository.list_codes_for_memberships([membership_id]).get(
            membership_id,
            [],
        )
        try:
            return [ModuleCode(code) for code in codes]
        except ValueError as error:
            raise InvalidModuleAccessError() from error

    def require_module_access(
        self,
        actor: ActorContext,
        module_code: ModuleCode,
    ) -> None:
        if not self.repository.has_module_access(actor.membership_id, module_code):
            raise ModuleAccessDeniedError()


class AccessManagementService:
    """Admin-only member, membership and Team lifecycle orchestration."""

    def __init__(
        self,
        session: Session,
        password_service: PasswordService,
        *,
        user_repository: UserRepository | None = None,
        team_repository: TeamRepository | None = None,
        membership_repository: MembershipRepository | None = None,
        module_access_repository: MembershipModuleAccessRepository | None = None,
        management_repository: AccessManagementRepository | None = None,
        human_session_repository: HumanSessionRepository | None = None,
        audit_log_service: AuditLogService | None = None,
    ) -> None:
        self.session = session
        self.password_service = password_service
        self.user_repository = user_repository or UserRepository(session)
        self.team_repository = team_repository or TeamRepository(session)
        self.membership_repository = membership_repository or MembershipRepository(
            session,
        )
        self.module_access_repository = (
            module_access_repository or MembershipModuleAccessRepository(session)
        )
        self.management_repository = management_repository or AccessManagementRepository(
            session,
        )
        self.human_session_repository = (
            human_session_repository or HumanSessionRepository(session)
        )
        self.audit_log_service = audit_log_service or AuditLogService(session)

    def list_members(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None,
    ) -> tuple[list[ManagedMember], int]:
        users = self.management_repository.list_users(
            offset=offset,
            limit=limit,
            search=search,
        )
        memberships = self.membership_repository.list_for_users(
            [user.user_id for user in users],
        )
        return (
            self._managed_members(users, memberships),
            self.management_repository.count_users(search=search),
        )

    def get_member(self, user_id: UUID) -> ManagedMember:
        user = self._get_user(user_id)
        memberships = self.membership_repository.list_for_user(user_id)
        return self._managed_members([user], memberships)[0]

    def create_member(
        self,
        data: AccessMemberCreate,
        *,
        actor: ActorContext | None = None,
        request_id: str | None = None,
    ) -> ManagedMember:
        if self.user_repository.get_by_login_name(data.login_name) is not None:
            raise HumanLoginNameConflictError()
        self._require_enabled_team(data.membership.team_id)

        user = User(
            display_name=data.display_name,
            login_name=data.login_name,
            password_hash=self.password_service.hash_password(
                data.password.get_secret_value(),
            ),
            enabled=True,
        )
        self.user_repository.add(user)
        try:
            self.session.flush()
            membership = TeamMembership(
                team_id=data.membership.team_id,
                user_id=user.user_id,
                role_code=data.membership.role_code,
                data_scope=data.membership.data_scope.value,
                enabled=data.membership.enabled,
            )
            self.membership_repository.add(membership)
            self.session.flush()
            self._replace_module_codes(
                membership.membership_id,
                data.membership.module_codes,
            )
            self._record_audit(
                actor=actor,
                request_id=request_id,
                action=AuditAction.CREATE_MEMBER,
                target_type=AuditTargetType.USER,
                target_id=user.user_id,
                details={
                    "membership_id": str(membership.membership_id),
                    "membership_team_id": str(membership.team_id),
                },
            )
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise HumanLoginNameConflictError() from error
        return self.get_member(user.user_id)

    def update_member(
        self,
        user_id: UUID,
        data: AccessMemberUpdate,
        *,
        actor: ActorContext | None = None,
        request_id: str | None = None,
    ) -> ManagedMember:
        user = self._get_user(user_id)
        changes: dict[str, dict[str, bool]] = {}
        if user.enabled != data.enabled:
            changes["enabled"] = {"from": user.enabled, "to": data.enabled}
        if data.enabled is False and user.enabled:
            if self.management_repository.user_has_active_access_administrator_membership(
                user_id,
            ) and (
                self.management_repository.count_active_access_administrators(
                    excluding_user_id=user_id,
                )
                == 0
            ):
                raise LastAccessAdministratorRequiredError()
            self.human_session_repository.revoke_all_for_user(
                user_id,
                revoked_at=datetime.now(UTC),
            )
        user.enabled = data.enabled
        if changes:
            self._record_audit(
                actor=actor,
                request_id=request_id,
                action=AuditAction.UPDATE_MEMBER,
                target_type=AuditTargetType.USER,
                target_id=user.user_id,
                details={"changes": changes},
            )
        self.session.commit()
        return self.get_member(user_id)

    def reset_member_password(
        self,
        user_id: UUID,
        *,
        password: str,
        actor: ActorContext | None = None,
        request_id: str | None = None,
    ) -> ManagedMember:
        user = self._get_user(user_id)
        if user.login_name is None:
            raise AccessMemberCredentialNotConfiguredError()
        user.password_hash = self.password_service.hash_password(password)
        self.human_session_repository.revoke_all_for_user(
            user_id,
            revoked_at=datetime.now(UTC),
        )
        self._record_audit(
            actor=actor,
            request_id=request_id,
            action=AuditAction.RESET_MEMBER_PASSWORD,
            target_type=AuditTargetType.USER,
            target_id=user.user_id,
        )
        self.session.commit()
        return self.get_member(user_id)

    def create_membership(
        self,
        user_id: UUID,
        data: AccessMembershipCreate,
        *,
        actor: ActorContext | None = None,
        request_id: str | None = None,
    ) -> ManagedMember:
        user = self._get_user(user_id)
        if not user.enabled:
            raise HumanUserDisabledError()
        self._require_enabled_team(data.team_id)
        if (
            self.membership_repository.get_for_user_and_team(
                user_id=user_id,
                team_id=data.team_id,
            )
            is not None
        ):
            raise TeamMembershipConflictError()
        membership = TeamMembership(
            team_id=data.team_id,
            user_id=user_id,
            role_code=data.role_code,
            data_scope=data.data_scope.value,
            enabled=data.enabled,
        )
        self.membership_repository.add(membership)
        try:
            self.session.flush()
            self._replace_module_codes(membership.membership_id, data.module_codes)
            self._record_audit(
                actor=actor,
                request_id=request_id,
                action=AuditAction.CREATE_MEMBERSHIP,
                target_type=AuditTargetType.MEMBERSHIP,
                target_id=membership.membership_id,
                details={
                    "user_id": str(membership.user_id),
                    "membership_team_id": str(membership.team_id),
                },
            )
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise TeamMembershipConflictError() from error
        return self.get_member(user_id)

    def update_membership(
        self,
        membership_id: UUID,
        data: AccessMembershipUpdate,
        *,
        actor: ActorContext | None = None,
        request_id: str | None = None,
    ) -> ManagedMember:
        membership = self.membership_repository.get(membership_id)
        if membership is None:
            raise TeamMembershipNotFoundError()
        next_role_code = data.role_code or membership.role_code
        next_enabled = (
            data.enabled if "enabled" in data.model_fields_set else membership.enabled
        )
        removes_last_administrator = (
            self.management_repository.membership_is_active_access_administrator(
                membership_id,
            )
            and (
                next_role_code != ACCESS_ADMIN_ROLE_CODE
                or not next_enabled
            )
        )
        if removes_last_administrator and (
            self.management_repository.count_active_access_administrators(
                excluding_membership_id=membership_id,
            )
            == 0
        ):
            raise LastAccessAdministratorRequiredError()

        changes: dict[str, dict[str, object]] = {}
        for field_name in ("role_code", "data_scope", "enabled"):
            if field_name not in data.model_fields_set:
                continue
            value = getattr(data, field_name)
            next_value = value.value if field_name == "data_scope" else value
            previous_value = getattr(membership, field_name)
            if previous_value != next_value:
                changes[field_name] = {
                    "from": previous_value,
                    "to": next_value,
                }
            setattr(membership, field_name, next_value)
        if "module_codes" in data.model_fields_set:
            current_codes = set(
                self.module_access_repository.list_codes_for_memberships(
                    [membership_id],
                ).get(membership_id, []),
            )
            next_codes = {
                module_code.value for module_code in (data.module_codes or [])
            }
            if current_codes != next_codes:
                changes["module_codes"] = {
                    "added": sorted(next_codes - current_codes),
                    "removed": sorted(current_codes - next_codes),
                }
            self._replace_module_codes(membership_id, data.module_codes or [])
        if changes:
            self._record_audit(
                actor=actor,
                request_id=request_id,
                action=AuditAction.UPDATE_MEMBERSHIP,
                target_type=AuditTargetType.MEMBERSHIP,
                target_id=membership.membership_id,
                details={"changes": changes},
            )
        self.session.commit()
        return self.get_member(membership.user_id)

    def list_teams(self) -> list[Team]:
        return self.team_repository.list()

    def create_team(
        self,
        data: TeamCreate,
        *,
        actor: ActorContext | None = None,
        request_id: str | None = None,
    ) -> Team:
        team = Team(**data.model_dump())
        self.team_repository.add(team)
        self.session.flush()
        self._record_audit(
            actor=actor,
            request_id=request_id,
            action=AuditAction.CREATE_TEAM,
            target_type=AuditTargetType.TEAM,
            target_id=team.team_id,
        )
        self.session.commit()
        self.session.refresh(team)
        return team

    def update_team(
        self,
        team_id: UUID,
        data: TeamUpdate,
        *,
        actor: ActorContext | None = None,
        request_id: str | None = None,
    ) -> Team:
        team = self.team_repository.get(team_id)
        if team is None:
            raise TeamNotFoundError()
        if data.enabled is False and team.enabled:
            if self.management_repository.team_has_active_access_administrator_membership(
                team_id,
            ) and (
                self.management_repository.count_active_access_administrators(
                    excluding_team_id=team_id,
                )
                == 0
            ):
                raise LastAccessAdministratorRequiredError()
        changes: dict[str, dict[str, object]] = {}
        for field_name, value in data.model_dump(exclude_unset=True).items():
            previous_value = getattr(team, field_name)
            if previous_value != value:
                changes[field_name] = {"from": previous_value, "to": value}
            setattr(team, field_name, value)
        if changes:
            self._record_audit(
                actor=actor,
                request_id=request_id,
                action=AuditAction.UPDATE_TEAM,
                target_type=AuditTargetType.TEAM,
                target_id=team.team_id,
                details={"changes": changes},
            )
        self.session.commit()
        self.session.refresh(team)
        return team

    def grant_access_administrator(self, membership_id: UUID) -> None:
        membership = self.membership_repository.get(membership_id)
        if membership is None:
            raise TeamMembershipNotFoundError()
        user = self._get_user(membership.user_id)
        team = self.team_repository.get(membership.team_id)
        if not user.enabled or team is None or not team.enabled or not membership.enabled:
            raise AccessAdministratorMembershipUnavailableError()
        membership.role_code = ACCESS_ADMIN_ROLE_CODE
        self.session.commit()

    def _managed_members(
        self,
        users: list[User],
        membership_pairs: list[tuple[TeamMembership, Team]],
    ) -> list[ManagedMember]:
        membership_ids = [membership.membership_id for membership, _ in membership_pairs]
        codes_by_membership = self.module_access_repository.list_codes_for_memberships(
            membership_ids,
        )
        memberships_by_user: dict[UUID, list[ManagedMembership]] = {}
        for membership, team in membership_pairs:
            memberships_by_user.setdefault(membership.user_id, []).append(
                ManagedMembership(
                    membership_id=membership.membership_id,
                    team_id=team.team_id,
                    team_name=team.name,
                    team_enabled=team.enabled,
                    role_code=membership.role_code,
                    data_scope=ActorContextService._validated_scope(
                        membership.data_scope,
                    ),
                    enabled=membership.enabled,
                    module_codes=tuple(
                        codes_by_membership.get(membership.membership_id, []),
                    ),
                ),
            )
        return [
            ManagedMember(
                user_id=user.user_id,
                display_name=user.display_name,
                login_name=user.login_name,
                enabled=user.enabled,
                memberships=tuple(memberships_by_user.get(user.user_id, [])),
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in users
        ]

    def _get_user(self, user_id: UUID) -> User:
        user = self.user_repository.get(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    def _require_enabled_team(self, team_id: UUID) -> Team:
        team = self.team_repository.get(team_id)
        if team is None:
            raise TeamNotFoundError()
        if not team.enabled:
            raise TeamDisabledError()
        return team

    def _replace_module_codes(
        self,
        membership_id: UUID,
        module_codes: list[ModuleCode],
    ) -> None:
        self.module_access_repository.replace_codes(
            membership_id,
            [module_code.value for module_code in module_codes],
        )

    def _record_audit(
        self,
        *,
        actor: ActorContext | None,
        request_id: str | None,
        action: AuditAction,
        target_type: AuditTargetType,
        target_id: UUID,
        details: dict[str, Any] | None = None,
    ) -> None:
        if actor is None or request_id is None:
            return
        self.audit_log_service.record_access_management_action(
            request_id=request_id,
            actor=actor,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
