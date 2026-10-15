"""Team blocking, immutable result membership and closed basic-info attempts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261015_0046"
down_revision = "20261013_0045"
branch_labels = None
depends_on = None

COUNTS = "(operation_kind = 'rank' AND supplemented_count + supplement_failed_count <= saved_count) OR (operation_kind = 'basic_info' AND saved_count = 0 AND supplemented_count + supplement_failed_count <= 1)"
TARGET = "(operation_kind = 'rank' AND target_observation_id IS NULL) OR (operation_kind = 'basic_info' AND target_observation_id IS NOT NULL AND strategy_id IS NULL AND result_detail_version IS NULL)"


def _counts_name(connection):
    known = {"ck_product_selection_runs_supplement_counts", "ck_product_selection_runs_ck_product_selection_runs_supplement_counts"}
    found = [c["name"] for c in sa.inspect(connection).get_check_constraints("product_selection_runs") if c["name"] in known]
    if len(found) != 1:
        raise RuntimeError("0046 existing counts constraint identity requires review")
    return found[0]


def upgrade():
    if op.get_context().as_sql:
        raise RuntimeError("0046 requires online constraint compatibility verification")
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE product_selection_candidates, product_selection_observations, product_selection_runs IN ACCESS EXCLUSIVE MODE"))
    counts_name = _counts_name(connection)
    op.add_column("product_selection_candidates", sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("product_selection_candidates", sa.Column("blocked_changed_at", sa.DateTime(timezone=True)))
    op.add_column("product_selection_candidates", sa.Column("blocked_changed_by_user_id", sa.Uuid()))
    op.add_column("product_selection_candidates", sa.Column("discovery_tracking_version", sa.Integer()))
    op.create_foreign_key("fk_selection_candidate_block_actor", "product_selection_candidates", "users", ["blocked_changed_by_user_id"], ["user_id"], ondelete="RESTRICT")
    op.create_check_constraint(op.f("ck_product_selection_candidates_block_actor_pair"), "product_selection_candidates", "(blocked_changed_at IS NULL) = (blocked_changed_by_user_id IS NULL)")
    op.create_check_constraint(op.f("ck_product_selection_candidates_tracking_version"), "product_selection_candidates", "discovery_tracking_version IS NULL OR discovery_tracking_version = 1")
    op.add_column("product_selection_observations", sa.Column("basic_info_status", postgresql.JSONB(none_as_null=True)))
    op.add_column("product_selection_observations", sa.Column("basic_info_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint(op.f("ck_product_selection_observations_basic_version"), "product_selection_observations", "basic_info_version >= 0")
    op.create_check_constraint(op.f("ck_product_selection_observations_basic_status_object"), "product_selection_observations", "basic_info_status IS NULL OR jsonb_typeof(basic_info_status) = 'object'")
    op.add_column("product_selection_runs", sa.Column("operation_kind", sa.String(16), nullable=False, server_default="rank"))
    op.add_column("product_selection_runs", sa.Column("target_observation_id", sa.Uuid()))
    op.add_column("product_selection_runs", sa.Column("result_detail_version", sa.Integer()))
    op.create_foreign_key("fk_selection_run_basic_observation", "product_selection_runs", "product_selection_observations", ["target_observation_id"], ["observation_id"], ondelete="RESTRICT")
    op.create_check_constraint(op.f("ck_product_selection_runs_operation_kind"), "product_selection_runs", "operation_kind IN ('rank','basic_info')")
    op.create_check_constraint(op.f("ck_product_selection_runs_operation_target"), "product_selection_runs", TARGET)
    op.create_check_constraint(op.f("ck_product_selection_runs_detail_version"), "product_selection_runs", "result_detail_version IS NULL OR result_detail_version = 1")
    op.drop_constraint(op.f(counts_name), "product_selection_runs", type_="check")
    op.create_check_constraint(op.f("ck_product_selection_runs_supplement_counts"), "product_selection_runs", COUNTS)
    op.create_index("ix_selection_run_basic_target", "product_selection_runs", ["target_observation_id", "created_at", "run_id"], postgresql_where=sa.text("operation_kind = 'basic_info'"))
    op.create_table("product_selection_result_items",
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("execution_run_id", sa.Uuid(), sa.ForeignKey("product_selection_runs.run_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("observation_id", sa.Uuid(), sa.ForeignKey("product_selection_observations.observation_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("discovery_scope_hash", sa.String(64), nullable=False),
        sa.Column("discovery_state", sa.String(16), nullable=False),
        sa.Column("hit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("item_id"),
        sa.UniqueConstraint("execution_run_id", "observation_id", name="uq_selection_result_run_observation"),
        sa.CheckConstraint("discovery_state IN ('new','known','unknown')", name="discovery_state"),
        sa.CheckConstraint("discovery_scope_hash ~ '^[a-f0-9]{64}$'", name="discovery_hash"),
        sa.CheckConstraint("jsonb_typeof(snapshot) = 'object'", name="snapshot_object"),
    )
    op.create_index("ix_selection_result_discovery", "product_selection_result_items", ["discovery_scope_hash", "observation_id", "hit_at"])
    op.create_index("ix_selection_result_hit", "product_selection_result_items", ["hit_at", "observation_id"])


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("0046 downgrade requires the registered rebuildable Feature database")
    connection = op.get_bind()
    if connection.engine.url.database != "control_center_feat_product_selection":
        raise RuntimeError("0046 downgrade only permits the registered Product Selection Feature database")
    connection.execute(sa.text("LOCK TABLE product_selection_candidates, product_selection_observations, product_selection_runs, product_selection_result_items, audit_logs IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text(
        "SELECT EXISTS(SELECT 1 FROM product_selection_result_items) OR "
        "EXISTS(SELECT 1 FROM product_selection_runs WHERE operation_kind <> 'rank' OR result_detail_version IS NOT NULL) OR "
        "EXISTS(SELECT 1 FROM product_selection_candidates WHERE blocked OR blocked_changed_at IS NOT NULL OR discovery_tracking_version IS NOT NULL) OR "
        "EXISTS(SELECT 1 FROM product_selection_observations WHERE basic_info_status IS NOT NULL OR basic_info_version <> 0) OR "
        "EXISTS(SELECT 1 FROM audit_logs WHERE action IN ('product_selection.block_candidate','product_selection.restore_candidate'))"
    )):
        raise RuntimeError("0046 result/attempt/blocking semantics exist; retain compatible readers and schema")
    op.drop_table("product_selection_result_items")
    op.drop_index("ix_selection_run_basic_target", table_name="product_selection_runs")
    op.drop_constraint(op.f("ck_product_selection_runs_supplement_counts"), "product_selection_runs", type_="check")
    op.create_check_constraint(op.f("ck_product_selection_runs_supplement_counts"), "product_selection_runs", "supplemented_count + supplement_failed_count <= saved_count")
    for name in ("operation_kind", "operation_target", "detail_version"):
        op.drop_constraint(op.f("ck_product_selection_runs_" + name), "product_selection_runs", type_="check")
    op.drop_constraint("fk_selection_run_basic_observation", "product_selection_runs", type_="foreignkey")
    for name in ("result_detail_version", "target_observation_id", "operation_kind"):
        op.drop_column("product_selection_runs", name)
    for name in ("basic_version", "basic_status_object"):
        op.drop_constraint(op.f("ck_product_selection_observations_" + name), "product_selection_observations", type_="check")
    for name in ("basic_info_status", "basic_info_version"):
        op.drop_column("product_selection_observations", name)
    for name in ("block_actor_pair", "tracking_version"):
        op.drop_constraint(op.f("ck_product_selection_candidates_" + name), "product_selection_candidates", type_="check")
    op.drop_constraint("fk_selection_candidate_block_actor", "product_selection_candidates", type_="foreignkey")
    for name in ("blocked", "blocked_changed_at", "blocked_changed_by_user_id", "discovery_tracking_version"):
        op.drop_column("product_selection_candidates", name)
