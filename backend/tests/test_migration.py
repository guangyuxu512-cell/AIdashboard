import importlib
from uuid import uuid4

import pytest


class OperationRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def create_table(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("create_table", name))

    def create_index(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("create_index", name))

    def add_column(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("add_column", name))

    def drop_column(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("drop_column", name))

    def alter_column(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("alter_column", name))

    def create_unique_constraint(
        self,
        name: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.calls.append(("create_unique_constraint", name))

    def execute(self, statement: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("execute", statement))

    def drop_index(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("drop_index", name))

    def drop_table(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("drop_table", name))

    def create_check_constraint(
        self,
        name: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.calls.append(("create_check_constraint", name))

    def create_foreign_key(
        self,
        name: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.calls.append(("create_foreign_key", name))

    @staticmethod
    def f(name: str) -> str:
        return name

    def drop_constraint(
        self,
        name: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        self.calls.append(("drop_constraint", name))


def test_core_domain_migration_upgrade_and_downgrade(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260818_0001_core_domain_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "users"),
        ("create_table", "devices"),
        ("create_table", "shops"),
        ("create_table", "shop_device_bindings"),
    ]
    assert (
        "create_index",
        "uq_shop_device_bindings_enabled_primary",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "shop_device_bindings"),
        ("drop_table", "shops"),
        ("drop_table", "devices"),
        ("drop_table", "users"),
    ]


def test_auth_domain_migration_upgrade_and_downgrade(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260819_0002_auth_domain_foundation",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "platform_credentials"),
        ("create_table", "shop_credential_bindings"),
        ("create_table", "shop_sessions"),
    ]
    assert (
        "create_index",
        "uq_shop_credential_bindings_enabled_shop",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "shop_sessions"),
        ("drop_table", "shop_credential_bindings"),
        ("drop_table", "platform_credentials"),
    ]


def test_worker_core_lite_migration_upgrade_and_downgrade(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260819_0003_worker_core_lite",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "worker_device_credentials"),
        ("create_table", "device_runtime"),
        ("create_table", "tasks"),
    ]

    recorder.calls.clear()
    migration.downgrade()
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "tasks"),
        ("drop_table", "device_runtime"),
        ("drop_table", "worker_device_credentials"),
    ]


def test_yingdao_skill_constraint_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260820_0004_yingdao_test_skill",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls == [
        ("drop_constraint", "ck_tasks_skill_id"),
        ("create_check_constraint", "ck_tasks_skill_id"),
    ]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [
        ("drop_constraint", "ck_tasks_skill_id"),
        ("create_check_constraint", "ck_tasks_skill_id"),
    ]


def test_provider_inventory_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260820_0005_provider_inventory",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls == [
        ("create_table", "device_provider_inventory"),
        ("drop_constraint", "ck_tasks_skill_id"),
        ("create_check_constraint", "ck_tasks_skill_id"),
    ]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [
        ("drop_constraint", "ck_tasks_skill_id"),
        ("create_check_constraint", "ck_tasks_skill_id"),
        ("drop_table", "device_provider_inventory"),
    ]


def test_management_login_session_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260821_0006_management_login_session",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert ("add_column", "shops") in recorder.calls
    assert ("create_unique_constraint", "uq_shops_platform_identity") in recorder.calls
    assert (
        "create_check_constraint",
        "shop_session_status",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert ("drop_constraint", "uq_shops_platform_identity") in recorder.calls
    assert ("drop_column", "shops") in recorder.calls


def test_shop_soft_delete_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260822_0008_shop_soft_delete",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls == [
        ("add_column", "shops"),
        ("create_index", "ix_shops_deleted_at"),
    ]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [
        ("drop_index", "ix_shops_deleted_at"),
        ("drop_column", "shops"),
    ]


def test_device_lifecycle_notification_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260822_0009_device_lifecycle_notifications",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert ("add_column", "devices") in recorder.calls
    assert recorder.calls.count(("add_column", "device_runtime")) == 2
    assert ("create_table", "notification_channels") in recorder.calls
    assert (
        "create_check_constraint",
        "ck_device_runtime_connection_status",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert ("drop_table", "notification_channels") in recorder.calls
    assert recorder.calls.count(("drop_column", "device_runtime")) == 2
    assert ("drop_column", "devices") in recorder.calls


def test_task_runtime_event_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260822_0010_task_runtime_events",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls == [
        ("create_table", "task_events"),
        ("create_index", "ix_task_events_task_seq"),
    ]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [
        ("drop_index", "ix_task_events_task_seq"),
        ("drop_table", "task_events"),
    ]


def test_automation_application_config_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260823_0011_automation_application_configs",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert ("create_table", "automation_application_configs") in recorder.calls
    assert ("drop_constraint", "ck_tasks_skill_id") in recorder.calls
    assert ("create_check_constraint", "ck_tasks_skill_id") in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert ("drop_table", "automation_application_configs") in recorder.calls


def test_device_skill_capability_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260823_0012_device_skill_capabilities",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls == [("create_table", "device_skill_capabilities")]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [("drop_table", "device_skill_capabilities")]


def test_task_execution_display_name_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260823_0013_task_execution_display_name",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls == [
        ("add_column", "tasks"),
        ("execute", "UPDATE tasks SET execution_display_name = skill_id"),
        ("alter_column", "tasks"),
    ]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [("drop_column", "tasks")]


def test_skill_classification_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260824_0014_skill_classification",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert [call[0] for call in recorder.calls] == [
        "add_column",
        "execute",
        "create_check_constraint",
    ]
    assert "system.echo" in recorder.calls[1][1]
    assert "yingdao.discover" in recorder.calls[1][1]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [
        ("drop_constraint", "ck_device_skill_capabilities_classification"),
        ("drop_column", "device_skill_capabilities"),
    ]


def test_task_query_runtime_retention_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260824_0015_task_query_runtime_retention",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert ("add_column", "tasks") in recorder.calls
    assert ("create_index", "ix_tasks_created_task") in recorder.calls
    assert ("create_index", "ix_tasks_target_created_task") in recorder.calls
    assert ("create_index", "ix_tasks_status_created_task") in recorder.calls
    assert (
        "create_index",
        "ix_tasks_terminal_finished_task",
    ) in recorder.calls
    assert (
        "create_index",
        "ix_task_events_task_type_seq",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert ("drop_column", "tasks") in recorder.calls
    assert ("create_index", "ix_tasks_status") in recorder.calls
    assert ("create_index", "ix_task_events_task_seq") in recorder.calls


def test_scheduler_v1_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260824_0016_scheduler_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "schedules"),
        ("create_table", "schedule_runs"),
    ]
    assert ("create_index", "ix_schedules_due") in recorder.calls
    assert (
        "create_index",
        "ix_schedule_runs_schedule_scheduled",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "schedule_runs"),
        ("drop_table", "schedules"),
    ]


def test_business_skill_catalog_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260825_0017_business_skill_catalog",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert ("add_column", "device_skill_capabilities") in recorder.calls
    assert (
        "create_check_constraint",
        "ck_device_skill_capabilities_input_schema_object",
    ) in recorder.calls
    assert recorder.calls.count(("alter_column", "tasks")) == 1
    assert recorder.calls.count(("alter_column", "schedules")) == 1
    assert recorder.calls.count(("drop_constraint", "ck_tasks_skill_id")) == 1
    assert recorder.calls.count(("drop_constraint", "ck_schedules_skill_id")) == 1

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls.count(("alter_column", "tasks")) == 1
    assert recorder.calls.count(("alter_column", "schedules")) == 1
    assert (
        "drop_constraint",
        "ck_device_skill_capabilities_input_schema_object",
    ) in recorder.calls
    assert ("drop_column", "device_skill_capabilities") in recorder.calls


def test_multi_shop_task_context_migration(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260826_0019_multi_shop_task_context",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "task_shops"),
        ("create_table", "schedule_shops"),
    ]
    assert ("drop_column", "tasks") in recorder.calls
    assert ("drop_column", "schedules") in recorder.calls
    assert ("drop_column", "shop_device_bindings") in recorder.calls
    assert (
        "drop_index",
        "uq_shop_device_bindings_enabled_primary",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert ("add_column", "tasks") in recorder.calls
    assert ("add_column", "schedules") in recorder.calls
    assert ("add_column", "shop_device_bindings") in recorder.calls
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "schedule_shops"),
        ("drop_table", "task_shops"),
    ]


def test_image_asset_migration_upgrade_and_downgrade(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260826_0020_image_assets_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "assets"),
        ("create_table", "task_assets"),
    ]
    assert ("create_index", "ix_task_assets_asset_task") in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "task_assets"),
        ("drop_table", "assets"),
    ]


def test_asset_foundation_v2_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260826_0021_asset_foundation_v2",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls.count(("add_column", "assets")) == 2
    assert (
        "drop_constraint",
        "ck_assets_supported_content_type",
    ) in recorder.calls
    assert [
        call for call in recorder.calls if call[0] == "create_check_constraint"
    ] == [
        ("create_check_constraint", "ck_assets_media_type"),
        ("create_check_constraint", "ck_assets_source_type"),
        ("create_check_constraint", "ck_assets_content_type_not_blank"),
    ]

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls.count(("drop_column", "assets")) == 2
    assert (
        "create_check_constraint",
        "ck_assets_supported_content_type",
    ) in recorder.calls


def test_access_foundation_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260831_0022_access_foundation_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        migration,
        "_backfill_default_team",
        lambda: recorder.calls.append(("execute", "default_team_backfill")),
    )

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "teams"),
        ("create_table", "team_memberships"),
    ]
    assert (
        "create_index",
        "ix_team_memberships_user_id",
    ) in recorder.calls
    assert (
        "create_index",
        "ix_team_memberships_active_user",
    ) in recorder.calls
    assert (
        "create_index",
        "ix_team_memberships_active_team",
    ) in recorder.calls
    assert ("execute", "default_team_backfill") in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "team_memberships"),
        ("drop_table", "teams"),
    ]


def test_access_default_team_backfill_rows_cover_empty_single_and_multiple_users() -> (
    None
):
    migration = importlib.import_module(
        "migrations.versions.20260831_0022_access_foundation_v1",
    )
    team_id = uuid4()
    user_ids = [uuid4(), uuid4()]

    assert migration._membership_rows([], team_id=team_id) == []
    single = migration._membership_rows(user_ids[:1], team_id=team_id)
    multiple = migration._membership_rows(user_ids, team_id=team_id)

    assert len(single) == 1
    assert len(multiple) == 2
    assert {row["user_id"] for row in multiple} == set(user_ids)
    assert all(row["team_id"] == team_id for row in multiple)
    assert all(row["role_code"] == "member" for row in multiple)
    assert all(row["data_scope"] == "team" for row in multiple)
    assert all(row["enabled"] is True for row in multiple)


def test_human_auth_migration_upgrade_and_downgrade(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260831_0023_human_auth_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    migration.upgrade()
    assert recorder.calls.count(("add_column", "users")) == 2
    assert (
        "create_check_constraint",
        "ck_users_login_name_normalized",
    ) in recorder.calls
    assert ("create_unique_constraint", "uq_users_login_name") in recorder.calls
    assert ("create_table", "human_sessions") in recorder.calls
    assert ("create_index", "ix_human_sessions_token_hash") in recorder.calls
    assert ("create_index", "ix_human_sessions_user_id") in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [
        ("drop_index", "ix_human_sessions_user_id"),
        ("drop_index", "ix_human_sessions_token_hash"),
        ("drop_table", "human_sessions"),
        ("drop_constraint", "uq_users_login_name"),
        ("drop_constraint", "ck_users_login_name_normalized"),
        ("drop_column", "users"),
        ("drop_column", "users"),
    ]


def test_asset_scope_migration_upgrade_and_downgrade(monkeypatch: object) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260901_0024_asset_scope_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        migration,
        "_backfill_asset_team",
        lambda: recorder.calls.append(("execute", "asset_team_backfill")),
    )

    migration.upgrade()
    assert recorder.calls.count(("add_column", "assets")) == 2
    assert ("execute", "asset_team_backfill") in recorder.calls
    assert ("alter_column", "assets") in recorder.calls
    assert (
        "create_foreign_key",
        "fk_assets_team_id_teams",
    ) in recorder.calls
    assert (
        "create_foreign_key",
        "fk_assets_created_by_user_id_users",
    ) in recorder.calls
    assert (
        "create_index",
        "ix_assets_team_created_asset",
    ) in recorder.calls
    assert (
        "create_index",
        "ix_assets_team_creator_created_asset",
    ) in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [
        ("drop_index", "ix_assets_team_creator_created_asset"),
        ("drop_index", "ix_assets_team_created_asset"),
        ("drop_constraint", "fk_assets_created_by_user_id_users"),
        ("drop_constraint", "fk_assets_team_id_teams"),
        ("drop_column", "assets"),
        ("drop_column", "assets"),
    ]


def test_access_management_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260902_0025_access_management_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]
    monkeypatch.setattr(
        migration,
        "_backfill_existing_memberships",
        lambda: recorder.calls.append(("execute", "module_access_backfill")),
    )

    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "membership_module_accesses"),
    ]
    assert ("execute", "module_access_backfill") in recorder.calls

    recorder.calls.clear()
    migration.downgrade()
    assert recorder.calls == [("drop_table", "membership_module_accesses")]


def test_access_management_backfill_grants_only_current_formal_modules(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260902_0025_access_management_v1",
    )
    membership_ids = [uuid4(), uuid4()]

    class ScalarRows:
        def scalars(self) -> list[object]:
            return membership_ids

    class Connection:
        inserted_rows: list[dict[str, object]] | None = None

        def execute(
            self,
            statement: object,
            parameters: list[dict[str, object]] | None = None,
        ) -> ScalarRows:
            del statement
            if parameters is not None:
                self.inserted_rows = parameters
            return ScalarRows()

    connection = Connection()
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)

    migration._backfill_existing_memberships()

    assert connection.inserted_rows is not None
    assert len(connection.inserted_rows) == len(membership_ids) * len(
        migration.BACKFILL_MODULE_CODES,
    )
    assert {row["membership_id"] for row in connection.inserted_rows} == set(
        membership_ids,
    )
    assert {row["module_code"] for row in connection.inserted_rows} == set(
        migration.BACKFILL_MODULE_CODES,
    )
    assert "foundation" not in migration.BACKFILL_MODULE_CODES


def test_asset_scope_backfill_requires_exactly_one_default_team(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260901_0024_asset_scope_v1",
    )

    class ScalarRows:
        def __init__(self, rows: list[object]) -> None:
            self.rows = rows

        def scalars(self) -> "ScalarRows":
            return self

        def all(self) -> list[object]:
            return self.rows

    class Connection:
        def __init__(self, rows: list[object]) -> None:
            self.rows = rows

        def execute(self, statement: object) -> ScalarRows:
            del statement
            return ScalarRows(self.rows)

    for rows in ([], [uuid4(), uuid4()]):
        connection = Connection(rows)
        monkeypatch.setattr(
            migration.op,
            "get_bind",
            lambda connection=connection: connection,
        )
        with pytest.raises(RuntimeError, match="唯一的默认团队"):
            migration._backfill_asset_team()


def test_ai_workbench_foundation_migration_upgrade_and_downgrade(
    monkeypatch: object,
) -> None:
    migration = importlib.import_module(
        "migrations.versions.20260903_0026_ai_workbench_backend_foundation_v1",
    )
    recorder = OperationRecorder()
    monkeypatch.setattr(migration, "op", recorder)  # type: ignore[attr-defined]

    assert migration.revision == "20260903_0026"
    assert migration.down_revision == "20260902_0025"
    migration.upgrade()
    assert [call for call in recorder.calls if call[0] == "create_table"] == [
        ("create_table", "template_groups"),
        ("create_table", "product_material_groups"),
        ("create_table", "prompt_templates"),
        ("create_table", "material_group_assets"),
        ("create_table", "material_group_template_bindings"),
    ]
    assert not {
        "generation_jobs",
        "generation_items",
        "provider_configs",
        "queue_tasks",
    } & {name for operation, name in recorder.calls if operation == "create_table"}

    recorder.calls.clear()
    migration.downgrade()
    assert [call for call in recorder.calls if call[0] == "drop_table"] == [
        ("drop_table", "material_group_template_bindings"),
        ("drop_table", "material_group_assets"),
        ("drop_table", "prompt_templates"),
        ("drop_table", "product_material_groups"),
        ("drop_table", "template_groups"),
    ]
