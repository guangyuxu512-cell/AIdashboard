"""Exact registered Feature target guard for Product Data PostgreSQL tests.

Never infer safety from the shared cluster's port, a prefix or a role alone.
No secret or database URL is returned by this helper.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
import pytest

from app.core.config import get_settings


FEATURE_DATABASE = "control_center_feat_shop_product_data_batch_queue"
FEATURE_ROLE = "control_center_dev_user"
FEATURE_PORT = 35433


def guarded_feature_engine():
    settings = get_settings()
    if settings.database_url is None:
        pytest.skip("Product Data Feature connection was not delivered; PostgreSQL not verified")
    url = make_url(str(settings.database_url))
    if (url.database, url.username, url.host, url.port) != (
        FEATURE_DATABASE, FEATURE_ROLE, "127.0.0.1", FEATURE_PORT,
    ):
        raise RuntimeError("Product Data PG guard rejected an unregistered target before connecting")
    engine = create_engine(url, echo=False)
    try:
        with engine.connect() as connection:
            facts = dict(connection.execute(text(
                "SELECT current_database() AS database, current_user AS role, "
                "rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                "FROM pg_roles WHERE rolname = current_user"
            )).mappings().one())
            if facts["database"] != FEATURE_DATABASE or facts["role"] != FEATURE_ROLE:
                raise RuntimeError("Product Data PG guard rejected the actual database or role")
            if any(facts[key] for key in ("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls")):
                raise RuntimeError("Product Data PG guard rejected elevated role flags")
        return engine, facts
    except Exception:
        engine.dispose()
        raise
