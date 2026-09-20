from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_super_account
from app.modules.access.enums import DataScope
from app.modules.automation_apps.api import (
    get_device_authorized_actor as get_automation_device_authorized_actor,
)
from app.modules.automation_apps.api import (
    get_catalog_service as get_automation_catalog_service,
)
from app.modules.automation_apps.api import get_service as get_automation_service
from app.modules.automation_apps.schemas import (
    AutomationApplicationConfigRead,
    AutomationApplicationConfigUpsert,
    AutomationParameterPresetCopy,
    AutomationParameterPresetCreate,
    AutomationParameterPresetRead,
    AutomationParameterPresetUpdate,
    YingdaoApplicationOptionRead,
)
from app.modules.automation_apps.exceptions import AutomationParameterPresetInUseError
from app.modules.automation_apps.presets_api import (
    get_device_authorized_actor as get_parameter_preset_authorized_actor,
)
from app.modules.automation_apps.presets_api import (
    get_service as get_parameter_preset_service,
)
from app.shared.pagination import Page, PaginationParams
from app.modules.devices.api import (
    get_device_authorized_actor,
    get_device_service,
    get_worker_service,
)
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.shops.api import (
    get_shop_authorized_actor,
    get_shop_platform_service,
    get_shop_service,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.schedules.api import (
    get_schedule_authorized_actor,
    get_schedule_service,
)
from app.modules.schedules.exceptions import ScheduleNotFoundError
from app.modules.schedules.enums import ScheduleExecutionType
from app.modules.schedules.schemas import (
    ScheduleCreate,
    ScheduleListItemRead,
    ScheduleRead,
    ScheduleRunRead,
)
from app.modules.tasks.api import get_task_authorized_actor, get_task_service
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.schemas import (
    TaskEventListRead,
    TaskEventPurgeRead,
    TaskListItemRead,
)
from app.platforms.schemas import PlatformShopIdentityRead
from app.shared.pagination import Page
from app.modules.users.api import get_user_service
from app.modules.users.models import User
from app.modules.workers.enums import WorkerConnectionStatus
from app.modules.workers.schemas import (
    BusinessSkillCatalogItemRead,
    DeviceRuntimeRead,
)


SHOP_ID = uuid4()
DEVICE_ID = uuid4()
USER_ID = uuid4()
SCHEDULE_ID = uuid4()
SCHEDULE_RUN_ID = uuid4()
SCHEDULE_TASK_ID = uuid4()
TEAM_ID = uuid4()
MEMBERSHIP_ID = uuid4()
API_ACTOR = ActorContext(
    user_id=USER_ID,
    user_display_name="API 用户",
    team_id=TEAM_ID,
    membership_id=MEMBERSHIP_ID,
    role_code="member",
    data_scope=DataScope.TEAM,
    is_super_account=True,
)


def stamp(entity: object) -> object:
    now = datetime.now(UTC)
    entity.created_at = now  # type: ignore[attr-defined]
    entity.updated_at = now  # type: ignore[attr-defined]
    return entity


class ApiShopService:
    last_list_filters: dict[str, object] | None = None

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        device_id: UUID | None = None,
        enabled: bool | None = None,
        owner_user_id: UUID | None = None,
        platform: str | None = None,
        name_query: str | None = None,
    ) -> tuple[list[Shop], int, dict[UUID, ShopSessionStatus]]:
        del actor
        type(self).last_list_filters = {
            "device_id": device_id,
            "enabled": enabled,
            "owner_user_id": owner_user_id,
            "platform": platform,
            "name_query": name_query,
        }
        return (
            [self.get(SHOP_ID)][offset : offset + limit],
            1,
            {SHOP_ID: ShopSessionStatus.VALID},
        )

    def get(self, *args: object) -> Shop:
        shop_id = args[-1]
        if shop_id != SHOP_ID:
            raise ShopNotFoundError()
        return stamp(
            Shop(
                shop_id=SHOP_ID,
                display_name="API 店铺",
                platform=ShopPlatform.DOUYIN,
                enabled=True,
                owner_user_id=USER_ID,
                note=None,
            ),
        )  # type: ignore[return-value]
    def create(self, actor: ActorContext, data: object) -> Shop:
        del actor, data
        return self.get(SHOP_ID)

    def update(self, actor: ActorContext, shop_id: UUID, data: object) -> Shop:
        del actor, data
        return self.get(shop_id)

    def remove(self, actor: ActorContext, shop_id: UUID) -> None:
        del actor
        self.get(shop_id)

    def list_bindings(self, actor: ActorContext, shop_id: UUID) -> list[ShopDeviceBinding]:
        del actor
        self.get(shop_id)
        return [self._binding()]

    def create_binding(
        self,
        actor: ActorContext,
        shop_id: UUID,
        data: object,
    ) -> ShopDeviceBinding:
        del actor, data
        self.get(shop_id)
        return self._binding()

    def update_binding(
        self,
        actor: ActorContext,
        shop_id: UUID,
        device_id: UUID,
        data: object,
    ) -> ShopDeviceBinding:
        del actor, data
        self.get(shop_id)
        return self._binding(device_id)

    @staticmethod
    def _binding(device_id: UUID = DEVICE_ID) -> ShopDeviceBinding:
        return stamp(
            ShopDeviceBinding(
                shop_id=SHOP_ID,
                device_id=device_id,
                enabled=True,
            ),
        )  # type: ignore[return-value]


class ApiShopPlatformService:
    def fetch_identity(self, shop_id: UUID) -> PlatformShopIdentityRead:
        if shop_id != SHOP_ID:
            raise ShopNotFoundError()
        return PlatformShopIdentityRead(
            shop_id=shop_id,
            platform=ShopPlatform.DOUYIN,
            platform_shop_id="platform-shop-1",
            shop_display_name="API 店铺",
            session_status=ShopSessionStatus.VALID,
        )


class ApiDeviceService:
    last_search: str | None = None

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[Device], int]:
        type(self).last_search = search
        return [self.get(actor, DEVICE_ID)][offset : offset + limit], 1

    def get(self, actor: ActorContext, device_id: UUID) -> Device:
        del actor
        if device_id != DEVICE_ID:
            raise DeviceNotFoundError()
        return stamp(
            Device(
                device_id=DEVICE_ID,
                display_name="API 设备",
                enabled=True,
                location="杭州",
                note=None,
            ),
        )  # type: ignore[return-value]

    def get_for_write(self, actor: ActorContext, device_id: UUID) -> Device:
        return self.get(actor, device_id)

    def create(self, actor: ActorContext, data: object) -> Device:
        del data
        return self.get(actor, DEVICE_ID)

    def update(self, actor: ActorContext, device_id: UUID, data: object) -> Device:
        del data
        return self.get(actor, device_id)

    def remove(self, actor: ActorContext, device_id: UUID) -> None:
        self.get(actor, device_id)


class ApiWorkerService:
    def get_runtime_reads(
        self,
        device_ids: list[UUID],
    ) -> dict[UUID, DeviceRuntimeRead]:
        now = datetime.now(UTC)
        return {
            device_id: DeviceRuntimeRead(
                device_id=device_id,
                worker_version="0.1.0",
                connection_status=WorkerConnectionStatus.OFFLINE,
                last_seen_at=now,
                started_at=now,
                updated_at=now,
            )
            for device_id in device_ids
        }

    def get_business_skill_catalog(
        self,
        device_id: UUID,
    ) -> list[BusinessSkillCatalogItemRead]:
        now = datetime.now(UTC)
        return [
            BusinessSkillCatalogItemRead(
                device_id=device_id,
                skill_id="catalog.fixture.run",
                display_name="目录测试能力",
                runtime="python",
                provider=None,
                version="1.0.0",
                classification="business",
                input_schema={
                    "type": "object",
                    "properties": {"keyword": {"type": "string"}},
                    "required": ["keyword"],
                    "additionalProperties": False,
                },
                availability="available",
                unavailable_reason=None,
                updated_at=now,
            ),
        ]


class ApiAutomationApplicationConfigService:
    last_data: AutomationApplicationConfigUpsert | None = None

    def upsert(
        self,
        provider_code: str,
        app_id: str,
        data: AutomationApplicationConfigUpsert,
    ) -> AutomationApplicationConfigRead:
        type(self).last_data = data
        now = datetime.now(UTC)
        return AutomationApplicationConfigRead(
            config_id=uuid4(),
            provider_code=provider_code,
            app_id=app_id,
            schema_source="manual",
            input_schema=data.input_schema,
            default_values={
                field.name: field.default_value
                for field in data.input_schema.fields
                if field.default_value is not None
            },
            version=1,
            created_at=now,
            updated_at=now,
        )


class ApiAutomationApplicationCatalogService:
    def list_yingdao_application_options(
        self,
        *,
        actor: ActorContext,
        device_id: UUID | None = None,
    ) -> list[YingdaoApplicationOptionRead]:
        assert actor == API_ACTOR
        type(self).last_device_id = device_id
        return [
            YingdaoApplicationOptionRead(
                app_id="preset-api-app",
                app_name="参数预设测试应用",
            ),
        ]


class ApiAutomationParameterPresetService:
    preset_id = uuid4()
    timestamp = datetime.now(UTC)
    last_create: AutomationParameterPresetCreate | None = None
    remove_schedule_references: tuple[tuple[UUID, str], ...] = ()

    @classmethod
    def read(cls, *, app_id: str, name: str) -> AutomationParameterPresetRead:
        now = cls.timestamp
        return AutomationParameterPresetRead(
            preset_id=cls.preset_id,
            team_id=TEAM_ID,
            created_by_user_id=USER_ID,
            app_id=app_id,
            name=name,
            input_schema={
                "fields": [
                    {
                        "name": "商品列表",
                        "label": "商品列表",
                        "type": "text",
                        "required": False,
                        "default_value": None,
                        "options": [],
                    },
                    {
                        "name": "数量",
                        "label": "数量",
                        "type": "number",
                        "required": False,
                        "default_value": 0,
                        "options": [],
                    },
                    {
                        "name": "启用",
                        "label": "启用",
                        "type": "boolean",
                        "required": False,
                        "default_value": False,
                        "options": [],
                    },
                ],
            },
            common_parameters={"商品列表": "", "数量": 0, "启用": False},
            shop_overrides={SHOP_ID: {"数量": 0, "启用": False}},
            version=1,
            created_at=now,
            updated_at=now,
        )

    def list(
        self,
        *,
        actor: ActorContext,
        app_id: str,
    ) -> list[AutomationParameterPresetRead]:
        del actor
        return [self.read(app_id=app_id, name="默认预设")]

    def list_all(
        self,
        *,
        actor: ActorContext,
        device_id: UUID | None = None,
        app_id: str | None = None,
        name_query: str | None = None,
        pagination: PaginationParams | None,
    ) -> Page[AutomationParameterPresetRead] | list[AutomationParameterPresetRead]:
        assert actor == API_ACTOR
        type(self).last_device_id = device_id
        app = app_id or "preset-api-app"
        name = "日常采集" if name_query else "默认预设"
        if pagination is None:
            return [self.read(app_id=app, name=name)]
        return Page(
            items=[self.read(app_id=app, name=name)],
            total=1,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    def create(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        data: AutomationParameterPresetCreate,
    ) -> AutomationParameterPresetRead:
        del actor
        type(self).last_create = data
        return self.read(app_id=app_id, name=data.name)

    def get(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: UUID,
    ) -> AutomationParameterPresetRead:
        del actor, preset_id
        return self.read(app_id=app_id, name="默认预设")

    def update(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: UUID,
        data: AutomationParameterPresetUpdate,
    ) -> AutomationParameterPresetRead:
        del actor, preset_id
        return self.read(app_id=app_id, name=data.name or "默认预设")

    def copy(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: UUID,
        data: AutomationParameterPresetCopy,
    ) -> AutomationParameterPresetRead:
        del actor, preset_id
        return self.read(app_id=app_id, name=data.name)

    def remove(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: UUID,
    ) -> None:
        assert actor == API_ACTOR
        assert app_id == "preset-api-app"
        assert preset_id == self.preset_id
        if type(self).remove_schedule_references:
            raise AutomationParameterPresetInUseError(
                type(self).remove_schedule_references,
            )


class ApiUserService:
    def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        return [self.get(USER_ID)][offset : offset + limit], 1

    def get(self, user_id: UUID) -> User:
        return stamp(
            User(user_id=user_id, display_name="API 用户", enabled=True),
        )  # type: ignore[return-value]

    def create(self, data: object) -> User:
        return self.get(USER_ID)

    def update(self, user_id: UUID, data: object) -> User:
        return self.get(user_id)


class ApiTaskService:
    last_list_arguments: dict[str, object] = {}

    def list_management_tasks(self, **kwargs: object) -> Page[TaskListItemRead]:
        type(self).last_list_arguments = kwargs
        now = datetime.now(UTC)
        return Page(
            items=[
                TaskListItemRead(
                    task_id=uuid4(),
                    target_device_id=DEVICE_ID,
                    device_display_name="API 设备",
                    skill_id="system.sleep",
                    skill_display_name="系统等待",
                    execution_display_name="安全等待",
                    status=TaskStatus.RUNNING,
                    progress={"current": 3, "total": 10},
                    current_message="正在处理第 3 项",
                    started_at=now,
                    finished_at=None,
                    created_at=now,
                ),
            ],
            total=1,
            page=int(kwargs["page"]),
            page_size=int(kwargs["page_size"]),
        )

    def purge_expired_events_for_actor(
        self,
        actor: ActorContext,
    ) -> TaskEventPurgeRead:
        del actor
        now = datetime.now(UTC)
        return TaskEventPurgeRead(
            cutoff=now,
            tasks_purged=2,
            events_deleted=15,
        )

    def list_events(
        self,
        actor: ActorContext,
        task_id: UUID,
        **kwargs: object,
    ) -> TaskEventListRead:
        del actor
        return TaskEventListRead(
            task_id=task_id,
            after_seq=kwargs["after_seq"],
            before_seq=kwargs["before_seq"],
            next_after_seq=int(kwargs["after_seq"] or 0),
            next_before_seq=None,
            has_more_before=False,
            items=[],
        )


class ApiScheduleService:
    last_create_data: ScheduleCreate | None = None
    last_list_kwargs: dict[str, object] | None = None

    @staticmethod
    def _read() -> ScheduleRead:
        now = datetime.now(UTC)
        return ScheduleRead(
            schedule_id=SCHEDULE_ID,
            name="API 每日计划",
            enabled=True,
            target_device_id=DEVICE_ID,
            shop_ids=[SHOP_ID],
            device_display_name="API 设备",
            execution_type="yingdao_application",
            skill_id="yingdao.app.run",
            execution_display_name="API 影刀应用",
            schedule_type="daily",
            local_time=time(9, 30),
            timezone="Asia/Shanghai",
            local_date=None,
            weekdays=[],
            next_run_at=now,
            latest_run=None,
            created_at=now,
            updated_at=now,
            application_id="api-yingdao-app",
            parameters={"keyword": "safe"},
        )

    def create(self, data: ScheduleCreate, actor: ActorContext) -> ScheduleRead:
        del actor
        type(self).last_create_data = data
        if data.execution_type == "business_skill":
            return self._read().model_copy(
                update={
                    "execution_type": ScheduleExecutionType.BUSINESS_SKILL,
                    "application_id": None,
                    "skill_id": data.skill_id,
                    "execution_display_name": "目录测试能力",
                    "parameters": data.parameters,
                },
            )
        return self._read()

    def list_management(self, **kwargs: object) -> Page[ScheduleListItemRead]:
        type(self).last_list_kwargs = dict(kwargs)
        detail = self._read()
        item = ScheduleListItemRead.model_validate(
            detail.model_dump(exclude={"application_id", "parameters"}),
        )
        return Page(
            items=[item],
            total=1,
            page=int(kwargs["page"]),
            page_size=int(kwargs["page_size"]),
        )

    def get(self, actor: ActorContext, schedule_id: UUID) -> ScheduleRead:
        del actor
        if schedule_id != SCHEDULE_ID:
            raise ScheduleNotFoundError()
        return self._read()

    def update(
        self,
        schedule_id: UUID,
        data: object,
        actor: ActorContext,
    ) -> ScheduleRead:
        del data
        return self.get(actor, schedule_id)

    def archive(self, schedule_id: UUID, actor: ActorContext) -> None:
        self.get(actor, schedule_id)

    def list_runs(
        self,
        schedule_id: UUID,
        actor: ActorContext,
        **kwargs: object,
    ) -> Page[ScheduleRunRead]:
        self.get(actor, schedule_id)
        now = datetime.now(UTC)
        return Page(
            items=[
                ScheduleRunRead(
                    run_id=SCHEDULE_RUN_ID,
                    schedule_id=schedule_id,
                    scheduled_for=now,
                    task_id=SCHEDULE_TASK_ID,
                    task_status="success",
                    trigger_result="task_created",
                    trigger_error_code=None,
                    trigger_error_message=None,
                    created_at=now,
                ),
            ],
            total=1,
            page=int(kwargs["page"]),
            page_size=int(kwargs["page_size"]),
        )

def request(method: str, path: str, **kwargs: object) -> Response:
    application = create_app()
    application.dependency_overrides[get_shop_service] = ApiShopService
    application.dependency_overrides[get_shop_platform_service] = (
        ApiShopPlatformService
    )
    application.dependency_overrides[get_device_service] = ApiDeviceService
    application.dependency_overrides[get_worker_service] = ApiWorkerService
    application.dependency_overrides[get_user_service] = ApiUserService
    application.dependency_overrides[get_task_service] = ApiTaskService
    application.dependency_overrides[get_schedule_service] = ApiScheduleService
    application.dependency_overrides[
        get_automation_service
    ] = ApiAutomationApplicationConfigService
    application.dependency_overrides[
        get_automation_catalog_service
    ] = ApiAutomationApplicationCatalogService
    application.dependency_overrides[
        get_parameter_preset_service
    ] = ApiAutomationParameterPresetService
    application.dependency_overrides[get_device_authorized_actor] = lambda: API_ACTOR
    application.dependency_overrides[get_task_authorized_actor] = lambda: API_ACTOR
    application.dependency_overrides[get_schedule_authorized_actor] = lambda: API_ACTOR
    application.dependency_overrides[get_shop_authorized_actor] = lambda: API_ACTOR
    application.dependency_overrides[get_super_account] = lambda: API_ACTOR
    application.dependency_overrides[
        get_automation_device_authorized_actor
    ] = lambda: API_ACTOR
    application.dependency_overrides[
        get_parameter_preset_authorized_actor
    ] = lambda: API_ACTOR

    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_shop_device_and_binding_success_paths() -> None:
    shop_response = request(
        "POST",
        "/api/v1/shops",
        json={"display_name": "店铺", "platform": "douyin"},
    )
    device_response = request(
        "POST",
        "/api/v1/devices",
        json={"display_name": "设备", "location": "杭州"},
    )
    list_response = request("GET", "/api/v1/shops?page=1&page_size=20")
    binding_response = request(
        "POST",
        f"/api/v1/shops/{SHOP_ID}/device-bindings",
        json={"device_id": str(DEVICE_ID)},
    )
    identity_response = request(
        "GET",
        f"/api/v1/shops/{SHOP_ID}/platform-identity",
    )

    assert shop_response.status_code == 201
    assert shop_response.json()["shop_id"] == str(SHOP_ID)
    assert device_response.status_code == 201
    assert device_response.json()["device_id"] == str(DEVICE_ID)
    assert list_response.json()["total"] == 1
    assert list_response.json()["page_size"] == 20
    assert list_response.json()["items"][0]["session_status"] == "valid"
    assert binding_response.status_code == 201
    assert binding_response.json()["enabled"] is True
    assert "binding_role" not in binding_response.json()
    assert identity_response.status_code == 200
    assert identity_response.json()["shop_display_name"] == "API 店铺"
    assert identity_response.json()["session_status"] == "valid"

    remove_response = request("DELETE", f"/api/v1/shops/{SHOP_ID}")
    assert remove_response.status_code == 204


def test_offline_device_is_a_successful_list_item() -> None:
    response = request("GET", "/api/v1/devices?page=1&page_size=20")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    item = response.json()["items"][0]
    assert item["device_id"] == str(DEVICE_ID)
    assert item["enabled"] is True
    assert item["worker_runtime"]["connection_status"] == "offline"
    assert item["worker_runtime"]["last_seen_at"] is not None


def test_shop_and_device_list_forward_server_search_filters() -> None:
    owner_id = uuid4()
    shop_response = request(
        "GET",
        "/api/v1/shops?page=2&page_size=10"
        f"&owner_user_id={owner_id}&platform=douyin&q=%E6%AD%A3%E5%BC%8F&enabled=true",
    )
    device_response = request(
        "GET",
        "/api/v1/devices?page=1&page_size=20&q=%E5%BD%B1%E5%88%80",
    )

    assert shop_response.status_code == 200
    assert ApiShopService.last_list_filters == {
        "device_id": None,
        "enabled": True,
        "owner_user_id": owner_id,
        "platform": "douyin",
        "name_query": "正式",
    }
    assert device_response.status_code == 200
    assert ApiDeviceService.last_search == "影刀"


def test_device_business_skill_catalog_contract() -> None:
    response = request("GET", f"/api/v1/devices/{DEVICE_ID}/business-skills")

    assert response.status_code == 200
    item = response.json()[0]
    assert item["skill_id"] == "catalog.fixture.run"
    assert item["classification"] == "business"
    assert item["availability"] == "available"
    assert item["input_schema"]["required"] == ["keyword"]


def test_task_center_list_contract() -> None:
    response = request(
        "GET",
        f"/api/v1/tasks?page=1&page_size=20&status=running&device_id={DEVICE_ID}",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["device_display_name"] == "API 设备"
    assert payload["items"][0]["progress"] == {"current": 3, "total": 10}
    assert payload["items"][0]["current_message"] == "正在处理第 3 项"


def test_schedule_management_api_contract() -> None:
    create_response = request(
        "POST",
        "/api/v1/schedules",
        json={
            "name": "API 每日计划",
            "target_device_id": str(DEVICE_ID),
            "shop_ids": [str(SHOP_ID)],
            "application_id": "api-yingdao-app",
            "parameters": {"keyword": "safe"},
            "schedule_type": "daily",
            "local_time": "09:30",
            "timezone": "Asia/Shanghai",
            "enabled": True,
        },
    )
    list_response = request(
        "GET",
        f"/api/v1/schedules?page=1&page_size=20&device_id={DEVICE_ID}",
    )
    detail_response = request("GET", f"/api/v1/schedules/{SCHEDULE_ID}")
    update_response = request(
        "PATCH",
        f"/api/v1/schedules/{SCHEDULE_ID}",
        json={"enabled": False},
    )
    runs_response = request(
        "GET",
        f"/api/v1/schedules/{SCHEDULE_ID}/runs?page=1&page_size=20",
    )
    remove_response = request("DELETE", f"/api/v1/schedules/{SCHEDULE_ID}")

    assert create_response.status_code == 201
    assert create_response.json()["skill_id"] == "yingdao.app.run"
    assert create_response.json()["local_date"] is None
    assert create_response.json()["weekdays"] == []
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["device_display_name"] == "API 设备"
    assert detail_response.json()["application_id"] == "api-yingdao-app"
    assert update_response.status_code == 200
    assert runs_response.json()["items"][0]["task_status"] == "success"
    assert remove_response.status_code == 204


def test_schedule_api_accepts_business_skill_target() -> None:
    response = request(
        "POST",
        "/api/v1/schedules",
        json={
            "name": "API 业务 Skill 计划",
            "target_device_id": str(DEVICE_ID),
            "shop_ids": [str(SHOP_ID)],
            "execution_type": "business_skill",
            "skill_id": "catalog.fixture.run",
            "parameters": {"keyword": "safe"},
            "schedule_type": "daily",
            "local_time": "09:30",
            "timezone": "Asia/Shanghai",
            "enabled": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["execution_type"] == "business_skill"
    assert response.json()["application_id"] is None
    assert response.json()["skill_id"] == "catalog.fixture.run"
    assert ApiScheduleService.last_create_data is not None
    assert ApiScheduleService.last_create_data.parameters == {"keyword": "safe"}


def test_schedule_api_accepts_once_and_weekly_rules() -> None:
    base = {
        "name": "重复规则计划",
        "target_device_id": str(DEVICE_ID),
        "application_id": "api-yingdao-app",
        "parameters": {},
        "local_time": "09:30",
        "timezone": "Asia/Shanghai",
        "enabled": True,
    }
    once_response = request(
        "POST",
        "/api/v1/schedules",
        json={
            **base,
            "schedule_type": "once",
            "local_date": "2026-08-26",
            "weekdays": [],
        },
    )
    weekly_response = request(
        "POST",
        "/api/v1/schedules",
        json={
            **base,
            "schedule_type": "weekly",
            "local_date": None,
            "weekdays": [1, 3, 5],
        },
    )
    invalid_once = request(
        "POST",
        "/api/v1/schedules",
        json={**base, "schedule_type": "once", "weekdays": []},
    )
    invalid_weekly = request(
        "POST",
        "/api/v1/schedules",
        json={**base, "schedule_type": "weekly", "weekdays": []},
    )

    assert once_response.status_code == 201
    assert weekly_response.status_code == 201
    assert ApiScheduleService.last_create_data is not None
    assert ApiScheduleService.last_create_data.weekdays == [1, 3, 5]
    assert invalid_once.status_code == 422
    assert invalid_weekly.status_code == 422


def test_schedule_api_rejects_cron_and_unknown_timezone() -> None:
    base = {
        "name": "无效计划",
        "target_device_id": str(DEVICE_ID),
        "application_id": "api-yingdao-app",
        "parameters": {},
        "local_time": "09:30",
        "timezone": "Asia/Shanghai",
        "enabled": True,
    }
    cron_response = request(
        "POST",
        "/api/v1/schedules",
        json={**base, "schedule_type": "cron"},
    )
    timezone_response = request(
        "POST",
        "/api/v1/schedules",
        json={**base, "schedule_type": "daily", "timezone": "Mars/Olympus"},
    )

    assert cron_response.status_code == 422
    assert timezone_response.status_code == 422


def test_schedule_api_passes_occurrence_date_and_view_timezone_together() -> None:
    response = request(
        "GET",
        "/api/v1/schedules?page=1&page_size=20"
        "&occurrence_date=2026-08-24&view_timezone=Asia%2FShanghai",
    )
    missing_timezone = request(
        "GET",
        "/api/v1/schedules?page=1&page_size=20&occurrence_date=2026-08-24",
    )

    assert response.status_code == 200
    assert ApiScheduleService.last_list_kwargs is not None
    assert str(ApiScheduleService.last_list_kwargs["occurrence_date"]) == "2026-08-24"
    assert ApiScheduleService.last_list_kwargs["view_timezone"] == "Asia/Shanghai"
    assert missing_timezone.status_code == 422


def test_task_center_accepts_aware_half_open_created_range() -> None:
    response = request(
        "GET",
        "/api/v1/tasks?page=1&page_size=20"
        "&created_from=2026-08-17T00:00:00%2B08:00"
        "&created_to=2026-08-24T00:00:00%2B08:00",
    )

    assert response.status_code == 200
    created_from = ApiTaskService.last_list_arguments["created_from"]
    created_to = ApiTaskService.last_list_arguments["created_to"]
    assert isinstance(created_from, datetime)
    assert isinstance(created_to, datetime)
    assert created_from.isoformat() == "2026-08-17T00:00:00+08:00"
    assert created_to.isoformat() == "2026-08-24T00:00:00+08:00"


def test_task_center_rejects_invalid_or_naive_created_range() -> None:
    reversed_response = request(
        "GET",
        "/api/v1/tasks?created_from=2026-08-24T00:00:00%2B08:00"
        "&created_to=2026-08-17T00:00:00%2B08:00",
    )
    naive_response = request(
        "GET",
        "/api/v1/tasks?created_from=2026-08-17T00:00:00",
    )

    assert reversed_response.status_code == 422
    assert naive_response.status_code == 422


def test_runtime_event_cursor_and_manual_purge_contracts() -> None:
    task_id = uuid4()
    event_response = request(
        "GET",
        f"/api/v1/tasks/{task_id}/events?before_seq=101&limit=50",
    )
    invalid_cursor_response = request(
        "GET",
        f"/api/v1/tasks/{task_id}/events?after_seq=1&before_seq=3",
    )
    oversized_response = request(
        "GET",
        f"/api/v1/tasks/{task_id}/events?limit=201",
    )
    purge_response = request(
        "POST",
        "/api/v1/tasks/runtime-events/purge-expired",
    )

    assert event_response.status_code == 200
    assert event_response.json()["before_seq"] == 101
    assert invalid_cursor_response.status_code == 422
    assert oversized_response.status_code == 422
    assert purge_response.status_code == 200
    assert purge_response.json()["tasks_purged"] == 2
    assert purge_response.json()["events_deleted"] == 15


def test_api_validation_and_business_not_found_error() -> None:
    validation_response = request(
        "POST",
        "/api/v1/shops",
        json={"display_name": "", "platform": "unknown"},
    )
    not_found_response = request("GET", f"/api/v1/devices/{uuid4()}")
    immutable_platform_id_response = request(
        "PATCH",
        f"/api/v1/shops/{SHOP_ID}",
        json={"platform_shop_id": "manually-overwritten"},
    )

    assert validation_response.status_code == 422
    assert validation_response.json()["code"] == "VALIDATION_ERROR"
    assert validation_response.json()["request_id"]
    assert not_found_response.status_code == 404
    assert not_found_response.json()["code"] == "DEVICE_NOT_FOUND"
    assert immutable_platform_id_response.status_code == 422
    assert immutable_platform_id_response.json()["code"] == "VALIDATION_ERROR"


def test_automation_application_config_api_accepts_unicode_name_and_label_fallback() -> None:
    response = request(
        "PUT",
        "/api/v1/automation-app-configs/yingdao/unicode-config-app",
        json={
            "input_schema": {
                "fields": [
                    {
                        "name": "商品列表",
                        "label": "",
                        "type": "text",
                        "required": True,
                        "default_value": '{"page":1}',
                        "options": [],
                    },
                ],
            },
        },
    )

    assert response.status_code == 200
    field = response.json()["input_schema"]["fields"][0]
    assert field["name"] == "商品列表"
    assert field["label"] == "商品列表"
    assert field["default_value"] == '{"page":1}'
    assert isinstance(field["default_value"], str)
    assert ApiAutomationApplicationConfigService.last_data is not None
    assert (
        ApiAutomationApplicationConfigService.last_data.input_schema.fields[0].label
        == "商品列表"
    )


def test_automation_parameter_preset_api_contract() -> None:
    base_path = "/api/v1/automation-app-configs/yingdao/preset-api-app/parameter-presets"

    list_response = request("GET", base_path)
    create_response = request(
        "POST",
        base_path,
        json={
            "name": "店铺覆盖",
            "input_schema": {
                "fields": [
                    {
                        "name": "商品列表",
                        "label": "商品列表",
                        "type": "text",
                        "required": False,
                        "default_value": None,
                        "options": [],
                    },
                    {
                        "name": "数量",
                        "label": "数量",
                        "type": "number",
                        "required": False,
                        "default_value": 0,
                        "options": [],
                    },
                    {
                        "name": "启用",
                        "label": "启用",
                        "type": "boolean",
                        "required": False,
                        "default_value": False,
                        "options": [],
                    },
                ],
            },
            "common_parameters": {"商品列表": "", "数量": 0, "启用": False},
            "shop_overrides": {str(SHOP_ID): {"数量": 0, "启用": False}},
        },
    )
    detail_response = request(
        "GET",
        f"{base_path}/{ApiAutomationParameterPresetService.preset_id}",
    )
    update_response = request(
        "PATCH",
        f"{base_path}/{ApiAutomationParameterPresetService.preset_id}",
        json={"name": "店铺覆盖（已更新）", "expected_version": 1},
    )
    copy_response = request(
        "POST",
        f"{base_path}/{ApiAutomationParameterPresetService.preset_id}/copy",
        json={"name": "店铺覆盖副本"},
    )
    delete_response = request(
        "DELETE",
        f"{base_path}/{ApiAutomationParameterPresetService.preset_id}",
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["team_id"] == str(TEAM_ID)
    assert create_response.status_code == 201
    assert create_response.json()["name"] == "店铺覆盖"
    assert create_response.json()["shop_overrides"][str(SHOP_ID)]["数量"] == 0
    assert create_response.json()["common_parameters"]["启用"] is False
    assert create_response.json()["input_schema"]["fields"][0]["name"] == "商品列表"
    assert ApiAutomationParameterPresetService.last_create is not None
    assert (
        ApiAutomationParameterPresetService.last_create.input_schema
        and ApiAutomationParameterPresetService.last_create.input_schema.fields[0].name
        == "商品列表"
    )
    assert ApiAutomationParameterPresetService.last_create.shop_overrides[SHOP_ID]["数量"] == 0
    assert detail_response.status_code == 200
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "店铺覆盖（已更新）"
    assert copy_response.status_code == 201
    assert copy_response.json()["name"] == "店铺覆盖副本"
    assert delete_response.status_code == 204


def test_automation_parameter_preset_delete_reports_undeleted_schedule_reference() -> None:
    schedule_id = uuid4()
    ApiAutomationParameterPresetService.remove_schedule_references = (
        (schedule_id, "正在使用的计划"),
    )
    try:
        response = request(
            "DELETE",
            "/api/v1/automation-app-configs/yingdao/preset-api-app/parameter-presets/"
            f"{ApiAutomationParameterPresetService.preset_id}",
        )
    finally:
        ApiAutomationParameterPresetService.remove_schedule_references = ()

    assert response.status_code == 409
    assert response.json()["code"] == "AUTOMATION_PARAMETER_PRESET_IN_USE"
    assert response.json()["details"] == {
        "schedules": [
            {"schedule_id": str(schedule_id), "name": "正在使用的计划"},
        ],
    }


def test_automation_parameter_preset_management_catalog_contract() -> None:
    device_id = uuid4()
    applications_response = request(
        "GET",
        "/api/v1/automation-app-configs/yingdao/applications",
        params={"device_id": str(device_id)},
    )
    presets_response = request(
        "GET",
        "/api/v1/automation-parameter-presets",
        params={
            "device_id": str(device_id),
            "app_id": "preset-api-app",
            "q": "日常",
            "page": 1,
        },
    )

    assert applications_response.status_code == 200
    assert ApiAutomationApplicationCatalogService.last_device_id == device_id
    assert ApiAutomationParameterPresetService.last_device_id == device_id
    assert applications_response.json() == [
        {"app_id": "preset-api-app", "app_name": "参数预设测试应用"},
    ]
    assert presets_response.status_code == 200
    assert presets_response.json()["items"][0]["app_id"] == "preset-api-app"
    assert presets_response.json()["items"][0]["name"] == "日常采集"
    assert presets_response.json()["total"] == 1
    assert presets_response.json()["page"] == 1
    assert presets_response.json()["page_size"] == 20


def test_preset_list_legacy_array_and_explicit_pagination_contract() -> None:
    path = "/api/v1/automation-parameter-presets"
    filters = {"app_id": "preset-api-app", "q": "日常"}
    legacy = request("GET", path, params=filters)
    assert legacy.status_code == 200
    assert isinstance(legacy.json(), list)
    for paging in ({"page": 1}, {"page_size": 20}, {"page": 1, "page_size": 20}):
        paged = request("GET", path, params={**filters, **paging})
        assert paged.status_code == 200
        assert paged.json()["items"] == legacy.json()
    for paging in (
        {"page": ""}, {"page_size": ""}, {"page": "invalid"},
        {"page": "0"}, {"page_size": "101"}, {"page_size": "-1"},
    ):
        invalid = request("GET", path, params={**filters, **paging})
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "VALIDATION_ERROR"


def test_preset_list_openapi_describes_both_response_shapes() -> None:
    schema = create_app().openapi()
    response_schema = schema["paths"]["/api/v1/automation-parameter-presets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert any(option.get("type") == "array" for option in response_schema["anyOf"])
    assert any("Page" in option.get("$ref", "") for option in response_schema["anyOf"])


def test_automation_application_config_api_rejects_duplicate_or_invalid_names() -> None:
    duplicate_response = request(
        "PUT",
        "/api/v1/automation-app-configs/yingdao/invalid-config-app",
        json={
            "input_schema": {
                "fields": [
                    {
                        "name": "商品列表",
                        "label": "列表一",
                        "type": "text",
                        "required": False,
                        "default_value": None,
                        "options": [],
                    },
                    {
                        "name": "商品列表",
                        "label": "列表二",
                        "type": "text",
                        "required": False,
                        "default_value": None,
                        "options": [],
                    },
                ],
            },
        },
    )
    invalid_response = request(
        "PUT",
        "/api/v1/automation-app-configs/yingdao/invalid-config-app",
        json={
            "input_schema": {
                "fields": [
                    {
                        "name": "商品 列表",
                        "label": "列表",
                        "type": "text",
                        "required": False,
                        "default_value": None,
                        "options": [],
                    },
                ],
            },
        },
    )

    assert duplicate_response.status_code == 422
    assert duplicate_response.json()["code"] == "VALIDATION_ERROR"
    duplicate_details = duplicate_response.json()["details"]
    assert [detail["loc"] for detail in duplicate_details] == [
        ["body", "input_schema", "fields", 0, "name"],
        ["body", "input_schema", "fields", 1, "name"],
    ]
    assert [detail["msg"] for detail in duplicate_details] == ["参数名不能重复", "参数名不能重复"]
    assert invalid_response.status_code == 422
    assert invalid_response.json()["code"] == "VALIDATION_ERROR"
    assert invalid_response.json()["details"]
