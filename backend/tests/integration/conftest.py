from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, make_url, text
from sqlalchemy.engine import URL

from app.core.config import get_settings
from app.core.database import get_database_engine


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CORE_TABLES = {
    "users",
    "shops",
    "devices",
    "shop_device_bindings",
    "platform_credentials",
    "shop_credential_bindings",
    "shop_sessions",
    "worker_device_credentials",
    "device_runtime",
    "tasks",
}
DESTRUCTIVE_TEST_DATABASE = "control_center_dev"


def _alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return config


@pytest.fixture(scope="session")
def postgresql_url() -> URL:
    database_url = get_settings().database_url
    if database_url is None:
        pytest.skip(
            "PostgreSQL integration tests require BACKEND_DATABASE_URL; "
            "no real database was configured",
        )

    url = make_url(str(database_url))
    if not url.drivername.startswith("postgresql"):
        pytest.fail("PostgreSQL integration tests refuse non-PostgreSQL databases")
    if url.database != DESTRUCTIVE_TEST_DATABASE:
        pytest.fail(
            "Destructive migration tests only run against the dedicated "
            f"{DESTRUCTIVE_TEST_DATABASE} database",
        )
    return url


@pytest.fixture(scope="session")
def postgresql_engine(postgresql_url: URL) -> Engine:
    engine = get_database_engine()
    assert engine.url == postgresql_url

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        assert connection.scalar(text("SELECT current_database()")) == DESTRUCTIVE_TEST_DATABASE

    alembic_config = _alembic_config()
    command.current(alembic_config)
    command.upgrade(alembic_config, "head")
    assert CORE_TABLES <= set(inspect(engine).get_table_names())

    database_is_at_base = False
    try:
        command.downgrade(alembic_config, "base")
        database_is_at_base = True
        assert CORE_TABLES.isdisjoint(inspect(engine).get_table_names())
        command.upgrade(alembic_config, "head")
        database_is_at_base = False
    finally:
        if database_is_at_base:
            command.upgrade(alembic_config, "head")

    assert CORE_TABLES <= set(inspect(engine).get_table_names())
    return engine
