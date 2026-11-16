"""Remove the retired AI workbench and its private tables.

Revision ID: 20261114_0052
Revises: 20261113_0051

The independent asset and task records are intentionally retained.
This change deletes AI workbench facts; a verified backup is required before
applying it to a shared environment.
"""

from alembic import op


revision = "20261114_0052"
down_revision = "20261113_0051"
branch_labels = None
depends_on = None


def upgrade():
    # Refuse to interrupt an in-flight provider request. The lock also prevents
    # the old executor from claiming another item while this transaction runs.
    op.execute("LOCK TABLE generation_items IN ACCESS EXCLUSIVE MODE")
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM generation_items WHERE status = 'RUNNING') THEN
            RAISE EXCEPTION 'AI workbench has running generation items';
          END IF;
        END
        $$
        """
    )
    op.execute("DELETE FROM membership_module_accesses WHERE module_code = 'ai-workbench'")
    op.execute("DELETE FROM team_module_accesses WHERE module_code = 'ai-workbench'")
    op.execute(
        """
        UPDATE api_tokens AS token
        SET permissions = COALESCE(
            (SELECT json_agg(item.value ORDER BY item.ordinality)
             FROM json_array_elements_text(token.permissions) WITH ORDINALITY AS item(value, ordinality)
             WHERE item.value NOT LIKE '% /api/v1/ai-workbench%'
               AND item.value NOT LIKE '% /api/v1/ai-models%'),
            '[]'::json
        )
        WHERE EXISTS (
            SELECT 1
            FROM json_array_elements_text(token.permissions) AS old_permission(value)
            WHERE old_permission.value LIKE '% /api/v1/ai-workbench%'
               OR old_permission.value LIKE '% /api/v1/ai-models%'
        )
        """
    )
    for table in (
        "generation_provider_executions",
        "generation_item_assets",
        "generation_items",
        "generation_jobs",
        "material_group_template_bindings",
        "material_group_assets",
        "prompt_templates",
        "product_material_groups",
        "template_groups",
        "ai_models",
    ):
        op.drop_table(table)


def downgrade():
    raise RuntimeError(
        "0052 removed AI workbench records; restore a verified backup to recover them"
    )
