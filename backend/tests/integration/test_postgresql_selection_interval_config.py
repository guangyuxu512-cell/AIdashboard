"""0045 saved N/unique Schedule roundtrip; saving never submits a Run or platform request."""

import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.modules.product_selection.models import ProductSelectionRun as Run, ProductSelectionStrategy as Strategy
from app.modules.schedules.models import Schedule
from tests.integration.test_postgresql_product_selection import selection_context, _api_client
from tests.integration.test_postgresql_selection_strategies import _save

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("hours", [1, 2, 3, 5, 6, 12])
def test_interval_json_save_read_edit_syncs_one_plan_without_platform(selection_context, hours):
    context = selection_context
    with Session(context[0]) as session:
        before_runs = session.scalar(select(func.count()).select_from(Run))
        before_plans = session.scalar(select(func.count()).select_from(Schedule))
    saved = _save(context, schedule={"scheduled": True, "kind": "hourly", "interval_hours": hours, "daily_time": "09:00", "timezone": "Asia/Shanghai"})
    with _api_client(context) as client:
        headers = {"X-Team-ID": str(context[1][0])}
        response = client.get(f"/api/v1/product-selection/strategies/{saved.strategy_id}", headers=headers)
        assert response.status_code == 200
        dto = response.json()
        assert dto["schedule"]["interval_hours"] == hours and dto["next_run_at"] is not None
        assert dto["schedule_available"] and not dto["schedule_execution_enabled"]
        body = {key: dto[key] for key in ["name", "shop_id", "enabled", "conditions", "schedule"]}
        body["schedule"]["interval_hours"] = hours + 1
        body["expected_version"] = dto["version"]
        changed = client.put(f"/api/v1/product-selection/strategies/{saved.strategy_id}", headers=headers, json=body)
        assert changed.status_code == 200
        assert client.get(f"/api/v1/product-selection/strategies/{saved.strategy_id}", headers=headers).json()["schedule"]["interval_hours"] == hours + 1
    with Session(context[0]) as session:
        assert session.get(Strategy, saved.strategy_id).schedule_config["interval_hours"] == hours + 1
        assert session.scalar(select(func.count()).select_from(Run)) == before_runs
        assert session.scalar(select(func.count()).select_from(Schedule)) == before_plans + 1
        plan = session.scalar(select(Schedule).where(Schedule.selection_strategy_id == saved.strategy_id))
        assert plan.interval_hours == hours + 1 and plan.local_time is None
