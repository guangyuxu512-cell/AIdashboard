from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, func, inspect, select, table, text

from app.core.database import Base
from app.modules.product_selection.models import (
    ProductSelectionCandidate, ProductSelectionObservation,
    ProductSelectionRun,
)
from tests.integration.test_postgresql_product_selection import selection_context, _save


pytestmark = pytest.mark.integration
SELECTION_TABLES = {"product_selection_candidates", "product_selection_observations", "product_selection_runs"}


def _row_counts(connection, names):
    # Identifiers come from PostgreSQL introspection, not user strings.
    return {
        name: connection.scalar(select(func.count()).select_from(table(name)))
        for name in names
    }


def test_0043_metadata_and_downgrade_preserve_0042_facts(
    postgresql_url, postgresql_engine, selection_context,
):
    assert postgresql_url.database in {
        "control_center_feat_product_selection",
    }, "Destructive lifecycle only targets this rebuildable Feature DB"
    observation_id = _save(selection_context)[0]
    engine = postgresql_engine
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == postgresql_url.database
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == ["20261010_0043"]
        if _row_counts(connection, {"product_selection_runs"})["product_selection_runs"]:
            pytest.skip("Refuse to downgrade an environment containing run history")
        existing = set(inspect(connection).get_table_names()) - SELECTION_TABLES - {"alembic_version"}
        before = _row_counts(connection, existing | (SELECTION_TABLES - {"product_selection_runs"}))
        metadata = MetaData(naming_convention=Base.metadata.naming_convention)
        metadata.reflect(bind=connection, only=["users", "teams", "shops"])
        for model in (ProductSelectionCandidate, ProductSelectionObservation, ProductSelectionRun):
            model.__table__.to_metadata(metadata)

        def include_object(obj, name, kind, reflected, compare_to):
            return (
                name in SELECTION_TABLES if kind == "table"
                else getattr(getattr(obj, "table", None), "name", None) in SELECTION_TABLES
            )

        context = MigrationContext.configure(connection, opts={"include_object": include_object})
        assert compare_metadata(context, metadata) == []
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    command.downgrade(config, "20261010_0042")
    try:
        with engine.connect() as connection:
            assert "product_selection_runs" not in inspect(connection).get_table_names()
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261010_0042"
            assert before == _row_counts(connection, before)
            assert connection.scalar(text("SELECT observation_id FROM product_selection_observations WHERE observation_id=:key"), {"key": observation_id}) == observation_id
    finally:
        # Restore Head even if a retention assertion fails; never leave the
        # developer's rebuildable database downgraded after this test.
        command.upgrade(config, "head")
    with engine.connect() as connection:
        assert SELECTION_TABLES <= set(inspect(connection).get_table_names())
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == ["20261010_0043"]
        assert before == _row_counts(connection, before)
