import asyncio
import csv
import ctypes
import logging
import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.providers.yingdao.api_response import normalize_shadowbot_api_envelope
from app.providers.yingdao.environment import (
    REQUIRED_YINGDAO_VERSION,
    read_windows_file_version,
)
from app.shared.subprocesses import run_noninteractive_command

_ACCOUNT_PATH = "/api/v1/account/current"
logger = logging.getLogger(__name__)


class YingdaoSessionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider_version: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider_version = provider_version


@dataclass(frozen=True)
class YingdaoProcess:
    pid: int
    executable_path: Path
    version: str


@dataclass(frozen=True)
class YingdaoRuntimeEndpoint:
    process: YingdaoProcess
    base_url: str


@dataclass(frozen=True)
class YingdaoSessionAccount:
    logged_in: bool
    user_name: str | None
    display_name: str | None
    user_id: str | None
    account_type: str | None
    enterprise_name: str | None


@dataclass(frozen=True)
class YingdaoSession:
    endpoint: YingdaoRuntimeEndpoint
    account: YingdaoSessionAccount


class WindowsYingdaoRuntimeLocator:
    def __init__(
        self,
        install_root: Path | None,
        *,
        version_reader: Callable[[Path], str] | None = None,
        startup_timeout_seconds: float = 30,
        probe_timeout_seconds: float = 2,
        probe_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.install_root = install_root.resolve() if install_root else None
        self.version_reader = version_reader or read_windows_file_version
        self.startup_timeout_seconds = startup_timeout_seconds
        self.probe_timeout_seconds = probe_timeout_seconds
        self.probe_transport = probe_transport
        self._resolution_lock = asyncio.Lock()

    async def resolve(self, *, start_if_missing: bool = True) -> YingdaoRuntimeEndpoint:
        async with self._resolution_lock:
            return await self._resolve(start_if_missing=start_if_missing)

    async def _resolve(self, *, start_if_missing: bool) -> YingdaoRuntimeEndpoint:
        processes = await asyncio.to_thread(self._list_shadowbot_processes)
        if processes:
            return await self._resolve_running(processes)
        if not start_if_missing:
            raise YingdaoSessionError("YINGDAO_NOT_RUNNING", "影刀当前未运行")
        executable = await asyncio.to_thread(self._find_supported_executable)
        if executable is None:
            raise YingdaoSessionError("YINGDAO_NOT_INSTALLED", "未安装受支持的影刀 6.3.6")
        try:
            subprocess.Popen(
                [str(executable)],
                cwd=str(executable.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise YingdaoSessionError("YINGDAO_START_FAILED", "影刀 6.3.6 启动失败") from error
        deadline = asyncio.get_running_loop().time() + self.startup_timeout_seconds
        last_error: YingdaoSessionError | None = None
        while asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.5)
            processes = await asyncio.to_thread(self._list_shadowbot_processes)
            if not processes:
                continue
            try:
                return await self._resolve_running(processes)
            except YingdaoSessionError as error:
                last_error = error
                if error.code == "YINGDAO_VERSION_UNSUPPORTED":
                    raise
        raise last_error or YingdaoSessionError(
            "YINGDAO_INTERFACE_UNREACHABLE",
            "影刀 6.3.6 本地会话接口启动超时",
        )

    async def _resolve_running(self, processes: list[YingdaoProcess]) -> YingdaoRuntimeEndpoint:
        versions = {process.version for process in processes}
        if versions != {REQUIRED_YINGDAO_VERSION}:
            running = ", ".join(sorted(versions)) or "unknown"
            raise YingdaoSessionError(
                "YINGDAO_VERSION_UNSUPPORTED",
                f"当前运行的影刀版本为 {running}；Worker V1 仅支持 {REQUIRED_YINGDAO_VERSION}",
                provider_version=running,
            )
        listeners = await asyncio.to_thread(
            self._list_loopback_ports,
            {process.pid for process in processes},
        )
        processes_by_pid = {process.pid: process for process in processes}
        async with httpx.AsyncClient(
            timeout=self.probe_timeout_seconds,
            transport=self.probe_transport,
        ) as client:
            for port, pid in listeners:
                base_url = f"http://127.0.0.1:{port}"
                try:
                    response = await client.get(f"{base_url}{_ACCOUNT_PATH}")
                except httpx.HTTPError:
                    continue
                if response.status_code == 200:
                    return YingdaoRuntimeEndpoint(
                        process=processes_by_pid[pid],
                        base_url=base_url,
                    )
        raise YingdaoSessionError(
            "YINGDAO_INTERFACE_UNREACHABLE",
            "影刀 6.3.6 本地会话接口不可达",
            provider_version=REQUIRED_YINGDAO_VERSION,
        )

    def _find_supported_executable(self) -> Path | None:
        for root in self._candidate_roots():
            for candidate in (
                root / f"shadowbot-{REQUIRED_YINGDAO_VERSION}" / "ShadowBot.Shell.exe",
                root / f"shadowbot-{REQUIRED_YINGDAO_VERSION}" / "ShadowBot.exe",
                root / "ShadowBot.Shell.exe",
                root / "ShadowBot.exe",
            ):
                if not candidate.is_file():
                    continue
                try:
                    if self.version_reader(candidate) == REQUIRED_YINGDAO_VERSION:
                        return candidate.resolve()
                except OSError:
                    continue
        return None

    def _candidate_roots(self) -> tuple[Path, ...]:
        roots: list[Path] = []
        if self.install_root is not None:
            roots.append(self.install_root)
        if os.name == "nt":
            try:
                import winreg
                for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
                        try:
                            key = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0, winreg.KEY_READ | view)
                        except OSError:
                            continue
                        with key:
                            for index in range(winreg.QueryInfoKey(key)[0]):
                                try:
                                    child = winreg.OpenKey(key, winreg.EnumKey(key, index))
                                    with child:
                                        name = str(winreg.QueryValueEx(child, "DisplayName")[0])
                                        location = str(winreg.QueryValueEx(child, "InstallLocation")[0])
                                    if "影刀" in name or "ShadowBot" in name:
                                        roots.append(Path(location))
                                except OSError:
                                    continue
            except OSError:
                pass
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            value = os.getenv(variable)
            if value:
                roots.extend((Path(value) / "ShadowBot", Path(value) / "影刀" / "ShadowBot"))
        return tuple(dict.fromkeys(root.resolve() for root in roots))

    def _list_shadowbot_processes(self) -> list[YingdaoProcess]:
        if os.name != "nt":
            return []
        result = run_noninteractive_command(
            ["tasklist.exe", "/fo", "csv", "/nh"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            logger.warning(
                "ShadowBot process scan failed: return_code=%s stderr=%s",
                result.returncode,
                _command_error_summary(result.stderr),
            )
            return []
        processes: list[YingdaoProcess] = []
        for row in csv.reader(result.stdout.splitlines()):
            if len(row) < 2 or row[0].lower() not in {
                "shadowbot.exe",
                "shadowbot.shell.exe",
            }:
                continue
            try:
                pid = int(row[1])
            except ValueError:
                continue
            try:
                executable = self._query_process_path(pid)
                version = self.version_reader(executable)
            except OSError:
                # A detected ShadowBot process must never be treated as "not
                # running": that could make the Worker start a second version.
                executable = Path(row[0])
                version = "unknown"
            processes.append(YingdaoProcess(pid, executable, version))
        return processes

    @staticmethod
    def _query_process_path(pid: int) -> Path:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            raise OSError(ctypes.get_last_error(), "Cannot inspect ShadowBot process")
        try:
            size = ctypes.c_ulong(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                raise OSError(ctypes.get_last_error(), "Cannot resolve ShadowBot executable")
            return Path(buffer.value).resolve()
        finally:
            kernel32.CloseHandle(handle)

    @staticmethod
    def _list_loopback_ports(pids: set[int]) -> list[tuple[int, int]]:
        result = run_noninteractive_command(
            ["netstat.exe", "-ano", "-p", "tcp"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            logger.warning(
                "ShadowBot listener scan failed: return_code=%s stderr=%s",
                result.returncode,
                _command_error_summary(result.stderr),
            )
            return []
        listeners: list[tuple[int, int]] = []
        pattern = re.compile(r"^\s*TCP\s+(\S+):(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$", re.I)
        for line in result.stdout.splitlines():
            match = pattern.match(line)
            if not match or int(match.group(3)) not in pids:
                continue
            if match.group(1).strip("[]") in {"127.0.0.1", "0.0.0.0", "::1", "::"}:
                listeners.append((int(match.group(2)), int(match.group(3))))
        return sorted(set(listeners))


class YingdaoSessionAdapter:
    def __init__(
        self,
        locator: WindowsYingdaoRuntimeLocator,
        *,
        request_timeout_seconds: float = 5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.locator = locator
        self.request_timeout_seconds = request_timeout_seconds
        self.transport = transport

    async def current(self, *, start_if_missing: bool = True) -> YingdaoSession:
        endpoint = await self.locator.resolve(start_if_missing=start_if_missing)
        try:
            async with httpx.AsyncClient(
                timeout=self.request_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(f"{endpoint.base_url}{_ACCOUNT_PATH}")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise YingdaoSessionError(
                "YINGDAO_INTERFACE_UNREACHABLE",
                "影刀 6.3.6 当前会话接口请求失败",
                provider_version=endpoint.process.version,
            ) from error
        try:
            envelope = normalize_shadowbot_api_envelope(payload)
        except ValueError as error:
            raise YingdaoSessionError(
                "YINGDAO_SESSION_INVALID",
                "影刀 6.3.6 当前会话响应无法解析",
                provider_version=endpoint.process.version,
            ) from error
        if envelope.code != 0:
            raise YingdaoSessionError(
                "YINGDAO_SESSION_INVALID",
                f"影刀 6.3.6 当前会话接口返回错误码 {envelope.code}",
                provider_version=endpoint.process.version,
            )
        if not isinstance(envelope.data, dict):
            raise YingdaoSessionError(
                "YINGDAO_SESSION_INVALID",
                "影刀 6.3.6 当前会话响应数据无效",
                provider_version=endpoint.process.version,
            )
        data = envelope.data
        raw_logged_in = _pick(data, "LoggedIn", "loggedIn")
        if not isinstance(raw_logged_in, bool):
            raise YingdaoSessionError(
                "YINGDAO_SESSION_INVALID",
                "影刀 6.3.6 当前会话响应缺少登录状态",
                provider_version=endpoint.process.version,
            )
        logged_in = raw_logged_in
        account = YingdaoSessionAccount(
            logged_in=logged_in,
            user_name=_string(_pick(data, "UserName", "userName")),
            display_name=_string(_pick(data, "DisplayName", "displayName")),
            user_id=_string(_pick(data, "UserId", "userId")),
            account_type=_string(_pick(data, "AccountType", "accountType")),
            enterprise_name=_string(_pick(data, "EnterpriseName", "enterpriseName")),
        )
        if not logged_in:
            raise YingdaoSessionError(
                "YINGDAO_NOT_LOGGED_IN",
                "影刀 6.3.6 已启动，但当前未登录",
                provider_version=endpoint.process.version,
            )
        if not account.user_id or not (account.display_name or account.user_name):
            raise YingdaoSessionError(
                "YINGDAO_SESSION_INVALID",
                "影刀 6.3.6 当前会话账号信息不完整",
                provider_version=endpoint.process.version,
            )
        return YingdaoSession(endpoint=endpoint, account=account)


def _pick(value: dict[str, Any], *keys: str) -> Any:
    return next((value[key] for key in keys if key in value), None)


def _string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _command_error_summary(value: str | None) -> str:
    summary = " ".join((value or "").split())
    return summary[:240] or "<empty>"
