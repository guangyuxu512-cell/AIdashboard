from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ModuleAccessService, TeamAuthorizationService
from app.modules.automation_apps.exceptions import (
    AutomationParameterPresetConflictError,
    AutomationParameterPresetInUseError,
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
    normalize_explicit_parameter_selection,
    validate_parameter_subset,
    YingdaoApplicationOptionRead,
)
from app.modules.devices.repository import DeviceRepository
from app.modules.devices.exceptions import DeviceNotFoundError
from app.modules.shops.repository import ShopRepository
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.schemas import YingdaoProviderInventory
from app.shared.identifiers import generate_id
from app.shared.pagination import Page, PaginationParams


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
        device_id: UUID | None = None,
    ) -> list[YingdaoApplicationOptionRead]:
        if device_id is None:
            devices = self.device_repository.list_all_for_actor(actor=actor)
        else:
            device = self.device_repository.get_for_actor(
                actor=actor,
                device_id=device_id,
            )
            if device is None:
                raise DeviceNotFoundError()
            devices = [device]
        # DeviceRepository already applies the Team's explicit device grants
        # in SQL.  Do not reintroduce the obsolete device.team_id ownership
        # filter here: a public Device may be granted to multiple Teams.
        device_ids = [device.device_id for device in devices]
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
        team_authorization_service: TeamAuthorizationService | None = None,
        application_catalog_service: AutomationApplicationCatalogService | None = None,
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
        self.team_authorization_service = (
            team_authorization_service or TeamAuthorizationService(session)
        )
        self.application_catalog_service = (
            application_catalog_service
            or AutomationApplicationCatalogService(session)
        )

    def list(
        self,
        *,
        actor: ActorContext,
        app_id: str,
    ) -> list[AutomationParameterPresetRead]:
        self._require_shop_access(actor)
        # A super account without an explicit Team context performs an
        # authorized cross-Team read.  Selecting a Team intentionally narrows
        # the collection again; writes still require that explicit context.
        presets = self.preset_repository.list_for_actor(actor=actor, app_id=app_id)
        if actor.team_id is not None:
            presets = [preset for preset in presets if preset.team_id == actor.team_id]
        return [self._to_read(preset) for preset in presets]

    def list_all(
        self,
        *,
        actor: ActorContext,
        device_id: UUID | None = None,
        app_id: str | None = None,
        name_query: str | None = None,
        pagination: PaginationParams | None = None,
    ) -> Page[AutomationParameterPresetRead] | list[AutomationParameterPresetRead]:
        self._require_shop_access(actor)
        allowed_app_ids = None
        if device_id is not None:
            allowed_app_ids = tuple(
                option.app_id
                for option in self.application_catalog_service.list_yingdao_application_options(
                    actor=actor,
                    device_id=device_id,
                )
            )
        presets = self.preset_repository.list_all_for_actor(
            actor=actor,
            team_id=actor.team_id,
            app_id=app_id,
            app_ids=allowed_app_ids,
            name_query=name_query,
            offset=pagination.offset if pagination is not None else 0,
            limit=pagination.page_size if pagination is not None else None,
        )
        items = [self._to_read(preset) for preset in presets]
        if pagination is None:
            return items
        total = self.preset_repository.count_all_for_actor(
            actor=actor,
            team_id=actor.team_id,
            app_id=app_id,
            app_ids=allowed_app_ids,
            name_query=name_query,
        )
        return Page(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

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
        team_id = actor.require_team_id()
        schema = (
            data.input_schema
            if data.input_schema is not None
            else self._application_schema(app_id)
        )
        common_parameters, shop_overrides = self._normalize_payload(
            actor=actor,
            schema=schema,
            common_parameters=data.common_parameters,
            shop_overrides=data.shop_overrides,
        )
        if self.preset_repository.exists_name(
            team_id=team_id,
            app_id=app_id,
            name=data.name,
        ):
            raise AutomationParameterPresetConflictError()
        preset = AutomationParameterPreset(
            preset_id=generate_id(),
            team_id=team_id,
            created_by_user_id=actor.user_id,
            app_id=app_id,
            name=data.name,
            common_parameters=common_parameters,
            shop_overrides=shop_overrides,
            input_schema_snapshot=schema.model_dump(mode="json"),
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
        team_id = actor.require_team_id()
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
        schema = (
            data.input_schema
            if data.input_schema is not None
            else self._preset_schema(preset)
        )
        common_parameters, shop_overrides = self._normalize_payload(
            actor=actor,
            schema=schema,
            common_parameters=values.get("common_parameters", preset.common_parameters),
            shop_overrides=values.get("shop_overrides", preset.shop_overrides),
        )
        if self.preset_repository.exists_name(
            team_id=team_id,
            app_id=app_id,
            name=name,
            exclude_preset_id=preset.preset_id,
        ):
            self.session.rollback()
            raise AutomationParameterPresetConflictError()
        preset.name = name
        preset.common_parameters = common_parameters
        preset.shop_overrides = shop_overrides
        if data.input_schema is not None:
            preset.input_schema_snapshot = schema.model_dump(mode="json")
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
        team_id = actor.require_team_id()
        source = self._get_for_actor(actor=actor, app_id=app_id, preset_id=preset_id)
        if self.preset_repository.exists_name(
            team_id=team_id,
            app_id=app_id,
            name=data.name,
        ):
            raise AutomationParameterPresetConflictError()
        preset = AutomationParameterPreset(
            preset_id=generate_id(),
            team_id=team_id,
            created_by_user_id=actor.user_id,
            app_id=app_id,
            name=data.name,
            common_parameters=dict(source.common_parameters),
            shop_overrides={
                shop_id: dict(values)
                for shop_id, values in source.shop_overrides.items()
            },
            input_schema_snapshot=deepcopy(source.input_schema_snapshot),
            version=1,
        )
        self.preset_repository.add(preset)
        self._commit(preset)
        return self._to_read(preset)

    def remove(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
    ) -> None:
        self._require_shop_access(actor)
        # Removing a Team-owned preset is a write.  A super account must first
        # select its target Team instead of deleting from the cross-Team read
        # view by accident.
        actor.require_team_id()
        preset = self._get_for_actor(
            actor=actor,
            app_id=app_id,
            preset_id=preset_id,
            for_update=True,
        )
        schedule_references = self.preset_repository.active_schedule_references(
            preset.preset_id,
        )
        if schedule_references:
            self.session.rollback()
            raise AutomationParameterPresetInUseError(schedule_references)

        # Task input_json is a completed, versioned snapshot.  An archived
        # Schedule cannot trigger again.  Keep those durable records and hide
        # this preset from every normal read/new-reference path instead.
        preset.deleted_at = datetime.now(UTC)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise

    def snapshot_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
        shop_ids: list[object],
    ) -> ParameterPresetSnapshot:
        self._require_shop_access(actor)
        # The same row lock as remove() makes resolution and logical deletion
        # serial: a deleted preset cannot race into a newly-created Task.
        preset = self._get_for_actor(
            actor=actor,
            app_id=app_id,
            preset_id=preset_id,
            for_update=True,
        )
        self._ensure_selected_shops_exist(actor, shop_ids)
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
            for_update=True,
        )
        if preset is None:
            raise AutomationParameterPresetNotFoundError()
        return self._snapshot(preset, shop_ids)

    def _application_schema(self, app_id: str) -> AutomationInputSchema:
        config = self.config_repository.get("yingdao", app_id)
        return AutomationInputSchema.model_validate(
            config.input_schema if config is not None else {"fields": []},
        )

    @staticmethod
    def _preset_schema(preset: AutomationParameterPreset) -> AutomationInputSchema:
        return AutomationInputSchema.model_validate(preset.input_schema_snapshot)

    def _normalize_payload(
        self,
        *,
        actor: ActorContext,
        schema: AutomationInputSchema,
        common_parameters: dict[str, object],
        shop_overrides: dict[object, dict[str, object]],
    ) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
        try:
            # A preset owns its explicit parameter selection. Validate that
            # selection without persisting schema defaults back into it: an
            # optional field removed from one preset must remain absent after
            # reread and cannot alter another preset.  The explicit selection
            # also enforces required fields; Task/Schedule snapshotting uses
            # the same rule so a later schema change fails closed instead of
            # silently adding a default.
            common = normalize_explicit_parameter_selection(
                schema,
                common_parameters,
            )
            overrides = {
                str(shop_id): validate_parameter_subset(schema, values)
                for shop_id, values in shop_overrides.items()
            }
        except ValueError as error:
            raise AutomationParameterPresetInvalidError(str(error)) from error
        self._ensure_selected_shops_exist(actor, list(shop_overrides))
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
                    self._preset_schema(preset),
                    common_parameters=preset.common_parameters,
                    shop_overrides=preset.shop_overrides,
                    shop_ids=shop_ids,  # type: ignore[arg-type]
                ),
            )
        except ValueError as error:
            raise AutomationParameterPresetInvalidError(str(error)) from error

    def _ensure_selected_shops_exist(
        self,
        actor: ActorContext,
        shop_ids: list[object],
    ) -> None:
        if not shop_ids:
            return
        shops = self.shop_repository.list_by_ids(shop_ids)  # type: ignore[arg-type]
        if len(shops) != len(set(shop_ids)):
            raise AutomationParameterPresetInvalidError("参数预设包含不存在或已移除的店铺")
        for shop_id in shop_ids:
            self.team_authorization_service.require_shop_access(actor, shop_id)  # type: ignore[arg-type]

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
        if preset is None:
            raise AutomationParameterPresetNotFoundError()
        # Normal members always have exactly one effective Team.  A super
        # account may omit its Team only for reads; when it selects one, the
        # selected context remains the write/read scope for this resource.
        if actor.team_id is not None and preset.team_id != actor.team_id:
            raise AutomationParameterPresetNotFoundError()
        if not actor.is_super_account and actor.team_id is None:
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

    def _to_read(
        self,
        preset: AutomationParameterPreset,
    ) -> AutomationParameterPresetRead:
        current_schema = self._preset_schema(preset)
        known_names = {field.name for field in current_schema.fields}
        invalid_names = sorted(
            {
                name
                for values in [preset.common_parameters, *preset.shop_overrides.values()]
                for name in values
                if name not in known_names
            },
        )
        return AutomationParameterPresetRead.model_validate(
            preset,
            from_attributes=True,
        ).model_copy(update={
            "input_schema": current_schema,
            "invalid_parameter_names": invalid_names,
        })
