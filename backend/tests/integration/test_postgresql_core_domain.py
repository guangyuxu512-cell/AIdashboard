from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, delete, inspect, select, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PostgreSQLUUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.devices.models import Device
from app.modules.devices.repository import DeviceRepository
from app.modules.devices.schemas import DeviceCreate, DeviceUpdate
from app.modules.devices.service import DeviceService
from app.modules.shops.enums import BindingRole, ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.shops.repository import ShopDeviceBindingRepository, ShopRepository
from app.modules.shops.schemas import (
    ShopCreate,
    ShopDeviceBindingCreate,
    ShopDeviceBindingUpdate,
    ShopUpdate,
)
from app.modules.shops.service import ShopService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserUpdate
from app.modules.users.service import UserService


pytestmark = pytest.mark.integration
TEST_PREFIX = "stage-2a1"
EXPECTED_TABLES = {"users", "shops", "devices", "shop_device_bindings"}


def _cleanup(
    engine: Engine,
    *,
    user_ids: set[UUID] | None = None,
    shop_ids: set[UUID] | None = None,
    device_ids: set[UUID] | None = None,
) -> None:
    user_ids = user_ids or set()
    shop_ids = shop_ids or set()
    device_ids = device_ids or set()
    with Session(engine) as session:
        if shop_ids or device_ids:
            predicates = []
            if shop_ids:
                predicates.append(ShopDeviceBinding.shop_id.in_(shop_ids))
            if device_ids:
                predicates.append(ShopDeviceBinding.device_id.in_(device_ids))
            for predicate in predicates:
                session.execute(delete(ShopDeviceBinding).where(predicate))
        if shop_ids:
            session.execute(delete(Shop).where(Shop.shop_id.in_(shop_ids)))
        if device_ids:
            session.execute(delete(Device).where(Device.device_id.in_(device_ids)))
        if user_ids:
            session.execute(delete(User).where(User.user_id.in_(user_ids)))
        session.commit()


def _assert_uuid_and_time(payload: dict[str, object], id_field: str) -> None:
    UUID(str(payload[id_field]))
    for field in ("created_at", "updated_at"):
        parsed = datetime.fromisoformat(str(payload[field]))
        assert parsed.tzinfo is not None


def test_postgresql_connection_and_real_schema(postgresql_engine: Engine) -> None:
    inspector = inspect(postgresql_engine)

    with postgresql_engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        assert connection.scalar(text("SHOW server_version"))
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20260820_0005"
        )

    assert EXPECTED_TABLES <= set(inspector.get_table_names())

    for table_name, id_column in (
        ("users", "user_id"),
        ("shops", "shop_id"),
        ("devices", "device_id"),
    ):
        columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        assert isinstance(columns[id_column]["type"], PostgreSQLUUID)
        assert isinstance(columns["created_at"]["type"], TIMESTAMP)
        assert columns["created_at"]["type"].timezone is True
        assert columns["updated_at"]["type"].timezone is True
        assert inspector.get_pk_constraint(table_name)["constrained_columns"] == [id_column]

    binding_pk = inspector.get_pk_constraint("shop_device_bindings")
    assert binding_pk["constrained_columns"] == ["shop_id", "device_id"]

    shop_foreign_keys = inspector.get_foreign_keys("shops")
    assert any(
        foreign_key["constrained_columns"] == ["owner_user_id"]
        and foreign_key["referred_table"] == "users"
        for foreign_key in shop_foreign_keys
    )
    binding_foreign_keys = inspector.get_foreign_keys("shop_device_bindings")
    assert {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in binding_foreign_keys
    } == {(('shop_id',), 'shops'), (('device_id',), 'devices')}

    indexes = {
        index["name"]: index for index in inspector.get_indexes("shop_device_bindings")
    }
    primary_index = indexes["uq_shop_device_bindings_enabled_primary"]
    assert primary_index["unique"] is True
    assert primary_index["column_names"] == ["shop_id"]
    predicate = str(primary_index.get("dialect_options", {}).get("postgresql_where", ""))
    assert "enabled" in predicate
    assert "binding_role" in predicate


def test_postgresql_enforces_core_constraints(postgresql_engine: Engine) -> None:
    shop_id = uuid4()
    invalid_shop_id = uuid4()
    primary_device_id = uuid4()
    second_primary_device_id = uuid4()
    backup_device_id = uuid4()
    device_ids = {primary_device_id, second_primary_device_id, backup_device_id}

    try:
        with Session(postgresql_engine) as session:
            session.add(
                Shop(
                    shop_id=invalid_shop_id,
                    display_name=f"{TEST_PREFIX}-invalid-owner",
                    platform=ShopPlatform.DOUYIN,
                    owner_user_id=uuid4(),
                ),
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with Session(postgresql_engine) as session:
            session.add(
                ShopDeviceBinding(
                    shop_id=uuid4(),
                    device_id=uuid4(),
                    binding_role=BindingRole.PRIMARY,
                ),
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with Session(postgresql_engine) as session:
            session.add(
                Shop(
                    shop_id=shop_id,
                    display_name=f"{TEST_PREFIX}-constraint-shop",
                    platform=ShopPlatform.PDD,
                ),
            )
            session.add_all(
                [
                    Device(device_id=device_id, display_name=f"{TEST_PREFIX}-{device_id}")
                    for device_id in device_ids
                ],
            )
            session.commit()

        with Session(postgresql_engine) as session:
            session.add(
                ShopDeviceBinding(
                    shop_id=shop_id,
                    device_id=primary_device_id,
                    binding_role=BindingRole.PRIMARY,
                ),
            )
            session.commit()

        with Session(postgresql_engine) as session:
            session.add(
                ShopDeviceBinding(
                    shop_id=shop_id,
                    device_id=second_primary_device_id,
                    binding_role=BindingRole.PRIMARY,
                ),
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with Session(postgresql_engine) as session:
            session.add(
                ShopDeviceBinding(
                    shop_id=shop_id,
                    device_id=primary_device_id,
                    binding_role=BindingRole.BACKUP,
                ),
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        with Session(postgresql_engine) as session:
            backup = ShopDeviceBinding(
                shop_id=shop_id,
                device_id=backup_device_id,
                binding_role=BindingRole.BACKUP,
            )
            session.add(backup)
            session.commit()
            assert session.get(ShopDeviceBinding, (shop_id, backup_device_id)) is not None
    finally:
        _cleanup(postgresql_engine, shop_ids={shop_id, invalid_shop_id}, device_ids=device_ids)


def test_repository_service_crud_and_transactions(postgresql_engine: Engine) -> None:
    user_ids: set[UUID] = set()
    shop_ids: set[UUID] = set()
    device_ids: set[UUID] = set()
    rolled_back_user_id = uuid4()

    try:
        with Session(postgresql_engine, expire_on_commit=False) as session:
            user_service = UserService(session)
            user = user_service.create(
                UserCreate(display_name=f"{TEST_PREFIX}-service-user"),
            )
            user_ids.add(user.user_id)
            assert UserRepository(session).get(user.user_id) is not None
            assert user_service.get(user.user_id).user_id == user.user_id
            assert user_service.list(offset=0, limit=100)[1] >= 1
            assert user_service.update(
                user.user_id,
                UserUpdate(display_name=f"{TEST_PREFIX}-service-user-updated"),
            ).display_name.endswith("updated")

            shop_service = ShopService(session)
            shop = shop_service.create(
                ShopCreate(
                    display_name=f"{TEST_PREFIX}-service-shop",
                    platform=ShopPlatform.DOUYIN,
                    owner_user_id=user.user_id,
                ),
            )
            shop_ids.add(shop.shop_id)
            assert ShopRepository(session).get(shop.shop_id) is not None
            assert shop_service.get(shop.shop_id).shop_id == shop.shop_id
            assert shop_service.list(offset=0, limit=100)[1] >= 1
            assert shop_service.update(
                shop.shop_id,
                ShopUpdate(note=f"{TEST_PREFIX}-updated"),
            ).note == f"{TEST_PREFIX}-updated"

            device_service = DeviceService(session)
            primary = device_service.create(
                DeviceCreate(display_name=f"{TEST_PREFIX}-service-primary"),
            )
            backup = device_service.create(
                DeviceCreate(display_name=f"{TEST_PREFIX}-service-backup"),
            )
            device_ids.update({primary.device_id, backup.device_id})
            assert DeviceRepository(session).get(primary.device_id) is not None
            assert device_service.get(primary.device_id).device_id == primary.device_id
            assert device_service.list(offset=0, limit=100)[1] >= 2
            assert device_service.update(
                primary.device_id,
                DeviceUpdate(location=f"{TEST_PREFIX}-location"),
            ).location == f"{TEST_PREFIX}-location"

            shop_service.create_binding(
                shop.shop_id,
                ShopDeviceBindingCreate(
                    device_id=primary.device_id,
                    binding_role=BindingRole.PRIMARY,
                ),
            )
            shop_service.create_binding(
                shop.shop_id,
                ShopDeviceBindingCreate(
                    device_id=backup.device_id,
                    binding_role=BindingRole.BACKUP,
                ),
            )
            assert len(shop_service.list_bindings(shop.shop_id)) == 2
            assert ShopDeviceBindingRepository(session).get(
                shop.shop_id,
                primary.device_id,
            ) is not None
            assert shop_service.update_binding(
                shop.shop_id,
                primary.device_id,
                ShopDeviceBindingUpdate(enabled=False),
            ).enabled is False
            changed = shop_service.update_binding(
                shop.shop_id,
                backup.device_id,
                ShopDeviceBindingUpdate(binding_role=BindingRole.PRIMARY),
            )
            assert changed.binding_role == BindingRole.PRIMARY

        with Session(postgresql_engine) as session:
            session.add(
                User(
                    user_id=rolled_back_user_id,
                    display_name=f"{TEST_PREFIX}-rollback-user",
                ),
            )
            session.flush()
            session.rollback()
        with Session(postgresql_engine) as session:
            assert session.get(User, rolled_back_user_id) is None
    finally:
        _cleanup(
            postgresql_engine,
            user_ids=user_ids | {rolled_back_user_id},
            shop_ids=shop_ids,
            device_ids=device_ids,
        )


async def _exercise_real_api(
    user_ids: set[UUID],
    shop_ids: set[UUID],
    device_ids: set[UUID],
) -> None:
    application = create_app()
    transport = ASGITransport(app=application)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        user_response = await client.post(
            "/api/v1/users",
            json={"display_name": f"{TEST_PREFIX}-api-user"},
        )
        assert user_response.status_code == 201
        user_payload = user_response.json()
        _assert_uuid_and_time(user_payload, "user_id")
        user_id = UUID(user_payload["user_id"])
        user_ids.add(user_id)

        user_list = await client.get("/api/v1/users", params={"page": 1, "page_size": 100})
        assert user_list.status_code == 200
        assert user_list.json()["page"] == 1
        assert user_list.json()["page_size"] == 100
        assert user_list.json()["total"] >= 1
        assert any(item["user_id"] == str(user_id) for item in user_list.json()["items"])
        user_update = await client.patch(
            f"/api/v1/users/{user_id}",
            json={"enabled": False},
        )
        assert user_update.status_code == 200
        assert user_update.json()["enabled"] is False

        shop_response = await client.post(
            "/api/v1/shops",
            json={
                "display_name": f"{TEST_PREFIX}-api-shop",
                "platform": "douyin",
                "owner_user_id": str(user_id),
            },
        )
        assert shop_response.status_code == 201
        shop_payload = shop_response.json()
        _assert_uuid_and_time(shop_payload, "shop_id")
        shop_id = UUID(shop_payload["shop_id"])
        shop_ids.add(shop_id)

        shop_detail = await client.get(f"/api/v1/shops/{shop_id}")
        assert shop_detail.status_code == 200
        shop_list = await client.get("/api/v1/shops", params={"page": 1, "page_size": 100})
        assert shop_list.status_code == 200
        assert any(item["shop_id"] == str(shop_id) for item in shop_list.json()["items"])
        shop_update = await client.patch(
            f"/api/v1/shops/{shop_id}",
            json={"note": f"{TEST_PREFIX}-api-updated"},
        )
        assert shop_update.status_code == 200
        assert shop_update.json()["note"] == f"{TEST_PREFIX}-api-updated"

        for role in ("primary", "backup"):
            device_response = await client.post(
                "/api/v1/devices",
                json={"display_name": f"{TEST_PREFIX}-api-{role}"},
            )
            assert device_response.status_code == 201
            device_payload = device_response.json()
            _assert_uuid_and_time(device_payload, "device_id")
            device_ids.add(UUID(device_payload["device_id"]))

        primary_device_id, backup_device_id = tuple(device_ids)
        device_detail = await client.get(f"/api/v1/devices/{primary_device_id}")
        assert device_detail.status_code == 200
        device_list = await client.get(
            "/api/v1/devices",
            params={"page": 1, "page_size": 100},
        )
        assert device_list.status_code == 200
        assert device_list.json()["total"] >= 2
        device_update = await client.patch(
            f"/api/v1/devices/{primary_device_id}",
            json={"location": f"{TEST_PREFIX}-api-location"},
        )
        assert device_update.status_code == 200

        for device_id, role in (
            (primary_device_id, "primary"),
            (backup_device_id, "backup"),
        ):
            binding_response = await client.post(
                f"/api/v1/shops/{shop_id}/device-bindings",
                json={"device_id": str(device_id), "binding_role": role},
            )
            assert binding_response.status_code == 201

        binding_list = await client.get(f"/api/v1/shops/{shop_id}/device-bindings")
        assert binding_list.status_code == 200
        assert len(binding_list.json()) == 2
        disable_response = await client.patch(
            f"/api/v1/shops/{shop_id}/device-bindings/{primary_device_id}",
            json={"enabled": False},
        )
        assert disable_response.status_code == 200
        change_response = await client.patch(
            f"/api/v1/shops/{shop_id}/device-bindings/{backup_device_id}",
            json={"binding_role": "primary"},
        )
        assert change_response.status_code == 200
        assert change_response.json()["binding_role"] == "primary"

        validation = await client.post(
            "/api/v1/shops",
            json={"display_name": "", "platform": "unknown"},
        )
        assert validation.status_code == 422
        assert validation.json()["code"] == "VALIDATION_ERROR"
        assert validation.json()["request_id"]

        not_found = await client.get(f"/api/v1/devices/{uuid4()}")
        assert not_found.status_code == 404
        assert not_found.json()["code"] == "DEVICE_NOT_FOUND"
        assert not_found.json()["request_id"]

def test_fastapi_uses_real_postgresql_contract(postgresql_engine: Engine) -> None:
    user_ids: set[UUID] = set()
    shop_ids: set[UUID] = set()
    device_ids: set[UUID] = set()
    try:
        asyncio.run(_exercise_real_api(user_ids, shop_ids, device_ids))
    finally:
        _cleanup(
            postgresql_engine,
            user_ids=user_ids,
            shop_ids=shop_ids,
            device_ids=device_ids,
        )
