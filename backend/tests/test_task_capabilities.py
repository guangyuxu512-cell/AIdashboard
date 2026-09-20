from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.devices.models import Device
from app.modules.tasks.enums import TaskSkillId
from app.modules.tasks.exceptions import (
    TaskApplicationNotAvailableError,
    TaskDeviceDisabledError,
    TaskProviderLoginRequiredError,
    TaskProviderNotReadyError,
    TaskProviderVersionUnsupportedError,
    TaskInputInvalidError,
    TaskSkillNotAvailableError,
    TaskSkillSchemaUnavailableError,
    TaskWorkerOfflineError,
    TaskTargetDeviceInvalidError,
    TaskShopDeviceBindingInvalidError,
    TaskShopInvalidError,
)
from app.modules.credentials.exceptions import CredentialNotFoundError
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.modules.automation_apps.service import ParameterPresetSnapshot
from app.modules.workers.models import DeviceProviderInventory, DeviceSkillCapability
from tests.support import AllowExecutionResources, FakeSession


ACTOR = ActorContext(
    user_id=uuid4(),
    user_display_name="任务能力测试人员",
    team_id=uuid4(),
    membership_id=uuid4(),
    role_code="member",
    data_scope=DataScope.TEAM,
)


class FakeTaskCapabilityRepository:
    def __init__(
        self,
        device: Device,
        capabilities: list[DeviceSkillCapability],
        inventory_payload: dict[str, object] | None = None,
        runtime_status: str = "online",
    ) -> None:
        self.device = device
        self.capabilities = {
            capability.skill_id: capability for capability in capabilities
        }
        self.inventory = (
            DeviceProviderInventory(
                device_id=device.device_id,
                provider_code="yingdao",
                available=bool(inventory_payload and inventory_payload.get("available")),
                provider_version=(
                    str(inventory_payload.get("provider_version"))
                    if inventory_payload and inventory_payload.get("provider_version")
                    else None
                ),
                account_display=None,
                account_type=None,
                enterprise_account=None,
                last_discovered_at=datetime.now(UTC),
                inventory_payload=inventory_payload,
            )
            if inventory_payload is not None
            else None
        )
        self.tasks: list[object] = []
        self.runtime_status = runtime_status

    def get_task_target_device(
        self,
        device_id: object,
        *,
        team_id: object | None = None,
    ) -> Device | None:
        if (
            device_id == self.device.device_id
            and self.device.deleted_at is None
            and (
                self.device.team_id is None
                or team_id == self.device.team_id
            )
        ):
            return self.device
        return None

    def get_skill_capability(
        self,
        device_id: object,
        skill_id: str,
    ) -> DeviceSkillCapability | None:
        return (
            self.capabilities.get(skill_id)
            if device_id == self.device.device_id
            else None
        )

    def get_device_runtime(self, device_id: object) -> object | None:
        if device_id != self.device.device_id:
            return None
        return SimpleNamespace(connection_status=self.runtime_status)

    def get_provider_inventory(
        self,
        device_id: object,
        provider_code: str,
    ) -> DeviceProviderInventory | None:
        if device_id == self.device.device_id and provider_code == "yingdao":
            return self.inventory
        return None

    def add(self, task: object) -> None:
        self.tasks.append(task)


class EmptyApplicationConfigRepository:
    def get(self, provider_code: str, app_id: str) -> None:
        del provider_code, app_id
        return None


def capability(
    device: Device,
    skill_id: str,
    *,
    runtime: str = "python",
    provider: str | None = None,
    classification: str = "internal",
    input_schema: dict[str, object] | None = None,
) -> DeviceSkillCapability:
    return DeviceSkillCapability(
        device_id=device.device_id,
        skill_id=skill_id,
        display_name=skill_id,
        runtime=runtime,
        provider_code=provider,
        skill_version="1",
        classification=classification,
        input_schema=input_schema,
    )


def ready_inventory(*, include_app: bool = True) -> dict[str, object]:
    return {
        "provider": "yingdao",
        "available": True,
        # Intentionally legacy: the status field was absent in existing rows.
        "provider_version": "6.3.6",
        "execution_available": True,
        "execution_version": "6.3.6",
        "logged_in": True,
        "account_display": "GY00999",
        "account_type": "PersonalBasic",
        "enterprise_account": False,
        "user_id": "906515367141965826",
        "applications": (
            [
                {
                    "app_id": "safe-app",
                    "app_name": "Safe App",
                    "version_id": "1",
                    "updated_at": None,
                    "app_type": None,
                    "group_id": None,
                },
            ]
            if include_app
            else []
        ),
        "discovered_at": datetime.now(UTC).isoformat(),
    }


def service_for(
    device: Device,
    capabilities: list[DeviceSkillCapability],
    inventory: dict[str, object] | None = None,
    *,
    runtime_status: str = "online",
    parameter_preset_service: object | None = None,
    shop_repository: object | None = None,
    shop_device_binding_repository: object | None = None,
    credential_service: object | None = None,
) -> TaskService:
    return TaskService(
        FakeSession(),  # type: ignore[arg-type]
        FakeTaskCapabilityRepository(  # type: ignore[arg-type]
            device,
            capabilities,
            inventory,
            runtime_status,
        ),
        application_config_repository=EmptyApplicationConfigRepository(),  # type: ignore[arg-type]
        parameter_preset_service=parameter_preset_service,  # type: ignore[arg-type]
        shop_repository=shop_repository,  # type: ignore[arg-type]
        shop_device_binding_repository=shop_device_binding_repository,  # type: ignore[arg-type]
        credential_service=credential_service,  # type: ignore[arg-type]
        team_authorization_service=AllowExecutionResources(),  # type: ignore[arg-type]
    )


class PresetSnapshotService:
    def __init__(self) -> None:
        self.actor: ActorContext | None = None
        self.shop_ids: list[object] = []

    def snapshot_for_actor(self, **kwargs: object) -> ParameterPresetSnapshot:
        self.actor = kwargs["actor"]  # type: ignore[assignment]
        self.shop_ids = list(kwargs["shop_ids"])  # type: ignore[arg-type]
        return ParameterPresetSnapshot(
            preset_id=kwargs["preset_id"],  # type: ignore[arg-type]
            preset_version=7,
            parameters={
                "格式版本": 1,
                "公共参数": {"标题": "公共标题"},
                "店铺参数": {
                    str(shop_id): {"标题": "店铺标题"}
                    for shop_id in self.shop_ids
                },
            },
        )


class SelectedShopRepository:
    def __init__(self, shop_id: object) -> None:
        self.shop_id = shop_id

    def list_by_ids(self, shop_ids: list[object]) -> list[object]:
        return [
            SimpleNamespace(shop_id=shop_id, enabled=True)
            for shop_id in shop_ids
            if shop_id == self.shop_id
        ]


class SelectedBindingRepository:
    def __init__(self, shop_id: object) -> None:
        self.shop_id = shop_id

    def list_enabled_shop_ids_for_device(
        self,
        device_id: object,
        shop_ids: list[object],
    ) -> set[object]:
        del device_id
        return {shop_id for shop_id in shop_ids if shop_id == self.shop_id}


class ReadyCredentialService:
    def ensure_task_accounts_available(self, shop_ids: list[object]) -> None:
        assert shop_ids


class UnavailableCredentialService:
    def ensure_task_accounts_available(self, shop_ids: list[object]) -> None:
        raise CredentialNotFoundError(details={"shop_ids": [str(shop_id) for shop_id in shop_ids]})


class NotCalledPresetSnapshotService:
    def __init__(self) -> None:
        self.called = False

    def snapshot_for_actor(self, **kwargs: object) -> ParameterPresetSnapshot:
        del kwargs
        self.called = True
        raise AssertionError("preset resolution must follow shop execution eligibility")


def test_system_skill_requires_device_capability_and_disabled_is_distinct() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    with pytest.raises(TaskSkillNotAvailableError):
        service_for(device, []).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "hello"},
            ),
            ACTOR,
        )

    device.enabled = False
    with pytest.raises(TaskDeviceDisabledError):
        service_for(device, [capability(device, "system.echo")]).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "hello"},
            ),
            ACTOR,
        )


def test_offline_device_cannot_create_an_immediate_task() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    with pytest.raises(TaskWorkerOfflineError):
        service_for(
            device,
            [capability(device, "system.echo")],
            runtime_status="offline",
        ).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "hello"},
            ),
            ACTOR,
        )


def test_offline_device_can_prepare_and_create_a_scheduled_task() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    service = service_for(
        device,
        [capability(device, "system.echo")],
        runtime_status="offline",
    )
    request = TaskCreate(
        target_device_id=device.device_id,
        skill_id=TaskSkillId.SYSTEM_ECHO,
        input={"message": "scheduled"},
    )

    prepared = service.prepare_scheduled_task(request, team_id=ACTOR.team_id)
    task = service.create_for_schedule(
        request,
        team_id=ACTOR.team_id,
        created_by_user_id=ACTOR.user_id,
    )

    assert prepared.execution_display_name == "system.echo"
    assert task.status == "pending"
    assert task.input_json == {"message": "scheduled"}

def test_yingdao_app_without_a_parameter_schema_keeps_empty_params() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    task = service_for(
        device,
        [capability(device, "yingdao.app.run", runtime="rpa", provider="yingdao")],
        ready_inventory(),
    ).create(
        TaskCreate(
            target_device_id=device.device_id,
            skill_id=TaskSkillId.YINGDAO_APP_RUN,
            input={"app_id": "safe-app", "params": {}},
        ),
        ACTOR,
    )
    assert task.skill_id == "yingdao.app.run"
    assert task.execution_display_name == "Safe App"
    # A missing application config means the app has no declared input schema.
    # It must not inherit values from an unrelated legacy application template.
    assert task.input_json == {"app_id": "safe-app", "params": {}}


def test_parameter_preset_cannot_be_silently_ignored_by_another_skill() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)

    with pytest.raises(TaskInputInvalidError):
        service_for(
            device,
            [capability(device, TaskSkillId.SYSTEM_ECHO)],
        ).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "safe"},
                parameter_preset_id=uuid4(),
            ),
            ACTOR,
        )


def test_task_rejects_a_target_device_outside_the_actor_team() -> None:
    device = Device(
        device_id=uuid4(),
        team_id=uuid4(),
        display_name="其他团队设备",
        enabled=True,
    )
    with pytest.raises(TaskTargetDeviceInvalidError):
        service_for(device, [capability(device, TaskSkillId.SYSTEM_ECHO)]).create(
            TaskCreate(
                target_device_id=device.device_id,
                skill_id=TaskSkillId.SYSTEM_ECHO,
                input={"message": "safe"},
            ),
            ACTOR,
        )


class EmptyBindingRepository:
    def list_enabled_shop_ids_for_device(
        self,
        device_id: object,
        shop_ids: list[object],
    ) -> set[object]:
        del device_id, shop_ids
        return set()


@pytest.mark.parametrize(
    ("scenario", "error"),
    [
        ("missing", TaskShopInvalidError),
        ("unbound", TaskShopDeviceBindingInvalidError),
        ("credential_unavailable", CredentialNotFoundError),
    ],
)
def test_preset_task_checks_selected_shop_execution_eligibility_before_resolution(
    scenario: str,
    error: type[Exception],
) -> None:
    """A preset cannot turn a missing/bad Shop into a runnable Task."""

    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    shop_id = uuid4()
    preset_service = NotCalledPresetSnapshotService()
    shop_repository = (
        SelectedShopRepository(uuid4())
        if scenario == "missing"
        else SelectedShopRepository(shop_id)
    )
    binding_repository = (
        EmptyBindingRepository()
        if scenario == "unbound"
        else SelectedBindingRepository(shop_id)
    )
    credential_service = (
        UnavailableCredentialService()
        if scenario == "credential_unavailable"
        else ReadyCredentialService()
    )

    with pytest.raises(error):
        service_for(
            device,
            [capability(device, "yingdao.app.run", runtime="rpa", provider="yingdao")],
            ready_inventory(),
            parameter_preset_service=preset_service,
            shop_repository=shop_repository,
            shop_device_binding_repository=binding_repository,
            credential_service=credential_service,
        ).create(
            TaskCreate(
                target_device_id=device.device_id,
                shop_ids=[shop_id],
                skill_id=TaskSkillId.YINGDAO_APP_RUN,
                input={"app_id": "safe-app", "params": {}},
                parameter_preset_id=uuid4(),
            ),
            ACTOR,
        )
    assert not preset_service.called


def test_yingdao_preset_is_materialized_by_task_service_after_shop_checks() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    shop_id = uuid4()
    preset_service = PresetSnapshotService()

    task = service_for(
        device,
        [capability(device, "yingdao.app.run", runtime="rpa", provider="yingdao")],
        ready_inventory(),
        parameter_preset_service=preset_service,
        shop_repository=SelectedShopRepository(shop_id),
        shop_device_binding_repository=SelectedBindingRepository(shop_id),
        credential_service=ReadyCredentialService(),
    ).create(
        TaskCreate(
            target_device_id=device.device_id,
            shop_ids=[shop_id],
            skill_id=TaskSkillId.YINGDAO_APP_RUN,
            input={"app_id": "safe-app", "params": {}},
            parameter_preset_id=uuid4(),
        ),
        ACTOR,
    )

    assert preset_service.actor is ACTOR
    assert preset_service.shop_ids == [shop_id]
    assert task.input_json == {
        "app_id": "safe-app",
        "params": {
            "格式版本": 1,
            "公共参数": {"标题": "公共标题"},
            "店铺参数": {str(shop_id): {"标题": "店铺标题"}},
        },
    }
    assert task.parameter_preset_version == 7


def test_yingdao_guard_returns_specific_provider_and_application_errors() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    skill = capability(
        device,
        "yingdao.app.run",
        runtime="rpa",
        provider="yingdao",
    )
    request = TaskCreate(
        target_device_id=device.device_id,
        skill_id=TaskSkillId.YINGDAO_APP_RUN,
        input={"app_id": "safe-app", "params": {}},
    )

    with pytest.raises(TaskProviderNotReadyError):
        service_for(device, [skill]).create(request, ACTOR)

    login = ready_inventory()
    login.update(
        status="need_login",
        available=False,
        execution_available=False,
        execution_version=None,
        logged_in=False,
        user_id=None,
    )
    with pytest.raises(TaskProviderLoginRequiredError):
        service_for(device, [skill], login).create(request, ACTOR)

    unsupported = ready_inventory()
    unsupported.update(
        status="version_unsupported",
        available=False,
        provider_version="6.3.9",
        execution_available=False,
        execution_version=None,
    )
    with pytest.raises(TaskProviderVersionUnsupportedError):
        service_for(device, [skill], unsupported).create(request, ACTOR)

    with pytest.raises(TaskApplicationNotAvailableError):
        service_for(device, [skill], ready_inventory(include_app=False)).create(
            request,
            ACTOR,
        )


def test_discovery_skill_does_not_require_ready_provider() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    task = service_for(
        device,
        [
            capability(
                device,
                "yingdao.discover",
                runtime="discovery",
                provider="yingdao",
            ),
        ],
    ).create(
        TaskCreate(
            target_device_id=device.device_id,
            skill_id=TaskSkillId.YINGDAO_DISCOVER,
            input={},
        ),
        ACTOR,
    )
    assert task.skill_id == "yingdao.discover"


def test_business_skill_uses_current_device_schema_and_applies_defaults() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    skill = capability(
        device,
        "refund.sync",
        classification="business",
        input_schema={
            "additionalProperties": False,
            "properties": {
                "keyword": {"title": "关键词", "type": "string"},
                "limit": {"default": 10, "title": "数量", "type": "integer"},
                "ratio": {"default": 0.5, "title": "比例", "type": "number"},
                "dry_run": {
                    "default": True,
                    "title": "仅验证",
                    "type": "boolean",
                },
                "mode": {
                    "default": "safe",
                    "enum": ["safe", "fast"],
                    "title": "模式",
                    "type": "string",
                },
            },
            "required": ["keyword"],
            "title": "RefundSyncInput",
            "type": "object",
        },
    )

    task = service_for(device, [skill]).create(
        TaskCreate(
            target_device_id=device.device_id,
            skill_id="refund.sync",
            input={"keyword": "退款"},
        ),
        ACTOR,
    )

    assert task.execution_display_name == "refund.sync"
    assert task.input_json == {
        "keyword": "退款",
        "limit": 10,
        "ratio": 0.5,
        "dry_run": True,
        "mode": "safe",
    }


def test_business_skill_rejects_invalid_input_and_unusable_schema() -> None:
    device = Device(device_id=uuid4(), display_name="PC-11", enabled=True)
    schema = {
        "additionalProperties": False,
        "properties": {
            "keyword": {"title": "关键词", "type": "string"},
        },
        "required": ["keyword"],
        "title": "RefundSyncInput",
        "type": "object",
    }
    request = TaskCreate(
        target_device_id=device.device_id,
        skill_id="refund.sync",
        input={},
    )

    with pytest.raises(TaskInputInvalidError):
        service_for(
            device,
            [
                capability(
                    device,
                    "refund.sync",
                    classification="business",
                    input_schema=schema,
                ),
            ],
        ).create(request, ACTOR)

    with pytest.raises(TaskSkillSchemaUnavailableError):
        service_for(
            device,
            [capability(device, "refund.sync", classification="business")],
        ).create(request, ACTOR)

    with pytest.raises(TaskSkillSchemaUnavailableError):
        service_for(
            device,
            [
                capability(
                    device,
                    "refund.sync",
                    classification="business",
                    input_schema={
                        "additionalProperties": False,
                        "properties": {
                            "items": {"title": "项目", "type": "array"},
                        },
                        "required": [],
                        "title": "UnsupportedInput",
                        "type": "object",
                    },
                ),
            ],
        ).create(request, ACTOR)
