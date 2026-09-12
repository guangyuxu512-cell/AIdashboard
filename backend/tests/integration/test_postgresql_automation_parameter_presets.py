import asyncio
from datetime import UTC, datetime, time
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete, inspect, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.core.security import SecretCipher
from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.models import MembershipModuleAccess, Team, TeamMembership
from app.modules.access.module_access import ModuleCode
from app.modules.automation_apps.models import (
    AutomationApplicationConfig,
    AutomationParameterPreset,
)
from app.modules.automation_apps.presets_api import (
    get_device_authorized_actor as get_parameter_preset_authorized_actor,
)
from app.modules.automation_apps.exceptions import (
    AutomationParameterPresetInUseError,
    AutomationParameterPresetNotFoundError,
)
from app.modules.automation_apps.schemas import (
    AutomationParameterPresetCreate,
    AutomationParameterPresetUpdate,
)
from app.modules.automation_apps.service import AutomationParameterPresetService
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.credentials.schemas import CredentialCreate
from app.modules.credentials.service import CredentialService
from app.modules.devices.models import Device
from app.modules.schedules.models import Schedule, ScheduleRun, ScheduleShop
from app.modules.schedules.schemas import ScheduleCreate
from app.modules.schedules.service import ScheduleService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.tasks.models import Task, TaskShop
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.users.models import User
from app.modules.workers.models import (
    DeviceProviderInventory,
    DeviceRuntime,
    DeviceSkillCapability,
)
from app.modules.workers.service import WorkerPrincipal
from app.shared.pagination import PaginationParams


pytestmark = pytest.mark.integration


def _actor(team_id: UUID, user_id: UUID, membership_id: UUID) -> ActorContext:
    return ActorContext(
        user_id=user_id,
        user_display_name="Parameter preset integration user",
        team_id=team_id,
        membership_id=membership_id,
        role_code="member",
        data_scope=DataScope.TEAM,
    )


def _inventory(now: datetime) -> dict[str, object]:
    return {
        "provider": "yingdao",
        "available": True,
        "status": "ready",
        "status_reason_code": None,
        "status_reason": None,
        "provider_version": "6.3.6",
        "execution_available": True,
        "execution_version": "6.3.6",
        "execution_unavailable_reason": None,
        "logged_in": True,
        "account_display": "Preset fixture",
        "account_type": "PersonalBasic",
        "enterprise_account": False,
        "user_id": "900000000000000099",
        "applications": [
            {
                "app_id": "preset-safe-app",
                "app_name": "Preset Safe App",
                "version_id": "1",
                "updated_at": None,
                "app_type": None,
                "group_id": None,
            },
        ],
        "discovered_at": now.isoformat(),
    }


def _cleanup(
    engine: Engine,
    *,
    team_id: UUID,
    user_id: UUID,
    membership_id: UUID,
    device_id: UUID,
    shop_ids: set[UUID],
    app_id: str,
) -> None:
    with Session(engine) as session:
        schedule_ids = session.query(Schedule.schedule_id).where(
            Schedule.target_device_id == device_id,
        )
        task_ids = session.query(Task.task_id).where(Task.target_device_id == device_id)
        session.execute(delete(ScheduleRun).where(ScheduleRun.schedule_id.in_(schedule_ids)))
        session.execute(delete(ScheduleShop).where(ScheduleShop.schedule_id.in_(schedule_ids)))
        session.execute(delete(Schedule).where(Schedule.target_device_id == device_id))
        session.execute(delete(TaskShop).where(TaskShop.task_id.in_(task_ids)))
        session.execute(delete(Task).where(Task.target_device_id == device_id))
        session.execute(
            delete(ShopCredentialBinding).where(
                ShopCredentialBinding.shop_id.in_(shop_ids),
            ),
        )
        session.execute(
            delete(PlatformCredential).where(
                PlatformCredential.login_identifier == f"preset-{device_id}",
            ),
        )
        session.execute(delete(ShopDeviceBinding).where(ShopDeviceBinding.shop_id.in_(shop_ids)))
        session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
        session.execute(
            delete(DeviceProviderInventory).where(
                DeviceProviderInventory.device_id == device_id,
            ),
        )
        session.execute(
            delete(DeviceSkillCapability).where(
                DeviceSkillCapability.device_id == device_id,
            ),
        )
        session.execute(delete(DeviceRuntime).where(DeviceRuntime.device_id == device_id))
        session.execute(delete(Device).where(Device.device_id == device_id))
        session.execute(
            delete(AutomationParameterPreset).where(
                AutomationParameterPreset.team_id == team_id,
            ),
        )
        session.execute(
            delete(AutomationApplicationConfig).where(
                AutomationApplicationConfig.provider_code == "yingdao",
                AutomationApplicationConfig.app_id == app_id,
            ),
        )
        session.execute(
            delete(MembershipModuleAccess).where(
                MembershipModuleAccess.membership_id == membership_id,
            ),
        )
        session.execute(
            delete(TeamMembership).where(TeamMembership.membership_id == membership_id),
        )
        session.execute(delete(User).where(User.user_id == user_id))
        session.execute(delete(Team).where(Team.team_id == team_id))
        session.commit()


def test_postgresql_preset_snapshot_and_schedule_use_current_saved_preset(
    postgresql_engine: Engine,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    team_id, user_id, membership_id, device_id = (uuid4() for _ in range(4))
    shop_a, shop_b = uuid4(), uuid4()
    app_id = "preset-safe-app"
    actor = _actor(team_id, user_id, membership_id)
    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            session.add_all(
                [
                    Team(team_id=team_id, name="Preset integration team"),
                    User(user_id=user_id, display_name="Preset integration user"),
                ],
            )
            session.flush()
            session.add(
                TeamMembership(
                    membership_id=membership_id,
                    team_id=team_id,
                    user_id=user_id,
                    role_code="member",
                    data_scope=DataScope.TEAM.value,
                ),
            )
            session.flush()
            session.add(
                MembershipModuleAccess(
                    membership_id=membership_id,
                    module_code=ModuleCode.SHOP.value,
                ),
            )
            session.add_all(
                [
                    Device(
                        device_id=device_id,
                        team_id=team_id,
                        display_name="Preset integration device",
                        enabled=True,
                    ),
                    DeviceRuntime(
                        device_id=device_id,
                        worker_version="0.4.7",
                        last_seen_at=now,
                        started_at=now,
                        connection_status="online",
                    ),
                    DeviceSkillCapability(
                        device_id=device_id,
                        skill_id="yingdao.app.run",
                        display_name="Run Yingdao application",
                        runtime="rpa",
                        provider_code="yingdao",
                        skill_version="1",
                        classification="internal",
                    ),
                    DeviceProviderInventory(
                        device_id=device_id,
                        provider_code="yingdao",
                        available=True,
                        provider_version="6.3.6",
                        account_display="Preset fixture",
                        account_type="PersonalBasic",
                        enterprise_account=False,
                        last_discovered_at=now,
                        inventory_payload=_inventory(now),
                    ),
                    AutomationApplicationConfig(
                        provider_code="yingdao",
                        app_id=app_id,
                        schema_source="manual",
                        input_schema={
                            "fields": [
                                {
                                    "name": "标题",
                                    "label": "标题",
                                    "type": "text",
                                    "required": True,
                                    "default_value": None,
                                    "options": [],
                                },
                                {
                                    "name": "数量",
                                    "label": "数量",
                                    "type": "number",
                                    "required": False,
                                    "default_value": 1,
                                    "options": [],
                                },
                                {
                                    "name": "启用",
                                    "label": "启用",
                                    "type": "boolean",
                                    "required": False,
                                    "default_value": True,
                                    "options": [],
                                },
                                {
                                    "name": "每页数量",
                                    "label": "每页数量",
                                    "type": "number",
                                    "required": False,
                                    "default_value": 20,
                                    "options": [],
                                },
                            ],
                        },
                        default_values={"数量": 1, "启用": True, "每页数量": 20},
                        version=1,
                    ),
                ],
            )
            session.add_all(
                [
                    Shop(
                        shop_id=shop_id,
                        display_name=f"Preset shop {position}",
                        platform=ShopPlatform.DOUYIN,
                        enabled=True,
                    )
                    for position, shop_id in enumerate([shop_a, shop_b], start=1)
                ],
            )
            session.add_all(
                [
                    ShopDeviceBinding(
                        shop_id=shop_id,
                        device_id=device_id,
                        enabled=True,
                    )
                    for shop_id in [shop_a, shop_b]
                ],
            )
            session.commit()

            credential_service = CredentialService(
                session,
                SecretCipher(Fernet.generate_key().decode("ascii")),
            )
            for shop_id in [shop_a, shop_b]:
                credential_service.create(
                    CredentialCreate(
                        shop_id=shop_id,
                        login_identifier=f"preset-{device_id}",
                        secret=SecretStr("fixture-secret"),
                    ),
                )

            presets = AutomationParameterPresetService(session)
            preset = presets.create(
                actor=actor,
                app_id=app_id,
                data=AutomationParameterPresetCreate(
                    name="多店铺发布",
                    common_parameters={"标题": "公共标题", "数量": 0, "启用": False},
                    shop_overrides={shop_b: {"标题": "店铺 B 标题"}},
                ),
            )
            assert preset.team_id == team_id
            assert presets.list(actor=actor, app_id=app_id) == [preset]

            # A second preset uses the same application field catalog, but
            # must never cause its values or unselected schema defaults to
            # appear in A's Task/Schedule/Claim payloads.
            preset_b = presets.create(
                actor=actor,
                app_id=app_id,
                data=AutomationParameterPresetCreate(
                    name="独立预设 B",
                    common_parameters={"标题": "B 标题", "数量": 5},
                ),
            )
            snapshot_b = presets.snapshot_for_actor(
                actor=actor,
                app_id=app_id,
                preset_id=preset_b.preset_id,
                shop_ids=[shop_a],
            )
            assert snapshot_b.parameters["店铺参数"][str(shop_a)] == {
                "标题": "B 标题",
                "数量": 5,
            }

            async def exercise_preset_api() -> None:
                application = create_app()
                application.dependency_overrides[
                    get_parameter_preset_authorized_actor
                ] = lambda: actor
                transport = ASGITransport(app=application)
                base_path = f"/api/v1/automation-app-configs/yingdao/{app_id}/parameter-presets"
                async with AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    create_response = await client.post(
                        base_path,
                        json={
                            "name": "API 保存回读",
                            "common_parameters": {
                                "标题": "API 标题",
                                "数量": 0,
                                "启用": False,
                            },
                            "shop_overrides": {
                                str(shop_b): {"标题": "API 店铺 B 标题"},
                            },
                        },
                    )
                    assert create_response.status_code == 201
                    api_preset = create_response.json()
                    assert api_preset["shop_overrides"][str(shop_b)]["标题"] == "API 店铺 B 标题"
                    read_response = await client.get(
                        f"{base_path}/{api_preset['preset_id']}",
                    )
                    assert read_response.status_code == 200
                    assert read_response.json()["common_parameters"]["数量"] == 0
                    assert read_response.json()["common_parameters"]["启用"] is False

                    management_response = await client.get(
                        "/api/v1/automation-parameter-presets",
                        params={"app_id": app_id, "page": 1, "page_size": 1},
                    )
                    assert management_response.status_code == 200
                    management_page = management_response.json()
                    assert management_page["total"] >= 3
                    assert management_page["page"] == 1
                    assert management_page["page_size"] == 1
                    assert len(management_page["items"]) == 1

            asyncio.run(exercise_preset_api())

            task = TaskService(session, credential_service=credential_service).create(
                TaskCreate(
                    target_device_id=device_id,
                    shop_ids=[shop_a, shop_b],
                    skill_id="yingdao.app.run",
                    input={"app_id": app_id, "params": {}},
                    parameter_preset_id=preset.preset_id,
                ),
                actor,
            )
            assert task.input_json["params"] == {
                "格式版本": 1,
                "公共参数": {"标题": "公共标题", "数量": 0, "启用": False},
                "店铺参数": {
                    str(shop_a): {"标题": "公共标题", "数量": 0, "启用": False},
                    str(shop_b): {"标题": "店铺 B 标题", "数量": 0, "启用": False},
                },
            }
            assert task.parameter_preset_id == preset.preset_id
            assert task.parameter_preset_version == preset.version
            assert "每页数量" not in task.input_json["params"]["公共参数"]
            assert all(
                "每页数量" not in values
                for values in task.input_json["params"]["店铺参数"].values()
            )
            claimed = TaskService(
                session,
                credential_service=credential_service,
            ).claim_with_account(WorkerPrincipal(device_id=device_id), now=now)
            assert claimed is not None
            assert claimed.task.task_id == task.task_id
            assert claimed.task.input_json["params"] == task.input_json["params"]
            assert [account.shop_id for account in claimed.accounts] == [shop_a, shop_b]

            schedule = ScheduleService(
                session,
                task_service=TaskService(
                    session,
                    credential_service=credential_service,
                ),
            ).create(
                ScheduleCreate(
                    name="预设计划",
                    target_device_id=device_id,
                    shop_ids=[shop_a, shop_b],
                    application_id=app_id,
                    parameter_preset_id=preset.preset_id,
                    parameters={},
                    local_time=time(9, 30),
                    timezone="Asia/Shanghai",
                ),
                actor,
                now=now,
            )
            updated_preset = presets.update(
                actor=actor,
                app_id=app_id,
                preset_id=preset.preset_id,
                data=AutomationParameterPresetUpdate(
                    expected_version=preset.version,
                    common_parameters={"标题": "后续标题", "数量": 0, "启用": False},
                ),
            )
            record = session.get(Schedule, schedule.schedule_id)
            assert record is not None
            record.next_run_at = now
            session.commit()

            triggered = ScheduleService(
                session,
                task_service=TaskService(
                    session,
                    credential_service=credential_service,
                ),
            ).trigger_next_due(now=now)
            assert triggered is not None and triggered.task_id is not None
            scheduled_task = session.get(Task, triggered.task_id)
            assert scheduled_task is not None
            assert scheduled_task.input_json["params"]["店铺参数"][str(shop_a)]["标题"] == "后续标题"
            assert task.input_json["params"]["店铺参数"][str(shop_a)]["标题"] == "公共标题"
            assert "每页数量" not in scheduled_task.input_json["params"]["公共参数"]
            assert all(
                "每页数量" not in values
                for values in scheduled_task.input_json["params"]["店铺参数"].values()
            )
            assert scheduled_task.parameter_preset_id == preset.preset_id
            assert scheduled_task.parameter_preset_version == updated_preset.version

            with pytest.raises(AutomationParameterPresetInUseError) as error:
                presets.remove(
                    actor=actor,
                    app_id=app_id,
                    preset_id=preset.preset_id,
                )
            assert error.value.details == {"reference_types": ["task", "schedule"]}
            assert session.get(AutomationParameterPreset, preset.preset_id) is not None
            assert session.get(Task, task.task_id) is not None
            assert session.get(Schedule, schedule.schedule_id) is not None

            removable = presets.create(
                actor=actor,
                app_id=app_id,
                data=AutomationParameterPresetCreate(
                    name="无引用配置",
                    common_parameters={"标题": "可删除", "数量": 0, "启用": False},
                ),
            )
            presets.remove(
                actor=actor,
                app_id=app_id,
                preset_id=removable.preset_id,
            )
            assert session.get(AutomationParameterPreset, removable.preset_id) is None

            # Presets themselves are Team-scoped.  A Shop has no separate Team
            # ownership field in the current model, so this verifies the real
            # authorization boundary instead of claiming one that does not
            # exist: neither immediate Tasks nor Schedules may resolve another
            # Team's preset, even though the target Device and selected Shops
            # are otherwise eligible for this Team.
            foreign_team_id, foreign_user_id = uuid4(), uuid4()
            foreign_preset = AutomationParameterPreset(
                preset_id=uuid4(),
                team_id=foreign_team_id,
                created_by_user_id=foreign_user_id,
                app_id=app_id,
                name="其他团队预设",
                common_parameters={"标题": "不应读取"},
                shop_overrides={},
                version=1,
            )
            session.add_all(
                [
                    Team(team_id=foreign_team_id, name="Foreign preset team"),
                    User(user_id=foreign_user_id, display_name="Foreign preset user"),
                ],
            )
            session.flush()
            session.add(foreign_preset)
            session.commit()

            all_scope_actor = ActorContext(
                user_id=actor.user_id,
                user_display_name=actor.user_display_name,
                team_id=actor.team_id,
                membership_id=actor.membership_id,
                role_code=actor.role_code,
                data_scope=DataScope.ALL,
            )
            management_page = presets.list_all(
                actor=all_scope_actor,
                pagination=PaginationParams(page=1, page_size=100),
            )
            assert management_page.total == 3
            assert all(item.team_id == team_id for item in management_page.items)

            with pytest.raises(AutomationParameterPresetNotFoundError):
                TaskService(session, credential_service=credential_service).create(
                    TaskCreate(
                        target_device_id=device_id,
                        shop_ids=[shop_a],
                        skill_id="yingdao.app.run",
                        input={"app_id": app_id, "params": {}},
                        parameter_preset_id=foreign_preset.preset_id,
                    ),
                    actor,
                )
            with pytest.raises(AutomationParameterPresetNotFoundError):
                ScheduleService(
                    session,
                    task_service=TaskService(
                        session,
                        credential_service=credential_service,
                    ),
                ).create(
                    ScheduleCreate(
                        name="跨团队预设计划",
                        target_device_id=device_id,
                        shop_ids=[shop_a],
                        application_id=app_id,
                        parameter_preset_id=foreign_preset.preset_id,
                        parameters={},
                        local_time=time(10, 30),
                        timezone="Asia/Shanghai",
                    ),
                    actor,
                    now=now,
                )

            session.delete(foreign_preset)
            session.delete(session.get(User, foreign_user_id))
            session.delete(session.get(Team, foreign_team_id))
            session.commit()

            # Changing the global application template after A/B exist must
            # neither add a value to their Task/Schedule snapshots nor make a
            # newly-required template field retroactively invalidate them.
            config = session.scalar(
                select(AutomationApplicationConfig).where(
                    AutomationApplicationConfig.provider_code == "yingdao",
                    AutomationApplicationConfig.app_id == app_id,
                ),
            )
            assert config is not None
            config.input_schema = {
                "fields": [
                    {
                        "name": "模板新增必填",
                        "label": "模板新增必填",
                        "type": "text",
                        "required": True,
                        "default_value": None,
                        "options": [],
                    },
                ],
            }
            config.default_values = {}
            config.version += 1
            session.commit()
            assert "模板新增必填" not in {
                field.name for field in preset.input_schema.fields
            }
            assert "模板新增必填" not in {
                field.name for field in preset_b.input_schema.fields
            }
            assert presets.snapshot_for_actor(
                actor=actor,
                app_id=app_id,
                preset_id=preset.preset_id,
                shop_ids=[shop_a],
            ).parameters["店铺参数"][str(shop_a)] == {
                "标题": "后续标题",
                "数量": 0,
                "启用": False,
            }
    finally:
        _cleanup(
            postgresql_engine,
            team_id=team_id,
            user_id=user_id,
            membership_id=membership_id,
            device_id=device_id,
            shop_ids={shop_a, shop_b},
            app_id=app_id,
        )


def test_postgresql_preset_schema_has_team_scope_and_schedule_reference(
    postgresql_engine: Engine,
) -> None:
    inspector = inspect(postgresql_engine)
    assert "automation_parameter_presets" in inspector.get_table_names()
    assert "uq_automation_preset_team_app_name" in {
        item["name"]
        for item in inspector.get_unique_constraints("automation_parameter_presets")
    }
    checks = {
        item["sqltext"]
        for item in inspector.get_check_constraints("automation_parameter_presets")
    }
    assert any("jsonb_typeof(common_parameters)" in check for check in checks)
    assert any("jsonb_typeof(shop_overrides)" in check for check in checks)
    assert any("jsonb_typeof(input_schema_snapshot)" in check for check in checks)
    assert "input_schema_snapshot" in {
        column["name"]
        for column in inspector.get_columns("automation_parameter_presets")
    }
    assert any(
        key["name"] == "fk_schedules_parameter_preset_id_automation_parameter_presets"
        for key in inspector.get_foreign_keys("schedules")
    )
    assert "parameter_preset_version" in {
        column["name"] for column in inspector.get_columns("tasks")
    }
    assert any(
        key["name"] == "fk_tasks_parameter_preset_id_automation_parameter_presets"
        for key in inspector.get_foreign_keys("tasks")
    )
