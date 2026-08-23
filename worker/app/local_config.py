import base64
import ctypes
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from pydantic import SecretStr


class WorkerConfigurationError(RuntimeError):
    pass


class WorkerConfigurationMissingError(WorkerConfigurationError):
    pass


class TokenProtector(Protocol):
    def protect(self, value: str) -> str: ...

    def unprotect(self, value: str) -> str: ...


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class WindowsDpapiTokenProtector:
    def __init__(self) -> None:
        if os.name != "nt":
            raise WorkerConfigurationError("DPAPI is only available on Windows")
        self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.c_wchar_p,
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(_DataBlob),
        ]
        self._crypt32.CryptProtectData.restype = ctypes.c_bool
        self._crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob),
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.POINTER(_DataBlob),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            ctypes.POINTER(_DataBlob),
        ]
        self._crypt32.CryptUnprotectData.restype = ctypes.c_bool
        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p

    def protect(self, value: str) -> str:
        protected = self._transform(value.encode("utf-8"), protect=True)
        return base64.b64encode(protected).decode("ascii")

    def unprotect(self, value: str) -> str:
        try:
            protected = base64.b64decode(value, validate=True)
        except ValueError as error:
            raise WorkerConfigurationError("Worker Token DPAPI payload is invalid") from error
        try:
            return self._transform(protected, protect=False).decode("utf-8")
        except UnicodeDecodeError as error:
            raise WorkerConfigurationError("Worker Token could not be decoded") from error

    def _transform(self, value: bytes, *, protect: bool) -> bytes:
        buffer = ctypes.create_string_buffer(value, len(value))
        source = _DataBlob(
            len(value),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        destination = _DataBlob()
        operation = (
            self._crypt32.CryptProtectData
            if protect
            else self._crypt32.CryptUnprotectData
        )
        success = operation(
            ctypes.byref(source),
            "EcommerceAIWorker" if protect else None,
            None,
            None,
            None,
            0,
            ctypes.byref(destination),
        )
        if not success:
            raise WorkerConfigurationError(
                f"DPAPI operation failed with Windows error {ctypes.get_last_error()}",
            )
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            self._kernel32.LocalFree(destination.pbData)


@dataclass(frozen=True)
class LocalWorkerConfig:
    server_url: str
    device_id: UUID
    device_token: SecretStr
    device_display_name: str | None
    yingdao_install_root: Path | None
    yingdao_data_root: Path | None
    yingdao_test_app_id: str | None
    configured_at_utc: str | None


def get_worker_data_root() -> Path:
    configured = os.environ.get("ECOMMERCE_WORKER_DATA_ROOT")
    if configured:
        return Path(configured).resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return Path(".").resolve()
    return (Path(local_app_data) / "EcommerceAIWorker").resolve()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class WorkerConfigService:
    def __init__(
        self,
        data_root: Path | None = None,
        *,
        protector: TokenProtector | None = None,
    ) -> None:
        self.data_root = (data_root or get_worker_data_root()).resolve()
        self.path = self.data_root / "config.json"
        self.protector = protector or WindowsDpapiTokenProtector()

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> LocalWorkerConfig:
        if not self.path.is_file():
            raise WorkerConfigurationMissingError("Worker is not configured")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkerConfigurationError("Worker configuration cannot be read") from error
        if not isinstance(payload, dict):
            raise WorkerConfigurationError("Worker configuration must be an object")
        try:
            protected_token = str(payload["device_token_protected"])
            token = self.protector.unprotect(protected_token)
            return LocalWorkerConfig(
                server_url=str(payload["server_url"]).rstrip("/"),
                device_id=UUID(str(payload["device_id"])),
                device_token=SecretStr(token),
                device_display_name=_optional_string(
                    payload.get("device_display_name"),
                ),
                yingdao_install_root=_optional_path(
                    payload.get("yingdao_install_root"),
                ),
                yingdao_data_root=_optional_path(payload.get("yingdao_data_root")),
                yingdao_test_app_id=_optional_string(
                    payload.get("yingdao_test_app_id"),
                ),
                configured_at_utc=_optional_string(
                    payload.get("configured_at_utc"),
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise WorkerConfigurationError("Worker configuration is incomplete") from error

    def save(
        self,
        *,
        server_url: str,
        device_id: UUID,
        device_token: str,
        device_display_name: str | None,
        yingdao_install_root: Path | None,
        yingdao_data_root: Path | None = None,
        yingdao_test_app_id: str | None = None,
    ) -> LocalWorkerConfig:
        if not device_token.strip():
            raise WorkerConfigurationError("Worker Token is required")
        payload = {
            "server_url": server_url.rstrip("/"),
            "device_id": str(device_id),
            "device_display_name": device_display_name,
            "device_token_protected": self.protector.protect(device_token),
            "yingdao_install_root": (
                str(yingdao_install_root.resolve())
                if yingdao_install_root is not None
                else None
            ),
            "yingdao_data_root": (
                str(yingdao_data_root.resolve())
                if yingdao_data_root is not None
                else None
            ),
            "yingdao_test_app_id": yingdao_test_app_id,
            "configured_at_utc": datetime.now(UTC).isoformat(),
        }
        write_json_atomic(self.path, payload)
        return self.load()


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _optional_path(value: object) -> Path | None:
    text = _optional_string(value)
    return Path(text).resolve() if text else None
