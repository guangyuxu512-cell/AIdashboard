"""introduce super account and Team-level resource authorization.

Revision ID: 20260919_0037
Revises: 20260912_0036
Create Date: 2026-09-19

The migration intentionally refuses to collapse ambiguous legacy membership
data.  A deployment operator must first normalize users with multiple active
Teams and Teams whose active members currently have different module grants.
Neither a union nor an intersection is a safe automatic replacement for the
old member-level permission model.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260919_0037"
down_revision: str | None = "20260912_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _legacy_preflight() -> None:
    connection = op.get_bind()
    multiple_active_users = int(
        connection.scalar(
            sa.text(
                """
                SELECT count(*)
                FROM (
                    SELECT tm.user_id
                    FROM team_memberships AS tm
                    JOIN teams AS team ON team.team_id = tm.team_id
                    WHERE tm.enabled IS TRUE AND team.enabled IS TRUE
                    GROUP BY tm.user_id
                    HAVING count(*) > 1
                ) AS conflicts
                """,
            ),
        )
        or 0,
    )
    if multiple_active_users:
        raise RuntimeError(
            "0037迁移前置条件未满足：存在"
            f"{multiple_active_users}名用户拥有多个有效团队，请先完成明确调组",
        )

    inconsistent_team_grants = int(
        connection.scalar(
            sa.text(
                """
                WITH membership_grants AS (
                    SELECT
                        tm.team_id,
                        tm.membership_id,
                        COALESCE(
                            string_agg(
                                mma.module_code,
                                ',' ORDER BY mma.module_code
                            ),
                            ''
                        ) AS grant_set
                    FROM team_memberships AS tm
                    JOIN teams AS team ON team.team_id = tm.team_id
                    LEFT JOIN membership_module_accesses AS mma
                        ON mma.membership_id = tm.membership_id
                    WHERE tm.enabled IS TRUE AND team.enabled IS TRUE
                    GROUP BY tm.team_id, tm.membership_id
                )
                SELECT count(*)
                FROM (
                    SELECT team_id
                    FROM membership_grants
                    GROUP BY team_id
                    HAVING count(DISTINCT grant_set) > 1
                ) AS conflicts
                """,
            ),
        )
        or 0,
    )
    if inconsistent_team_grants:
        raise RuntimeError(
            "0037迁移前置条件未满足：存在"
            f"{inconsistent_team_grants}个团队的有效成员模块权限不一致，"
            "请先由超级账号确认统一团队授权",
        )


def upgrade() -> None:
    _legacy_preflight()

    # A membership in an archived Team is historical, not an effective Team
    # assignment.  Marking it disabled is unambiguous and lets the partial
    # one-current-Team index describe the same rule as ActorContext.
    op.execute(
        sa.text(
            """
            UPDATE team_memberships AS tm
            SET enabled = FALSE
            FROM teams AS team
            WHERE team.team_id = tm.team_id
              AND team.enabled IS FALSE
              AND tm.enabled IS TRUE
            """,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "is_super_account",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "uq_users_single_super_account",
        "users",
        ["is_super_account"],
        unique=True,
        postgresql_where=sa.text("is_super_account"),
    )

    # Access-management actions are global for a super account.  Historical
    # audit rows keep their Team ID; new global operations intentionally have
    # no invented default Team.
    op.alter_column("audit_logs", "team_id", existing_type=sa.Uuid(), nullable=True)

    op.create_table(
        "team_module_accesses",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_team_module_accesses_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("team_id", "module_code"),
    )
    op.create_table(
        "team_device_accesses",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_team_device_accesses_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_team_device_accesses_device_id_devices",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("team_id", "device_id"),
    )
    op.create_index(
        "ix_team_device_accesses_device",
        "team_device_accesses",
        ["device_id"],
        unique=False,
    )
    op.create_table(
        "team_shop_accesses",
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("shop_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.team_id"],
            name="fk_team_shop_accesses_team_id_teams",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.shop_id"],
            name="fk_team_shop_accesses_shop_id_shops",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("team_id", "shop_id"),
    )
    op.create_index(
        "ix_team_shop_accesses_shop",
        "team_shop_accesses",
        ["shop_id"],
        unique=False,
    )

    # Only proven-equal legacy grants reach the Team table because the
    # preflight above rejects any Team where a member-level collapse could
    # widen or silently revoke access.
    op.execute(
        sa.text(
            """
            INSERT INTO team_module_accesses (team_id, module_code)
            SELECT DISTINCT tm.team_id, mma.module_code
            FROM team_memberships AS tm
            JOIN teams AS team ON team.team_id = tm.team_id
            JOIN membership_module_accesses AS mma
                ON mma.membership_id = tm.membership_id
            WHERE tm.enabled IS TRUE AND team.enabled IS TRUE
            ON CONFLICT (team_id, module_code) DO NOTHING
            """,
        ),
    )
    # Legacy Device.team_id is a single, explicit ownership fact, so it can
    # safely seed the new many-Team device grant table.  Shops have no such
    # trustworthy Team owner and are deliberately *not* guessed here.
    op.execute(
        sa.text(
            """
            INSERT INTO team_device_accesses (team_id, device_id)
            SELECT device.team_id, device.device_id
            FROM devices AS device
            JOIN teams AS team ON team.team_id = device.team_id
            WHERE device.deleted_at IS NULL AND team.enabled IS TRUE
            ON CONFLICT (team_id, device_id) DO NOTHING
            """,
        ),
    )
    op.create_index(
        "uq_team_memberships_one_active_user",
        "team_memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("enabled"),
    )


def downgrade() -> None:
    null_audit_team_count = int(
        op.get_bind().scalar(
            sa.text("SELECT count(*) FROM audit_logs WHERE team_id IS NULL"),
        )
        or 0,
    )
    if null_audit_team_count:
        raise RuntimeError(
            "0037降级前置条件未满足：存在全局超级账号审计记录，"
            "不能安全恢复 audit_logs.team_id 非空约束",
        )
    op.drop_index(
        "uq_team_memberships_one_active_user",
        table_name="team_memberships",
    )
    op.drop_index("ix_team_shop_accesses_shop", table_name="team_shop_accesses")
    op.drop_table("team_shop_accesses")
    op.drop_index(
        "ix_team_device_accesses_device",
        table_name="team_device_accesses",
    )
    op.drop_table("team_device_accesses")
    op.drop_table("team_module_accesses")
    op.alter_column("audit_logs", "team_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_index("uq_users_single_super_account", table_name="users")
    op.drop_column("users", "is_super_account")
