from sqlalchemy import Engine, inspect, text

import pytest

pytestmark = pytest.mark.integration


def test_postgresql_preserves_historical_facts_without_central_shop_credentials(postgresql_engine: Engine) -> None:
    inspector = inspect(postgresql_engine)
    tables = set(inspector.get_table_names())
    assert {"users", "devices", "tasks", "schedules", "historical_shop_identities",
            "historical_team_shop_accesses", "historical_task_shop_refs",
            "historical_schedule_shop_refs", "shop_operating_daily_metrics"} <= tables
    assert not ({"shops", "shop_device_bindings", "shop_sessions",
                 "shop_credential_bindings", "platform_credentials"} & tables)
    assert any(fk["referred_table"] == "historical_shop_identities"
               for fk in inspector.get_foreign_keys("shop_operating_daily_metrics"))
    with postgresql_engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261116_0056"
