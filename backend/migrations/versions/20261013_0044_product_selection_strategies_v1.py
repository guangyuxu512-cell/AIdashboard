"""Saved selection strategies; retain all applied 0042/0043 facts and runs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261013_0044"
down_revision = "20261010_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_selection_strategies",
        sa.Column("strategy_id", sa.Uuid(), primary_key=True),
        sa.Column("team_id", sa.Uuid(), sa.ForeignKey("teams.team_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_shop_id", sa.Uuid(), sa.ForeignKey("shops.shop_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=False),
        sa.Column("schedule_config", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_product_selection_strategies_name_not_blank")),
        sa.CheckConstraint("version > 0", name=op.f("ck_product_selection_strategies_version_positive")),
        sa.CheckConstraint("jsonb_typeof(conditions) = 'object'", name=op.f("ck_product_selection_strategies_conditions_object")),
        sa.CheckConstraint("jsonb_typeof(schedule_config) = 'object'", name=op.f("ck_product_selection_strategies_schedule_object")),
    )
    op.create_index("ix_selection_strategy_team_updated", "product_selection_strategies", ["team_id", "updated_at", "strategy_id"])
    op.create_index("ix_selection_strategy_shop", "product_selection_strategies", ["request_shop_id", "strategy_id"])
    op.add_column("product_selection_runs", sa.Column("strategy_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_selection_run_strategy", "product_selection_runs", "product_selection_strategies", ["strategy_id"], ["strategy_id"], ondelete="RESTRICT")
    op.create_index("ix_selection_run_strategy_created", "product_selection_runs", ["strategy_id", "created_at", "run_id"])


def downgrade() -> None:
    # Verify the live target in this execution path, not only in test wrappers
    # or a configured URL. This active Slot has one registered rebuildable DB.
    # Offline SQL cannot establish that identity and must not emit drop DDL.
    if op.get_context().as_sql:
        raise RuntimeError("0044 downgrade requires online verification of the registered Feature database")
    connection = op.get_bind()
    database = connection.scalar(sa.text("SELECT current_database()"))
    if database != "control_center_feat_product_selection":
        raise RuntimeError("0044 downgrade only permits the registered rebuildable Product Selection Feature database")
    # Lock both writers before inspecting data so a concurrent insert cannot
    # escape the check. Main/Integration/production never reach this lock.
    connection.execute(sa.text("LOCK TABLE product_selection_strategies, product_selection_runs IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM product_selection_strategies) OR EXISTS(SELECT 1 FROM product_selection_runs WHERE strategy_id IS NOT NULL)")):
        raise RuntimeError("Selection strategy data exists; retain schema and use a compatible application rollback")
    op.drop_index("ix_selection_run_strategy_created", table_name="product_selection_runs")
    op.drop_constraint("fk_selection_run_strategy", "product_selection_runs", type_="foreignkey")
    op.drop_column("product_selection_runs", "strategy_id")
    op.drop_index("ix_selection_strategy_shop", table_name="product_selection_strategies")
    op.drop_index("ix_selection_strategy_team_updated", table_name="product_selection_strategies")
    op.drop_table("product_selection_strategies")
