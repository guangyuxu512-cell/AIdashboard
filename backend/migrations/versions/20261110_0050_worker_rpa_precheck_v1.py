"""Add device-local RPA inventory and application precheck identity.

Revision ID: 20261110_0050
Revises: 20261020_0049
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261110_0050"
down_revision = "20261020_0049"
branch_labels = None
depends_on = None

FEATURE_DATABASE = "control_center_feat_worker_capability_precheck"
FEATURE_TABLES = ("application_worker_prechecks", "worker_rpa_shop_inventories")


def upgrade():
    op.create_table(
        "worker_rpa_shop_inventories",
        sa.Column("device_id", sa.Uuid(), primary_key=True),
        sa.Column("installation_id", sa.Uuid(), nullable=True),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("shops", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("jsonb_typeof(shops) = 'array'", name="worker_rpa_shops_array"),
        sa.CheckConstraint("jsonb_array_length(shops) <= 500", name="worker_rpa_shops_limit"),
        sa.CheckConstraint("NOT available OR installation_id IS NOT NULL", name="worker_rpa_available_installation"),
    )
    op.create_table(
        "application_worker_prechecks",
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("client_id", "product_id", "revision"),
        sa.UniqueConstraint("task_id", name="uq_application_worker_prechecks_task"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.task_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("length(trim(product_id)) > 0", name="precheck_product_not_blank"),
        sa.CheckConstraint("revision > 0", name="precheck_revision_positive"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="precheck_request_hash"),
    )


def downgrade():
    if op.get_context().as_sql:
        raise RuntimeError("0050 downgrade requires an online Feature target check")
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT current_database()")) != FEATURE_DATABASE:
        raise RuntimeError("0050 downgrade permits only the registered Feature database")
    connection.execute(sa.text("LOCK TABLE " + ", ".join(FEATURE_TABLES) + " IN ACCESS EXCLUSIVE MODE"))
    for table_name in FEATURE_TABLES:
        if connection.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table_name} LIMIT 1)")):
            raise RuntimeError("0050 contains precheck facts; retain schema and audit data")
    for table_name in FEATURE_TABLES:
        op.drop_table(table_name)
