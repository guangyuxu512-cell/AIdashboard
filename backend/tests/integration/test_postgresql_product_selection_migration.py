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
)


pytestmark = pytest.mark.integration
SELECTION_TABLES = {"product_selection_candidates", "product_selection_observations"}


def _row_counts(connection, names):
    # Identifiers come from PostgreSQL introspection, not user strings.
    return {
        name: connection.scalar(select(func.count()).select_from(table(name)))
        for name in names
    }


def test_0042_metadata_and_rebuildable_migration_preserve_existing_domains(
    postgresql_url, postgresql_engine,
):
    assert postgresql_url.database in {
        "control_center_feat_product_selection", "control_center_integration",
    }, "Migration lifecycle only targets this registered Feature/Integration DB"
    engine = postgresql_engine
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == postgresql_url.database
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == ["20261010_0042"]
        if any(_row_counts(connection, SELECTION_TABLES).values()):
            pytest.skip("Refuse to downgrade an environment containing real selection facts")
        existing = set(inspect(connection).get_table_names()) - SELECTION_TABLES - {"alembic_version"}
        before = _row_counts(connection, existing)
        metadata = MetaData(naming_convention=Base.metadata.naming_convention)
        metadata.reflect(bind=connection, only=["users", "teams", "shops"])
        for model in (ProductSelectionCandidate, ProductSelectionObservation):
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
    command.downgrade(config, "20260924_0041")
    try:
        with engine.connect() as connection:
            assert not SELECTION_TABLES.intersection(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260924_0041"
            assert before == _row_counts(connection, existing)
    finally:
        # Restore Head even if a retention assertion fails; never leave the
        # developer's rebuildable database downgraded after this test.
        command.upgrade(config, "head")
    with engine.connect() as connection:
        assert SELECTION_TABLES <= set(inspect(connection).get_table_names())
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == ["20261010_0042"]
        assert before == _row_counts(connection, existing)
        assert not any(_row_counts(connection, SELECTION_TABLES).values())
