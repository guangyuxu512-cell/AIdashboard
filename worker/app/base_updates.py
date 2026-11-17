"""Verify and stage signed Worker base releases without touching user data."""
from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import uuid
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.capability_updates import _atomic_write, _local_link, _no_duplicates


MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_UNPACKED_BYTES = 768 * 1024 * 1024
MAX_FILES = 5000
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.I)


class BaseUpdateError(RuntimeError):
    """A fixed code; never includes package contents, credentials or URLs."""


@dataclass(frozen=True)
class BaseRelease:
    sequence: int
    version: str
    digest: str
    size: int
    directory: Path

    @property
    def executable(self) -> Path:
        return self.directory / "app" / "ecommerce-worker.exe"


def _version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise BaseUpdateError("BASE_RELEASE_INVALID")
    return tuple(int(part) for part in match.groups())


def verify_manifest(envelope: dict, public_key: bytes) -> dict:
    try:
        if not isinstance(envelope, dict) or set(envelope) != {"manifest", "signature"}:
            raise ValueError
        encoded, signature = envelope["manifest"], envelope["signature"]
        if not isinstance(encoded, str) or not isinstance(signature, str) or len(encoded) > 128 * 1024 or len(signature) > 128:
            raise ValueError
        raw = base64.b64decode(encoded, validate=True)
        signed = base64.b64decode(signature, validate=True)
        if len(raw) > 64 * 1024 or len(signed) != 64 or len(public_key) != 32:
            raise ValueError
        Ed25519PublicKey.from_public_bytes(public_key).verify(signed, raw)
        item = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
        if (not isinstance(item, dict) or set(item) != {"schema_version", "sequence", "version", "sha256", "size", "platform"}
                or type(item["schema_version"]) is not int or item["schema_version"] != 1
                or type(item["sequence"]) is not int or item["sequence"] < 1
                or not isinstance(item["sha256"], str) or not _DIGEST.fullmatch(item["sha256"])
                or type(item["size"]) is not int or not 0 < item["size"] <= MAX_ARCHIVE_BYTES
                or item["platform"] != "windows-x86_64"):
            raise ValueError
        _version(item["version"])
        return item
    except (InvalidSignature, ValueError, TypeError, UnicodeError, KeyError, BaseUpdateError):
        raise BaseUpdateError("BASE_MANIFEST_INVALID") from None


def archive_members(archive: zipfile.ZipFile) -> tuple[list[zipfile.ZipInfo], int]:
    infos = archive.infolist()
    if not infos or len(infos) > MAX_FILES:
        raise BaseUpdateError("BASE_ARCHIVE_INVALID")
    total, names, files = 0, set(), set()
    for info in infos:
        name = info.orig_filename
        path = PurePosixPath(name)
        parts = name.rstrip("/").split("/")
        mode = (info.external_attr >> 16) & 0o170000
        if (not name or name.startswith("/") or "\\" in name or ":" in name
                or any(ord(char) < 32 for char in name) or any(part in ("", ".", "..") for part in parts)
                or any(part.endswith((".", " ")) or _RESERVED.fullmatch(part) for part in parts)
                or info.flag_bits & 1 or mode not in (0, stat.S_IFREG, stat.S_IFDIR)):
            raise BaseUpdateError("BASE_ARCHIVE_INVALID")
        normalized = str(path).casefold().rstrip("/")
        if normalized in names:
            raise BaseUpdateError("BASE_ARCHIVE_INVALID")
        names.add(normalized)
        if not info.is_dir():
            if mode == stat.S_IFDIR or info.file_size < 0:
                raise BaseUpdateError("BASE_ARCHIVE_INVALID")
            total += info.file_size
            files.add(str(path))
    required = {"ecommerce-worker.exe", "VERSION", "_internal/capability-public-key.txt"}
    if total > MAX_UNPACKED_BYTES or not required.issubset(files):
        raise BaseUpdateError("BASE_ARCHIVE_INVALID")
    return infos, total


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_release(release: BaseRelease, public_key: bytes) -> None:
    try:
        if any(_local_link(path) for path in (release.directory, release.directory.parent, release.directory.parent.parent)):
            raise ValueError
        envelope_path, archive_path = release.directory / "envelope.json", release.directory / "package.zip"
        if _local_link(envelope_path) or _local_link(archive_path) or archive_path.stat().st_size != release.size:
            raise ValueError
        item = verify_manifest(json.loads(envelope_path.read_text(encoding="utf-8")), public_key)
        if (item["sequence"], item["version"], item["sha256"], item["size"]) != (
                release.sequence, release.version, release.digest, release.size):
            raise ValueError
        if _hash_file(archive_path) != release.digest:
            raise ValueError
        app = release.directory / "app"
        if _local_link(app):
            raise ValueError
        with zipfile.ZipFile(archive_path) as archive:
            infos, _ = archive_members(archive)
            expected = set()
            for info in infos:
                if info.is_dir():
                    continue
                path = app.joinpath(*PurePosixPath(info.orig_filename).parts)
                if any(_local_link(parent) for parent in (path, *path.parents) if parent != app.parent and parent.exists()
                       and (parent == app or app in parent.parents)):
                    raise ValueError
                if not path.is_file() or path.stat().st_size != info.file_size:
                    raise ValueError
                with archive.open(info) as source, path.open("rb") as target:
                    while True:
                        a, b = source.read(1024 * 1024), target.read(1024 * 1024)
                        if a != b:
                            raise ValueError
                        if not a:
                            break
                expected.add(path.relative_to(app).as_posix().casefold())
            actual = set()
            for current, dirs, files in os.walk(app, followlinks=False):
                for name in dirs + files:
                    path = Path(current) / name
                    if _local_link(path):
                        raise ValueError
                actual.update((Path(current) / name).relative_to(app).as_posix().casefold() for name in files)
            packaged_key = base64.b64decode((app / "_internal/capability-public-key.txt").read_text(encoding="ascii").strip(), validate=True)
            if (actual != expected or (app / "VERSION").read_text(encoding="utf-8-sig").strip() != release.version
                    or packaged_key != public_key):
                raise ValueError
    except (OSError, ValueError, UnicodeError, zipfile.BadZipFile, BaseUpdateError):
        raise BaseUpdateError("BASE_RELEASE_INVALID") from None


class BaseUpdater:
    def __init__(self, root: Path, public_key: bytes, current_version: str):
        self.root = Path(root)
        if not self.root.is_absolute() or str(self.root).startswith(("\\\\", "//")) or len(public_key) != 32:
            raise ValueError("Invalid Worker release configuration")
        self.public_key = public_key
        self.current_version = _version(current_version)

    def state(self) -> dict:
        path = self.root / "state.json"
        if not path.exists():
            return {}
        try:
            if _local_link(path) or path.stat().st_size > 4096:
                raise ValueError
            value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicates)
            allowed = {"accepted_sequence", "active_version", "active_digest", "active_size", "rejected_digest", "rejected_sequence"}
            if not isinstance(value, dict) or set(value) - allowed:
                raise ValueError
            active = {"accepted_sequence", "active_version", "active_digest", "active_size"}
            if active & set(value):
                if not active.issubset(value) or type(value["accepted_sequence"]) is not int or value["accepted_sequence"] < 1:
                    raise ValueError
                _version(value["active_version"])
                if (not isinstance(value["active_digest"], str) or not _DIGEST.fullmatch(value["active_digest"])
                        or type(value["active_size"]) is not int or not 0 < value["active_size"] <= MAX_ARCHIVE_BYTES):
                    raise ValueError
            rejected = value.get("rejected_digest")
            if rejected is not None and (not isinstance(rejected, str) or not _DIGEST.fullmatch(rejected)):
                raise ValueError
            rejected_sequence = value.get("rejected_sequence")
            if rejected_sequence is not None and (type(rejected_sequence) is not int or rejected_sequence < 1 or rejected is None):
                raise ValueError
            return value
        except (OSError, ValueError, UnicodeError, BaseUpdateError):
            raise BaseUpdateError("BASE_STATE_INVALID") from None

    def save_state(self, value: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        if _local_link(self.root):
            raise BaseUpdateError("BASE_STORAGE_INVALID")
        _atomic_write(self.root / "state.json", json.dumps(value, separators=(",", ":")).encode())

    def active_release(self) -> BaseRelease | None:
        state = self.state()
        if "active_digest" not in state:
            return None
        release = BaseRelease(state["accepted_sequence"], state["active_version"], state["active_digest"],
                              state["active_size"], self.root / "releases" / f'{state["active_digest"][:16]}-{state["accepted_sequence"]}')
        verify_release(release, self.public_key)
        return release

    def accept(self, release: BaseRelease) -> None:
        verify_release(release, self.public_key)
        self.save_state({"accepted_sequence": release.sequence, "active_version": release.version,
                         "active_digest": release.digest, "active_size": release.size})

    def reject(self, release: BaseRelease) -> None:
        value = self.state()
        value["rejected_digest"] = release.digest
        value["rejected_sequence"] = release.sequence
        self.save_state(value)

    async def _candidate(self, client) -> tuple[dict, dict] | None:
        envelope = await client.fetch_base_release_manifest()
        item = verify_manifest(envelope, self.public_key)
        state = self.state()
        if (_version(item["version"]) <= self.current_version
                or item["sequence"] <= state.get("accepted_sequence", 0)
                or (item["sha256"] == state.get("rejected_digest")
                    and item["sequence"] <= state.get("rejected_sequence", item["sequence"]))):
            return None
        return envelope, item

    async def update_available(self, client) -> bool:
        """Check only the signed manifest; do not touch an active task."""
        return await self._candidate(client) is not None

    async def stage_when_idle(self, client, *, idle: bool) -> BaseRelease | None:
        if not idle:
            return None
        candidate = await self._candidate(client)
        if candidate is None:
            return None
        envelope, item = candidate
        self.root.mkdir(parents=True, exist_ok=True)
        releases = self.root / "releases"
        releases.mkdir(exist_ok=True)
        if _local_link(self.root) or _local_link(releases):
            raise BaseUpdateError("BASE_STORAGE_INVALID")
        # Full SHA-256 remains in the signed manifest and state.  Keeping only
        # a prefix in the directory name avoids Windows path-length failures;
        # an existing directory is always checked against the complete digest.
        target = releases / f'{item["sha256"][:16]}-{item["sequence"]}'
        release = BaseRelease(item["sequence"], item["version"], item["sha256"], item["size"], target)
        if target.exists():
            verify_release(release, self.public_key)
            return release
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=releases))
        try:
            archive_path = staging / "package.zip"
            await client.download_base_release(item["sha256"], size=item["size"], target=archive_path)
            if archive_path.stat().st_size != item["size"] or _hash_file(archive_path) != item["sha256"]:
                raise BaseUpdateError("BASE_ARCHIVE_INVALID")
            with zipfile.ZipFile(archive_path) as archive:
                infos, total = archive_members(archive)
                if shutil.disk_usage(staging).free < total + 32 * 1024 * 1024:
                    raise BaseUpdateError("BASE_DISK_FULL")
                app = staging / "app"
                app.mkdir()
                for info in infos:
                    destination = app.joinpath(*PurePosixPath(info.orig_filename).parts)
                    if info.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(info) as source, destination.open("xb") as output:
                            shutil.copyfileobj(source, output, length=1024 * 1024)
            (staging / "envelope.json").write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
            staged = BaseRelease(release.sequence, release.version, release.digest, release.size, staging)
            verify_release(staged, self.public_key)
            os.replace(staging, target)
            return release
        except (OSError, zipfile.BadZipFile) as error:
            raise BaseUpdateError("BASE_STORAGE_INVALID") from error
        finally:
            if staging.exists() and staging.name.startswith(".staging-") and staging.resolve().parent == releases.resolve():
                shutil.rmtree(staging)
