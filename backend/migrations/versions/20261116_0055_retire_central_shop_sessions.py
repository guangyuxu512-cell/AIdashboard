"""Retire server-side shop sessions; Worker reports local shop state.

Revision ID: 20261116_0055
Revises: 20261116_0054

Human login sessions, Worker credentials, shop identities and historical facts
are not affected. A readable backup is required before this upgrade.
"""
from alembic import op


revision = "20261116_0055"
down_revision = "20261116_0054"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("DELETE FROM shop_sessions")
    op.create_check_constraint(
        op.f("ck_shop_sessions_no_server_session_payload"),
        "shop_sessions",
        "octet_length(payload_encrypted) = 0",
    )
    op.execute("""
        UPDATE api_tokens AS token
        SET permissions = COALESCE(
            (SELECT json_agg(item.value ORDER BY item.ordinality)
             FROM json_array_elements_text(token.permissions) WITH ORDINALITY AS item(value, ordinality)
             WHERE item.value NOT LIKE '% /api/v1/shop-onboarding%'
               AND item.value NOT LIKE '% /api/v1/shops/%/session%'
               AND item.value NOT LIKE '% /api/v1/shops/%/platform-identity'),
            '[]'::json
        )
        WHERE EXISTS (
            SELECT 1 FROM json_array_elements_text(token.permissions) AS old_permission(value)
            WHERE old_permission.value LIKE '% /api/v1/shop-onboarding%'
               OR old_permission.value LIKE '% /api/v1/shops/%/session%'
               OR old_permission.value LIKE '% /api/v1/shops/%/platform-identity'
        )
    """)


def downgrade():
    raise RuntimeError("0055 removed central shop sessions; restore a verified backup to recover them")
