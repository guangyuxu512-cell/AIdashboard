from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.modules.access.models import (
    MembershipModuleAccess,
    Team,
    TeamDeviceAccess,
    TeamMembership,
    TeamModuleAccess,
    TeamShopAccess,
)
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

    def list_enabled(self) -> list[Team]:
        return list(
            self.session.scalars(
                select(Team)
                .where(Team.enabled.is_(True))
                .order_by(Team.name.asc(), Team.team_id.asc()),
            ),
        )

    def add(self, team: Team) -> None:
        self.session.add(team)

    def remove(self, team: Team) -> None:
        self.session.delete(team)


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

    def list_active_for_user_for_update(
        self,
        user_id: UUID,
    ) -> list[MembershipWithTeam]:
        statement = (
            select(TeamMembership, Team)
            .join(Team, Team.team_id == TeamMembership.team_id)
            .where(
                TeamMembership.user_id == user_id,
                TeamMembership.enabled.is_(True),
            )
            .order_by(TeamMembership.membership_id.asc())
            .with_for_update()
        )
        return [(row[0], row[1]) for row in self.session.execute(statement)]

    def disable_active_for_user(self, user_id: UUID) -> list[UUID]:
        memberships = self.list_active_for_user_for_update(user_id)
        for membership, _team in memberships:
            membership.enabled = False
        return [membership.membership_id for membership, _team in memberships]

    def disable_active_for_team(self, team_id: UUID) -> list[UUID]:
        memberships = list(
            self.session.scalars(
                select(TeamMembership)
                .where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.enabled.is_(True),
                )
                .with_for_update(),
            ),
        )
        for membership in memberships:
            membership.enabled = False
        return [membership.user_id for membership in memberships]

    def list_active_user_ids_for_team(self, team_id: UUID) -> list[UUID]:
        """Return current members before a Team-wide authorization change.

        The caller uses this narrowly to revoke their Human sessions after a
        grant update, so stale renderer navigation cannot survive a revocation.
        It deliberately does not include historical or disabled memberships.
        """

        return list(
            self.session.scalars(
                select(TeamMembership.user_id)
                .where(
                    TeamMembership.team_id == team_id,
                    TeamMembership.enabled.is_(True),
                )
                .order_by(TeamMembership.user_id.asc()),
            ),
        )

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


class TeamModuleAccessRepository:
    """Current Team-level module grants.

    ``MembershipModuleAccess`` remains readable only as a migration source for
    historical records.  All runtime checks use this repository instead.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_codes(self, team_id: UUID) -> list[str]:
        return list(
            self.session.scalars(
                select(TeamModuleAccess.module_code)
                .where(TeamModuleAccess.team_id == team_id)
                .order_by(TeamModuleAccess.module_code.asc()),
            ),
        )

    def list_codes_for_teams(
        self,
        team_ids: Sequence[UUID],
    ) -> dict[UUID, list[str]]:
        if not team_ids:
            return {}
        rows = self.session.execute(
            select(TeamModuleAccess.team_id, TeamModuleAccess.module_code)
            .where(TeamModuleAccess.team_id.in_(team_ids))
            .order_by(TeamModuleAccess.team_id.asc(), TeamModuleAccess.module_code.asc()),
        )
        result: dict[UUID, list[str]] = {}
        for team_id, module_code in rows:
            result.setdefault(team_id, []).append(module_code)
        return result

    def replace_codes(self, team_id: UUID, module_codes: Sequence[str]) -> None:
        self.session.execute(
            delete(TeamModuleAccess).where(TeamModuleAccess.team_id == team_id),
        )
        self.session.add_all(
            [
                TeamModuleAccess(team_id=team_id, module_code=module_code)
                for module_code in module_codes
            ],
        )

    def has_module_access(self, team_id: UUID, module_code: str) -> bool:
        return (
            self.session.scalar(
                select(TeamModuleAccess.team_id).where(
                    TeamModuleAccess.team_id == team_id,
                    TeamModuleAccess.module_code == module_code,
                ),
            )
            is not None
        )


class TeamResourceAccessRepository:
    """Resource grants maintained centrally by a super account."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_device_ids(self, team_id: UUID) -> list[UUID]:
        return list(
            self.session.scalars(
                select(TeamDeviceAccess.device_id)
                .where(TeamDeviceAccess.team_id == team_id)
                .order_by(TeamDeviceAccess.device_id.asc()),
            ),
        )

    def list_shop_ids(self, team_id: UUID) -> list[UUID]:
        return list(
            self.session.scalars(
                select(TeamShopAccess.shop_id)
                .where(TeamShopAccess.team_id == team_id)
                .order_by(TeamShopAccess.shop_id.asc()),
            ),
        )

    def replace_device_ids(self, team_id: UUID, device_ids: Sequence[UUID]) -> None:
        self.session.execute(
            delete(TeamDeviceAccess).where(TeamDeviceAccess.team_id == team_id),
        )
        self.session.add_all(
            [TeamDeviceAccess(team_id=team_id, device_id=device_id) for device_id in device_ids],
        )

    def replace_shop_ids(self, team_id: UUID, shop_ids: Sequence[UUID]) -> None:
        self.session.execute(
            delete(TeamShopAccess).where(TeamShopAccess.team_id == team_id),
        )
        self.session.add_all(
            [TeamShopAccess(team_id=team_id, shop_id=shop_id) for shop_id in shop_ids],
        )

    def has_device_access(self, team_id: UUID, device_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(TeamDeviceAccess.team_id).where(
                    TeamDeviceAccess.team_id == team_id,
                    TeamDeviceAccess.device_id == device_id,
                ),
            )
            is not None
        )

    def has_shop_access(self, team_id: UUID, shop_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(TeamShopAccess.team_id).where(
                    TeamShopAccess.team_id == team_id,
                    TeamShopAccess.shop_id == shop_id,
                ),
            )
            is not None
        )


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

    def count_enabled_super_accounts(
        self,
        *,
        excluding_user_id: UUID | None = None,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(User)
            .where(User.enabled.is_(True), User.is_super_account.is_(True))
        )
        if excluding_user_id is not None:
            statement = statement.where(User.user_id != excluding_user_id)
        return int(self.session.scalar(statement) or 0)

    def team_has_references(self, team_id: UUID) -> bool:
        """Return whether deleting a Team would orphan durable business data.

        Imports are intentionally local: this repository owns the control
        plane, while each business module continues to own its model.
        """

        from app.modules.ai_workbench.models import (
            GenerationJob,
            ProductMaterialGroup,
            TemplateGroup,
        )
        from app.modules.assets.models import Asset
        from app.modules.automation_apps.models import AutomationParameterPreset
        from app.modules.audit.models import AuditLog
        from app.modules.devices.models import Device
        from app.modules.schedules.models import Schedule
        from app.modules.tasks.models import Task

        model_columns = (
            (TeamMembership, TeamMembership.team_id),
            (TeamModuleAccess, TeamModuleAccess.team_id),
            (TeamDeviceAccess, TeamDeviceAccess.team_id),
            (TeamShopAccess, TeamShopAccess.team_id),
            (Device, Device.team_id),
            (Asset, Asset.team_id),
            (AutomationParameterPreset, AutomationParameterPreset.team_id),
            (Schedule, Schedule.team_id),
            (Task, Task.team_id),
            (TemplateGroup, TemplateGroup.team_id),
            (ProductMaterialGroup, ProductMaterialGroup.team_id),
            (GenerationJob, GenerationJob.team_id),
            (AuditLog, AuditLog.team_id),
        )
        return any(
            self.session.scalar(
                select(model).where(column == team_id).limit(1),
            )
            is not None
            for model, column in model_columns
        )

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
