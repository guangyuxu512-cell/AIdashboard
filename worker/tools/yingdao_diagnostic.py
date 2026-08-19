from __future__ import annotations

import argparse
import asyncio
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.providers.yingdao import YingdaoDiscoveryError, YingdaoDiscoveryService


DIAGNOSTIC_VERSION = "1"
DEVELOPMENT_TABLE = "developmentsync_apps_v2"
SAFE_DEVELOPMENT_COLUMNS = (
    "uuid",
    "name",
    "ownerName",
    "modifyTime",
    "isSynchronized",
    "isRecycleBin",
    "robotType",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect a read-only Yingdao diagnostic")
    parser.add_argument("--install-root", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd() / "yingdao-diagnostic.json",
    )
    return parser


def _read_worker_install_root() -> Path | None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return None
    config_path = Path(local_app_data) / "EcommerceAIWorker" / "config.json"
    if not config_path.is_file():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
        value = payload.get("yingdao_install_root")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    return Path(value) if isinstance(value, str) and value.strip() else None


def resolve_install_root(explicit: Path | None) -> Path:
    candidates = [
        explicit,
        _read_worker_install_root(),
        Path(r"D:\影刀\ShadowBot"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "ShadowBot",
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        resolved = candidate.expanduser().resolve()
        if (
            (resolved / "shadowbot.shell-cli.exe").is_file()
            and (resolved / "ShadowBot.exe").is_file()
        ):
            return resolved
    if sys.stdin.isatty():
        value = input("ShadowBot install root: ").strip().strip('"')
        if value:
            resolved = Path(value).expanduser().resolve()
            if (
                (resolved / "shadowbot.shell-cli.exe").is_file()
                and (resolved / "ShadowBot.exe").is_file()
            ):
                return resolved
    raise RuntimeError("ShadowBot install root was not found")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _safe_package(package_path: Path) -> dict[str, Any]:
    if not package_path.is_file():
        return {"exists": False}
    try:
        payload = json.loads(package_path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict):
            raise ValueError("package metadata is not an object")
        return {
            "exists": True,
            "valid_json": True,
            "app_id": payload.get("uuid"),
            "app_name": payload.get("name"),
            "package_version": payload.get("version"),
            "entrypoint": payload.get("startup"),
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        return {
            "exists": True,
            "valid_json": False,
            "error_type": type(error).__name__,
        }


def _table_metadata(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name",
        ).fetchall()
        if isinstance(row[0], str)
    ]
    result: list[dict[str, Any]] = []
    for name in names:
        lowered = name.lower()
        if not any(part in lowered for part in ("app", "robot", "develop", "sync", "subscrib")):
            continue
        columns = [
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({_quote_identifier(name)})",
            ).fetchall()
            if isinstance(row[1], str)
        ]
        try:
            row_count = connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(name)}",
            ).fetchone()[0]
        except sqlite3.Error:
            row_count = None
        result.append({"table": name, "row_count": row_count, "columns": columns})
    return result


def collect_local_state(data_root: Path, user_id: str) -> dict[str, Any]:
    user_directory = data_root / "users" / user_id
    database_path = user_directory / "user.db3"
    apps_root = user_directory / "apps"
    if not database_path.is_file():
        raise RuntimeError("Current Yingdao user database was not found")

    connection = sqlite3.connect(
        f"{database_path.resolve().as_uri()}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        tables = _table_metadata(connection)
        available_columns = {
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({_quote_identifier(DEVELOPMENT_TABLE)})",
            ).fetchall()
            if isinstance(row[1], str)
        }
        selected_columns = [
            name for name in SAFE_DEVELOPMENT_COLUMNS if name in available_columns
        ]
        if "uuid" not in selected_columns or "name" not in selected_columns:
            raise RuntimeError("Yingdao development application table is incompatible")
        order = " ORDER BY modifyTime DESC" if "modifyTime" in available_columns else ""
        rows = connection.execute(
            "SELECT "
            + ", ".join(_quote_identifier(name) for name in selected_columns)
            + f" FROM {_quote_identifier(DEVELOPMENT_TABLE)}"
            + order,
        ).fetchall()
    finally:
        connection.close()

    applications: list[dict[str, Any]] = []
    database_app_ids: set[str] = set()
    for row in rows:
        item = {name: row[name] for name in selected_columns}
        app_id = item.get("uuid")
        if isinstance(app_id, str):
            database_app_ids.add(app_id)
            package = _safe_package(apps_root / app_id / "xbot_robot" / "package.json")
        else:
            package = {"exists": False}
        item["package"] = package
        applications.append(item)

    orphan_packages: list[dict[str, Any]] = []
    if apps_root.is_dir():
        for app_directory in sorted(apps_root.iterdir(), key=lambda path: path.name):
            if not app_directory.is_dir() or app_directory.name in database_app_ids:
                continue
            orphan_packages.append(
                {
                    "directory_app_id": app_directory.name,
                    "package": _safe_package(
                        app_directory / "xbot_robot" / "package.json",
                    ),
                },
            )

    active_count = sum(
        item.get("isRecycleBin") in (0, False, None) for item in applications
    )
    recycled_count = len(applications) - active_count
    return {
        "development_table": DEVELOPMENT_TABLE,
        "database_row_count": len(applications),
        "active_row_count": active_count,
        "recycled_row_count": recycled_count,
        "applications": applications,
        "orphan_packages": orphan_packages,
        "candidate_tables": tables,
    }


async def collect_diagnostic(install_root: Path) -> dict[str, Any]:
    service = YingdaoDiscoveryService(
        install_root=install_root,
        data_root=None,
        command_timeout_seconds=15,
    )
    discovery = await service.discover()
    if not discovery.user_id:
        raise RuntimeError("Yingdao current user ID is unavailable")
    local_state = collect_local_state(service.data_root, discovery.user_id)
    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "collected_at": datetime.now(UTC).isoformat(),
        "computer_name": os.environ.get("COMPUTERNAME"),
        "provider": {
            "provider_version": discovery.provider_version,
            "logged_in": discovery.logged_in,
            "account_display": discovery.account_display,
            "account_type": discovery.account_type,
            "enterprise_account": discovery.enterprise_account,
            "user_id": discovery.user_id,
            "discovery_application_count": len(discovery.applications),
        },
        "local_state": local_state,
        "privacy": {
            "password_collected": False,
            "cookie_collected": False,
            "token_collected": False,
            "application_variables_collected": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        install_root = resolve_install_root(args.install_root)
        diagnostic = asyncio.run(collect_diagnostic(install_root))
        output_path = args.output.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(diagnostic, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (RuntimeError, OSError, sqlite3.Error, YingdaoDiscoveryError) as error:
        print(f"Diagnostic failed: {error}", file=sys.stderr)
        return 1
    print(f"Diagnostic completed: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
