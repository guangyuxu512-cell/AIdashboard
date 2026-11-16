"""Remove API-token grants for the retired product-metrics collector.

Revision ID: 20261116_0054
Revises: 20261116_0053
"""
from alembic import op


revision = "20261116_0054"
down_revision = "20261116_0053"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE api_tokens AS token
        SET permissions = COALESCE(
            (SELECT json_agg(item.value ORDER BY item.ordinality)
             FROM json_array_elements_text(token.permissions) WITH ORDINALITY AS item(value, ordinality)
             WHERE item.value NOT LIKE '% /api/v1/product-data/collection%'),
            '[]'::json
        )
        WHERE EXISTS (
            SELECT 1 FROM json_array_elements_text(token.permissions) AS old_permission(value)
            WHERE old_permission.value LIKE '% /api/v1/product-data/collection%'
        )
    """)


def downgrade():
    raise RuntimeError("0054 removed retired permission entries; restore a verified backup to recover them")
