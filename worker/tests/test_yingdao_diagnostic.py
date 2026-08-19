from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tools.yingdao_diagnostic import collect_local_state


def write_package(root: Path, app_id: str, app_name: str) -> None:
    package_root = root / app_id / "xbot_robot"
    package_root.mkdir(parents=True)
    (package_root / "package.json").write_text(
        json.dumps(
            {
                "uuid": app_id,
                "name": app_name,
                "version": "1",
                "startup": "main",
                "variables": [{"secret": "must-not-be-collected"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_collect_local_state_is_read_only_and_sanitized(tmp_path: Path) -> None:
    user_id = "current-user"
    user_root = tmp_path / "users" / user_id
    apps_root = user_root / "apps"
    apps_root.mkdir(parents=True)
    database_path = user_root / "user.db3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE developmentsync_apps_v2 ("
            "uuid TEXT, name TEXT, ownerName TEXT, modifyTime INTEGER, "
            "isSynchronized INTEGER, isRecycleBin INTEGER, robotType TEXT)",
        )
        connection.execute("CREATE TABLE subscribed_apps (uuid TEXT)")
        connection.executemany(
            "INSERT INTO developmentsync_apps_v2 VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("app-1", "应用一", "账号", 2, 1, 0, "robot"),
                ("app-2", "已回收", "账号", 1, 1, 1, "robot"),
            ],
        )
    write_package(apps_root, "app-1", "应用一")
    write_package(apps_root, "orphan-app", "本地孤立应用")

    result = collect_local_state(tmp_path, user_id)

    assert result["database_row_count"] == 2
    assert result["active_row_count"] == 1
    assert result["recycled_row_count"] == 1
    assert result["applications"][0]["package"] == {
        "exists": True,
        "valid_json": True,
        "app_id": "app-1",
        "app_name": "应用一",
        "package_version": "1",
        "entrypoint": "main",
    }
    assert result["orphan_packages"][0]["directory_app_id"] == "orphan-app"
    assert "variables" not in json.dumps(result, ensure_ascii=False)
    assert "must-not-be-collected" not in json.dumps(result, ensure_ascii=False)
    assert database_path.is_file()
