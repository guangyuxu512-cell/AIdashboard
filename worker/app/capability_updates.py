"""Install signed capability packages without trusting task-provided paths."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from typing import Any, Callable, Protocol
import zipfile
import zlib

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


MAX_PACKAGE_BYTES = 25 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
MAX_FILES = 256
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


class CapabilityUpdateError(RuntimeError):
    """A fixed, non-sensitive failure code; old active packages remain intact."""


@dataclass(frozen=True)
class ActiveCapability:
    skill_id: str
    version: str
    path: Path
    entrypoint: Path
    sha256: str


class CapabilityClient(Protocol):
    async def fetch_capability_manifest(self) -> dict[str, str]: ...

    async def download_capability_package(self, digest: str, *, max_size: int) -> bytes: ...


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _local_link(path: Path) -> bool:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return True
    return bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def _atomic_write(path: Path, data: bytes) -> None:
    descriptor, name = tempfile.mkstemp(dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _archive_contents(data: bytes) -> dict[str, bytes]:
    """Accept only bounded, regular relative files and never extract links."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise ValueError
            result: dict[str, bytes] = {}
            seen: set[str] = set()
            total = 0
            for info in infos:
                # On Windows ZipInfo.filename normalizes backslashes.  Inspect
                # the original archive name before pathlib can hide them.
                name = info.orig_filename
                path = PurePosixPath(name)
                mode = (info.external_attr >> 16) & 0o170000
                if (
                    not name or name.startswith("/") or "\\" in name or ":" in name
                    or any(ord(character) < 32 for character in name)
                    or any(part in (".", "..") for part in name.split("/"))
                    or info.flag_bits & 1
                    or mode not in (0, stat.S_IFREG, stat.S_IFDIR)
                ):
                    raise ValueError
                normalized = str(path).casefold()
                if normalized in seen:
                    raise ValueError
                seen.add(normalized)
                if info.is_dir():
                    continue
                if mode == stat.S_IFDIR:
                    raise ValueError
                total += info.file_size
                if total > MAX_PACKAGE_BYTES:
                    raise ValueError
                with archive.open(info) as stream:
                    value = stream.read(info.file_size + 1)
                if len(value) != info.file_size:
                    raise ValueError
                result[str(path)] = value
            return result
    except (OSError, RuntimeError, ValueError, EOFError, UnicodeError, zlib.error,
            zipfile.BadZipFile, NotImplementedError):
        raise CapabilityUpdateError("CAPABILITY_ARCHIVE_INVALID") from None


def _matches_tree(directory: Path, expected: dict[str, bytes]) -> bool:
    if not directory.is_dir() or _local_link(directory):
        return False
    actual: set[str] = set()
    for current, dirs, files in os.walk(directory, followlinks=False):
        base = Path(current)
        for name in dirs + files:
            path = base / name
            if _local_link(path):
                return False
        for name in files:
            path = base / name
            relative = path.relative_to(directory).as_posix()
            if relative not in expected or path.stat().st_size != len(expected[relative]):
                return False
            if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(expected[relative]).digest():
                return False
            actual.add(relative)
    return actual == set(expected)


class CapabilityUpdater:
    """Keep the last verified release active until an idle, verified switch."""

    def __init__(
        self,
        root: Path,
        public_key: bytes,
        host_api_version: int,
    ) -> None:
        root = Path(root)
        if (not root.is_absolute() or str(root).startswith(("\\\\", "//"))
            or not isinstance(public_key, bytes) or len(public_key) != 32
            or type(host_api_version) is not int or host_api_version < 1):
            raise ValueError("Invalid trusted capability configuration")
        self.root = root
        self.public_key = Ed25519PublicKey.from_public_bytes(public_key)
        self.host_api_version = host_api_version

    def _manifest(self, envelope: dict[str, str]) -> tuple[bytes, dict[str, Any], list[dict[str, Any]]]:
        try:
            if set(envelope) != {"manifest", "signature"}:
                raise ValueError
            encoded, signed = envelope["manifest"], envelope["signature"]
            if not isinstance(encoded, str) or not isinstance(signed, str):
                raise ValueError
            if len(encoded) > MAX_MANIFEST_BYTES * 2 or len(signed) > 128:
                raise ValueError
            raw = base64.b64decode(encoded, validate=True)
            signature = base64.b64decode(signed, validate=True)
            if len(raw) > MAX_MANIFEST_BYTES or len(signature) != 64:
                raise ValueError
            self.public_key.verify(signature, raw)
            manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
            required = {"schema_version", "sequence", "packages"}
            if not isinstance(manifest, dict) or set(manifest) not in (required, required | {"rpa_helper_sha256"}):
                raise ValueError
            if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
                raise ValueError
            if type(manifest["sequence"]) is not int or manifest["sequence"] < 1:
                raise ValueError
            packages = manifest["packages"]
            helper_digests = manifest.get("rpa_helper_sha256", [])
            if (not isinstance(helper_digests, list) or len(helper_digests) > 50
                    or any(not isinstance(value, str) or not _DIGEST.fullmatch(value) for value in helper_digests)
                    or len(set(helper_digests)) != len(helper_digests)):
                raise ValueError
            if not isinstance(packages, list) or len(packages) > MAX_FILES:
                raise ValueError
            selected = []
            seen: set[str] = set()
            for package in packages:
                if not isinstance(package, dict) or set(package) != {
                    "skill_id", "version", "entrypoint", "host_api_version", "sha256", "size"
                }:
                    raise ValueError
                skill, version, digest = package["skill_id"], package["version"], package["sha256"]
                if (not isinstance(skill, str) or len(skill) > 200 or not _IDENTIFIER.fullmatch(skill)
                    or not isinstance(version, str) or not _VERSION.fullmatch(version)
                    or not isinstance(digest, str) or not _DIGEST.fullmatch(digest)
                    or type(package["size"]) is not int or not 0 < package["size"] <= MAX_PACKAGE_BYTES
                    or type(package["host_api_version"]) is not int
                    or not isinstance(package["entrypoint"], str)):
                    raise ValueError
                if skill in seen:
                    raise ValueError
                seen.add(skill)
                # Only a signed manifest can introduce a skill.  Its ID is
                # metadata, never an executable path or a task-supplied command.
                if package["entrypoint"] != "capability.py" or package["host_api_version"] != self.host_api_version:
                    raise ValueError
                selected.append(package)
            return raw, manifest, selected
        except (InvalidSignature, ValueError, TypeError, UnicodeError, KeyError):
            raise CapabilityUpdateError("CAPABILITY_MANIFEST_INVALID") from None

    def trusted_rpa_digests(self) -> frozenset[str]:
        current = self._current()
        return frozenset(current[2].get("rpa_helper_sha256", ())) if current is not None else frozenset()

    def _current(self) -> tuple[dict[str, str], bytes, dict[str, Any], list[dict[str, Any]]] | None:
        path = self.root / "active.json"
        if not path.exists():
            return None
        try:
            if _local_link(path) or path.stat().st_size > MAX_MANIFEST_BYTES * 2:
                raise ValueError
            envelope = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
            raw, manifest, selected = self._manifest(envelope)
            return envelope, raw, manifest, selected
        except (OSError, ValueError, TypeError, UnicodeError):
            raise CapabilityUpdateError("CAPABILITY_ACTIVE_INVALID") from None

    def active_packages(self) -> tuple[ActiveCapability, ...]:
        current = self._current()
        if current is None:
            return ()
        packages: list[ActiveCapability] = []
        for package in current[3]:
            digest = package["sha256"]
            archive_path = self.root / "archives" / f"{digest}.zip"
            package_path = self.root / "packages" / digest
            try:
                if _local_link(archive_path) or archive_path.stat().st_size != package["size"]:
                    raise ValueError
                data = archive_path.read_bytes()
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError
                contents = _archive_contents(data)
                if package["entrypoint"] not in contents or not _matches_tree(package_path, contents):
                    raise ValueError
            except (OSError, ValueError):
                raise CapabilityUpdateError("CAPABILITY_ACTIVE_INVALID") from None
            packages.append(ActiveCapability(package["skill_id"], package["version"], package_path,
                                             package_path / package["entrypoint"], digest))
        return tuple(packages)

    async def sync_when_idle(
        self,
        client: CapabilityClient,
        *,
        idle: bool,
        validate_entry: Callable[[str, str, bytes], None] | None = None,
    ) -> bool:
        """Caller must serialize this whole operation with task claim/execution."""
        if not idle:
            return False
        envelope = await client.fetch_capability_manifest()
        raw, manifest, packages = self._manifest(envelope)
        current = self._current()
        if current is not None:
            if manifest["sequence"] < current[2]["sequence"]:
                raise CapabilityUpdateError("CAPABILITY_ROLLBACK_REJECTED")
            if manifest["sequence"] == current[2]["sequence"]:
                if raw != current[1]:
                    raise CapabilityUpdateError("CAPABILITY_SEQUENCE_CONFLICT")
                self.active_packages()
                return False
        self.root.mkdir(parents=True, exist_ok=True)
        archives = self.root / "archives"
        unpacked = self.root / "packages"
        archives.mkdir(exist_ok=True)
        unpacked.mkdir(exist_ok=True)
        if any(_local_link(path) for path in (self.root, archives, unpacked)):
            raise CapabilityUpdateError("CAPABILITY_STORAGE_INVALID")
        for package in packages:
            digest = package["sha256"]
            archive_path = archives / f"{digest}.zip"
            target = unpacked / digest
            if archive_path.exists():
                if _local_link(archive_path) or archive_path.stat().st_size != package["size"]:
                    raise CapabilityUpdateError("CAPABILITY_ARCHIVE_INVALID")
                data = archive_path.read_bytes()
            else:
                data = await client.download_capability_package(digest, max_size=MAX_PACKAGE_BYTES)
            if (not isinstance(data, bytes) or len(data) != package["size"]
                or hashlib.sha256(data).hexdigest() != digest):
                raise CapabilityUpdateError("CAPABILITY_ARCHIVE_INVALID")
            contents = _archive_contents(data)
            if package["entrypoint"] not in contents:
                raise CapabilityUpdateError("CAPABILITY_ARCHIVE_INVALID")
            if validate_entry is not None:
                try:
                    validate_entry(package["skill_id"], package["version"], contents[package["entrypoint"]])
                except Exception:
                    raise CapabilityUpdateError("CAPABILITY_ENTRY_INVALID") from None
            if not archive_path.exists():
                _atomic_write(archive_path, data)
            if target.exists():
                if not _matches_tree(target, contents):
                    raise CapabilityUpdateError("CAPABILITY_STORAGE_INVALID")
            else:
                staging = Path(tempfile.mkdtemp(prefix="staging-", dir=unpacked))
                try:
                    for name, value in contents.items():
                        destination = staging.joinpath(*PurePosixPath(name).parts)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(value)
                    os.replace(staging, target)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
        encoded = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
        _atomic_write(self.root / "active.json", encoded)
        return True
