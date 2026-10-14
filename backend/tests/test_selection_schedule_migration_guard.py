"""Check the actual 0045 entrypoint without opening a database."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest


class Probe:
    def __init__(self, database=None, *, offline=False, incompatible=False):
        self.database, self.offline, self.incompatible = database, offline, incompatible
        self.calls = []

    def get_context(self):
        return SimpleNamespace(as_sql=self.offline)

    def get_bind(self):
        self.calls.append("bind")
        return self

    def scalar(self, statement):
        query = str(statement)
        self.calls.append(query)
        return self.database if query == "SELECT current_database()" else self.incompatible

    def execute(self, statement):
        self.calls.append(str(statement))

    def __getattr__(self, name):
        if name == "f": return lambda value: value
        if name.startswith(("drop_", "add_", "alter_", "create_")):
            return lambda *args, **kwargs: self.calls.append(name)
        raise AttributeError(name)


def migration(probe):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/20261013_0045_product_selection_server_schedule_v1.py"
    spec = spec_from_file_location("selection_schedule_migration", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = probe
    return module


@pytest.mark.parametrize("database", ["control_center_integration", "control_center_dev", "control_center_production", "control_center_feat_other", None])
def test_non_registered_downgrade_refuses_before_lock_ddl(database):
    probe = Probe(database)
    with pytest.raises(RuntimeError, match="registered rebuildable"):
        migration(probe).downgrade()
    assert probe.calls == ["bind", "SELECT current_database()"]


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
def test_offline_refuses_unverified_ddl(action):
    probe = Probe(offline=True)
    with pytest.raises(RuntimeError, match="online"):
        getattr(migration(probe), action)()
    assert probe.calls == []


@pytest.mark.parametrize("action", ["upgrade", "downgrade"])
def test_incompatible_old_pc_or_new_server_facts_are_not_modified(action):
    probe = Probe("control_center_feat_product_selection", incompatible=True)
    with pytest.raises(RuntimeError):
        getattr(migration(probe), action)()
    assert any(call.startswith("LOCK TABLE") for call in probe.calls)
    assert not any(call.startswith(("drop_", "add_", "alter_", "create_")) for call in probe.calls)


def test_compatible_pc_and_a_are_preserved_without_delete_or_update():
    probe = Probe("control_center_feat_product_selection")
    module = migration(probe)
    module._legacy_check = lambda connection, table, logical: f"ck_{table}_ck_{table}_{logical}"
    module.upgrade()
    assert probe.calls[1].startswith("LOCK TABLE")
    assert not any("DELETE " in call or "UPDATE " in call for call in probe.calls)
