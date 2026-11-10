import hashlib
import json
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from tools.publish_capability import publish


def test_offline_publish_creates_verifiable_package_and_requires_increasing_sequence(tmp_path):
    private = Ed25519PrivateKey.generate()
    key_file = tmp_path / "synthetic-private.pem"
    key_file.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    source = tmp_path / "capability.py"
    source.write_text("SKILL_ID = 'douyin.category_schema'\n", encoding="utf-8")
    output = tmp_path / "isolated-staging"
    helper_digest = "a" * 64
    digest = publish(source=source, skill_id="douyin.category_schema", version="0.1.0", sequence=1,
                     private_key_file=key_file, output_dir=output, rpa_helper_sha256=[helper_digest])
    raw = (output / "manifest.json").read_bytes()
    private.public_key().verify((output / "manifest.sig").read_bytes(), raw)
    manifest = json.loads(raw)
    assert manifest["sequence"] == 1 and manifest["rpa_helper_sha256"] == [helper_digest]
    assert manifest["packages"][0]["sha256"] == digest
    artifact = output / "packages" / f"{digest}.zip"
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(artifact) as package:
        assert package.namelist() == ["capability.py"]
        assert package.read("capability.py") == source.read_bytes()
    with pytest.raises(ValueError, match="sequence must increase"):
        publish(source=source, skill_id="douyin.category_schema", version="0.1.0", sequence=1,
                private_key_file=key_file, output_dir=output)
    assert (output / "manifest.json").read_bytes() == raw
