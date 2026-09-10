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
    "teams",
    "team_memberships",
    "human_sessions",
    "shops",
    "devices",
    "shop_device_bindings",
    "platform_credentials",
    "shop_credential_bindings",
    "shop_sessions",
    "worker_device_credentials",
    "device_runtime",
    "device_provider_inventory",
    "device_skill_capabilities",
    "tasks",
    "task_shops",
    "assets",
    "task_assets",
    "notification_channels",
    "automation_application_configs",
    "schedules",
    "schedule_shops",
    "schedule_runs",
}
FEATURE_DATABASE_PREFIX = "control_center_feat_"
INTEGRATION_DATABASE = "control_center_integration"


def _is_allowed_integration_database(database: str | None) -> bool:
    return database == INTEGRATION_DATABASE or bool(
        database and database.startswith(FEATURE_DATABASE_PREFIX),
    )


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
    if not _is_allowed_integration_database(url.database):
        pytest.fail(
            "PostgreSQL integration tests only run against a dedicated "
            "Feature database or control_center_integration",
        )
    return url


@pytest.fixture(scope="session")
def postgresql_engine(postgresql_url: URL) -> Engine:
    engine = get_database_engine()
    assert engine.url == postgresql_url

    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        assert _is_allowed_integration_database(
            connection.scalar(text("SELECT current_database()")),
        )

    alembic_config = _alembic_config()
    command.current(alembic_config)
    command.upgrade(alembic_config, "head")
    assert CORE_TABLES <= set(inspect(engine).get_table_names())

    assert CORE_TABLES <= set(inspect(engine).get_table_names())
    return engine
