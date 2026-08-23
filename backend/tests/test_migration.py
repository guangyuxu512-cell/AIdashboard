import importlib


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
