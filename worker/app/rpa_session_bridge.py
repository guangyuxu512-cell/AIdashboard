"""Restricted same-user stdio bridge to the local RPA application.

The remote server cannot choose a program or a local path.  Session values
are returned only in memory and are never written to Worker runtime files.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import AsyncIterator, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError


_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_MAX_LINE = 1024 * 1024
_MAX_HELPER_FILES = 20_000
_MAX_HELPER_BYTES = 1024 * 1024 * 1024


class RpaBridgeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code if _ERROR_CODE.fullmatch(code) else "RPA_BRIDGE_FAILED"
        super().__init__(self.code)


class BridgeDiscovery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)
    contract_version: Literal[1] = Field(alias="contractVersion")
    installation_id: UUID = Field(alias="installationId")
    app_version: str = Field(alias="appVersion", min_length=1, max_length=64)
    helper_path: str = Field(alias="helperPath", min_length=1, max_length=4096)
    database_path: str = Field(alias="databasePath", min_length=1, max_length=4096)


@dataclass(frozen=True, slots=True)
class TrustedRpaInstallation:
    """Installation root and full helper-tree digest from a trusted release.

    Values come from Worker local configuration / a verified release manifest,
    never the discovery marker or a remote task body.
    """

    installation_root: Path
    helper_tree_sha256: str


def helper_tree_digest(root: Path) -> str:
    """Digest all names and bytes, including PyInstaller onedir dependencies."""
    if not root.is_dir() or root.is_symlink() or not root.is_absolute():
        raise RpaBridgeError("RPA_HELPER_UNTRUSTED")
    files: list[tuple[str, Path, int]] = []
    total = 0
    try:
        for current, directories, filenames in os.walk(root, followlinks=False):
            for name in [*directories, *filenames]:
                path = Path(current) / name
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
                    raise ValueError("linked helper path")
                if not path.is_file():
                    continue
                relative = path.relative_to(root).as_posix()
                total += metadata.st_size
                files.append((relative, path, metadata.st_size))
                if len(files) > _MAX_HELPER_FILES or total > _MAX_HELPER_BYTES:
                    raise ValueError("helper tree too large")
        if not files:
            raise ValueError("empty helper tree")
        digest = hashlib.sha256()
        for relative, path, size in sorted(files):
            encoded_name = relative.encode("utf-8")
            digest.update(len(encoded_name).to_bytes(4, "big"))
            digest.update(encoded_name)
            digest.update(size.to_bytes(8, "big"))
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        return digest.hexdigest()
    except (OSError, ValueError, UnicodeError):
        raise RpaBridgeError("RPA_HELPER_UNTRUSTED") from None


def verify_discovery(
    info: BridgeDiscovery, data_directory: Path, trust: TrustedRpaInstallation,
) -> None:
    try:
        expected_root = trust.installation_root
        helper = Path(info.helper_path)
        database = Path(info.database_path)
        if (
            not expected_root.is_absolute() or not helper.is_absolute() or not database.is_absolute()
            or any(".." in path.parts for path in (expected_root, helper, database))
            or str(expected_root).startswith(("\\\\", "//"))
            or info.helper_path.startswith(("\\\\", "//"))
            or info.database_path.startswith(("\\\\", "//"))
            or not re.fullmatch(r"[0-9a-f]{64}", trust.helper_tree_sha256)
        ):
            raise ValueError("invalid trusted paths")
        expected_root = expected_root.resolve(strict=True)
        expected_helper = expected_root / "resources" / "listing-worker" / "listing-worker.exe"
        helper_root = expected_helper.parent
        if (
            helper.resolve(strict=True) != expected_helper
            or database.resolve(strict=True) != (data_directory.resolve() / "shop-manager.db")
            or not expected_helper.is_file() or not database.is_file()
            or helper_tree_digest(helper_root) != trust.helper_tree_sha256
        ):
            raise ValueError("untrusted helper")
    except (OSError, ValueError):
        raise RpaBridgeError("RPA_HELPER_UNTRUSTED") from None


class LocalShop(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)
    local_shop_id: str = Field(alias="localShopId", min_length=1, max_length=160)
    platform_shop_id: str | None = Field(alias="platformShopId", default=None, max_length=160)
    shop_name: str = Field(alias="shopName", min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=64)
    browser_open: bool | None = Field(alias="browserOpen", default=None)


class LocalShopInventory(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)
    installation_id: UUID = Field(alias="installationId")
    shops: list[LocalShop] = Field(max_length=500)


class LocalCookie(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)
    name: str = Field(min_length=1, max_length=512)
    value: SecretStr = Field(repr=False)
    domain: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1, max_length=2048)
    secure: bool = False
    http_only: bool = Field(default=False, alias="httpOnly")
    same_site: Literal["Strict", "Lax", "None"] | None = Field(default=None, alias="sameSite")
    expiration_date: float | None = Field(default=None, alias="expirationDate")


class LocalSession(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)
    local_shop_id: str = Field(alias="localShopId", min_length=1, max_length=160)
    platform_shop_id: str = Field(alias="platformShopId", min_length=1, max_length=160)
    platform: Literal["douyin"]
    user_agent: str = Field(alias="userAgent", min_length=1, max_length=2048)
    cookies: list[LocalCookie] = Field(min_length=1, max_length=500, repr=False)


def discover_rpa(data_directory: Path, trust: TrustedRpaInstallation) -> BridgeDiscovery:
    """Read the fixed local discovery file, never a remote-provided path."""
    data_directory = data_directory.resolve()
    marker = data_directory / "worker-session-bridge.json"
    try:
        raw = marker.read_bytes()
        if len(raw) > 16 * 1024:
            raise ValueError("discovery is too large")
        info = BridgeDiscovery.model_validate_json(raw)
        verify_discovery(info, data_directory, trust)
        return info
    except (OSError, ValueError, ValidationError):
        raise RpaBridgeError("RPA_NOT_READY") from None


def default_rpa_data_directory() -> Path:
    value = os.environ.get("APPDATA")
    if not value:
        raise RpaBridgeError("RPA_NOT_READY")
    return Path(value) / "店群自动化软件" / "data"


class RpaLocalBridge:
    def __init__(self, discovery: BridgeDiscovery, data_directory: Path,
                 trust: TrustedRpaInstallation, *, timeout: float = 15) -> None:
        self.discovery = discovery
        self.data_directory = data_directory
        self.trust = trust
        self.timeout = timeout

    @asynccontextmanager
    async def _connection(self) -> AsyncIterator["_BridgeProcess"]:
        # Recheck immediately before launch; the marker never chooses an exe.
        verify_discovery(self.discovery, self.data_directory, self.trust)
        try:
            environment = dict(os.environ)
            environment.pop("SHOP_FLEET_WORKER_TEST", None)
            environment.pop("SHOP_FLEET_WORKER_TEST_DELAY_MS", None)
            process = await asyncio.create_subprocess_exec(
                self.discovery.helper_path, "--worker-session-stdio",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=_MAX_LINE, env=environment,
            )
        except OSError:
            raise RpaBridgeError("RPA_NOT_READY") from None
        bridge = _BridgeProcess(process, self.timeout)
        try:
            init = await bridge.call({"type": "init", "databasePath": self.discovery.database_path})
            if (
                init.get("contractVersion") != 1
                or str(init.get("installationId")) != str(self.discovery.installation_id)
            ):
                raise RpaBridgeError("RPA_IDENTITY_MISMATCH")
            yield bridge
        finally:
            await bridge.close()

    async def list_shops(self) -> LocalShopInventory:
        async with self._connection() as bridge:
            raw = await bridge.call({"type": "list_shops"})
            try:
                inventory = LocalShopInventory.model_validate(raw)
            except ValidationError:
                raise RpaBridgeError("RPA_BRIDGE_RESPONSE_INVALID") from None
            if inventory.installation_id != self.discovery.installation_id:
                raise RpaBridgeError("RPA_IDENTITY_MISMATCH")
            if len({shop.local_shop_id for shop in inventory.shops}) != len(inventory.shops):
                raise RpaBridgeError("RPA_BRIDGE_RESPONSE_INVALID")
            return inventory

    async def read_session(self, local_shop_id: str, platform_shop_id: str) -> LocalSession:
        async with self._connection() as bridge:
            raw = await bridge.call({"type": "read_session", "localShopId": local_shop_id,
                                     "expectedPlatformShopId": platform_shop_id})
            try:
                session = LocalSession.model_validate(raw)
            except ValidationError:
                raise RpaBridgeError("RPA_BRIDGE_RESPONSE_INVALID") from None
            if session.local_shop_id != local_shop_id or session.platform_shop_id != platform_shop_id:
                raise RpaBridgeError("RPA_SHOP_IDENTITY_MISMATCH")
            for cookie in session.cookies:
                if cookie.domain.lstrip(".").lower() not in {"jinritemai.com", "fxg.jinritemai.com"}:
                    raise RpaBridgeError("RPA_BRIDGE_RESPONSE_INVALID")
                if not cookie.path.startswith("/"):
                    raise RpaBridgeError("RPA_BRIDGE_RESPONSE_INVALID")
            return session


class RpaAutoBridge:
    """Re-read same-user discovery so opening RPA later needs no Worker restart."""
    def __init__(self, data_directory: Path, trusted_digests) -> None:
        self.data_directory = data_directory
        self.trusted_digests = trusted_digests

    def _bridge(self) -> RpaLocalBridge:
        try:
            raw = (self.data_directory / "worker-session-bridge.json").read_bytes()
            if len(raw) > 16 * 1024:
                raise ValueError("marker too large")
            info = BridgeDiscovery.model_validate_json(raw)
            helper = Path(info.helper_path)
            if (not helper.is_absolute() or info.helper_path.startswith(("\\\\", "//"))
                    or ".." in helper.parts or tuple(part.lower() for part in helper.parts[-3:])
                    != ("resources", "listing-worker", "listing-worker.exe")):
                raise ValueError("invalid helper location")
            root = helper.parents[2].resolve(strict=True)
            if not (root / "店群自动化软件.exe").is_file():
                raise ValueError("RPA installation missing")
            digest = helper_tree_digest(root / "resources/listing-worker")
            if digest not in self.trusted_digests():
                raise ValueError("unapproved helper release")
            trust = TrustedRpaInstallation(root, digest)
            verify_discovery(info, self.data_directory, trust)
            return RpaLocalBridge(info, self.data_directory, trust)
        except RpaBridgeError:
            raise
        except (OSError, ValueError, ValidationError, IndexError):
            raise RpaBridgeError("RPA_HELPER_UNTRUSTED") from None

    async def list_shops(self) -> LocalShopInventory:
        return await self._bridge().list_shops()

    async def read_session(self, local_shop_id: str, platform_shop_id: str) -> LocalSession:
        return await self._bridge().read_session(local_shop_id, platform_shop_id)


class _BridgeProcess:
    def __init__(self, process: asyncio.subprocess.Process, timeout: float) -> None:
        self.process = process
        self.timeout = timeout

    async def call(self, data: dict) -> dict:
        assert self.process.stdin is not None and self.process.stdout is not None
        encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            self.process.stdin.write(encoded)
            await asyncio.wait_for(self.process.stdin.drain(), self.timeout)
            line = await asyncio.wait_for(self.process.stdout.readline(), self.timeout)
            if not line or len(line) > _MAX_LINE:
                raise ValueError("invalid bridge response")
            body = json.loads(line)
            if not isinstance(body, dict):
                raise ValueError("invalid bridge response")
            if body.get("ok") is False:
                raise RpaBridgeError(str(body.get("errorCode") or "RPA_BRIDGE_FAILED"))
            if body.get("ok") is not True or not isinstance(body.get("result"), dict):
                raise ValueError("invalid bridge response")
            return body["result"]
        except RpaBridgeError:
            raise
        except (OSError, ValueError, TypeError, asyncio.TimeoutError):
            raise RpaBridgeError("RPA_BRIDGE_UNAVAILABLE") from None

    async def close(self) -> None:
        if self.process.stdin is not None:
            self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), 2)
        except asyncio.TimeoutError:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 2)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
