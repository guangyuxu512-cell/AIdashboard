"""Real Feature-DB coverage for the 0035 -> 0036 preset data migration."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.modules.automation_apps.models import AutomationParameterPreset
from app.modules.automation_apps.service import AutomationParameterPresetService


pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return config


def test_postgresql_schema_snapshot_migrates_known_values_and_diagnoses_unknown(
    postgresql_engine: Engine,
) -> None:
    """Do not infer a schema for legacy unknown JSON keys during backfill."""

    team_id, user_id, preset_id = uuid4(), uuid4(), uuid4()
    app_id = f"preset-schema-migration-{preset_id}"
    config = _alembic_config()

    command.downgrade(config, "20260912_0035")
    try:
        with postgresql_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO teams (team_id, name, enabled) "
                    "VALUES (:team_id, :name, true)",
                ),
                {"team_id": team_id, "name": f"Schema migration {team_id}"},
            )
            connection.execute(
                text(
                    "INSERT INTO users (user_id, display_name, enabled) "
                    "VALUES (:user_id, :display_name, true)",
                ),
                {"user_id": user_id, "display_name": f"Schema migration {user_id}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO automation_application_configs (
                        config_id, provider_code, app_id, schema_source,
                        input_schema, default_values, version
                    ) VALUES (
                        :config_id, 'yingdao', :app_id, 'manual',
                        CAST(:input_schema AS jsonb), CAST('{}' AS jsonb), 1
                    )
                    """,
                ),
                {
                    "config_id": uuid4(),
                    "app_id": app_id,
                    "input_schema": json.dumps(
                        {
                            "fields": [
                                {
                                    "name": "已知页码",
                                    "label": "已知页码",
                                    "type": "number",
                                    "required": False,
                                    "default_value": 1,
                                    "options": [],
                                },
                                {
                                    "name": "未使用模板字段",
                                    "label": "未使用模板字段",
                                    "type": "text",
                                    "required": False,
                                    "default_value": None,
                                    "options": [],
                                },
                            ],
                        },
                    ),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO automation_parameter_presets (
                        preset_id, team_id, created_by_user_id, app_id, name,
                        common_parameters, shop_overrides, version
                    ) VALUES (
                        :preset_id, :team_id, :user_id, :app_id, :name,
                        CAST(:common AS jsonb), CAST(:overrides AS jsonb), 1
                    )
                    """,
                ),
                {
                    "preset_id": preset_id,
                    "team_id": team_id,
                    "user_id": user_id,
                    "app_id": app_id,
                    "name": "历史预设",
                    "common": json.dumps({"已知页码": 2, "历史未知键": "保留"}),
                    "overrides": json.dumps(
                        {str(uuid4()): {"店铺历史未知键": False}},
                    ),
                },
            )

        command.upgrade(config, "head")
        with Session(postgresql_engine) as session:
            preset = session.get(AutomationParameterPreset, preset_id)
            assert preset is not None
            assert preset.input_schema_snapshot == {
                "fields": [
                    {
                        "name": "已知页码",
                        "label": "已知页码",
                        "type": "number",
                        "required": False,
                        "default_value": 1,
                        "options": [],
                    },
                ],
            }
            assert preset.common_parameters == {"已知页码": 2, "历史未知键": "保留"}
            assert AutomationParameterPresetService(session)._to_read(
                preset,
            ).invalid_parameter_names == ["历史未知键", "店铺历史未知键"]

        # A downgrade intentionally drops the new independent snapshot. The
        # re-upgrade is still deterministic for the legacy persisted values;
        # values are never cleared or guessed as new fields.
        command.downgrade(config, "20260912_0035")
        with postgresql_engine.connect() as connection:
            column_names = {
                row[0]
                for row in connection.execute(
                    text(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'automation_parameter_presets'
                        """,
                    ),
                )
            }
            assert "input_schema_snapshot" not in column_names
        command.upgrade(config, "head")
        with Session(postgresql_engine) as session:
            preset = session.get(AutomationParameterPreset, preset_id)
            assert preset is not None
            assert preset.common_parameters["历史未知键"] == "保留"
            assert preset.input_schema_snapshot["fields"][0]["name"] == "已知页码"
    finally:
        command.upgrade(config, "head")
        with postgresql_engine.begin() as connection:
            connection.execute(
                text("DELETE FROM automation_parameter_presets WHERE preset_id = :id"),
                {"id": preset_id},
            )
            connection.execute(
                text(
                    "DELETE FROM automation_application_configs "
                    "WHERE provider_code = 'yingdao' AND app_id = :app_id",
                ),
                {"app_id": app_id},
            )
            connection.execute(text("DELETE FROM users WHERE user_id = :id"), {"id": user_id})
            connection.execute(text("DELETE FROM teams WHERE team_id = :id"), {"id": team_id})
