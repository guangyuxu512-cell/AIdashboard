"""Remove the retired central product-data history and its five dedicated tables.

The independent ProductDataCenter, Worker inventory, tasks and operating data
are outside this migration. Shared databases require a verified backup first.
"""
from alembic import op
import sqlalchemy as sa


revision = '20261124_0059'
down_revision = '20261121_0058'
branch_labels = None
depends_on = None


def upgrade():
    if op.get_context().as_sql:
        raise RuntimeError('0059 requires online verification of old product-data activity')
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute('LOCK TABLE shop_product_data_collection_batches, shop_product_data_products, '
               'shop_product_data_series, shop_product_data_generations, '
               'shop_product_data_metric_snapshots IN ACCESS EXCLUSIVE MODE')
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM shop_product_data_generations "
                                    "WHERE status = 'running' AND (lease_until IS NULL OR lease_until > now()))")):
        raise RuntimeError('A central product-data collection still has an active lease')
    op.execute("""
        UPDATE api_tokens AS token
        SET permissions = COALESCE(
            (SELECT json_agg(item.value ORDER BY item.ordinality)
             FROM json_array_elements_text(token.permissions) WITH ORDINALITY AS item(value, ordinality)
             WHERE item.value NOT LIKE '% /api/v1/product-data'
               AND item.value NOT LIKE '% /api/v1/product-data/%'),
            '[]'::json
        )
        WHERE EXISTS (
            SELECT 1 FROM json_array_elements_text(token.permissions) AS item(value)
            WHERE item.value LIKE '% /api/v1/product-data'
               OR item.value LIKE '% /api/v1/product-data/%'
        )
    """)
    op.drop_constraint('fk_spd_series_current', 'shop_product_data_series', type_='foreignkey')
    op.drop_constraint('fk_spd_series_previous', 'shop_product_data_series', type_='foreignkey')
    for table in ('shop_product_data_metric_snapshots', 'shop_product_data_generations',
                  'shop_product_data_series', 'shop_product_data_products',
                  'shop_product_data_collection_batches'):
        op.drop_table(table)


def downgrade():
    raise RuntimeError('0059 removed central product-data history; restore a verified backup to recover it')
