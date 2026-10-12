"""Exercise the migration itself without connecting to any shared database."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest


FEATURE_DATABASE = "control_center_feat_product_selection"


class MigrationProbe:
    def __init__(self, database, *, offline=False):
        self.database = database
        self.offline = offline
        self.calls = []
        # A configured URL/name must not replace current_database() evidence.
        self.url = SimpleNamespace(database=FEATURE_DATABASE)

    def get_context(self):
        return SimpleNamespace(as_sql=self.offline)

    def get_bind(self):
        self.calls.append("bind")
        return self

    def scalar(self, statement):
        query = str(statement)
        self.calls.append(query)
        if query == "SELECT current_database()":
            return self.database
        if query.startswith("SELECT EXISTS"):
            return False
        pytest.fail("Unexpected migration query")

    def execute(self, statement):
        self.calls.append(str(statement))

    def drop_index(self, *args, **kwargs):
        self.calls.append("drop_index")

    def drop_constraint(self, *args, **kwargs):
        self.calls.append("drop_constraint")

    def drop_column(self, *args, **kwargs):
        self.calls.append("drop_column")

    def drop_table(self, *args, **kwargs):
        self.calls.append("drop_table")


def migration(probe):
    path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "20261013_0044_product_selection_strategies_v1.py"
    spec = spec_from_file_location("selection_strategy_guard", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = probe
    return module


@pytest.mark.parametrize("database", [
    "control_center_dev", "control_center_integration", "control_center_production",
    "postgres", "control_center_feat_other_task", FEATURE_DATABASE + "_backup", None,
])
def test_0044_rejects_non_registered_target_before_lock_or_ddl(database):
    probe = MigrationProbe(database)
    with pytest.raises(RuntimeError, match="registered.*Feature"):
        migration(probe).downgrade()
    assert probe.calls == ["bind", "SELECT current_database()"]


def test_0044_offline_downgrade_cannot_emit_unverified_ddl():
    probe = MigrationProbe(FEATURE_DATABASE, offline=True)
    with pytest.raises(RuntimeError, match="online verification"):
        migration(probe).downgrade()
    assert probe.calls == []


def test_0044_registered_target_is_verified_before_existing_lock_and_data_check():
    probe = MigrationProbe(FEATURE_DATABASE)
    migration(probe).downgrade()
    assert probe.calls[:3] == [
        "bind", "SELECT current_database()",
        "LOCK TABLE product_selection_strategies, product_selection_runs IN ACCESS EXCLUSIVE MODE",
    ]
    assert probe.calls[3].startswith("SELECT EXISTS")
    assert probe.calls[4:] == ["drop_index", "drop_constraint", "drop_column", "drop_index", "drop_index", "drop_table"]
