from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ModuleAccessService
from app.modules.automation_apps.exceptions import (
    AutomationParameterPresetConflictError,
    AutomationParameterPresetInvalidError,
    AutomationParameterPresetNotFoundError,
    AutomationParameterPresetVersionConflictError,
)
from app.modules.automation_apps.models import (
    AutomationApplicationConfig,
    AutomationParameterPreset,
)
from app.modules.automation_apps.repository import (
    AutomationApplicationConfigRepository,
    AutomationParameterPresetRepository,
)
from app.modules.automation_apps.schemas import (
    AutomationApplicationConfigRead,
    AutomationApplicationConfigUpsert,
    AutomationInputSchema,
    AutomationParameterPresetCopy,
    AutomationParameterPresetCreate,
    AutomationParameterPresetRead,
    AutomationParameterPresetUpdate,
    build_parameter_preset_snapshot,
    normalize_parameters,
    validate_parameter_subset,
    YingdaoApplicationOptionRead,
)
from app.modules.devices.repository import DeviceRepository
from app.modules.shops.repository import ShopRepository
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.schemas import YingdaoProviderInventory
from app.shared.identifiers import generate_id


@dataclass(frozen=True)
class ParameterPresetSnapshot:
    """A resolved preset whose values are safe to persist on exactly one Task."""

    preset_id: UUID
    preset_version: int
    parameters: dict[str, Any]


class AutomationApplicationConfigService:
    def __init__(
        self,
        session: Session,
        repository: AutomationApplicationConfigRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AutomationApplicationConfigRepository(session)

    def get(
        self,
        provider_code: str,
        app_id: str,
    ) -> AutomationApplicationConfigRead | None:
        config = self.repository.get(provider_code, app_id)
        return self._to_read(config) if config is not None else None

    def upsert(
        self,
        provider_code: str,
        app_id: str,
        data: AutomationApplicationConfigUpsert,
    ) -> AutomationApplicationConfigRead:
        config = self.repository.get(provider_code, app_id)
        payload = data.input_schema.model_dump(mode="json")
        defaults = {
            field.name: field.default_value
            for field in data.input_schema.fields
            if field.default_value is not None
        }
        if config is None:
            config = AutomationApplicationConfig(
                provider_code=provider_code,
                app_id=app_id,
                schema_source="manual",
                input_schema=payload,
                default_values=defaults,
                version=1,
            )
            self.repository.add(config)
        else:
            config.input_schema = payload
            config.default_values = defaults
            config.schema_source = "manual"
            config.version += 1
        self.session.commit()
        self.session.refresh(config)
        return self._to_read(config)

    @staticmethod
    def _to_read(config: AutomationApplicationConfig) -> AutomationApplicationConfigRead:
        return AutomationApplicationConfigRead.model_validate(config, from_attributes=True)


class AutomationApplicationCatalogService:
    """Read only the Yingdao apps from Devices the actor can already view."""

    def __init__(
        self,
        session: Session,
        *,
        device_repository: DeviceRepository | None = None,
        worker_repository: WorkerRepository | None = None,
    ) -> None:
        self.device_repository = device_repository or DeviceRepository(session)
        self.worker_repository = worker_repository or WorkerRepository(session)

    def list_yingdao_application_options(
        self,
        *,
        actor: ActorContext,
    ) -> list[YingdaoApplicationOptionRead]:
        devices = self.device_repository.list_all_for_actor(actor=actor)
        # Parameter presets are always scoped to the active Team.  A human
        # actor can have a broader Device data scope elsewhere, but that must
        # not turn this options endpoint into a cross-Team application catalog.
        device_ids = [
            device.device_id
            for device in devices
            if device.team_id == actor.team_id
        ]
        records = self.worker_repository.get_provider_inventories_for_devices(
            device_ids,
            provider_code="yingdao",
        )
        options: dict[str, str] = {}
        for record in records:
            inventory = YingdaoProviderInventory.model_validate(record.inventory_payload)
            for application in inventory.applications:
                # Keep a deterministic value when one visible application is
                # reported by multiple Devices; no Device/account data leaves
                # this catalog endpoint.
                options.setdefault(application.app_id, application.app_name)
        return [
            YingdaoApplicationOptionRead(app_id=app_id, app_name=app_name)
            for app_id, app_name in sorted(
                options.items(),
                key=lambda item: (item[1], item[0]),
            )
        ]


class AutomationParameterPresetService:
    """Team-scoped Yingdao parameter presets and their final Task snapshots."""

    def __init__(
        self,
        session: Session,
        *,
        config_repository: AutomationApplicationConfigRepository | None = None,
        preset_repository: AutomationParameterPresetRepository | None = None,
        shop_repository: ShopRepository | None = None,
        module_access_service: ModuleAccessService | None = None,
    ) -> None:
        self.session = session
        self.config_repository = config_repository or AutomationApplicationConfigRepository(
            session,
        )
        self.preset_repository = preset_repository or AutomationParameterPresetRepository(
            session,
        )
        self.shop_repository = shop_repository or ShopRepository(session)
        self.module_access_service = module_access_service or ModuleAccessService(session)

    def list(
        self,
        *,
        actor: ActorContext,
        app_id: str,
    ) -> list[AutomationParameterPresetRead]:
        self._require_shop_access(actor)
        return [
            self._to_read(preset)
            for preset in self.preset_repository.list_for_actor(
                actor=actor,
                app_id=app_id,
            )
            # Parameter presets are intentionally Team-scoped even when an
            # operator has ALL scope for another resource type.
            if preset.team_id == actor.team_id
        ]

    def list_all(
        self,
        *,
        actor: ActorContext,
        app_id: str | None = None,
        name_query: str | None = None,
    ) -> list[AutomationParameterPresetRead]:
        self._require_shop_access(actor)
        return [
            self._to_read(preset)
            for preset in self.preset_repository.list_all_for_actor(
                actor=actor,
                app_id=app_id,
                name_query=name_query,
            )
            # Parameter presets intentionally never escape the active Team,
            # including for an ActorContext with ALL scope elsewhere.
            if preset.team_id == actor.team_id
        ]

    def get(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
    ) -> AutomationParameterPresetRead:
        self._require_shop_access(actor)
        preset = self._get_for_actor(actor=actor, app_id=app_id, preset_id=preset_id)
        return self._to_read(preset)

    def create(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        data: AutomationParameterPresetCreate,
    ) -> AutomationParameterPresetRead:
        self._require_shop_access(actor)
        common_parameters, shop_overrides = self._normalize_payload(
            app_id=app_id,
            common_parameters=data.common_parameters,
            shop_overrides=data.shop_overrides,
        )
        if self.preset_repository.exists_name(
            team_id=actor.team_id,
            app_id=app_id,
            name=data.name,
        ):
            raise AutomationParameterPresetConflictError()
        preset = AutomationParameterPreset(
            preset_id=generate_id(),
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            app_id=app_id,
            name=data.name,
            common_parameters=common_parameters,
            shop_overrides=shop_overrides,
            version=1,
        )
        self.preset_repository.add(preset)
        self._commit(preset)
        return self._to_read(preset)

    def update(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
        data: AutomationParameterPresetUpdate,
    ) -> AutomationParameterPresetRead:
        self._require_shop_access(actor)
        preset = self._get_for_actor(
            actor=actor,
            app_id=app_id,
            preset_id=preset_id,
            for_update=True,
        )
        if preset.version != data.expected_version:
            self.session.rollback()
            raise AutomationParameterPresetVersionConflictError()
        values = data.model_dump(exclude_unset=True)
        name = values.get("name", preset.name)
        common_parameters, shop_overrides = self._normalize_payload(
            app_id=app_id,
            common_parameters=values.get("common_parameters", preset.common_parameters),
            shop_overrides=values.get("shop_overrides", preset.shop_overrides),
        )
        if self.preset_repository.exists_name(
            team_id=actor.team_id,
            app_id=app_id,
            name=name,
            exclude_preset_id=preset.preset_id,
        ):
            self.session.rollback()
            raise AutomationParameterPresetConflictError()
        preset.name = name
        preset.common_parameters = common_parameters
        preset.shop_overrides = shop_overrides
        preset.version += 1
        self._commit(preset)
        return self._to_read(preset)

    def copy(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
        data: AutomationParameterPresetCopy,
    ) -> AutomationParameterPresetRead:
        self._require_shop_access(actor)
        source = self._get_for_actor(actor=actor, app_id=app_id, preset_id=preset_id)
        if self.preset_repository.exists_name(
            team_id=actor.team_id,
            app_id=app_id,
            name=data.name,
        ):
            raise AutomationParameterPresetConflictError()
        preset = AutomationParameterPreset(
            preset_id=generate_id(),
            team_id=actor.team_id,
            created_by_user_id=actor.user_id,
            app_id=app_id,
            name=data.name,
            common_parameters=dict(source.common_parameters),
            shop_overrides={
                shop_id: dict(values)
                for shop_id, values in source.shop_overrides.items()
            },
            version=1,
        )
        self.preset_repository.add(preset)
        self._commit(preset)
        return self._to_read(preset)

    def snapshot_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
        shop_ids: list[object],
    ) -> ParameterPresetSnapshot:
        self._require_shop_access(actor)
        preset = self._get_for_actor(actor=actor, app_id=app_id, preset_id=preset_id)
        self._ensure_selected_shops_exist(shop_ids)
        return self._snapshot(preset, shop_ids)

    def snapshot_for_team(
        self,
        *,
        team_id: object,
        app_id: str,
        preset_id: object,
        shop_ids: list[object],
    ) -> ParameterPresetSnapshot:
        preset = self.preset_repository.get_for_team(
            team_id=team_id,
            app_id=app_id,
            preset_id=preset_id,
        )
        if preset is None:
            raise AutomationParameterPresetNotFoundError()
        return self._snapshot(preset, shop_ids)

    def _schema(self, app_id: str) -> AutomationInputSchema:
        config = self.config_repository.get("yingdao", app_id)
        return AutomationInputSchema.model_validate(
            config.input_schema if config is not None else {"fields": []},
        )

    def _normalize_payload(
        self,
        *,
        app_id: str,
        common_parameters: dict[str, object],
        shop_overrides: dict[object, dict[str, object]],
    ) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        schema = self._schema(app_id)
        try:
            common = normalize_parameters(schema, common_parameters)
            overrides = {
                str(shop_id): validate_parameter_subset(schema, values)
                for shop_id, values in shop_overrides.items()
            }
        except ValueError as error:
            raise AutomationParameterPresetInvalidError(str(error)) from error
        self._ensure_selected_shops_exist(list(shop_overrides))
        return common, overrides

    def _snapshot(
        self,
        preset: AutomationParameterPreset,
        shop_ids: list[object],
    ) -> ParameterPresetSnapshot:
        try:
            return ParameterPresetSnapshot(
                preset_id=preset.preset_id,
                preset_version=preset.version,
                parameters=build_parameter_preset_snapshot(
                    self._schema(preset.app_id),
                    common_parameters=preset.common_parameters,
                    shop_overrides=preset.shop_overrides,
                    shop_ids=shop_ids,  # type: ignore[arg-type]
                ),
            )
        except ValueError as error:
            raise AutomationParameterPresetInvalidError(str(error)) from error

    def _ensure_selected_shops_exist(self, shop_ids: list[object]) -> None:
        if not shop_ids:
            return
        shops = self.shop_repository.list_by_ids(shop_ids)  # type: ignore[arg-type]
        if len(shops) != len(set(shop_ids)):
            raise AutomationParameterPresetInvalidError("参数预设包含不存在或已移除的店铺")

    def _get_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
        for_update: bool = False,
    ) -> AutomationParameterPreset:
        preset = self.preset_repository.get_for_actor(
            actor=actor,
            app_id=app_id,
            preset_id=preset_id,
            for_update=for_update,
        )
        if preset is None or preset.team_id != actor.team_id:
            raise AutomationParameterPresetNotFoundError()
        return preset

    def _require_shop_access(self, actor: ActorContext) -> None:
        self.module_access_service.require_module_access(actor, ModuleCode.SHOP)

    def _commit(self, preset: AutomationParameterPreset) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise AutomationParameterPresetConflictError() from error
        self.session.refresh(preset)

    @staticmethod
    def _to_read(preset: AutomationParameterPreset) -> AutomationParameterPresetRead:
        return AutomationParameterPresetRead.model_validate(preset, from_attributes=True)
