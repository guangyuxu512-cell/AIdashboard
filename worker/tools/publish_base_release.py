"""Prepare one signed Worker release for the existing private distribution store."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.base_updates import MAX_ARCHIVE_BYTES, archive_members, verify_manifest
from app.capability_updates import _atomic_write


def publish(*, archive: Path, version: str, sequence: int, private_key_file: Path, output_dir: Path) -> str:
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version) or sequence < 1:
        raise ValueError("invalid Worker release metadata")
    if not archive.is_file() or archive.is_symlink() or not 0 < archive.stat().st_size <= MAX_ARCHIVE_BYTES:
        raise ValueError("invalid Worker release archive")
    key = serialization.load_pem_private_key(private_key_file.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("expected an Ed25519 signing key")
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    with zipfile.ZipFile(archive) as source:
        archive_members(source)
        if (source.read("VERSION").decode("utf-8-sig").strip() != version
                or base64.b64decode(source.read("_internal/capability-public-key.txt").strip(), validate=True) != public):
            raise ValueError("Worker archive version or trust key mismatch")
    manifest_path, signature_path = output_dir / "manifest.json", output_dir / "manifest.sig"
    if manifest_path.exists() or signature_path.exists():
        old = {"manifest": base64.b64encode(manifest_path.read_bytes()).decode(),
               "signature": base64.b64encode(signature_path.read_bytes()).decode()}
        if sequence <= verify_manifest(old, public)["sequence"]:
            raise ValueError("release sequence must increase")
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    result = digest.hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    packages = output_dir / "packages"
    packages.mkdir(exist_ok=True)
    target = packages / f"{result}.zip"
    if target.exists():
        with target.open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
        if actual != result:
            raise ValueError("existing release artifact is invalid")
    else:
        fd, name = tempfile.mkstemp(prefix=".worker-base-", dir=packages)
        try:
            with os.fdopen(fd, "wb") as out, archive.open("rb") as source:
                shutil.copyfileobj(source, out, length=1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, target)
        finally:
            Path(name).unlink(missing_ok=True)
    release = {"schema_version": 1, "sequence": sequence, "version": version,
               "sha256": result, "size": archive.stat().st_size, "platform": "windows-x86_64"}
    raw = json.dumps(release, separators=(",", ":"), sort_keys=True).encode("utf-8")
    _atomic_write(manifest_path, raw)
    _atomic_write(signature_path, key.sign(raw))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--private-key-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    digest = publish(archive=args.archive, version=args.version, sequence=args.sequence,
                     private_key_file=args.private_key_file, output_dir=args.output_dir)
    print(f"Prepared signed Worker release {args.version} sha256={digest}")


if __name__ == "__main__":
    main()
