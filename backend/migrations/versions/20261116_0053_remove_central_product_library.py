"""Remove the retired central product library and its collection history.

Revision ID: 20261116_0053
Revises: 20261114_0052

The independent product library, selection facts, Worker and operating metrics
are not part of this migration. A readable backup is required before upgrade.
"""
from alembic import op


revision = "20261116_0053"
down_revision = "20261114_0052"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("DELETE FROM membership_module_accesses WHERE module_code = 'product-library'")
    op.execute("DELETE FROM team_module_accesses WHERE module_code = 'product-library'")
    op.execute("""
        UPDATE api_tokens AS token
        SET permissions = COALESCE(
            (SELECT json_agg(item.value ORDER BY item.ordinality)
             FROM json_array_elements_text(token.permissions) WITH ORDINALITY AS item(value, ordinality)
             WHERE item.value NOT LIKE '% /api/v1/product-library%'
               AND item.value NOT LIKE '% /api/v1/product-collection%'
               AND item.value NOT LIKE '% /api/v1/mobile-collection%'),
            '[]'::json
        )
        WHERE EXISTS (
            SELECT 1 FROM json_array_elements_text(token.permissions) AS old_permission(value)
            WHERE old_permission.value LIKE '% /api/v1/product-library%'
               OR old_permission.value LIKE '% /api/v1/product-collection%'
               OR old_permission.value LIKE '% /api/v1/mobile-collection%'
        )
    """)
    # These two foreign keys form cycles inside the retired schema.
    op.drop_constraint("fk_collection_item_current_dispatch", "product_collection_items", type_="foreignkey")
    op.drop_constraint("fk_library_product_adopted_version", "product_library_products", type_="foreignkey")
    for table in (
        "product_collection_persist_receipts",
        "product_library_product_versions",
        "product_collection_upload_receipts",
        "product_collection_capture_attempts",
        "product_collection_dispatches",
        "product_collection_items",
        "product_collection_requests",
        "product_library_products",
        "product_library_groups",
    ):
        op.drop_table(table)


def downgrade():
    raise RuntimeError("0053 removed central library records; restore a verified backup to recover them")
