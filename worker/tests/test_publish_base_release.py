import base64
import io
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from app.base_updates import verify_manifest
from tools.publish_base_release import publish


def test_publisher_signs_verified_package_without_github_credentials(tmp_path, monkeypatch):
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "private.pem"
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    archive = tmp_path / "worker.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("ecommerce-worker.exe", b"synthetic")
        z.writestr("VERSION", "0.5.9")
        z.writestr("_internal/capability-public-key.txt", base64.b64encode(public))
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    output = tmp_path / "worker-base"
    digest = publish(archive=archive, version="0.5.9", sequence=1, private_key_file=private, output_dir=output)
    envelope = {"manifest": base64.b64encode((output / "manifest.json").read_bytes()).decode(),
                "signature": base64.b64encode((output / "manifest.sig").read_bytes()).decode()}
    assert verify_manifest(envelope, public)["sha256"] == digest
    assert (output / "packages" / f"{digest}.zip").read_bytes() == archive.read_bytes()
    with pytest.raises(ValueError):
        publish(archive=archive, version="0.5.9", sequence=1, private_key_file=private, output_dir=output)


def test_publisher_rejects_package_with_different_trust_anchor(tmp_path):
    key = Ed25519PrivateKey.generate()
    private = tmp_path / "private.pem"
    private.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    archive = tmp_path / "worker.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("ecommerce-worker.exe", b"synthetic")
        z.writestr("VERSION", "0.5.9")
        z.writestr("_internal/capability-public-key.txt", base64.b64encode(b"x" * 32))
    with pytest.raises(ValueError, match="trust key"):
        publish(archive=archive, version="0.5.9", sequence=1, private_key_file=private, output_dir=tmp_path / "out")
