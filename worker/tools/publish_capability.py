"""Offline-sign one capability release into the protected server directory.

The signing private key stays on the release machine. This command never
deploys, contacts devices, or prints its key or package contents.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def _atomic(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        try:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish(*, source: Path, skill_id: str, version: str, sequence: int,
            private_key_file: Path, output_dir: Path, rpa_helper_sha256: list[str] | None = None) -> str:
    if (not re.fullmatch(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+", skill_id)
            or len(skill_id) > 200 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", version)
            or sequence < 1 or source.name != "capability.py"):
        raise ValueError("invalid capability release metadata")
    code = source.read_bytes()
    if not code or len(code) > 5 * 1024 * 1024:
        raise ValueError("invalid capability entrypoint")
    key = serialization.load_pem_private_key(private_key_file.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("expected an Ed25519 signing key")
    existing = []
    trusted_helpers = []
    manifest_path, signature_path = output_dir / "manifest.json", output_dir / "manifest.sig"
    if manifest_path.exists() or signature_path.exists():
        raw, signature = manifest_path.read_bytes(), signature_path.read_bytes()
        key.public_key().verify(signature, raw)
        manifest = json.loads(raw)
        if manifest.get("schema_version") != 1 or sequence <= manifest.get("sequence", 0):
            raise ValueError("release sequence must increase")
        existing = [item for item in manifest["packages"] if item["skill_id"] != skill_id]
        trusted_helpers = manifest.get("rpa_helper_sha256", [])
    if rpa_helper_sha256 is not None:
        trusted_helpers = rpa_helper_sha256
    if (not isinstance(trusted_helpers, list) or len(trusted_helpers) > 50
            or len(set(trusted_helpers)) != len(trusted_helpers)
            or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in trusted_helpers)):
        raise ValueError("invalid trusted RPA helper digests")
    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr("capability.py", code)
    package_bytes = package_buffer.getvalue()
    digest = hashlib.sha256(package_bytes).hexdigest()
    metadata = {"skill_id": skill_id, "version": version, "entrypoint": "capability.py",
                "host_api_version": 1, "sha256": digest, "size": len(package_bytes)}
    release = {"schema_version": 1, "sequence": sequence, "rpa_helper_sha256": trusted_helpers,
               "packages": sorted([*existing, metadata], key=lambda item: item["skill_id"])}
    raw = json.dumps(release, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    packages_dir = output_dir / "packages"
    packages_dir.mkdir(exist_ok=True)
    artifact = packages_dir / f"{digest}.zip"
    if artifact.exists() and hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
        raise ValueError("existing release artifact is invalid")
    if not artifact.exists():
        _atomic(artifact, package_bytes)
    _atomic(manifest_path, raw)
    _atomic(signature_path, key.sign(raw))
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--private-key-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rpa-helper-sha256", action="append", default=None)
    args = parser.parse_args()
    digest = publish(source=args.source, skill_id=args.skill_id, version=args.version,
                     sequence=args.sequence, private_key_file=args.private_key_file, output_dir=args.output_dir,
                     rpa_helper_sha256=args.rpa_helper_sha256)
    print(f"Published signed capability {args.skill_id} {args.version} sha256={digest}")


if __name__ == "__main__":
    main()
