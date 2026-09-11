from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ModuleAccessService
from app.modules.automation_apps.exceptions import (
    AutomationParameterPresetConflictError,
    AutomationParameterPresetInvalidError,
    AutomationParameterPresetNotFoundError,
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
)
from app.modules.shops.repository import ShopRepository
from app.shared.identifiers import generate_id


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
    ) -> dict[str, object]:
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
    ) -> dict[str, object]:
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
    ) -> dict[str, object]:
        try:
            return build_parameter_preset_snapshot(
                self._schema(preset.app_id),
                common_parameters=preset.common_parameters,
                shop_overrides=preset.shop_overrides,
                shop_ids=shop_ids,  # type: ignore[arg-type]
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
