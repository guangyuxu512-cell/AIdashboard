import asyncio
import ctypes
import json
import os
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.providers.yingdao.contracts import (
    YingdaoApplication,
    YingdaoDiscoveryResult,
)


class YingdaoDiscoveryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _VSFixedFileInfo(ctypes.Structure):
    _fields_ = [
        ("signature", ctypes.c_uint32),
        ("structure_version", ctypes.c_uint32),
        ("file_version_ms", ctypes.c_uint32),
        ("file_version_ls", ctypes.c_uint32),
        ("product_version_ms", ctypes.c_uint32),
        ("product_version_ls", ctypes.c_uint32),
        ("file_flags_mask", ctypes.c_uint32),
        ("file_flags", ctypes.c_uint32),
        ("file_os", ctypes.c_uint32),
        ("file_type", ctypes.c_uint32),
        ("file_subtype", ctypes.c_uint32),
        ("file_date_ms", ctypes.c_uint32),
        ("file_date_ls", ctypes.c_uint32),
    ]


def read_windows_file_version(path: Path) -> str:
    if os.name != "nt":
        raise OSError("Windows file version metadata is unavailable")
    version_api = ctypes.WinDLL("version", use_last_error=True)
    size = version_api.GetFileVersionInfoSizeW(str(path), None)
    if size == 0:
        raise OSError(ctypes.get_last_error(), "File version metadata is unavailable")
    buffer = ctypes.create_string_buffer(size)
    if not version_api.GetFileVersionInfoW(str(path), 0, size, buffer):
        raise OSError(ctypes.get_last_error(), "File version metadata is unreadable")
    pointer = ctypes.c_void_p()
    length = ctypes.c_uint()
    if not version_api.VerQueryValueW(
        buffer,
        "\\",
        ctypes.byref(pointer),
        ctypes.byref(length),
    ):
        raise OSError(ctypes.get_last_error(), "File version metadata is invalid")
    info = ctypes.cast(pointer, ctypes.POINTER(_VSFixedFileInfo)).contents
    parts = [
        info.file_version_ms >> 16,
        info.file_version_ms & 0xFFFF,
        info.file_version_ls >> 16,
        info.file_version_ls & 0xFFFF,
    ]
    if parts[-1] == 0:
        parts.pop()
    return ".".join(str(value) for value in parts)


class YingdaoDiscoveryService:
    def __init__(
        self,
        *,
        install_root: Path | None,
        data_root: Path | None,
        command_timeout_seconds: float,
        version_reader: Callable[[Path], str] | None = None,
    ) -> None:
        self.install_root = install_root.resolve() if install_root else None
        self.data_root = data_root.resolve() if data_root else self._default_data_root()
        self.command_timeout_seconds = command_timeout_seconds
        self.version_reader = version_reader or read_windows_file_version

    async def discover(self) -> YingdaoDiscoveryResult:
        environment = self._require_installation()
        cli_path = environment.discovery_cli_path
        health = await self._run_cli(cli_path, "system", "health")
        health_data = health.get("data")
        if (
            not health.get("ok")
            or not isinstance(health_data, dict)
            or health_data.get("status") != "ready"
        ):
            raise YingdaoDiscoveryError(
                "YINGDAO_NOT_READY",
                "Yingdao console REST API is not ready",
            )

        auth = await self._run_cli(cli_path, "auth", "current")
        auth_data = auth.get("data")
        if not auth.get("ok") or not isinstance(auth_data, dict):
            raise YingdaoDiscoveryError(
                "YINGDAO_AUTH_UNAVAILABLE",
                "Yingdao current account could not be read",
            )
        if auth_data.get("loggedIn") is not True:
            raise YingdaoDiscoveryError(
                "YINGDAO_NOT_LOGGED_IN",
                "Yingdao is not logged in",
            )

        user_id = auth_data.get("userId")
        account_display = auth_data.get("displayName") or auth_data.get("userName")
        account_type = auth_data.get("accountType")
        enterprise_account = auth_data.get("isEnterprise")
        if (
            not isinstance(user_id, str)
            or not user_id
            or not isinstance(account_display, str)
            or not account_display
            or not isinstance(account_type, str)
            or not account_type
            or not isinstance(enterprise_account, bool)
        ):
            raise YingdaoDiscoveryError(
                "YINGDAO_ACCOUNT_INVALID",
                "Yingdao returned incomplete account metadata",
            )

        applications = await asyncio.to_thread(self._read_applications, user_id)
        return YingdaoDiscoveryResult(
            provider_available=True,
            provider_version=environment.provider_version,
            execution_available=environment.execution_available,
            execution_version=environment.execution_version,
            execution_unavailable_reason=(
                environment.execution_unavailable_reason
            ),
            logged_in=True,
            account_display=account_display,
            account_type=account_type,
            enterprise_account=enterprise_account,
            user_id=user_id,
            applications=applications,
            discovered_at=datetime.now(UTC),
        )

    def _require_installation(self) -> Any:
        if self.install_root is None:
            raise YingdaoDiscoveryError(
                "YINGDAO_NOT_INSTALLED",
                "Yingdao install root is not configured",
            )
        from app.providers.yingdao.environment import YingdaoVersionResolver

        try:
            return YingdaoVersionResolver(
                self.install_root,
                version_reader=self.version_reader,
            ).resolve()
        except FileNotFoundError as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_NOT_INSTALLED",
                "Yingdao executable or CLI was not found",
            ) from error
        except OSError as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_VERSION_UNAVAILABLE",
                "Yingdao version metadata could not be read",
            ) from error

    async def _run_cli(self, cli_path: Path, *arguments: str) -> dict[str, Any]:
        try:
            process = await asyncio.create_subprocess_exec(
                str(cli_path),
                *arguments,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=self.command_timeout_seconds,
            )
        except TimeoutError as error:
            if "process" in locals() and process.returncode is None:
                process.kill()
                await process.wait()
            raise YingdaoDiscoveryError(
                "YINGDAO_CLI_TIMEOUT",
                "Yingdao CLI command timed out",
            ) from error
        except OSError as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_NOT_INSTALLED",
                "Yingdao CLI could not be started",
            ) from error
        try:
            payload = json.loads(stdout.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_CLI_RESULT_INVALID",
                "Yingdao CLI returned invalid JSON",
            ) from error
        if not isinstance(payload, dict):
            raise YingdaoDiscoveryError(
                "YINGDAO_CLI_RESULT_INVALID",
                "Yingdao CLI returned a non-object result",
            )
        return payload

    def _read_applications(self, user_id: str) -> list[YingdaoApplication]:
        user_directory = self.data_root / "users" / user_id
        database_path = user_directory / "user.db3"
        if not database_path.is_file():
            raise YingdaoDiscoveryError(
                "YINGDAO_USER_DATABASE_NOT_FOUND",
                "Yingdao user database was not found",
            )
        try:
            connection = sqlite3.connect(
                f"{database_path.resolve().as_uri()}?mode=ro",
                uri=True,
            )
            connection.row_factory = sqlite3.Row
            try:
                rows = connection.execute(
                    "SELECT uuid, name FROM developmentsync_apps_v2 "
                    "WHERE isRecycleBin = 0 ORDER BY modifyTime DESC",
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_USER_DATABASE_INVALID",
                "Yingdao user database could not be read",
            ) from error

        applications: list[YingdaoApplication] = []
        for row in rows:
            app_id = row["uuid"]
            app_name = row["name"]
            if not isinstance(app_id, str) or not isinstance(app_name, str):
                raise YingdaoDiscoveryError(
                    "YINGDAO_APPLICATION_INVALID",
                    "Yingdao application metadata is invalid",
                )
            package_path = (
                user_directory
                / "apps"
                / app_id
                / "xbot_robot"
                / "package.json"
            )
            try:
                package = json.loads(package_path.read_text(encoding="utf-8-sig"))
                if not isinstance(package, dict):
                    raise ValueError("Package metadata must be an object")
                application = YingdaoApplication(
                    app_id=app_id,
                    app_name=app_name,
                    package_version=package.get("version"),
                    entrypoint=package.get("startup"),
                )
                if package.get("uuid") != app_id or package.get("name") != app_name:
                    raise ValueError("Package identity does not match the database")
                if not application.package_version or not application.entrypoint:
                    raise ValueError("Package execution metadata is incomplete")
            except (OSError, ValueError, TypeError, ValidationError) as error:
                raise YingdaoDiscoveryError(
                    "YINGDAO_PACKAGE_INVALID",
                    f"Yingdao package is invalid for application {app_id}",
                ) from error
            applications.append(application)
        return applications

    @staticmethod
    def _default_data_root() -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return Path("__yingdao_data_root_unavailable__").resolve()
        return (Path(local_app_data) / "ShadowBot").resolve()
