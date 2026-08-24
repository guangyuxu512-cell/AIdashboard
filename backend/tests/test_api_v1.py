from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient, Response

from app.main import create_app
from app.modules.devices.api import get_device_service, get_worker_service
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.devices.models import Device
from app.modules.shops.api import get_shop_service
from app.modules.shops.api import get_shop_platform_service
from app.modules.shops.enums import BindingRole, ShopPlatform
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.tasks.api import get_task_service
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
from app.modules.workers.schemas import DeviceRuntimeRead


SHOP_ID = uuid4()
DEVICE_ID = uuid4()
USER_ID = uuid4()


def stamp(entity: object) -> object:
    now = datetime.now(UTC)
    entity.created_at = now  # type: ignore[attr-defined]
    entity.updated_at = now  # type: ignore[attr-defined]
    return entity


class ApiShopService:
    def list(
        self,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[Shop], int, dict[UUID, ShopSessionStatus]]:
        return (
            [self.get(SHOP_ID)][offset : offset + limit],
            1,
            {SHOP_ID: ShopSessionStatus.VALID},
        )

    def get(self, shop_id: UUID) -> Shop:
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
    def create(self, data: object) -> Shop:
        return self.get(SHOP_ID)

    def update(self, shop_id: UUID, data: object) -> Shop:
        return self.get(shop_id)

    def remove(self, shop_id: UUID) -> None:
        self.get(shop_id)

    def list_bindings(self, shop_id: UUID) -> list[ShopDeviceBinding]:
        self.get(shop_id)
        return [self._binding()]

    def create_binding(self, shop_id: UUID, data: object) -> ShopDeviceBinding:
        self.get(shop_id)
        return self._binding()

    def update_binding(
        self,
        shop_id: UUID,
        device_id: UUID,
        data: object,
    ) -> ShopDeviceBinding:
        self.get(shop_id)
        return self._binding(device_id)

    @staticmethod
    def _binding(device_id: UUID = DEVICE_ID) -> ShopDeviceBinding:
        return stamp(
            ShopDeviceBinding(
                shop_id=SHOP_ID,
                device_id=device_id,
                binding_role=BindingRole.PRIMARY,
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
    def list(self, *, offset: int, limit: int) -> tuple[list[Device], int]:
        return [self.get(DEVICE_ID)][offset : offset + limit], 1

    def get(self, device_id: UUID) -> Device:
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

    def create(self, data: object) -> Device:
        return self.get(DEVICE_ID)

    def update(self, device_id: UUID, data: object) -> Device:
        return self.get(device_id)


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

    def purge_expired_events(self) -> TaskEventPurgeRead:
        now = datetime.now(UTC)
        return TaskEventPurgeRead(
            cutoff=now,
            tasks_purged=2,
            events_deleted=15,
        )

    def list_events(self, task_id: UUID, **kwargs: object) -> TaskEventListRead:
        return TaskEventListRead(
            task_id=task_id,
            after_seq=kwargs["after_seq"],
            before_seq=kwargs["before_seq"],
            next_after_seq=int(kwargs["after_seq"] or 0),
            next_before_seq=None,
            has_more_before=False,
            items=[],
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
        json={"device_id": str(DEVICE_ID), "binding_role": "primary"},
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
    assert binding_response.json()["binding_role"] == "primary"
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
