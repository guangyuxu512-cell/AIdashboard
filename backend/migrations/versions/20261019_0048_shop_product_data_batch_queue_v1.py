"""Add a durable, finite multi-Shop queue to Product Data.

Revision ID: 20261019_0048
Revises: 20261017_0047
"""

from alembic import op
import sqlalchemy as sa


revision = "20261019_0048"
down_revision = "20261017_0047"
branch_labels = None
depends_on = None

BATCHES = "shop_product_data_collection_batches"
GENERATIONS = "shop_product_data_generations"
PRODUCT_DATA_TABLES = (
    BATCHES,
    "shop_product_data_metric_snapshots",
    GENERATIONS,
    "shop_product_data_series",
    "shop_product_data_products",
)
FEATURE_DATABASE = "control_center_feat_shop_product_data_batch_queue"

NEW_STATE_FIELDS = (
    "(status = 'pending' AND attempt_count = 0 AND lease_id IS NULL AND "
    "lease_until IS NULL AND last_heartbeat_at IS NULL AND started_at IS NULL AND "
    "finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
    "(status = 'running' AND attempt_count > 0 AND lease_id IS NOT NULL AND "
    "lease_until IS NOT NULL AND last_heartbeat_at IS NOT NULL AND started_at IS NOT NULL AND "
    "finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
    "(status = 'succeeded' AND attempt_count > 0 AND lease_id IS NULL AND "
    "lease_until IS NULL AND last_heartbeat_at IS NOT NULL AND started_at IS NOT NULL AND "
    "finished_at IS NOT NULL AND published_at IS NOT NULL AND pages_complete AND "
    "expected_total IS NOT NULL AND received_total IS NOT NULL AND received_total = expected_total AND "
    "raw_complete_rows IS NOT NULL AND unit_complete_rows IS NOT NULL AND failure_code IS NULL) OR "
    "(status = 'failed' AND attempt_count > 0 AND lease_id IS NULL AND lease_until IS NULL AND "
    "last_heartbeat_at IS NOT NULL AND finished_at IS NOT NULL AND published_at IS NULL AND "
    "NOT pages_complete AND failure_code IS NOT NULL)"
)

OLD_STATE_FIELDS = (
    "(status = 'pending' AND lease_id IS NULL AND lease_until IS NULL AND started_at IS NULL AND "
    "finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
    "(status = 'running' AND lease_id IS NOT NULL AND lease_until IS NOT NULL AND "
    "started_at IS NOT NULL AND finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
    "(status = 'succeeded' AND lease_id IS NULL AND lease_until IS NULL AND started_at IS NOT NULL AND "
    "finished_at IS NOT NULL AND published_at IS NOT NULL AND pages_complete AND expected_total IS NOT NULL AND "
    "received_total IS NOT NULL AND received_total = expected_total AND raw_complete_rows IS NOT NULL AND "
    "unit_complete_rows IS NOT NULL AND failure_code IS NULL) OR "
    "(status = 'failed' AND lease_id IS NULL AND lease_until IS NULL AND finished_at IS NOT NULL AND "
    "published_at IS NULL AND NOT pages_complete AND failure_code IS NOT NULL)"
)


def _timestamps():
    return [
        sa.Column(
            name,
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        for name in ("created_at", "updated_at")
    ]


def _scalar(connection, statement: str):
    return connection.scalar(sa.text(statement))


def upgrade():
    connection = op.get_bind()
    if _scalar(
        connection,
        "SELECT EXISTS ("
        "SELECT 1 FROM shop_product_data_generations "
        "WHERE status = 'running' GROUP BY shop_id HAVING count(*) > 1)",
    ):
        raise RuntimeError(
            "0048 requires at most one existing running Product Data generation per Shop",
        )

    op.create_table(
        BATCHES,
        sa.Column("collection_batch_id", sa.Uuid(), nullable=False),
        sa.Column(
            "requested_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_team_id",
            sa.Uuid(),
            sa.ForeignKey("teams.team_id", ondelete="RESTRICT"),
        ),
        sa.Column("submission_key", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(8), nullable=False),
        sa.Column("sale_type", sa.String(8), nullable=False),
        sa.Column("content_type", sa.String(8), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("collection_batch_id"),
        sa.UniqueConstraint(
            "requested_by_user_id",
            "submission_key",
            name="uq_spd_batch_actor_key",
        ),
        sa.CheckConstraint(
            "period IN ('1d','7d','30d') AND sale_type = '1' AND content_type = '1'",
            name="native_scope",
        ),
    )
    op.add_column(
        GENERATIONS,
        sa.Column("collection_batch_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        GENERATIONS,
        sa.Column("batch_position", sa.Integer(), nullable=True),
    )
    op.add_column(
        GENERATIONS,
        sa.Column("attempt_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        GENERATIONS,
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Every 0047 generation becomes one deterministic compatibility batch.
    # No business fact, pointer, original status, lease or audit timestamp is rewritten.
    op.execute(sa.text(
        "INSERT INTO shop_product_data_collection_batches ("
        "collection_batch_id, requested_by_user_id, requested_team_id, submission_key, "
        "period, sale_type, content_type, created_at, updated_at) "
        "SELECT generation_id, requested_by_user_id, requested_team_id, submission_key, "
        "period, request_scope ->> 'sale_type', request_scope ->> 'content_type', created_at, updated_at "
        "FROM shop_product_data_generations",
    ))
    op.execute(sa.text(
        "UPDATE shop_product_data_generations SET "
        "collection_batch_id = generation_id, batch_position = 0, "
        "attempt_count = CASE WHEN status = 'pending' THEN 0 ELSE 1 END, "
        "last_heartbeat_at = CASE WHEN status = 'pending' THEN NULL "
        "ELSE COALESCE(updated_at, started_at, created_at) END",
    ))

    op.alter_column(GENERATIONS, "collection_batch_id", nullable=False)
    op.alter_column(GENERATIONS, "batch_position", nullable=False)
    op.alter_column(
        GENERATIONS,
        "attempt_count",
        nullable=False,
        server_default="0",
    )
    op.drop_constraint(
        "uq_spd_generation_actor_key",
        GENERATIONS,
        type_="unique",
    )
    op.drop_index("uq_spd_active_slice", table_name=GENERATIONS)
    op.drop_constraint("state_fields", GENERATIONS, type_="check")
    op.create_foreign_key(
        "fk_spd_generation_batch",
        GENERATIONS,
        BATCHES,
        ["collection_batch_id"],
        ["collection_batch_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_spd_batch_shop",
        GENERATIONS,
        ["collection_batch_id", "shop_id"],
    )
    op.create_unique_constraint(
        "uq_spd_batch_position",
        GENERATIONS,
        ["collection_batch_id", "batch_position"],
    )
    op.create_index(
        "uq_spd_running_shop",
        GENERATIONS,
        ["shop_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "ix_spd_generation_queue",
        GENERATIONS,
        ["status", "created_at", "generation_id"],
    )
    op.create_index(
        "ix_spd_generation_batch",
        GENERATIONS,
        ["collection_batch_id", "batch_position"],
    )
    op.create_check_constraint(
        "state_fields",
        GENERATIONS,
        NEW_STATE_FIELDS,
    )
    op.create_check_constraint(
        "queue_counts",
        GENERATIONS,
        "batch_position >= 0 AND attempt_count >= 0",
    )


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("0048 downgrade requires an online exact Feature target check")
    connection = op.get_bind()
    if _scalar(connection, "SELECT current_database()") != FEATURE_DATABASE:
        raise RuntimeError(
            "0048 downgrade permits only the registered Product Data batch-queue Feature database",
        )
    connection.execute(sa.text(
        "LOCK TABLE " + ", ".join(PRODUCT_DATA_TABLES) + " IN ACCESS EXCLUSIVE MODE",
    ))
    incompatible = _scalar(connection, """
        SELECT EXISTS (
            SELECT 1
            FROM shop_product_data_collection_batches AS batch
            FULL OUTER JOIN shop_product_data_generations AS generation
              ON generation.collection_batch_id = batch.collection_batch_id
            WHERE batch.collection_batch_id IS NULL
               OR generation.generation_id IS NULL
               OR batch.collection_batch_id <> generation.generation_id
               OR generation.batch_position <> 0
               OR batch.requested_by_user_id <> generation.requested_by_user_id
               OR batch.requested_team_id IS DISTINCT FROM generation.requested_team_id
               OR batch.submission_key <> generation.submission_key
               OR batch.period <> generation.period
               OR batch.sale_type <> generation.request_scope ->> 'sale_type'
               OR batch.content_type <> generation.request_scope ->> 'content_type'
               OR batch.created_at <> generation.created_at
               OR batch.updated_at <> generation.updated_at
               OR generation.attempt_count <> CASE
                    WHEN generation.status = 'pending' THEN 0 ELSE 1 END
               OR generation.last_heartbeat_at IS DISTINCT FROM CASE
                    WHEN generation.status = 'pending' THEN NULL
                    ELSE COALESCE(
                        generation.updated_at,
                        generation.started_at,
                        generation.created_at
                    )
                  END
        )
    """)
    if incompatible:
        raise RuntimeError(
            "0048 queue history is not an exact one-to-one 0047 backfill; retain schema and audit data",
        )
    if _scalar(connection, """
        SELECT EXISTS (
            SELECT 1 FROM shop_product_data_generations
            GROUP BY requested_by_user_id, submission_key
            HAVING count(*) > 1
        )
    """):
        raise RuntimeError("0048 generations cannot restore the 0047 actor idempotency key")
    if _scalar(connection, """
        SELECT EXISTS (
            SELECT 1 FROM shop_product_data_generations
            WHERE status IN ('pending','running')
            GROUP BY shop_id, source_scope_hash
            HAVING count(*) > 1
        )
    """):
        raise RuntimeError("0048 generations cannot restore the 0047 active-slice key")

    op.drop_constraint("state_fields", GENERATIONS, type_="check")
    op.drop_constraint("queue_counts", GENERATIONS, type_="check")
    op.drop_index("ix_spd_generation_batch", table_name=GENERATIONS)
    op.drop_index("ix_spd_generation_queue", table_name=GENERATIONS)
    op.drop_index("uq_spd_running_shop", table_name=GENERATIONS)
    op.drop_constraint("uq_spd_batch_position", GENERATIONS, type_="unique")
    op.drop_constraint("uq_spd_batch_shop", GENERATIONS, type_="unique")
    op.drop_constraint("fk_spd_generation_batch", GENERATIONS, type_="foreignkey")
    op.create_unique_constraint(
        "uq_spd_generation_actor_key",
        GENERATIONS,
        ["requested_by_user_id", "submission_key"],
    )
    op.create_index(
        "uq_spd_active_slice",
        GENERATIONS,
        ["shop_id", "source_scope_hash"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending','running')"),
    )
    op.create_check_constraint(
        "state_fields",
        GENERATIONS,
        OLD_STATE_FIELDS,
    )
    op.drop_column(GENERATIONS, "last_heartbeat_at")
    op.drop_column(GENERATIONS, "attempt_count")
    op.drop_column(GENERATIONS, "batch_position")
    op.drop_column(GENERATIONS, "collection_batch_id")
    op.drop_table(BATCHES)
