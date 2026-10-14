from pathlib import Path
from threading import Event, Thread

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, event, text
from sqlalchemy.orm import Session

from app.modules.product_selection.models import ProductSelectionRun as Run, ProductSelectionStrategy as Strategy
from tests.integration.test_postgresql_product_selection import selection_context, _save
from tests.integration.test_postgresql_selection_runs import _submit
from tests.integration.test_postgresql_selection_strategies import _config, _save as save_strategy

pytestmark = pytest.mark.integration


def _config_migration(database_name):
    assert database_name == "control_center_feat_product_selection", "Destructive migration tests only use the assigned rebuildable Feature"
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    return config


def test_0044_empty_downgrade_upgrade_preserves_0042_facts_and_0043_runs(selection_context, postgresql_url):
    context = selection_context
    observation = _save(context)[0]
    receipt = _submit(context)
    config = _config_migration(postgresql_url.database)
    try:
        command.downgrade(config, "20261010_0043")
        with context[0].connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261010_0043"
            assert connection.scalar(text("SELECT observation_id FROM product_selection_observations WHERE observation_id=:key"), {"key": observation}) == observation
            assert connection.scalar(text("SELECT status FROM product_selection_runs WHERE run_id=:key"), {"key": receipt.execution_run_id}) == "pending"
    finally:
        command.upgrade(config, "head")
    with Session(context[0]) as session:
        assert session.get(Run, receipt.execution_run_id).strategy_id is None
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "20261013_0045"


def test_0044_refuses_data_loss_and_retains_strategy(selection_context, postgresql_url):
    saved = save_strategy(selection_context, schedule={"scheduled": False})
    config = _config_migration(postgresql_url.database)
    command.downgrade(config, "20261013_0044")
    try:
        with pytest.raises(RuntimeError, match="retain schema"):
            command.downgrade(config, "20261010_0043")
        with Session(selection_context[0]) as session:
            assert session.get(Strategy, saved.strategy_id).version == 1
            assert session.scalar(text("SELECT version_num FROM alembic_version")) == "20261013_0044"
    finally:
        command.upgrade(config, "head")


def test_0044_lock_waits_for_concurrent_writer_then_refuses_loss(selection_context, postgresql_url):
    context = selection_context
    config = _config_migration(postgresql_url.database)
    command.downgrade(config, "20261013_0044")
    lock_started, results = Event(), []
    def observe(connection, cursor, statement, *args):
        if statement.startswith("LOCK TABLE product_selection_strategies,"):
            lock_started.set()
    def downgrade():
        try:
            command.downgrade(config, "20261010_0043")
            results.append("unexpected success")
        except RuntimeError:
            results.append("refused")
    event.listen(Engine, "before_cursor_execute", observe)
    try:
        with Session(context[0]) as writer:
            config_row = _config(context)
            row = Strategy(team_id=context[1][0], created_by_user_id=context[2][0], request_shop_id=context[3][0], name=config_row.name, version=1, enabled=True, conditions=config_row.conditions.model_dump(mode="json"), schedule_config=config_row.schedule.model_dump(mode="json"))
            writer.add(row)
            writer.flush()
            thread = Thread(target=downgrade)
            thread.start()
            assert lock_started.wait(timeout=10)
            writer.commit()
            thread.join(timeout=20)
            assert not thread.is_alive() and results == ["refused"]
            assert writer.get(Strategy, row.strategy_id) is not None
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
        command.upgrade(config, "head")
