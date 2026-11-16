"""Historical product metrics stay readable without a live collector."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.access.service import ActorContextService
from app.modules.product_data.service import ProductDataService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.users.models import User
from tests.test_product_data_service_postgres import complete, query, submit


pytestmark = pytest.mark.integration


def test_saved_metrics_remain_readable_and_collection_is_unavailable(postgresql_engine):
    with postgresql_engine.connect() as connection:
        assert connection.scalar(text("select current_database()")) == "control_center_feat_windows_execution_slim"
        assert connection.scalar(text("select count(*) from shop_product_data_generations "
                                      "where status in ('pending','running')")) == 0
        connection.rollback()
        outer = connection.begin()
        session = Session(connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
        try:
            user = User(display_name="historical-metrics-fixture", enabled=True, is_super_account=True)
            shop = Shop(display_name="historical-metrics-fixture", enabled=True,
                        platform=ShopPlatform.DOUYIN, platform_shop_id="900000001")
            session.add_all([user, shop])
            session.flush()
            actor = ActorContextService(session).resolve(user_id=user.user_id, requested_team_id=None)
            settings = Settings(product_data_collection_execution_enabled=True)
            service = ProductDataService(session, settings=settings)
            graph = SimpleNamespace(session=session, users=[user], shops=[shop], actors=[actor],
                                    settings=settings, service=service)
            receipt, lease = submit(graph)
            service.publish(receipt.generation_id, lease, complete(receipt, shop, total=1))
            result = service.list(actor, query(receipt))
            assert result.total == 1
            assert result.items[0].product_id == "9000000000000000000"
            assert result.coverage.collection_available is False
        finally:
            session.close()
            outer.rollback()
