import base64
from pathlib import Path
import sys

from app.release_trust import packaged_capability_public_key


def test_packaged_public_key_is_loaded_without_environment_variables(tmp_path, monkeypatch):
    public_key = bytes(range(32))
    (tmp_path / "capability-public-key.txt").write_text(base64.b64encode(public_key).decode("ascii"))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.delenv("WORKER_CAPABILITY_PUBLIC_KEY_B64", raising=False)
    assert packaged_capability_public_key() == public_key
    (tmp_path / "capability-public-key.txt").write_text("invalid")
    assert packaged_capability_public_key() is None


def test_release_build_requires_and_embeds_named_public_key():
    script = (Path(__file__).resolve().parents[2] / "scripts/build-worker.ps1").read_text(encoding="utf-8")
    assert "CapabilityPublicKeyFile" in script
    assert "capability-public-key.txt" in script
    assert "--add-data" in script
