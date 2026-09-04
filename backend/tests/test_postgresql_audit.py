from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership
from app.modules.access.module_access import ModuleCode
from app.modules.access.schemas import (
    AccessMemberMembershipCreate,
    AccessMemberCreate,
)
from app.modules.access.service import AccessManagementService
from app.modules.audit.enums import AuditAction
from app.modules.audit.models import AuditLog
from app.modules.human_auth.exceptions import HumanLoginNameConflictError
from app.modules.human_auth.passwords import PasswordService
from app.modules.users.models import User


pytestmark = pytest.mark.integration

FEATURE_DATABASE = "control_center_feat_audit"
TEST_PASSWORD = "audit-integration-password"


def _require_feature_database() -> None:
    database_url = get_settings().database_url
    if database_url is None:
        pytest.skip("Audit integration test requires BACKEND_DATABASE_URL")
    url = make_url(str(database_url))
    if not url.drivername.startswith("postgresql"):
        pytest.fail("Audit integration test requires PostgreSQL")
    if url.database != FEATURE_DATABASE:
        pytest.fail(
            "Audit integration test only runs against "
            f"the dedicated {FEATURE_DATABASE} database",
        )


def _create_actor(
    session: Session,
    *,
    suffix: str,
) -> tuple[ActorContext, UUID, UUID]:
    user = User(
        display_name="审计集成管理员",
        login_name=f"audit-integration-{suffix}",
        password_hash=PasswordService().hash_password(TEST_PASSWORD),
        enabled=True,
    )
    team = Team(name=f"审计集成团队-{suffix}")
    session.add_all([user, team])
    session.flush()
    membership = TeamMembership(
        membership_id=uuid4(),
        user_id=user.user_id,
        team_id=team.team_id,
        role_code="access_admin",
        data_scope=DataScope.ALL.value,
        enabled=True,
    )
    session.add(membership)
    session.commit()
    return (
        ActorContext(
            user_id=user.user_id,
            user_display_name=user.display_name,
            team_id=team.team_id,
            membership_id=membership.membership_id,
            role_code=membership.role_code,
            data_scope=DataScope.ALL,
        ),
        user.user_id,
        team.team_id,
    )


def _cleanup(
    session: Session,
    *,
    user_ids: list[UUID],
    team_ids: list[UUID],
) -> None:
    membership_ids = list(
        session.scalars(
            select(TeamMembership.membership_id).where(
                TeamMembership.user_id.in_(user_ids),
            ),
        ),
    )
    session.execute(
        delete(AuditLog).where(AuditLog.actor_user_id.in_(user_ids)),
    )
    if membership_ids:
        session.execute(
            delete(MembershipModuleAccess).where(
                MembershipModuleAccess.membership_id.in_(membership_ids),
            ),
        )
    session.execute(
        delete(TeamMembership).where(TeamMembership.user_id.in_(user_ids)),
    )
    session.execute(delete(User).where(User.user_id.in_(user_ids)))
    session.execute(delete(Team).where(Team.team_id.in_(team_ids)))
    session.commit()


def test_access_management_audit_is_atomic_and_minimal() -> None:
    _require_feature_database()
    engine = get_database_engine()
    suffix = str(uuid4())
    created_user_id: UUID | None = None
    actor_user_id: UUID | None = None
    team_id: UUID | None = None
    created_team_id: UUID | None = None

    with Session(engine, expire_on_commit=False) as session:
        try:
            actor, actor_user_id, team_id = _create_actor(session, suffix=suffix)
            service = AccessManagementService(session, PasswordService())
            request_id = f"audit-integration-{suffix}"
            created = service.create_member(
                AccessMemberCreate(
                    display_name="审计新增员工",
                    login_name=f"audit-member-{suffix}",
                    password=TEST_PASSWORD,
                    membership=AccessMemberMembershipCreate(
                        team_id=team_id,
                        role_code="member",
                        data_scope=DataScope.TEAM,
                        module_codes=[ModuleCode.ASSET],
                    ),
                ),
                actor=actor,
                request_id=request_id,
            )
            created_user_id = created.user_id

            audit_log = session.scalar(
                select(AuditLog).where(AuditLog.request_id == request_id),
            )
            assert audit_log is not None
            assert audit_log.action == AuditAction.CREATE_MEMBER.value
            assert audit_log.actor_user_id == actor.user_id
            assert audit_log.target_id == created.user_id
            assert TEST_PASSWORD not in repr(audit_log.details)

            team_request_id = f"audit-integration-team-{suffix}"
            created_team = service.create_team(
                TeamCreate(name=f"审计新增团队-{suffix}"),
                actor=actor,
                request_id=team_request_id,
            )
            created_team_id = created_team.team_id
            team_audit_log = session.scalar(
                select(AuditLog).where(AuditLog.request_id == team_request_id),
            )
            assert team_audit_log is not None
            assert team_audit_log.action == AuditAction.CREATE_TEAM.value
            assert team_audit_log.details == {}

            password_request_id = f"audit-integration-password-{suffix}"
            service.reset_member_password(
                created.user_id,
                password="audit-integration-new-password",
                actor=actor,
                request_id=password_request_id,
            )
            password_audit_log = session.scalar(
                select(AuditLog).where(AuditLog.request_id == password_request_id),
            )
            assert password_audit_log is not None
            assert password_audit_log.action == AuditAction.RESET_MEMBER_PASSWORD.value
            assert password_audit_log.details == {}

            audit_count = session.scalar(select(func.count()).select_from(AuditLog))
            service.list_members(offset=0, limit=20, search=None)
            assert session.scalar(select(func.count()).select_from(AuditLog)) == audit_count

            with pytest.raises(HumanLoginNameConflictError):
                service.create_member(
                    AccessMemberCreate(
                        display_name="重复员工",
                        login_name=f"audit-member-{suffix}",
                        password=TEST_PASSWORD,
                        membership=AccessMemberMembershipCreate(
                            team_id=team_id,
                            role_code="member",
                            data_scope=DataScope.TEAM,
                            module_codes=[ModuleCode.ASSET],
                        ),
                    ),
                    actor=actor,
                    request_id=f"audit-integration-failed-{suffix}",
                )
            assert session.scalar(select(func.count()).select_from(AuditLog)) == audit_count
        finally:
            if actor_user_id is not None and team_id is not None:
                _cleanup(
                    session,
                    user_ids=[
                        actor_user_id,
                        *([] if created_user_id is None else [created_user_id]),
                    ],
                    team_ids=[
                        team_id,
                        *([] if created_team_id is None else [created_team_id]),
                    ],
                )
