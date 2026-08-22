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
        user_id: str | None = None,
        version_reader: Callable[[Path], str] | None = None,
    ) -> None:
        self.install_root = install_root.resolve() if install_root else None
        self.data_root = data_root.resolve() if data_root else self._default_data_root()
        if user_id is not None and not user_id.isdigit():
            raise ValueError("Yingdao user ID must contain digits only")
        self.user_id = user_id
        self.version_reader = version_reader or read_windows_file_version

    async def discover(self) -> YingdaoDiscoveryResult:
        environment = self._require_installation()
        user_id, marker_display = await asyncio.to_thread(
            self._read_current_account,
        )
        account_display, applications = await asyncio.to_thread(
            self._read_applications,
            user_id,
            marker_display,
        )
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
            account_type=None,
            enterprise_account=None,
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
                "Yingdao executable was not found",
            ) from error
        except OSError as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_VERSION_UNAVAILABLE",
                "Yingdao version metadata could not be read",
            ) from error

    def _read_current_account(self) -> tuple[str, str]:
        users_root = self.data_root / "users"
        if self.user_id is not None:
            user_directory = users_root / self.user_id
            if not (user_directory / "user.db3").is_file():
                raise YingdaoDiscoveryError(
                    "YINGDAO_ACCOUNT_NOT_FOUND",
                    "Configured Yingdao account database was not found",
                )
            if (user_directory / "username.ini").is_file():
                return self.user_id, self._read_account_marker(user_directory)
            account_displays = self._read_database_account_displays(user_directory)
            if len(account_displays) != 1:
                code = (
                    "YINGDAO_ACCOUNT_AMBIGUOUS"
                    if len(account_displays) > 1
                    else "YINGDAO_ACCOUNT_INVALID"
                )
                raise YingdaoDiscoveryError(
                    code,
                    "Configured Yingdao account is not uniquely identified by local applications",
                )
            return self.user_id, next(iter(account_displays))

        try:
            user_directories = [
                directory
                for directory in users_root.iterdir()
                if directory.is_dir()
                and directory.name.isdigit()
                and (directory / "user.db3").is_file()
            ]
        except OSError as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_USER_DATA_UNAVAILABLE",
                "Yingdao local user data could not be read",
            ) from error

        marked_directories = [
            directory
            for directory in user_directories
            if (directory / "username.ini").is_file()
        ]
        if len(marked_directories) > 1:
            raise YingdaoDiscoveryError(
                "YINGDAO_ACCOUNT_AMBIGUOUS",
                "Multiple Yingdao local account markers were found",
            )
        if marked_directories:
            user_directory = marked_directories[0]
            return user_directory.name, self._read_account_marker(user_directory)

        if not user_directories:
            raise YingdaoDiscoveryError(
                "YINGDAO_NOT_LOGGED_IN",
                "Yingdao local user database was not found for this Windows user",
            )
        if len(user_directories) != 1:
            raise YingdaoDiscoveryError(
                "YINGDAO_ACCOUNT_AMBIGUOUS",
                "Multiple Yingdao local accounts exist without a current account marker",
            )

        user_directory = user_directories[0]
        account_displays = self._read_database_account_displays(user_directory)
        if len(account_displays) != 1:
            code = (
                "YINGDAO_ACCOUNT_AMBIGUOUS"
                if len(account_displays) > 1
                else "YINGDAO_ACCOUNT_INVALID"
            )
            raise YingdaoDiscoveryError(
                code,
                "Yingdao local applications do not uniquely identify the current account",
            )
        return user_directory.name, next(iter(account_displays))

    @staticmethod
    def _read_account_marker(user_directory: Path) -> str:
        try:
            account_display = (user_directory / "username.ini").read_text(
                encoding="utf-8-sig",
            ).strip()
        except (OSError, UnicodeDecodeError) as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_ACCOUNT_INVALID",
                "Yingdao local account metadata could not be read",
            ) from error
        if not account_display:
            raise YingdaoDiscoveryError(
                "YINGDAO_ACCOUNT_INVALID",
                "Yingdao local account metadata is empty",
            )
        return account_display

    @staticmethod
    def _read_database_account_displays(user_directory: Path) -> set[str]:
        database_path = user_directory / "user.db3"
        try:
            connection = sqlite3.connect(
                f"{database_path.resolve().as_uri()}?mode=ro",
                uri=True,
            )
            try:
                rows = connection.execute(
                    "SELECT DISTINCT ownerName FROM developmentsync_apps_v2 "
                    "WHERE isRecycleBin = 0 AND ownerName IS NOT NULL",
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as error:
            raise YingdaoDiscoveryError(
                "YINGDAO_USER_DATABASE_INVALID",
                "Yingdao user database could not be read",
            ) from error
        return {
            owner_name.strip()
            for (owner_name,) in rows
            if isinstance(owner_name, str) and owner_name.strip()
        }

    def _read_applications(
        self,
        user_id: str,
        marker_display: str,
    ) -> tuple[str, list[YingdaoApplication]]:
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
                    "SELECT uuid, name, ownerName FROM developmentsync_apps_v2 "
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
        account_displays: set[str] = set()
        for row in rows:
            app_id = row["uuid"]
            app_name = row["name"]
            owner_name = row["ownerName"]
            if not isinstance(app_id, str) or not isinstance(app_name, str):
                raise YingdaoDiscoveryError(
                    "YINGDAO_APPLICATION_INVALID",
                    "Yingdao application metadata is invalid",
                )
            if isinstance(owner_name, str) and owner_name.strip():
                account_displays.add(owner_name.strip())
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
        if len(account_displays) > 1:
            raise YingdaoDiscoveryError(
                "YINGDAO_ACCOUNT_AMBIGUOUS",
                "Yingdao local applications contain multiple owners",
            )
        account_display = next(iter(account_displays), marker_display)
        return account_display, applications

    @staticmethod
    def _default_data_root() -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return Path("__yingdao_data_root_unavailable__").resolve()
        return (Path(local_app_data) / "ShadowBot").resolve()
