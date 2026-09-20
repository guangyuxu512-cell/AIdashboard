#!/usr/bin/env bash
set -euo pipefail

# This helper is intentionally limited to a single, read-only release
# preflight.  It never builds images, starts/stops services, runs Alembic
# migrations, alters host configuration, or executes DML/DDL against PostgreSQL.

remote_root="${1:?production deployment root is required}"
if [[ "$remote_root" != "/opt/ecommerce-control-center/production" ]]; then
    echo "Refusing an unexpected production deployment root" >&2
    exit 2
fi

current_release="$(readlink -f "$remote_root/current" 2>/dev/null || true)"
if [[ ! "$current_release" =~ ^/opt/ecommerce-control-center/production/releases/[0-9a-f]{40}$ ]]; then
    echo "Production current release is unavailable or has an unexpected path" >&2
    exit 2
fi

environment_file="$remote_root/.env"
if [[ ! -f "$environment_file" ]]; then
    echo "Production environment file is unavailable" >&2
    exit 2
fi

release_sha="${current_release##*/}"
export DEPLOYMENT_IMAGE_TAG="$release_sha"
export PRODUCTION_ENV_FILE="$environment_file"
export CONTROL_CENTER_PREFLIGHT_RELEASE_SHA="$release_sha"
compose=(
    docker compose
    --project-name control-center-production
    --env-file "$environment_file"
    -f "$current_release/deploy/production/compose.yaml"
)
"${compose[@]}" config -q

# Run only in the already-running Backend container for the exact active release.
# This preflight never creates a container, builds an image, starts/stops a
# service, or modifies the deployment environment.
backend_container="$("${compose[@]}" ps -q backend)"
if [[ -z "$backend_container" ]]; then
    echo "Production Backend container is not running" >&2
    exit 2
fi

expected_image="ecommerce-control-center-backend-prod:${release_sha}"
backend_image="$(docker inspect --format '{{.Config.Image}}' "$backend_container")"
if [[ "$backend_image" != "$expected_image" ]]; then
    echo "Running Backend image does not match the active production release" >&2
    exit 2
fi

export CONTROL_CENTER_PREFLIGHT_BACKEND_IMAGE="$backend_image"

# The running Backend image owns configuration parsing.  The embedded program
# begins a repeatable-read PostgreSQL READ ONLY transaction before every database
# query. Its JSON report intentionally excludes credentials, session material,
# secrets, cookies, storage keys, file paths, and business payloads.
docker exec \
    -e CONTROL_CENTER_PREFLIGHT_RELEASE_SHA \
    -e CONTROL_CENTER_PREFLIGHT_BACKEND_IMAGE \
    -i "$backend_container" python - <<'PY'
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text

from app.core.config import get_settings
from app.core.database.session import create_database_engine


def serialize(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def rows(connection: Any, statement: str) -> list[dict[str, Any]]:
    return [serialize(dict(row._mapping)) for row in connection.execute(text(statement))]


def scalar(
    connection: Any,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> Any:
    return serialize(connection.execute(text(statement), parameters or {}).scalar_one_or_none())


def table_exists(connection: Any, table_name: str) -> bool:
    return bool(scalar(connection, f"SELECT to_regclass('public.{table_name}') IS NOT NULL"))


def column_exists(connection: Any, table_name: str, column_name: str) -> bool:
    return bool(
        scalar(
            connection,
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = :table_name
                  AND column_name = :column_name
            )
            """,
            {"table_name": table_name, "column_name": column_name},
        )
    )


# These identifiers are fixed repository schema names, not user-controlled
# input.  Parameterized forms are unnecessary because no external values reach
# SQL in this preflight.
settings = get_settings()
engine = create_database_engine(settings)

with engine.connect() as connection:
    connection.execute(text("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
    try:
        report: dict[str, Any] = {
            "report_version": 1,
            "release_sha": __import__("os").environ["CONTROL_CENTER_PREFLIGHT_RELEASE_SHA"],
            "backend_image": __import__("os").environ["CONTROL_CENTER_PREFLIGHT_BACKEND_IMAGE"],
            "database": scalar(connection, "SELECT current_database()"),
            "database_role": scalar(connection, "SELECT current_user"),
            "migration_head": scalar(connection, "SELECT version_num FROM alembic_version"),
            "asset_storage_mode": settings.asset_storage_mode,
        }

        has_super_column = column_exists(connection, "users", "is_super_account")
        report["super_account_column_present"] = has_super_column
        if has_super_column:
            report["super_accounts"] = rows(
                connection,
                """
                SELECT user_id::text, login_name, enabled, is_super_account
                FROM users
                WHERE is_super_account IS TRUE
                ORDER BY user_id
                """,
            )
        else:
            report["super_accounts"] = []

        report["active_user_count"] = scalar(
            connection,
            "SELECT count(*) FROM users WHERE enabled IS TRUE",
        )
        report["active_user_candidates"] = rows(
            connection,
            """
            SELECT
                user_record.user_id::text,
                user_record.login_name,
                user_record.enabled,
                count(membership.membership_id) AS active_team_count
            FROM users AS user_record
            LEFT JOIN team_memberships AS membership
                ON membership.user_id = user_record.user_id
               AND membership.enabled IS TRUE
            LEFT JOIN teams AS team
                ON team.team_id = membership.team_id
               AND team.enabled IS TRUE
            WHERE user_record.enabled IS TRUE
            GROUP BY user_record.user_id, user_record.login_name, user_record.enabled
            ORDER BY user_record.user_id
            LIMIT 50
            """,
        )

        report["multiple_active_team_users"] = rows(
            connection,
            """
            SELECT
                membership.user_id::text,
                array_agg(membership.team_id::text ORDER BY membership.team_id) AS active_team_ids
            FROM team_memberships AS membership
            JOIN teams AS team ON team.team_id = membership.team_id
            WHERE membership.enabled IS TRUE AND team.enabled IS TRUE
            GROUP BY membership.user_id
            HAVING count(*) > 1
            ORDER BY membership.user_id
            """,
        )

        membership_grants = rows(
            connection,
            """
            SELECT
                membership.team_id::text,
                membership.membership_id::text,
                membership.user_id::text,
                COALESCE(
                    array_agg(module_access.module_code ORDER BY module_access.module_code)
                        FILTER (WHERE module_access.module_code IS NOT NULL),
                    ARRAY[]::text[]
                ) AS module_codes
            FROM team_memberships AS membership
            JOIN teams AS team ON team.team_id = membership.team_id
            LEFT JOIN membership_module_accesses AS module_access
                ON module_access.membership_id = membership.membership_id
            WHERE membership.enabled IS TRUE AND team.enabled IS TRUE
            GROUP BY membership.team_id, membership.membership_id, membership.user_id
            ORDER BY membership.team_id, membership.membership_id
            """,
        )
        grants_by_team: dict[str, list[dict[str, Any]]] = {}
        for grant in membership_grants:
            grants_by_team.setdefault(grant["team_id"], []).append(grant)
        report["teams_with_inconsistent_legacy_module_grants"] = [
            {"team_id": team_id, "memberships": grants}
            for team_id, grants in grants_by_team.items()
            if len({tuple(grant["module_codes"]) for grant in grants}) > 1
        ]

        has_device_access = table_exists(connection, "team_device_accesses")
        has_shop_access = table_exists(connection, "team_shop_accesses")
        report["team_device_access_table_present"] = has_device_access
        report["team_shop_access_table_present"] = has_shop_access

        device_grants = (
            rows(
                connection,
                """
                SELECT device_id::text, array_agg(team_id::text ORDER BY team_id) AS authorized_team_ids
                FROM team_device_accesses
                GROUP BY device_id
                """,
            )
            if has_device_access
            else []
        )
        device_grant_map = {item["device_id"]: item["authorized_team_ids"] for item in device_grants}
        report["active_devices"] = [
            {
                "device_id": item["device_id"],
                "owner_team_id": item["team_id"],
                "enabled": item["enabled"],
                "authorized_team_ids": device_grant_map.get(item["device_id"], []),
            }
            for item in rows(
                connection,
                """
                SELECT device_id::text, team_id::text, enabled
                FROM devices
                WHERE deleted_at IS NULL
                ORDER BY device_id
                LIMIT 100
                """,
            )
        ]

        shop_grants = (
            rows(
                connection,
                """
                SELECT shop_id::text, array_agg(team_id::text ORDER BY team_id) AS authorized_team_ids
                FROM team_shop_accesses
                GROUP BY shop_id
                """,
            )
            if has_shop_access
            else []
        )
        shop_grant_map = {item["shop_id"]: item["authorized_team_ids"] for item in shop_grants}
        report["active_shops"] = [
            {
                "shop_id": item["shop_id"],
                "owner_user_id": item["owner_user_id"],
                "enabled": item["enabled"],
                "authorized_team_ids": shop_grant_map.get(item["shop_id"], []),
            }
            for item in rows(
                connection,
                """
                SELECT shop_id::text, owner_user_id::text, enabled
                FROM shops
                WHERE deleted_at IS NULL
                ORDER BY shop_id
                LIMIT 100
                """,
            )
        ]

        # Repository governance has no registered production PostgreSQL backup
        # catalog path.  Do not scan arbitrary host paths as a substitute.
        report["backup_catalog"] = "NOT_REGISTERED_REQUIRES_OPERATOR_PATH"
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    finally:
        connection.execute(text("ROLLBACK"))
PY
