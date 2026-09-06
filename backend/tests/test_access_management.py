from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import (
    LastAccessAdministratorRequiredError,
    ModuleAccessDeniedError,
)
from app.modules.human_auth.exceptions import HumanLoginNameConflictError
from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership
from app.modules.access.module_access import ModuleCode
from app.modules.access.schemas import (
    AccessMemberCreate,
    AccessMemberMembershipCreate,
    AccessMemberPasswordReset,
    AccessMemberUpdate,
    AccessMembershipUpdate,
    TeamCreate,
)
from app.modules.access.service import AccessManagementService, ModuleAccessService
from app.modules.audit.enums import AuditAction, AuditTargetType
from app.modules.human_auth.models import HumanSession
from app.modules.human_auth.passwords import PasswordService
from app.modules.users.models import User


TEST_PASSWORD = "correct-horse-battery"


@pytest.fixture()
def database() -> tuple[sessionmaker[Session], PasswordService]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Team.__table__,
            TeamMembership.__table__,
            MembershipModuleAccess.__table__,
            HumanSession.__table__,
        ],
    )
    return sessionmaker(bind=engine, expire_on_commit=False), PasswordService()


def create_member_input(
    team_id: UUID,
    *,
    login_name: str = "operator",
    role_code: str = "member",
    module_codes: list[ModuleCode] | None = None,
) -> AccessMemberCreate:
    return AccessMemberCreate(
        display_name="访问管理测试人员",
        login_name=login_name,
        password=TEST_PASSWORD,
        membership=AccessMemberMembershipCreate(
            team_id=team_id,
            role_code=role_code,
            data_scope=DataScope.TEAM,
            module_codes=module_codes or [ModuleCode.ASSET],
        ),
    )


def test_create_member_persists_argon2_and_module_access(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        team = service.create_team(TeamCreate(name="访问管理团队"))

        member = service.create_member(
            create_member_input(
                team.team_id,
                module_codes=[ModuleCode.ASSET, ModuleCode.SETTINGS],
            ),
        )

        stored_user = session.get(User, member.user_id)
        assert stored_user is not None
        assert stored_user.login_name == "operator"
        assert stored_user.password_hash is not None
        assert TEST_PASSWORD not in stored_user.password_hash
        assert password_service.verify_and_update(
            TEST_PASSWORD,
            stored_user.password_hash,
        )[0]
        assert member.login_name == "operator"
        assert member.memberships[0].module_codes == (
            ModuleCode.ASSET.value,
            ModuleCode.SETTINGS.value,
        )


def test_reset_password_and_disable_member_revoke_all_human_sessions(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        team = service.create_team(TeamCreate(name="会话撤销团队"))
        member = service.create_member(create_member_input(team.team_id))
        now = datetime.now(UTC)
        session.add(
            HumanSession(
                user_id=member.user_id,
                token_hash=sha256(b"access-management-session").hexdigest(),
                created_at=now,
                expires_at=now + timedelta(hours=1),
            ),
        )
        session.commit()

        result = service.reset_member_password(
            member.user_id,
            password=AccessMemberPasswordReset(
                password="new-correct-password",
            ).password.get_secret_value(),
        )
        stored_session = session.scalar(select(HumanSession))
        assert result.user_id == member.user_id
        assert stored_session is not None and stored_session.revoked_at is not None

        service.update_member(member.user_id, AccessMemberUpdate(enabled=False))
        stored_user = session.get(User, member.user_id)
        assert stored_user is not None
        assert stored_user.enabled is False


def test_last_active_access_administrator_cannot_be_disabled_or_demoted(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        team = service.create_team(TeamCreate(name="权限管理员团队"))
        member = service.create_member(
            create_member_input(
                team.team_id,
                login_name="access-admin",
                role_code="access_admin",
            ),
        )
        membership_id = member.memberships[0].membership_id

        with pytest.raises(LastAccessAdministratorRequiredError):
            service.update_member(member.user_id, AccessMemberUpdate(enabled=False))
        with pytest.raises(LastAccessAdministratorRequiredError):
            service.update_membership(
                membership_id,
                AccessMembershipUpdate(role_code="member"),
            )


def test_module_access_fails_closed_for_a_membership_without_a_grant(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        team = service.create_team(TeamCreate(name="模块授权团队"))
        member = service.create_member(
            create_member_input(team.team_id, module_codes=[ModuleCode.ASSET]),
        )
        membership = member.memberships[0]
        actor = ActorContext(
            user_id=member.user_id,
            user_display_name=member.display_name,
            team_id=membership.team_id,
            membership_id=membership.membership_id,
            role_code=membership.role_code,
            data_scope=membership.data_scope,
        )
        module_service = ModuleAccessService(session)

        module_service.require_module_access(actor, ModuleCode.ASSET)
        with pytest.raises(ModuleAccessDeniedError):
            module_service.require_module_access(actor, ModuleCode.SETTINGS)

        service.update_membership(
            membership.membership_id,
            AccessMembershipUpdate(module_codes=[ModuleCode.SETTINGS]),
        )
        module_service.require_module_access(actor, ModuleCode.SETTINGS)
        with pytest.raises(ModuleAccessDeniedError):
            module_service.require_module_access(actor, ModuleCode.ASSET)


def test_access_management_records_minimal_audit_data_only_after_success(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    class AuditRecorder:
        def __init__(self) -> None:
            self.records: list[dict[str, object]] = []

        def record_access_management_action(self, **kwargs: object) -> None:
            self.records.append(kwargs)

    factory, password_service = database
    recorder = AuditRecorder()
    with factory() as session:
        service = AccessManagementService(
            session,
            password_service,
            audit_log_service=recorder,  # type: ignore[arg-type]
        )
        team = service.create_team(TeamCreate(name="审计管理团队"))
        administrator = service.create_member(
            create_member_input(
                team.team_id,
                login_name="audit-admin",
                role_code="access_admin",
            ),
        )
        admin_membership = administrator.memberships[0]
        actor = ActorContext(
            user_id=administrator.user_id,
            user_display_name=administrator.display_name,
            team_id=admin_membership.team_id,
            membership_id=admin_membership.membership_id,
            role_code=admin_membership.role_code,
            data_scope=admin_membership.data_scope,
        )

        created = service.create_member(
            create_member_input(team.team_id, login_name="audited-member"),
            actor=actor,
            request_id="request-audit-create-member",
        )

        assert len(recorder.records) == 1
        record = recorder.records[0]
        assert record["request_id"] == "request-audit-create-member"
        assert record["actor"] == actor
        assert record["action"] is AuditAction.CREATE_MEMBER
        assert record["target_type"] is AuditTargetType.USER
        assert record["target_id"] == created.user_id
        assert TEST_PASSWORD not in repr(record["details"])

        with pytest.raises(HumanLoginNameConflictError):
            service.create_member(
                create_member_input(team.team_id, login_name="audited-member"),
                actor=actor,
                request_id="request-audit-failed",
            )
        assert len(recorder.records) == 1
