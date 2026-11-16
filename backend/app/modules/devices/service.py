from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.exceptions import SuperAccountRequiredError
from app.modules.access.repository import TeamResourceAccessRepository
from app.modules.devices.exceptions import (
    DeviceHasActiveTasksError,
    DeviceNotFoundError,
)
from app.modules.devices.models import Device
from app.modules.devices.repository import DeviceRepository
from app.modules.devices.schemas import (
    DeviceCreate, DeviceLocalShopInventoryRead, DeviceLocalShopRead, DeviceUpdate,
)
from app.modules.tasks.repository import TaskRepository
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.precheck_models import WorkerRpaShopInventory
from app.modules.workers.session_health import merge_session_observations, worker_session_observation
from app.modules.tasks.models import Task


class DeviceService:
    def __init__(
        self,
        session: Session,
        repository: DeviceRepository | None = None,
        task_repository: TaskRepository | None = None,
        worker_repository: WorkerRepository | None = None,
        resource_access_repository: TeamResourceAccessRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or DeviceRepository(session)
        self.task_repository = task_repository or TaskRepository(session)
        self.worker_repository = worker_repository or WorkerRepository(session)
        self.resource_access_repository = (
            resource_access_repository or TeamResourceAccessRepository(session)
        )

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None = None,
    ) -> tuple[list[Device], int]:
        return (
            self.repository.list(
                actor=actor,
                offset=offset,
                limit=limit,
                search=search,
            ),
            self.repository.count(actor=actor, search=search),
        )

    def get(self, actor: ActorContext, device_id: UUID) -> Device:
        device = self.repository.get_for_actor(actor=actor, device_id=device_id)
        if device is None:
            raise DeviceNotFoundError()
        return device

    def get_for_write(self, actor: ActorContext, device_id: UUID) -> Device:
        self._require_super_account(actor)
        device = self.repository.get_for_update(device_id)
        if device is None:
            raise DeviceNotFoundError()
        return device

    def get_local_shops(
        self, actor: ActorContext, device_id: UUID,
    ) -> DeviceLocalShopInventoryRead:
        # Check the existing device/team authorization before reading inventory.
        self.get(actor, device_id)
        inventory = self.session.get(WorkerRpaShopInventory, device_id)
        if inventory is None:
            return DeviceLocalShopInventoryRead(
                device_id=device_id, available=False, last_discovered_at=None, shops=[],
            )
        now = datetime.now(UTC)
        recent = self.session.execute(
            select(Task.input_json, Task.status, Task.error_code, Task.finished_at)
            .where(
                Task.target_device_id == device_id,
                Task.skill_id == "douyin.category_schema",
                or_(
                    and_(Task.status == "success", Task.finished_at >= now - timedelta(minutes=30)),
                    and_(Task.status == "failed", Task.error_code == "SHOP_SESSION_EXPIRED"),
                ),
            )
            .order_by(Task.finished_at.desc().nullslast(), Task.created_at.desc())
        ).all()
        observations = {}
        for params, state, error, finished_at in recent:
            key = (params.get("local_shop_id"), params.get("platform_shop_id"), params.get("_session_revision"))
            if not all(isinstance(value, str) and value for value in key):
                continue
            if not finished_at or finished_at.tzinfo is None:
                continue
            if state == "success":
                status = "valid" if finished_at >= now - timedelta(minutes=30) else "unknown"
                observations.setdefault(key, (status, finished_at))
            elif state == "failed" and error == "SHOP_SESSION_EXPIRED":
                # A late success from the same snapshot cannot undo a clear
                # expiry; the dispatcher also waits for a new RPA snapshot.
                previous = observations.get(key)
                if previous is None or previous[0] != "invalid":
                    observations[key] = ("invalid", finished_at)
        shops = []
        for shop in inventory.shops:
            local_id, platform_id = shop.get("localShopId"), shop.get("platformShopId")
            name, platform = shop.get("shopName"), shop.get("platform")
            if not isinstance(local_id, str) or not isinstance(name, str) or not isinstance(platform, str):
                continue
            if shop.get("sessionStored") is not True:
                state, observed_at = "reauthorization_required", inventory.last_discovered_at
            else:
                state, observed_at = observations.get(
                    (local_id, platform_id, shop.get("sessionRevision")), ("unknown", None),
                )
                reported = worker_session_observation(shop, now=now)
                state, observed_at = merge_session_observations(
                    (state, observed_at) if observed_at else None, reported,
                ) or ("unknown", None)
            shops.append(DeviceLocalShopRead(
                local_shop_id=local_id, platform_shop_id=platform_id,
                shop_name=name, platform=platform, session_status=state,
                status_observed_at=observed_at,
            ))
        available = bool(
            inventory.available
            and inventory.last_discovered_at >= now - timedelta(minutes=5)
        )
        return DeviceLocalShopInventoryRead(
            device_id=device_id, available=available,
            last_discovered_at=inventory.last_discovered_at, shops=shops,
        )

    def create(self, actor: ActorContext, data: DeviceCreate) -> Device:
        self._require_super_account(actor)
        team_id = actor.require_team_id()
        device = Device(
            **data.model_dump(),
            team_id=team_id,
            created_by_user_id=actor.user_id,
        )
        self.repository.add(device)
        self.session.flush()
        self.resource_access_repository.replace_device_ids(
            team_id,
            [
                *self.resource_access_repository.list_device_ids(team_id),
                device.device_id,
            ],
        )
        self.session.commit()
        self.session.refresh(device)
        return device

    def update(
        self,
        actor: ActorContext,
        device_id: UUID,
        data: DeviceUpdate,
    ) -> Device:
        device = self.get_for_write(actor, device_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(device, field, value)
        self.session.commit()
        self.session.refresh(device)
        return device

    def remove(self, actor: ActorContext, device_id: UUID) -> None:
        device = self.get_for_write(actor, device_id)
        if self.task_repository.has_active_for_device(device_id):
            self.session.rollback()
            raise DeviceHasActiveTasksError()

        device.enabled = False
        device.deleted_at = datetime.now(UTC)
        self.worker_repository.disable_credentials_by_device(device_id)
        self.session.commit()

    @staticmethod
    def _require_super_account(actor: ActorContext) -> None:
        if not actor.is_super_account:
            raise SuperAccountRequiredError()
