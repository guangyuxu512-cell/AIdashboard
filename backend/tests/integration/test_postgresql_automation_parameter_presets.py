import asyncio
from datetime import UTC, datetime, time
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import Engine, delete, inspect
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
                            ],
                        },
                        default_values={"数量": 1, "启用": True},
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
                "format_version": 1,
                "common_parameters": {"标题": "公共标题", "数量": 0, "启用": False},
                "shop_parameters": {
                    str(shop_a): {"标题": "公共标题", "数量": 0, "启用": False},
                    str(shop_b): {"标题": "店铺 B 标题", "数量": 0, "启用": False},
                },
            }

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
            presets.update(
                actor=actor,
                app_id=app_id,
                preset_id=preset.preset_id,
                data=AutomationParameterPresetUpdate(
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
            assert scheduled_task.input_json["params"]["shop_parameters"][str(shop_a)]["标题"] == "后续标题"
            assert task.input_json["params"]["shop_parameters"][str(shop_a)]["标题"] == "公共标题"
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
    assert any(
        key["name"] == "fk_schedules_parameter_preset_id_automation_parameter_presets"
        for key in inspector.get_foreign_keys("schedules")
    )
