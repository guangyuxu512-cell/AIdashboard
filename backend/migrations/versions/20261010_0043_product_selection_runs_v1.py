"""Business-only manual executions and independently replayable receipts.

Revision ID: 20261010_0043
Revises: 20261010_0042

0042 facts are retained. Application rollback retains this schema. A schema
downgrade is only allowed in a rebuildable Feature DB with zero run rows.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261010_0043"
down_revision: str | None = "20261010_0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_selection_runs",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("request_shop_id", sa.Uuid(), nullable=False),
        sa.Column("submission_key", sa.Uuid(), nullable=False),
        sa.Column("reused_run_id", sa.Uuid()),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("request_conditions", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("result_count", sa.Integer()),
        sa.Column("saved_count", sa.Integer(), nullable=False),
        sa.Column("supplemented_count", sa.Integer(), nullable=False),
        sa.Column("supplement_failed_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(96)),
        sa.Column("error_stage", sa.String(32)),
        sa.Column("platform_business_code", postgresql.JSONB()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("lease_id", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_product_selection_runs")),
        sa.ForeignKeyConstraint(["team_id"], ["teams.team_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["request_shop_id"], ["shops.shop_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reused_run_id"], ["product_selection_runs.run_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("team_id", "created_by_user_id", "submission_key", name="uq_selection_run_submission"),
        sa.CheckConstraint("status IN ('pending','running','succeeded','partial','failed','interrupted','reused')", name="status"),
        sa.CheckConstraint("(status = 'reused') = (reused_run_id IS NOT NULL)", name="reuse_state"),
        sa.CheckConstraint("reused_run_id IS NULL OR reused_run_id <> run_id", name="reuse_not_self"),
        sa.CheckConstraint("reused_run_id IS NULL OR (lease_id IS NULL AND lease_expires_at IS NULL AND started_at IS NULL AND finished_at IS NULL)", name="reuse_not_execution"),
        sa.CheckConstraint("reused_run_id IS NULL OR (result_count IS NULL AND saved_count = 0 AND supplemented_count = 0 AND supplement_failed_count = 0 AND error_code IS NULL AND error_stage IS NULL AND platform_business_code IS NULL)", name="reuse_not_result"),
        sa.CheckConstraint("stage IN ('queued','session','rank','persistence','basic_info','completed')", name="stage"),
        sa.CheckConstraint("request_fingerprint ~ '^[a-f0-9]{64}$'", name="request_hash"),
        sa.CheckConstraint("jsonb_typeof(request_conditions) = 'object'", name="request_object"),
        sa.CheckConstraint("result_count IS NULL OR result_count >= 0", name="result_non_negative"),
        sa.CheckConstraint("saved_count >= 0 AND supplemented_count >= 0 AND supplement_failed_count >= 0", name="counts_non_negative"),
        sa.CheckConstraint("supplemented_count + supplement_failed_count <= saved_count", name="supplement_counts"),
        sa.CheckConstraint("platform_business_code IS NULL OR jsonb_typeof(platform_business_code) IN ('string','number')", name="business_code_scalar"),
    )
    op.create_index("uq_selection_run_active_request", "product_selection_runs", ["team_id", "request_shop_id", "request_fingerprint"], unique=True, postgresql_where=sa.text("status IN ('pending', 'running')"))
    # One bounded manual execution globally, even with several Backend workers.
    op.create_index("uq_selection_run_running", "product_selection_runs", [sa.text("(1)")], unique=True, postgresql_where=sa.text("status = 'running'"))
    op.create_index("ix_selection_run_pending", "product_selection_runs", ["status", "created_at", "run_id"])
    op.create_index("ix_selection_run_team_created", "product_selection_runs", ["team_id", "created_at", "run_id"])
    op.add_column("product_selection_observations", sa.Column("last_run_id", sa.Uuid()))
    op.create_foreign_key(op.f("fk_product_selection_observations_last_run_id_product_selection_runs"), "product_selection_observations", "product_selection_runs", ["last_run_id"], ["run_id"], ondelete="RESTRICT")


def downgrade() -> None:
    connection = op.get_bind()
    database = connection.scalar(sa.text("SELECT current_database()"))
    if not isinstance(database, str) or not database.startswith("control_center_feat_"):
        raise RuntimeError("0043 downgrade only permits an explicitly rebuildable Feature database")
    # Lock before inspecting emptiness so a concurrent receipt cannot be lost.
    connection.execute(sa.text("LOCK TABLE product_selection_runs IN ACCESS EXCLUSIVE MODE"))
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM product_selection_runs)")):
        raise RuntimeError("0043 contains run history; retain schema for application rollback")
    op.drop_constraint(op.f("fk_product_selection_observations_last_run_id_product_selection_runs"), "product_selection_observations", type_="foreignkey")
    op.drop_column("product_selection_observations", "last_run_id")
    op.drop_table("product_selection_runs")
