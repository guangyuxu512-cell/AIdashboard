from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from app.core.database import get_database_engine
from app.modules.ai_workbench.repository import GenerationRepository


pytestmark = pytest.mark.integration
FEATURE_DATABASE = "control_center_feat_ai_workbench_real_api"
BACKEND_ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = "20260906_0031"
HEAD_REVISION = "20260906_0032"


def alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return config


def revision(engine: Engine) -> str:
    with engine.connect() as connection:
        return connection.scalar(text("SELECT version_num FROM alembic_version"))


def test_generation_job_model_migration_backfill_and_roundtrip() -> None:
    engine = get_database_engine()
    if not engine.url.drivername.startswith("postgresql"):
        pytest.fail("AI workbench real API integration tests require PostgreSQL")
    if engine.url.database != FEATURE_DATABASE:
        pytest.fail(f"AI workbench tests only run against {FEATURE_DATABASE}")

    config = alembic_config()
    if revision(engine) == HEAD_REVISION:
        command.downgrade(config, BASE_REVISION)
    assert revision(engine) == BASE_REVISION

    team_id = uuid4()
    user_id = uuid4()
    job_id = uuid4()
    item_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO teams (team_id, name, enabled) "
                "VALUES (:team_id, :name, true)",
            ),
            {"team_id": team_id, "name": "0032 Migration Team"},
        )
        connection.execute(
            text(
                "INSERT INTO users (user_id, display_name, enabled) "
                "VALUES (:user_id, :display_name, true)",
            ),
            {"user_id": user_id, "display_name": "0032 Migration User"},
        )
        connection.execute(
            text(
                """
                INSERT INTO generation_jobs (
                    generation_job_id,
                    team_id,
                    created_by_user_id,
                    created_by_display_name,
                    work_mode,
                    mode,
                    status,
                    submission_key,
                    submission_fingerprint
                ) VALUES (
                    :job_id,
                    :team_id,
                    :user_id,
                    '0032 Migration User',
                    'INSTANT',
                    'NORMAL_GENERATION',
                    'PENDING',
                    :submission_key,
                    :fingerprint
                )
                """,
            ),
            {
                "job_id": job_id,
                "team_id": team_id,
                "user_id": user_id,
                "submission_key": f"migration-{job_id}",
                "fingerprint": "a" * 64,
            },
        )

    try:
        command.upgrade(config, HEAD_REVISION)
        assert revision(engine) == HEAD_REVISION
        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("generation_jobs")
        }
        assert columns["model_id"]["nullable"] is False
        with engine.connect() as connection:
            expected_model_id = connection.scalar(
                text(
                    """
                    SELECT model_id
                    FROM ai_models
                    WHERE provider_code = 'toapis'
                      AND model_code = 'gpt-image-2'
                      AND enabled IS TRUE
                      AND is_default IS TRUE
                    """,
                ),
            )
            assert expected_model_id is not None
            assert connection.scalar(
                text(
                    "SELECT model_id FROM generation_jobs "
                    "WHERE generation_job_id = :job_id",
                ),
                {"job_id": job_id},
            ) == expected_model_id

        command.downgrade(config, BASE_REVISION)
        assert revision(engine) == BASE_REVISION
        assert "model_id" not in {
            column["name"]
            for column in inspect(engine).get_columns("generation_jobs")
        }

        command.upgrade(config, HEAD_REVISION)
        assert revision(engine) == HEAD_REVISION
        assert "model_id" in {
            column["name"]
            for column in inspect(engine).get_columns("generation_jobs")
        }

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO generation_items (
                        generation_item_id,
                        generation_job_id,
                        position,
                        status,
                        final_prompt,
                        output_role,
                        output_format,
                        size,
                        output_ordinal
                    ) VALUES (
                        :item_id,
                        :job_id,
                        0,
                        'PENDING',
                        '0032 provider execution lock regression',
                        'MAIN_IMAGE',
                        'SINGLE',
                        '1:1',
                        0
                    )
                    """,
                ),
                {"item_id": item_id, "job_id": job_id},
            )
        with Session(engine) as session:
            locked_item = GenerationRepository(session).get_item_for_execution(
                item_id,
            )
            assert locked_item is not None
            assert locked_item.job.model_id is not None
            session.rollback()
    finally:
        if revision(engine) == BASE_REVISION:
            command.upgrade(config, HEAD_REVISION)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM generation_items "
                    "WHERE generation_item_id = :item_id",
                ),
                {"item_id": item_id},
            )
            connection.execute(
                text(
                    "DELETE FROM generation_jobs "
                    "WHERE generation_job_id = :job_id",
                ),
                {"job_id": job_id},
            )
            connection.execute(
                text("DELETE FROM users WHERE user_id = :user_id"),
                {"user_id": user_id},
            )
            connection.execute(
                text("DELETE FROM teams WHERE team_id = :team_id"),
                {"team_id": team_id},
            )
