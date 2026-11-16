"""0053 removes only the retired central library and its grants."""
import pytest
from sqlalchemy import inspect, text


pytestmark = pytest.mark.integration


def test_retired_library_tables_and_permissions_are_gone(postgresql_engine):
    retired = {
        "product_collection_persist_receipts", "product_library_product_versions",
        "product_collection_upload_receipts", "product_collection_capture_attempts",
        "product_collection_dispatches", "product_collection_items", "product_collection_requests",
        "product_library_products", "product_library_groups",
    }
    with postgresql_engine.connect() as connection:
        assert connection.scalar(text("select version_num from alembic_version")) == "20261116_0054"
        tables = set(inspect(connection).get_table_names())
        assert not retired.intersection(tables)
        assert {"product_selection_candidates", "product_selection_runs", "product_selection_strategies",
                "shop_product_data_products", "shop_product_data_metric_snapshots", "shop_operating_daily_metrics",
                "worker_rpa_shop_inventories", "tasks", "task_events", "assets", "schedules"} <= tables
        for table in ("team_module_accesses", "membership_module_accesses"):
            assert connection.scalar(text("select count(*) from " + table + " where module_code = 'product-library'")) == 0
        assert connection.scalar(text("""
            SELECT count(*) FROM api_tokens token,
                LATERAL json_array_elements_text(token.permissions) AS item(value)
            WHERE item.value LIKE '% /api/v1/product-library%'
               OR item.value LIKE '% /api/v1/product-collection%'
               OR item.value LIKE '% /api/v1/mobile-collection%'
               OR item.value LIKE '% /api/v1/product-data/collection%'
        """)) == 0
