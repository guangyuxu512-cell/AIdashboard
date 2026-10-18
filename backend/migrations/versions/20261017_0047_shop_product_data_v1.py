"""Four product-data tables, exact raw metrics and atomic generation references."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261017_0047"
down_revision = "20261015_0046"
branch_labels = None
depends_on = None

# Frozen migration-local definitions: never import mutable application models.
METRICS = (
    ("product_show_cnt", "count", 5), ("product_click_cnt", "count", 5),
    ("product_show_click_converse_uv_rate", "ratio", 4), ("click_add_to_cart_uv", "count", 5),
    ("product_add_show_converse_uv_ratio", "ratio", 4), ("net_pay_cnt", "count", 5),
    ("pay_cnt_exclude_refund", "count", 5), ("product_click_pay_converse_uv_rate", "ratio", 4),
    ("pay_refund_ratio", "ratio", 4), ("pay_amt", "amount", 3), ("pay_cnt", "count", 5),
    ("pay_ucnt", "count", 5), ("per_user_price", "amount", 3),
    ("pay_refund_success_amt", "amount", 3), ("pay_refund_success_order_cnt", "count", 5),
    ("product_show_ucnt", "count", 5), ("product_click_ucnt", "count", 5),
)
TABLES = ("shop_product_data_products", "shop_product_data_series", "shop_product_data_generations", "shop_product_data_metric_snapshots")


def _timestamps():
    return [sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            for name in ("created_at", "updated_at")]


def _exact_keys(column, keys):
    array = "ARRAY[" + ",".join("'" + key + "'" for key in keys) + "]"
    return f"jsonb_typeof({column}) = 'object' AND {column} ?& {array} AND ({column} - {array}) = '{{}}'::jsonb"


def _metric_checks():
    codes = tuple(code for code, _, _ in METRICS)
    checks = [sa.CheckConstraint(_exact_keys("raw_units", codes), name="unit_keys"),
              sa.CheckConstraint(_exact_keys("metric_states", codes), name="state_keys")]
    for index, (code, kind, observed_unit) in enumerate(METRICS):
        unit = f"raw_units -> '{code}'"
        state = f"metric_states ->> '{code}'"
        checks.extend((
            sa.CheckConstraint(f"({unit} = 'null'::jsonb OR (jsonb_typeof({unit}) = 'number' AND (raw_units ->> '{code}') ~ '^[0-9]+$'))", name=f"unit_{index}"),
            sa.CheckConstraint(f"jsonb_typeof(metric_states -> '{code}') = 'string' AND {state} IN ('available','missing','null','invalid')", name=f"state_{index}"),
            sa.CheckConstraint(f"{code} IS NULL OR {code}::text NOT IN ('NaN','Infinity','-Infinity')", name=f"finite_{index}"),
            sa.CheckConstraint(f"{state} <> 'available' OR ({code} IS NOT NULL AND {code} >= 0 AND (raw_units ->> '{code}' = '{observed_unit}') IS TRUE"
                               + (f" AND {code} = trunc({code})" if kind == "count" else "") + ")", name=f"available_{index}"),
        ))
    return checks


def upgrade():
    op.create_table(TABLES[0],
        sa.Column("shop_product_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), sa.ForeignKey("shops.shop_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("platform_product_id", sa.String(32), nullable=False),
        *_timestamps(), sa.PrimaryKeyConstraint("shop_product_id"),
        sa.UniqueConstraint("shop_id", "platform", "platform_product_id", name="uq_spd_product_identity"),
        sa.UniqueConstraint("shop_product_id", "shop_id", name="uq_spd_product_shop"),
        sa.CheckConstraint("platform = 'douyin'", name="platform"),
        sa.CheckConstraint("platform_product_id ~ '^[0-9]{1,32}$'", name="product_id"),
    )
    op.create_table(TABLES[1],
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), sa.ForeignKey("shops.shop_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("rolling_series_hash", sa.String(64), nullable=False),
        sa.Column("period", sa.String(8), nullable=False),
        sa.Column("sale_type", sa.String(8), nullable=False),
        sa.Column("content_type", sa.String(8), nullable=False),
        sa.Column("request_contract", sa.String(64), nullable=False),
        sa.Column("metric_contract", sa.String(64), nullable=False),
        sa.Column("next_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_generation_id", sa.Uuid()),
        sa.Column("previous_generation_id", sa.Uuid()),
        *_timestamps(), sa.PrimaryKeyConstraint("series_id"),
        sa.UniqueConstraint("shop_id", "rolling_series_hash", name="uq_spd_series_scope"),
        sa.UniqueConstraint("series_id", "shop_id", name="uq_spd_series_shop"),
        sa.CheckConstraint("rolling_series_hash ~ '^[a-f0-9]{64}$'", name="scope_hash"),
        sa.CheckConstraint("period IN ('1d','7d','30d') AND sale_type = '1' AND content_type = '1'", name="native_scope"),
        sa.CheckConstraint("next_sequence > 0 AND published_sequence >= 0 AND published_sequence < next_sequence", name="sequences"),
        sa.CheckConstraint("(current_generation_id IS NULL AND published_sequence = 0 AND previous_generation_id IS NULL) OR (current_generation_id IS NOT NULL AND published_sequence > 0)", name="current_pair"),
        sa.CheckConstraint("previous_generation_id IS NULL OR current_generation_id <> previous_generation_id", name="distinct_pointers"),
    )
    op.create_table(TABLES[2],
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requested_team_id", sa.Uuid(), sa.ForeignKey("teams.team_id", ondelete="RESTRICT")),
        sa.Column("submission_key", sa.Uuid(), nullable=False),
        sa.Column("period", sa.String(8), nullable=False),
        sa.Column("date_type", sa.String(8), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("source_scope_hash", sa.String(64), nullable=False),
        sa.Column("request_scope", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("received_pages", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expected_total", sa.Integer()), sa.Column("received_total", sa.Integer()),
        sa.Column("raw_complete_rows", sa.Integer()), sa.Column("unit_complete_rows", sa.Integer()),
        sa.Column("pages_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stage", sa.String(32), nullable=False), sa.Column("failure_code", sa.String(96)),
        sa.Column("lease_id", sa.Uuid()), sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        *_timestamps(), sa.PrimaryKeyConstraint("generation_id"),
        sa.ForeignKeyConstraint(["series_id", "shop_id"], [TABLES[1] + ".series_id", TABLES[1] + ".shop_id"], ondelete="RESTRICT", name="fk_spd_generation_series_shop"),
        sa.UniqueConstraint("generation_id", "shop_id", name="uq_spd_generation_shop"),
        sa.UniqueConstraint("generation_id", "series_id", name="uq_spd_generation_series"),
        sa.UniqueConstraint("series_id", "sequence", name="uq_spd_generation_sequence"),
        sa.UniqueConstraint("requested_by_user_id", "submission_key", name="uq_spd_generation_actor_key"),
        sa.CheckConstraint("source_scope_hash ~ '^[a-f0-9]{64}$'", name="scope_hash"),
        sa.CheckConstraint("sequence > 0", name="sequence"),
        sa.CheckConstraint("status IN ('pending','running','succeeded','failed')", name="status"),
        sa.CheckConstraint("start_date <= end_date", name="date_order"),
        sa.CheckConstraint("(period = '1d' AND date_type = '20' AND end_date - start_date = 0) OR (period = '7d' AND date_type = '21' AND end_date - start_date = 6) OR (period = '30d' AND date_type = '23' AND end_date - start_date = 29)", name="native_window"),
        sa.CheckConstraint("received_pages >= 0 AND (expected_total IS NULL OR expected_total > 0) AND (received_total IS NULL OR received_total >= 0) AND (raw_complete_rows IS NULL OR raw_complete_rows >= 0) AND (unit_complete_rows IS NULL OR unit_complete_rows >= 0)", name="counts"),
        sa.CheckConstraint("(received_total IS NULL OR expected_total IS NULL OR received_total <= expected_total) AND (raw_complete_rows IS NULL OR (received_total IS NOT NULL AND raw_complete_rows <= received_total)) AND (unit_complete_rows IS NULL OR (raw_complete_rows IS NOT NULL AND unit_complete_rows <= raw_complete_rows))", name="coverage_counts"),
        sa.CheckConstraint("stage IN ('queued','session_preparation','signing','platform_response','response_parse','collection_coverage','publication','execution','complete')", name="stage"),
        sa.CheckConstraint(_exact_keys("request_scope", ("shop_id", "period", "start_date", "end_date", "timezone", "platform", "sale_type", "content_type", "request_contract", "metric_contract")), name="scope_keys"),
        sa.CheckConstraint(
            "(status = 'pending' AND lease_id IS NULL AND lease_until IS NULL AND started_at IS NULL AND finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
            "(status = 'running' AND lease_id IS NOT NULL AND lease_until IS NOT NULL AND started_at IS NOT NULL AND finished_at IS NULL AND published_at IS NULL AND NOT pages_complete) OR "
            "(status = 'succeeded' AND lease_id IS NULL AND lease_until IS NULL AND started_at IS NOT NULL AND finished_at IS NOT NULL AND published_at IS NOT NULL AND pages_complete AND expected_total IS NOT NULL AND received_total IS NOT NULL AND received_total = expected_total AND raw_complete_rows IS NOT NULL AND unit_complete_rows IS NOT NULL AND failure_code IS NULL) OR "
            "(status = 'failed' AND lease_id IS NULL AND lease_until IS NULL AND finished_at IS NOT NULL AND published_at IS NULL AND NOT pages_complete AND failure_code IS NOT NULL)",
            name="state_fields",
        ),
    )
    op.create_index("uq_spd_active_slice", TABLES[2], ["shop_id", "source_scope_hash"], unique=True, postgresql_where=sa.text("status IN ('pending','running')"))
    op.create_index("ix_spd_generation_actor", TABLES[2], ["requested_by_user_id", "requested_team_id", "created_at", "generation_id"])
    op.create_table(TABLES[3],
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("shop_product_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column("observed_title", sa.Text()), sa.Column("observed_image_url", sa.Text()),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_units", postgresql.JSONB(), nullable=False),
        sa.Column("metric_states", postgresql.JSONB(), nullable=False),
        *(sa.Column(code, sa.Numeric()) for code, _, _ in METRICS),
        sa.PrimaryKeyConstraint("generation_id", "shop_product_id"),
        sa.ForeignKeyConstraint(["generation_id", "shop_id"], [TABLES[2] + ".generation_id", TABLES[2] + ".shop_id"], ondelete="RESTRICT", name="fk_spd_snapshot_generation_shop"),
        sa.ForeignKeyConstraint(["shop_product_id", "shop_id"], [TABLES[0] + ".shop_product_id", TABLES[0] + ".shop_id"], ondelete="RESTRICT", name="fk_spd_snapshot_product_shop"),
        *_metric_checks(),
    )
    for column, name in (("current_generation_id", "fk_spd_series_current"), ("previous_generation_id", "fk_spd_series_previous")):
        op.create_foreign_key(name, TABLES[1], TABLES[2], [column, "series_id"], ["generation_id", "series_id"], ondelete="RESTRICT")


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("0047 downgrade requires an online exact Feature target check")
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT current_database()")) != "control_center_feat_shop_product_data":
        raise RuntimeError("0047 downgrade permits only the registered Product Data Feature database")
    connection.execute(sa.text("LOCK TABLE " + ", ".join(TABLES) + " IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT " + " OR ".join("EXISTS(SELECT 1 FROM " + table + ")" for table in TABLES))):
        raise RuntimeError("0047 business data exists; retain compatible readers, facts and schema")
    for name in ("fk_spd_series_current", "fk_spd_series_previous"):
        op.drop_constraint(name, TABLES[1], type_="foreignkey")
    for table in (TABLES[3], TABLES[2], TABLES[1], TABLES[0]):
        op.drop_table(table)
