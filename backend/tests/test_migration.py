import importlib


class OperationRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def create_table(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("create_table", name))

    def create_index(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("create_index", name))

    def drop_index(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("drop_index", name))

    def drop_table(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append(("drop_table", name))


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
