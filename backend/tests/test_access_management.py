from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.main import create_app
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.dependencies import (
    get_actor_context_service,
    get_module_access_service,
)
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import (
    LastSuperAccountRequiredError,
    ModuleAccessDeniedError,
    TeamInUseError,
    TeamResourceAccessDeniedError,
)
from app.modules.access.models import (
    MembershipModuleAccess,
    Team,
    TeamDeviceAccess,
    TeamMembership,
    TeamModuleAccess,
    TeamShopAccess,
)
from app.modules.access.module_access import ModuleCode
from app.modules.access.schemas import (
    AccessMemberCreate,
    AccessMemberTeamUpdate,
    AccessMemberPasswordReset,
    AccessMemberUpdate,
    TeamAuthorizationUpdate,
    TeamCreate,
)
from app.modules.access.service import (
    AccessManagementService,
    ModuleAccessService,
    TeamAuthorizationService,
)
from app.modules.devices.models import Device
from app.modules.human_auth.models import HumanSession
from app.modules.human_auth.passwords import PasswordService
from app.modules.shops.models import Shop
from app.modules.users.models import User


TEST_PASSWORD = "correct-horse-battery"


def test_product_module_authorization_contract_accepts_registered_values_only() -> None:
    payload = TeamAuthorizationUpdate.model_validate(
        {"module_codes": ["product-selection", "product-library"]}
    )
    assert payload.module_codes == [ModuleCode.PRODUCT_SELECTION, ModuleCode.PRODUCT_LIBRARY]
    for values in (["product-center"], ["product-library", "product-library"]):
        with pytest.raises(ValidationError):
            TeamAuthorizationUpdate.model_validate({"module_codes": values})


def test_product_modules_require_explicit_team_grants_and_revocation_takes_effect(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        team = service.create_team(TeamCreate(name="商品占位授权团队"))
        member = service.create_member(create_member_input(team.team_id))
        actor = actor_for(member.user_id, team.team_id, member.memberships[0].membership_id)
        modules = ModuleAccessService(session)
        for code in (ModuleCode.PRODUCT_SELECTION, ModuleCode.PRODUCT_LIBRARY):
            with pytest.raises(ModuleAccessDeniedError):
                modules.require_module_access(actor, code)
        service.update_team_authorization(
            team.team_id,
            TeamAuthorizationUpdate(module_codes=[ModuleCode.PRODUCT_SELECTION]),
        )
        modules.require_module_access(actor, ModuleCode.PRODUCT_SELECTION)
        with pytest.raises(ModuleAccessDeniedError):
            modules.require_module_access(actor, ModuleCode.PRODUCT_LIBRARY)
        service.update_team_authorization(team.team_id, TeamAuthorizationUpdate(module_codes=[]))
        with pytest.raises(ModuleAccessDeniedError):
            modules.require_module_access(actor, ModuleCode.PRODUCT_SELECTION)


class UnassignedActorContextService:
    def resolve(self, **_kwargs: object) -> ActorContext:
        from app.modules.access.exceptions import TeamMembershipRequiredError

        raise TeamMembershipRequiredError()


class UnexpectedModuleAccessService:
    def list_for_actor(self, _actor: ActorContext) -> list[ModuleCode]:
        raise AssertionError("unassigned users must not receive a module lookup")


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
            TeamModuleAccess.__table__,
            Device.__table__,
            Shop.__table__,
            TeamDeviceAccess.__table__,
            TeamShopAccess.__table__,
            HumanSession.__table__,
        ],
    )
    return sessionmaker(bind=engine, expire_on_commit=False), PasswordService()


def create_member_input(team_id: UUID | None, *, login_name: str = "operator") -> AccessMemberCreate:
    return AccessMemberCreate(
        display_name="访问管理测试人员",
        login_name=login_name,
        password=TEST_PASSWORD,
        team_id=team_id,
    )


def actor_for(member_user_id: UUID, team_id: UUID, membership_id: UUID) -> ActorContext:
    return ActorContext(
        user_id=member_user_id,
        user_display_name="测试成员",
        team_id=team_id,
        membership_id=membership_id,
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def test_team_grants_are_shared_by_current_members_and_not_member_rows(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        team = service.create_team(TeamCreate(name="访问管理团队"))
        service.update_team_authorization(
            team.team_id,
            TeamAuthorizationUpdate(
                module_codes=[ModuleCode.ASSET, ModuleCode.SETTINGS],
            ),
        )
        member = service.create_member(create_member_input(team.team_id))

        stored_user = session.get(User, member.user_id)
        assert stored_user is not None
        assert stored_user.password_hash is not None
        assert TEST_PASSWORD not in stored_user.password_hash
        assert password_service.verify_and_update(TEST_PASSWORD, stored_user.password_hash)[0]
        assert member.memberships[0].module_codes == (
            ModuleCode.ASSET.value,
            ModuleCode.SETTINGS.value,
        )

        membership = member.memberships[0]
        module_service = ModuleAccessService(session)
        actor = actor_for(member.user_id, team.team_id, membership.membership_id)
        module_service.require_module_access(actor, ModuleCode.ASSET)
        module_service.require_module_access(actor, ModuleCode.SETTINGS)
        with pytest.raises(ModuleAccessDeniedError):
            module_service.require_module_access(actor, ModuleCode.AI_WORKBENCH)


def test_unassigned_member_keeps_a_valid_session_with_no_module_menu() -> None:
    application = create_app()
    application.dependency_overrides[get_human_principal] = lambda: HumanPrincipal(
        user_id=uuid4(),
        display_name="未分配团队成员",
    )
    application.dependency_overrides[get_actor_context_service] = (
        UnassignedActorContextService
    )
    application.dependency_overrides[get_module_access_service] = (
        UnexpectedModuleAccessService
    )

    async def request() -> tuple[int, dict[str, object]]:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/access-management/me/module-access")
        return response.status_code, response.json()

    status_code, payload = asyncio.run(request())

    assert status_code == 200
    assert payload == {
        "module_codes": [],
        "is_super_account": False,
        "is_access_administrator": False,
    }


def test_resource_grants_are_enforced_and_revocation_takes_effect_immediately(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        management = AccessManagementService(session, password_service)
        team = management.create_team(TeamCreate(name="资源授权团队"))
        device = Device(team_id=team.team_id, display_name="共享执行设备")
        shop = Shop(display_name="共享店铺", platform="douyin")
        session.add_all([device, shop])
        session.flush()
        management.update_team_authorization(
            team.team_id,
            TeamAuthorizationUpdate(
                device_ids=[device.device_id],
                shop_ids=[shop.shop_id],
            ),
        )
        member = management.create_member(create_member_input(team.team_id))
        actor = actor_for(
            member.user_id,
            team.team_id,
            member.memberships[0].membership_id,
        )
        authorization = TeamAuthorizationService(session)
        authorization.require_device_access(actor, device.device_id)
        authorization.require_shop_access(actor, shop.shop_id)

        now = datetime.now(UTC)
        session.add(
            HumanSession(
                user_id=member.user_id,
                token_hash=sha256(b"team-grant-revocation-session").hexdigest(),
                created_at=now,
                expires_at=now + timedelta(hours=1),
            ),
        )
        session.commit()

        management.update_team_authorization(
            team.team_id,
            TeamAuthorizationUpdate(),
        )
        with pytest.raises(TeamResourceAccessDeniedError):
            authorization.require_device_access(actor, device.device_id)
        with pytest.raises(TeamResourceAccessDeniedError):
            authorization.require_shop_access(actor, shop.shop_id)
        stored_session = session.scalar(select(HumanSession))
        assert stored_session is not None
        assert stored_session.revoked_at is not None


def test_move_and_remove_member_revoke_sessions_without_losing_history(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        first = service.create_team(TeamCreate(name="原团队"))
        second = service.create_team(TeamCreate(name="目标团队"))
        member = service.create_member(create_member_input(first.team_id))
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

        moved = service.move_member_to_team(
            member.user_id,
            AccessMemberTeamUpdate(team_id=second.team_id),
        )
        active = [
            item
            for item in moved.memberships
            if item.enabled and item.team_enabled
        ]
        assert [item.team_id for item in active] == [second.team_id]
        assert {item.team_id for item in moved.memberships} == {
            first.team_id,
            second.team_id,
        }
        assert session.scalar(select(HumanSession)).revoked_at is not None  # type: ignore[union-attr]

        removed = service.move_member_to_team(
            member.user_id,
            AccessMemberTeamUpdate(team_id=None),
        )
        assert not [
            item
            for item in removed.memberships
            if item.enabled and item.team_enabled
        ]
        assert len(removed.memberships) == 2


def test_super_account_has_no_membership_and_cannot_be_last_disabled(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        user = User(
            display_name="超级账号",
            login_name="super",
            password_hash=password_service.hash_password(TEST_PASSWORD),
            enabled=True,
            is_super_account=True,
        )
        session.add(user)
        session.commit()

        member = service.get_member(user.user_id)
        assert member.is_super_account is True
        assert member.memberships == ()
        with pytest.raises(LastSuperAccountRequiredError):
            service.update_member(user.user_id, AccessMemberUpdate(enabled=False))

        actor = ActorContext(
            user_id=user.user_id,
            user_display_name=user.display_name,
            team_id=None,
            membership_id=None,
            role_code="super_account",
            data_scope=DataScope.ALL,
            is_super_account=True,
        )
        assert set(ModuleAccessService(session).list_for_actor(actor)) == set(ModuleCode)


def test_empty_team_deletes_but_team_with_history_requires_archive(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    class ManagementRepository:
        def __init__(self, has_references: bool) -> None:
            self.has_references = has_references

        def team_has_references(self, _team_id: UUID) -> bool:
            return self.has_references

        def count_enabled_super_accounts(self, **_kwargs: object) -> int:
            return 1

    factory, password_service = database
    with factory() as session:
        empty_service = AccessManagementService(
            session,
            password_service,
            management_repository=ManagementRepository(False),  # type: ignore[arg-type]
        )
        empty_team = empty_service.create_team(TeamCreate(name="可删除空团队"))
        empty_service.delete_team(empty_team.team_id)
        assert session.get(Team, empty_team.team_id) is None

        history_service = AccessManagementService(
            session,
            password_service,
            management_repository=ManagementRepository(True),  # type: ignore[arg-type]
        )
        retained_team = history_service.create_team(TeamCreate(name="历史数据团队"))
        with pytest.raises(TeamInUseError):
            history_service.delete_team(retained_team.team_id)
        archived = history_service.archive_team(retained_team.team_id)
        assert archived.enabled is False


def test_reset_password_revokes_sessions(
    database: tuple[sessionmaker[Session], PasswordService],
) -> None:
    factory, password_service = database
    with factory() as session:
        service = AccessManagementService(session, password_service)
        member = service.create_member(create_member_input(None))
        now = datetime.now(UTC)
        session.add(
            HumanSession(
                user_id=member.user_id,
                token_hash=sha256(b"password-reset-session").hexdigest(),
                created_at=now,
                expires_at=now + timedelta(hours=1),
            ),
        )
        session.commit()
        service.reset_member_password(
            member.user_id,
            password=AccessMemberPasswordReset(password="new-correct-password").password.get_secret_value(),
        )
        stored_session = session.scalar(select(HumanSession))
        assert stored_session is not None and stored_session.revoked_at is not None
