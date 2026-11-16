import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.modules.access.models import Team, TeamModuleAccess
from app.modules.access.repository import TeamModuleAccessRepository


pytestmark = pytest.mark.integration


def test_retired_workbench_tables_are_removed_without_removing_execution_assets(postgresql_engine):
    with postgresql_engine.connect() as connection:
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '20261114_0052'
        tables = set(inspect(connection).get_table_names())
    assert not tables.intersection({
        'ai_models', 'template_groups', 'prompt_templates', 'product_material_groups',
        'material_group_assets', 'material_group_template_bindings', 'generation_jobs',
        'generation_items', 'generation_item_assets', 'generation_provider_executions',
    })
    assert {'assets', 'task_assets', 'tasks', 'task_events', 'schedules',
            'worker_rpa_shop_inventories'} <= tables


def test_legacy_library_grant_is_read_safely_before_retirement(postgresql_engine):
    with Session(postgresql_engine) as session:
        team = Team(name='feature-retired-library-grant-test')
        session.add(team)
        session.flush()
        session.add_all([
            TeamModuleAccess(team_id=team.team_id, module_code='task'),
            TeamModuleAccess(team_id=team.team_id, module_code='product-library'),
        ])
        session.flush()
        repository = TeamModuleAccessRepository(session)
        assert repository.list_codes(team.team_id) == ['task']
        assert repository.list_codes_for_teams([team.team_id]) == {team.team_id: ['task']}
        assert session.get(TeamModuleAccess, (team.team_id, 'product-library')) is not None
        session.rollback()
