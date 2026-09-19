from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import ModuleAccessDeniedError
from app.modules.access.exceptions import TeamResourceAccessDeniedError
from app.modules.access.exceptions import TeamContextRequiredError
from app.modules.automation_apps.exceptions import (
    AutomationParameterPresetInUseError,
    AutomationParameterPresetInvalidError,
    AutomationParameterPresetNotFoundError,
    AutomationParameterPresetVersionConflictError,
)
from app.modules.automation_apps.models import AutomationParameterPreset
from app.modules.automation_apps.schemas import (
    AutomationInputSchema,
    AutomationParameterPresetCopy,
    AutomationParameterPresetCreate,
    AutomationParameterPresetUpdate,
    YingdaoApplicationOptionRead,
)
from app.modules.automation_apps.service import (
    AutomationApplicationCatalogService,
    AutomationParameterPresetService,
)
from app.modules.devices.exceptions import DeviceNotFoundError
from app.shared.pagination import PaginationParams


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, preset: AutomationParameterPreset) -> None:
        now = datetime.now(UTC)
        preset.created_at = preset.created_at or now
        preset.updated_at = now


class FakePresetRepository:
    def __init__(self) -> None:
        self.presets: list[AutomationParameterPreset] = []
        self.references: dict[UUID, tuple[str, ...]] = {}

    def add(self, preset: AutomationParameterPreset) -> None:
        self.presets.append(preset)

    def list_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str,
    ) -> list[AutomationParameterPreset]:
        # This fake deliberately honors ALL to prove the service still keeps
        # presets inside the current Team.
        candidates = [preset for preset in self.presets if preset.app_id == app_id]
        if actor.data_scope is DataScope.SELF:
            candidates = [
                preset
                for preset in candidates
                if preset.team_id == actor.team_id
                and preset.created_by_user_id == actor.user_id
            ]
        elif actor.data_scope is DataScope.TEAM:
            candidates = [
                preset for preset in candidates if preset.team_id == actor.team_id
            ]
        return candidates

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: UUID,
        for_update: bool = False,
    ) -> AutomationParameterPreset | None:
        del for_update
        return next(
            (
                preset
                for preset in self.list_for_actor(actor=actor, app_id=app_id)
                if preset.preset_id == preset_id
            ),
            None,
        )

    def get_for_team(
        self,
        *,
        team_id: UUID,
        app_id: str,
        preset_id: UUID,
    ) -> AutomationParameterPreset | None:
        return next(
            (
                preset
                for preset in self.presets
                if preset.preset_id == preset_id
                and preset.team_id == team_id
                and preset.app_id == app_id
            ),
            None,
        )

    def list_all_for_actor(
        self,
        *,
        actor: ActorContext,
        team_id: UUID | None,
        app_id: str | None = None,
        app_ids: tuple[str, ...] | None = None,
        name_query: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AutomationParameterPreset]:
        candidates = (
            list(self.presets)
            if team_id is None
            else [preset for preset in self.presets if preset.team_id == team_id]
        )
        if actor.data_scope is DataScope.SELF:
            candidates = [
                preset
                for preset in candidates
                if preset.created_by_user_id == actor.user_id
            ]
        if app_id is not None:
            candidates = [preset for preset in candidates if preset.app_id == app_id]
        if app_ids is not None:
            candidates = [preset for preset in candidates if preset.app_id in app_ids]
        if name_query:
            candidates = [preset for preset in candidates if name_query in preset.name]
        candidates.sort(key=lambda preset: preset.preset_id)
        candidates.sort(key=lambda preset: preset.updated_at, reverse=True)
        return candidates[offset : offset + limit if limit is not None else None]

    def count_all_for_actor(
        self,
        *,
        actor: ActorContext,
        team_id: UUID | None,
        app_id: str | None = None,
        app_ids: tuple[str, ...] | None = None,
        name_query: str | None = None,
    ) -> int:
        return len(
            self.list_all_for_actor(
                actor=actor,
                team_id=team_id,
                app_id=app_id,
                app_ids=app_ids,
                name_query=name_query,
            ),
        )

    def exists_name(
        self,
        *,
        team_id: UUID,
        app_id: str,
        name: str,
        exclude_preset_id: UUID | None = None,
    ) -> bool:
        return any(
            preset.team_id == team_id
            and preset.app_id == app_id
            and preset.name == name
            and preset.preset_id != exclude_preset_id
            for preset in self.presets
        )

    def reference_types(self, preset_id: UUID) -> tuple[str, ...]:
        return self.references.get(preset_id, ())

    def remove(self, preset: AutomationParameterPreset) -> None:
        self.presets.remove(preset)


class FakeConfigRepository:
    def __init__(self) -> None:
        self.input_schema = {
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
                    "name": "备注",
                    "label": "备注",
                    "type": "text",
                    "required": False,
                    "default_value": "默认备注",
                    "options": [],
                },
            ],
        }

    def get(self, provider_code: str, app_id: str) -> SimpleNamespace:
        assert (provider_code, app_id) == ("yingdao", "safe-app")
        return SimpleNamespace(input_schema=self.input_schema)


class FakeShopRepository:
    def __init__(self, shop_ids: set[UUID]) -> None:
        self.shop_ids = shop_ids

    def list_by_ids(self, shop_ids: list[UUID]) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(shop_id=shop_id)
            for shop_id in shop_ids
            if shop_id in self.shop_ids
        ]


class FakeModuleAccessService:
    def __init__(self, *, allowed: bool) -> None:
        self.allowed = allowed

    def require_module_access(self, actor: ActorContext, module_code: object) -> None:
        del actor, module_code
        if not self.allowed:
            raise ModuleAccessDeniedError()


class FakeTeamAuthorizationService:
    def __init__(self, allowed_shop_ids: set[UUID]) -> None:
        self.allowed_shop_ids = allowed_shop_ids

    def require_shop_access(self, _actor: ActorContext, shop_id: UUID) -> None:
        if shop_id not in self.allowed_shop_ids:
            raise TeamResourceAccessDeniedError()


def actor(*, team_id: UUID, scope: DataScope = DataScope.TEAM) -> ActorContext:
    return ActorContext(
        user_id=uuid4(),
        user_display_name="参数预设测试人员",
        team_id=team_id,
        membership_id=uuid4(),
        role_code="member",
        data_scope=scope,
    )


def service_for(
    *,
    repository: FakePresetRepository,
    shop_ids: set[UUID],
    allowed: bool = True,
    application_catalog_service: object | None = None,
) -> AutomationParameterPresetService:
    return AutomationParameterPresetService(
        FakeSession(),  # type: ignore[arg-type]
        config_repository=FakeConfigRepository(),  # type: ignore[arg-type]
        preset_repository=repository,  # type: ignore[arg-type]
        shop_repository=FakeShopRepository(shop_ids),  # type: ignore[arg-type]
        module_access_service=FakeModuleAccessService(allowed=allowed),  # type: ignore[arg-type]
        team_authorization_service=FakeTeamAuthorizationService(shop_ids),  # type: ignore[arg-type]
        application_catalog_service=application_catalog_service,  # type: ignore[arg-type]
    )


def test_preset_keeps_false_zero_and_empty_string_and_snapshots_selected_shops() -> None:
    team_id = uuid4()
    actor_context = actor(team_id=team_id)
    shop_a, shop_b = uuid4(), uuid4()
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids={shop_a, shop_b})

    created = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="中文店铺预设",
            common_parameters={"标题": "公共标题", "数量": 0, "启用": False, "备注": ""},
            shop_overrides={shop_a: {"标题": "店铺 A"}},
        ),
    )
    assert created.common_parameters == {
        "标题": "公共标题",
        "数量": 0,
        "启用": False,
        "备注": "",
    }

    updated = service.update(
        actor=actor_context,
        app_id="safe-app",
        preset_id=created.preset_id,
        data=AutomationParameterPresetUpdate(
            expected_version=created.version,
            shop_overrides={shop_a: {"标题": "店铺 A 更新"}},
        ),
    )
    assert updated.shop_overrides == {shop_a: {"标题": "店铺 A 更新"}}
    snapshot = service.snapshot_for_actor(
        actor=actor_context,
        app_id="safe-app",
        preset_id=created.preset_id,
        shop_ids=[shop_a],
    )
    assert snapshot.parameters == {
        "格式版本": 1,
        "公共参数": created.common_parameters,
        "店铺参数": {
            str(shop_a): {
                "标题": "店铺 A 更新",
                "数量": 0,
                "启用": False,
                "备注": "",
            },
        },
    }
    assert str(shop_b) not in snapshot.parameters["店铺参数"]
    assert snapshot.preset_id == created.preset_id
    assert snapshot.preset_version == updated.version

    with pytest.raises(AutomationParameterPresetVersionConflictError):
        service.update(
            actor=actor_context,
            app_id="safe-app",
            preset_id=created.preset_id,
            data=AutomationParameterPresetUpdate(
                expected_version=created.version,
                common_parameters={"标题": "过期写入"},
            ),
        )


def test_preset_is_team_scoped_even_for_all_scope_and_copy_is_independent() -> None:
    own_team, other_team = uuid4(), uuid4()
    own_actor = actor(team_id=own_team, scope=DataScope.ALL)
    shop_id = uuid4()
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids={shop_id})

    own = service.create(
        actor=own_actor,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="团队内预设",
            common_parameters={"标题": "原始"},
        ),
    )
    repository.add(
        AutomationParameterPreset(
            preset_id=uuid4(),
            team_id=other_team,
            created_by_user_id=uuid4(),
            app_id="safe-app",
            name="其他团队预设",
            common_parameters={"标题": "不可见"},
            shop_overrides={},
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    )

    assert [preset.preset_id for preset in service.list(actor=own_actor, app_id="safe-app")] == [
        own.preset_id,
    ]
    copied = service.copy(
        actor=own_actor,
        app_id="safe-app",
        preset_id=own.preset_id,
        data=AutomationParameterPresetCopy(name="团队内预设副本"),
    )
    service.update(
        actor=own_actor,
        app_id="safe-app",
        preset_id=own.preset_id,
        data=AutomationParameterPresetUpdate(
            expected_version=own.version,
            common_parameters={"标题": "已修改"},
        ),
    )
    assert copied.common_parameters == {"标题": "原始"}

    with pytest.raises(AutomationParameterPresetNotFoundError):
        service.get(
            actor=actor(team_id=other_team),
            app_id="safe-app",
            preset_id=own.preset_id,
        )


def test_preset_parameter_selection_is_independent_and_task_snapshot_keeps_only_enabled_fields() -> None:
    team_id = uuid4()
    actor_context = actor(team_id=team_id)
    shop_a, shop_b = uuid4(), uuid4()
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids={shop_a, shop_b})

    source = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="配置 A",
            common_parameters={"标题": "A", "数量": 2},
            shop_overrides={shop_a: {"备注": "A 店铺"}},
        ),
    )
    copied = service.copy(
        actor=actor_context,
        app_id="safe-app",
        preset_id=source.preset_id,
        data=AutomationParameterPresetCopy(name="配置 B"),
    )

    updated_source = service.update(
        actor=actor_context,
        app_id="safe-app",
        preset_id=source.preset_id,
        data=AutomationParameterPresetUpdate(
            expected_version=source.version,
            common_parameters={"标题": "A 已修改"},
            shop_overrides={shop_a: {"备注": "A 店铺已修改"}},
        ),
    )
    updated_copy = service.update(
        actor=actor_context,
        app_id="safe-app",
        preset_id=copied.preset_id,
        data=AutomationParameterPresetUpdate(
            expected_version=copied.version,
            common_parameters={"标题": "B", "启用": False},
            shop_overrides={shop_b: {"数量": 0}},
        ),
    )

    assert updated_source.common_parameters == {"标题": "A 已修改"}
    assert updated_source.shop_overrides == {shop_a: {"备注": "A 店铺已修改"}}
    assert updated_copy.common_parameters == {"标题": "B", "启用": False}
    assert updated_copy.shop_overrides == {shop_b: {"数量": 0}}

    snapshot = service.snapshot_for_actor(
        actor=actor_context,
        app_id="safe-app",
        preset_id=updated_source.preset_id,
        shop_ids=[shop_a],
    )
    assert snapshot.parameters == {
        "格式版本": 1,
        "公共参数": {
            "标题": "A 已修改",
        },
        "店铺参数": {
            str(shop_a): {
                "标题": "A 已修改",
                "备注": "A 店铺已修改",
            },
        },
    }

    copied_snapshot = service.snapshot_for_actor(
        actor=actor_context,
        app_id="safe-app",
        preset_id=updated_copy.preset_id,
        shop_ids=[shop_b],
    )
    assert copied_snapshot.parameters == {
        "格式版本": 1,
        "公共参数": {"标题": "B", "启用": False},
        "店铺参数": {
            str(shop_b): {"标题": "B", "数量": 0, "启用": False},
        },
    }


def test_preset_schema_snapshot_is_independent_from_template_and_copy() -> None:
    team_id = uuid4()
    actor_context = actor(team_id=team_id)
    shop_a = uuid4()
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids={shop_a})

    schema_a = AutomationInputSchema.model_validate(
        {
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
                    "name": "页码",
                    "label": "页码",
                    "type": "number",
                    "required": False,
                    "default_value": 1,
                    "options": [],
                },
            ],
        },
    )
    schema_b = AutomationInputSchema.model_validate(
        {
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
                    "name": "启用",
                    "label": "启用",
                    "type": "boolean",
                    "required": False,
                    "default_value": False,
                    "options": [],
                },
            ],
        },
    )
    preset_a = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="配置 A",
            input_schema=schema_a,
            common_parameters={"标题": "A", "页码": 2},
        ),
    )
    preset_b = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="配置 B",
            input_schema=schema_b,
            common_parameters={"标题": "B", "启用": False},
        ),
    )
    copied_a = service.copy(
        actor=actor_context,
        app_id="safe-app",
        preset_id=preset_a.preset_id,
        data=AutomationParameterPresetCopy(name="配置 C"),
    )

    # A later application-template change is deliberately irrelevant to all
    # existing preset schemas, values, and materialized Task/Schedule params.
    config = service.config_repository  # type: ignore[assignment]
    config.input_schema = {  # type: ignore[attr-defined]
        "fields": [
            {
                "name": "新必填字段",
                "label": "新必填字段",
                "type": "text",
                "required": True,
                "default_value": None,
                "options": [],
            },
        ],
    }
    assert service.get(
        actor=actor_context,
        app_id="safe-app",
        preset_id=preset_a.preset_id,
    ).input_schema == schema_a
    assert service.snapshot_for_actor(
        actor=actor_context,
        app_id="safe-app",
        preset_id=preset_a.preset_id,
        shop_ids=[shop_a],
    ).parameters["店铺参数"][str(shop_a)] == {"标题": "A", "页码": 2}
    assert service.snapshot_for_actor(
        actor=actor_context,
        app_id="safe-app",
        preset_id=preset_b.preset_id,
        shop_ids=[shop_a],
    ).parameters["店铺参数"][str(shop_a)] == {"标题": "B", "启用": False}
    assert copied_a.input_schema == schema_a

    # Field editing is an explicit versioned fact of A only.  B and C retain
    # their own contracts and values after A removes its optional page field.
    updated_a = service.update(
        actor=actor_context,
        app_id="safe-app",
        preset_id=preset_a.preset_id,
        data=AutomationParameterPresetUpdate(
            expected_version=preset_a.version,
            input_schema=AutomationInputSchema.model_validate(
                {"fields": [schema_a.fields[0].model_dump(mode="json")]},
            ),
            common_parameters={"标题": "A 已编辑"},
            shop_overrides={},
        ),
    )
    assert [field.name for field in updated_a.input_schema.fields] == ["标题"]
    assert [field.name for field in preset_b.input_schema.fields] == ["标题", "启用"]
    assert [field.name for field in copied_a.input_schema.fields] == ["标题", "页码"]


def test_preset_snapshot_fails_when_a_current_required_field_is_not_explicitly_enabled() -> None:
    team_id = uuid4()
    actor_context = actor(team_id=team_id)
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids=set())
    preset = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="已有预设",
            common_parameters={"标题": "保存时完整"},
        ),
    )

    # Simulate a legacy stored selection after the current schema gains (or
    # exposes) a required field.  Snapshotting must fail closed, not add a
    # default or let the Worker receive an incomplete payload.
    repository.presets[0].common_parameters = {"数量": 2}
    with pytest.raises(AutomationParameterPresetInvalidError, match="缺少必填参数: 标题"):
        service.snapshot_for_actor(
            actor=actor_context,
            app_id="safe-app",
            preset_id=preset.preset_id,
            shop_ids=[],
        )

def test_preset_remove_keeps_task_and_schedule_references_intact() -> None:
    team_id = uuid4()
    actor_context = actor(team_id=team_id)
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids=set())
    preset = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="可删除配置",
            common_parameters={"标题": "公共标题"},
        ),
    )

    service.remove(
        actor=actor_context,
        app_id="safe-app",
        preset_id=preset.preset_id,
    )
    assert repository.presets == []

    referenced = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="被引用配置",
            common_parameters={"标题": "公共标题"},
        ),
    )
    repository.references[referenced.preset_id] = ("task", "schedule")

    with pytest.raises(AutomationParameterPresetInUseError) as error:
        service.remove(
            actor=actor_context,
            app_id="safe-app",
            preset_id=referenced.preset_id,
        )

    assert error.value.details == {"reference_types": ["task", "schedule"]}
    assert [preset.preset_id for preset in repository.presets] == [
        referenced.preset_id,
    ]


def test_preset_read_marks_only_values_missing_from_the_current_schema() -> None:
    team_id = uuid4()
    actor_context = actor(team_id=team_id)
    shop_id = uuid4()
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids={shop_id})
    preset = service.create(
        actor=actor_context,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="含历史字段配置",
            common_parameters={"标题": "当前字段"},
            shop_overrides={shop_id: {"标题": "店铺字段"}},
        ),
    )

    # A schema change must retain and surface old values rather than silently
    # dropping them from an otherwise readable preset.
    stored = repository.presets[0]
    stored.common_parameters = {"标题": "当前字段", "1": "旧公共值"}
    stored.shop_overrides = {shop_id: {"已移除店铺字段": "旧店铺值"}}

    read = service.get(
        actor=actor_context,
        app_id="safe-app",
        preset_id=preset.preset_id,
    )

    assert read.common_parameters["1"] == "旧公共值"
    assert read.shop_overrides[shop_id]["已移除店铺字段"] == "旧店铺值"
    assert read.invalid_parameter_names == ["1", "已移除店铺字段"]


def test_preset_requires_existing_shop_module_access() -> None:
    preset_service = service_for(
        repository=FakePresetRepository(),
        shop_ids=set(),
        allowed=False,
    )
    with pytest.raises(ModuleAccessDeniedError):
        preset_service.list(actor=actor(team_id=uuid4()), app_id="safe-app")


def test_management_list_remains_inside_current_team_for_all_scope() -> None:
    own_team, other_team = uuid4(), uuid4()
    own_actor = actor(team_id=own_team, scope=DataScope.ALL)
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids=set())
    own = service.create(
        actor=own_actor,
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="日常采集",
            common_parameters={"标题": "公共标题"},
        ),
    )
    repository.add(
        AutomationParameterPreset(
            preset_id=uuid4(),
            team_id=other_team,
            created_by_user_id=uuid4(),
            app_id="other-app",
            name="日常采集（其他团队）",
            common_parameters={},
            shop_overrides={},
            input_schema_snapshot={"fields": []},
            version=1,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        ),
    )

    page = service.list_all(
        actor=own_actor,
        app_id="safe-app",
        name_query="日常",
        pagination=PaginationParams(),
    )
    assert [preset.preset_id for preset in page.items] == [own.preset_id]
    assert page.total == 1


def test_management_list_counts_and_pages_only_authorized_team_rows() -> None:
    team_id, other_team_id = uuid4(), uuid4()
    actor_context = actor(team_id=team_id, scope=DataScope.ALL)
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids=set())
    now = datetime.now(UTC)
    own_presets = [
        AutomationParameterPreset(
            preset_id=uuid4(),
            team_id=team_id,
            created_by_user_id=actor_context.user_id,
            app_id="safe-app",
            name=f"当前团队配置 {index}",
            common_parameters={},
            shop_overrides={},
            input_schema_snapshot={"fields": []},
            version=1,
            created_at=now,
            updated_at=now.replace(microsecond=index),
        )
        for index in range(1, 4)
    ]
    foreign = AutomationParameterPreset(
        preset_id=uuid4(),
        team_id=other_team_id,
        created_by_user_id=uuid4(),
        app_id="safe-app",
        name="其他团队配置",
        common_parameters={},
        shop_overrides={},
        input_schema_snapshot={"fields": []},
        version=1,
        created_at=now,
        updated_at=now.replace(microsecond=999999),
    )
    repository.presets.extend([*own_presets, foreign])

    page = service.list_all(
        actor=actor_context,
        app_id="safe-app",
        pagination=PaginationParams(page=2, page_size=1),
    )

    assert page.total == 3
    assert page.page == 2
    assert page.page_size == 1
    assert [preset.preset_id for preset in page.items] == [own_presets[1].preset_id]
    legacy = service.list_all(actor=actor_context, app_id="safe-app")
    assert [preset.preset_id for preset in legacy] == [
        preset.preset_id for preset in reversed(own_presets)
    ]
    assert legacy[1] == page.items[0]


def test_super_without_team_reads_all_presets_but_writes_require_selected_team() -> None:
    team_a, team_b = uuid4(), uuid4()
    repository = FakePresetRepository()
    service = service_for(repository=repository, shop_ids=set())
    preset_a = service.create(
        actor=actor(team_id=team_a),
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="团队 A 配置",
            common_parameters={"标题": "A"},
        ),
    )
    preset_b = service.create(
        actor=actor(team_id=team_b),
        app_id="safe-app",
        data=AutomationParameterPresetCreate(
            name="团队 B 配置",
            common_parameters={"标题": "B"},
        ),
    )
    super_actor = ActorContext(
        user_id=uuid4(),
        user_display_name="超级账号",
        team_id=None,
        membership_id=None,
        role_code="super_account",
        data_scope=DataScope.ALL,
        is_super_account=True,
    )

    page = service.list_all(
        actor=super_actor,
        app_id="safe-app",
        pagination=PaginationParams(page=1, page_size=10),
    )

    assert page.total == 2
    assert {preset.preset_id for preset in page.items} == {
        preset_a.preset_id,
        preset_b.preset_id,
    }
    assert service.get(
        actor=super_actor,
        app_id="safe-app",
        preset_id=preset_b.preset_id,
    ).name == "团队 B 配置"

    with pytest.raises(TeamContextRequiredError):
        service.create(
            actor=super_actor,
            app_id="safe-app",
            data=AutomationParameterPresetCreate(
                name="不得隐式归属",
                common_parameters={"标题": "X"},
            ),
        )
    with pytest.raises(TeamContextRequiredError):
        service.remove(
            actor=super_actor,
            app_id="safe-app",
            preset_id=preset_a.preset_id,
        )
    assert {preset.preset_id for preset in repository.presets} == {
        preset_a.preset_id,
        preset_b.preset_id,
    }


class FakeDeviceCatalogRepository:
    def __init__(self) -> None:
        self.team_device_id = uuid4()
        self.foreign_device_id = uuid4()

    def list_all_for_actor(self, *, actor: ActorContext) -> list[SimpleNamespace]:
        # The real repository applies Team device grants in SQL.  The catalog
        # deliberately trusts that scope instead of reopening device.team_id.
        del actor
        return [
            SimpleNamespace(device_id=self.team_device_id),
        ]

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        device_id: UUID,
    ) -> SimpleNamespace | None:
        if device_id != self.team_device_id:
            return None
        del actor
        return SimpleNamespace(device_id=device_id)


class FakeWorkerCatalogRepository:
    def get_provider_inventories_for_devices(
        self,
        device_ids: list[UUID],
        *,
        provider_code: str,
    ) -> list[SimpleNamespace]:
        assert len(device_ids) == 1
        assert provider_code == "yingdao"
        return [
            SimpleNamespace(
                inventory_payload={
                    "provider": "yingdao",
                    "available": True,
                    "status": "need_login",
                    "status_reason_code": None,
                    "status_reason": None,
                    "provider_version": "6.3.6",
                    "execution_available": False,
                    "execution_version": None,
                    "execution_unavailable_reason": None,
                    "logged_in": False,
                    "account_display": None,
                    "account_type": None,
                    "enterprise_account": None,
                    "user_id": None,
                    "applications": [
                        {"app_id": "daily", "app_name": "日常采集"},
                        {"app_id": "after-sale", "app_name": "售后同步"},
                        {"app_id": "daily", "app_name": "重复报告不覆盖"},
                    ],
                    "discovered_at": datetime.now(UTC).isoformat(),
                },
            ),
        ]


def test_application_catalog_returns_only_deduplicated_current_team_application_options() -> None:
    device_repository = FakeDeviceCatalogRepository()
    service = AutomationApplicationCatalogService(
        FakeSession(),  # type: ignore[arg-type]
        device_repository=device_repository,  # type: ignore[arg-type]
        worker_repository=FakeWorkerCatalogRepository(),  # type: ignore[arg-type]
    )

    assert [
        option.model_dump()
        for option in service.list_yingdao_application_options(
            actor=actor(team_id=uuid4()),
        )
    ] == [
        {"app_id": "after-sale", "app_name": "售后同步"},
        {"app_id": "daily", "app_name": "日常采集"},
    ]

    assert len(
        service.list_yingdao_application_options(
            actor=actor(team_id=uuid4()),
            device_id=device_repository.team_device_id,
        ),
    ) == 2
    with pytest.raises(DeviceNotFoundError):
        service.list_yingdao_application_options(
            actor=actor(team_id=uuid4()),
            device_id=uuid4(),
        )


def test_management_list_filters_authorized_rows_by_selected_device_apps() -> None:
    team_id = uuid4()
    actor_context = actor(team_id=team_id)
    repository = FakePresetRepository()
    now = datetime.now(UTC)
    for app_id in ("daily", "other-app"):
        repository.add(
            AutomationParameterPreset(
                preset_id=uuid4(),
                team_id=team_id,
                created_by_user_id=actor_context.user_id,
                app_id=app_id,
                name=app_id,
                common_parameters={},
                shop_overrides={},
                input_schema_snapshot={"fields": []},
                version=1,
                created_at=now,
                updated_at=now,
            ),
        )

    class SelectedDeviceCatalog:
        def list_yingdao_application_options(
            self,
            *,
            actor: ActorContext,
            device_id: UUID,
        ) -> list[YingdaoApplicationOptionRead]:
            assert actor == actor_context
            assert device_id == selected_device_id
            return [YingdaoApplicationOptionRead(app_id="daily", app_name="日常采集")]

    selected_device_id = uuid4()
    service = service_for(
        repository=repository,
        shop_ids=set(),
        application_catalog_service=SelectedDeviceCatalog(),
    )
    page = service.list_all(
        actor=actor_context,
        device_id=selected_device_id,
        pagination=PaginationParams(),
    )

    assert page.total == 1
    assert [item.app_id for item in page.items] == ["daily"]
