import asyncio
import base64
import hashlib
import io
import json
import stat
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from app.base_updates import BaseUpdateError, BaseUpdater, verify_release
from app.local_config import WorkerConfigService
from uuid import uuid4


def package(*, version="0.5.9", extra=(), public=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("ecommerce-worker.exe", b"synthetic-executable")
        archive.writestr("VERSION", version)
        archive.writestr("_internal/runtime.dat", b"synthetic-runtime")
        archive.writestr("_internal/capability-public-key.txt", base64.b64encode(public or b"x" * 32))
        for name, content in extra:
            archive.writestr(name, content)
    return out.getvalue()


class Source:
    def __init__(self, key, data, *, sequence=1, version="0.5.9"):
        self.data = data
        self.calls = 0
        raw = json.dumps({"schema_version": 1, "sequence": sequence, "version": version,
                          "sha256": hashlib.sha256(data).hexdigest(), "size": len(data),
                          "platform": "windows-x86_64"}, separators=(",", ":")).encode()
        self.envelope = {"manifest": base64.b64encode(raw).decode(),
                         "signature": base64.b64encode(key.sign(raw)).decode()}

    async def fetch_base_release_manifest(self):
        self.calls += 1
        return self.envelope

    async def download_base_release(self, digest, *, size, target):
        assert hashlib.sha256(self.data).hexdigest() == digest and len(self.data) == size
        target.write_bytes(self.data)


@pytest.fixture
def context(tmp_path):
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return key, BaseUpdater(tmp_path / "runtime" / "base-releases", public, "0.5.8")


def test_signed_update_is_staged_only_when_idle_and_leaves_user_data_untouched(context, tmp_path):
    key, updater = context
    config = tmp_path / "config.json"
    config.write_text("existing device identity")
    rpa = tmp_path / "rpa-shop-data"
    rpa.write_text("existing shop data")
    source = Source(key, package(public=updater.public_key))
    assert asyncio.run(updater.update_available(source))
    assert not updater.root.exists()
    source.calls = 0
    assert asyncio.run(updater.stage_when_idle(source, idle=False)) is None
    assert source.calls == 0
    release = asyncio.run(updater.stage_when_idle(source, idle=True))
    assert release.version == "0.5.9" and release.executable.is_file()
    assert release.directory.name == f"{release.digest[:16]}-1"
    verify_release(release, updater.public_key)
    assert config.read_text() == "existing device identity" and rpa.read_text() == "existing shop data"
    assert asyncio.run(updater.stage_when_idle(source, idle=True)) == release


def test_existing_short_directory_must_match_full_signed_release(context):
    key, updater = context
    source = Source(key, package(public=updater.public_key))
    item = json.loads(base64.b64decode(source.envelope["manifest"]))
    collision = updater.root / "releases" / f'{item["sha256"][:16]}-1'
    collision.mkdir(parents=True)
    (collision / "sentinel").write_text("keep")
    with pytest.raises(BaseUpdateError):
        asyncio.run(updater.stage_when_idle(source, idle=True))
    assert (collision / "sentinel").read_text() == "keep"


def test_previous_worker_device_config_is_read_without_discarding_extra_fields(tmp_path):
    class Protector:
        def unprotect(self, value):
            assert value == "synthetic-protected-value"
            return "synthetic-device-identity"
    device_id = uuid4()
    path = tmp_path / "config.json"
    old = {"server_url": "https://center.example.test", "device_id": str(device_id),
           "device_token_protected": "synthetic-protected-value", "images_dir": str(tmp_path / "images"),
           "params_json_path": str(tmp_path / "params.json"), "account_json_path": str(tmp_path / "account.json"),
           "yingdao_install_root": "legacy-value"}
    path.write_text(json.dumps(old), encoding="utf-8")
    before = path.read_bytes()
    loaded = WorkerConfigService(tmp_path, protector=Protector()).load()
    assert loaded.device_id == device_id and loaded.device_token.get_secret_value() == "synthetic-device-identity"
    assert path.read_bytes() == before


def test_bad_signature_hash_version_and_rejected_release_do_not_replace_current(context):
    key, updater = context
    source = Source(key, package(public=updater.public_key))
    source.envelope["signature"] = base64.b64encode(b"x" * 64).decode()
    with pytest.raises(BaseUpdateError):
        asyncio.run(updater.stage_when_idle(source, idle=True))
    source = Source(key, package(public=updater.public_key))
    async def tampered_download(_digest, *, size, target):
        target.write_bytes(b"x" * size)
    source.download_base_release = tampered_download
    with pytest.raises(BaseUpdateError):
        asyncio.run(updater.stage_when_idle(source, idle=True))
    assert asyncio.run(updater.stage_when_idle(Source(key, package(version="0.5.8", public=updater.public_key), version="0.5.8"), idle=True)) is None
    good = Source(key, package(public=updater.public_key))
    digest = json.loads(base64.b64decode(good.envelope["manifest"]))["sha256"]
    staged = asyncio.run(updater.stage_when_idle(good, idle=True))
    assert staged.digest == digest
    updater.save_state({"rejected_digest": digest, "rejected_sequence": 1})
    assert asyncio.run(updater.stage_when_idle(good, idle=True)) is None
    retried_by_signed_new_sequence = Source(key, good.data, sequence=2)
    assert asyncio.run(updater.stage_when_idle(retried_by_signed_new_sequence, idle=True)).digest == digest


@pytest.mark.parametrize("bad", ["../escape", "/escape", "dir\\escape", "C:escape", "CON", "folder./evil"])
def test_archive_rejects_paths_that_escape_or_are_unsafe_on_windows(context, bad):
    key, updater = context
    if "\\" in bad:
        data = package(extra=[("dir/escape", b"invalid")], public=updater.public_key).replace(b"dir/escape", b"dir\\escape")
    else:
        data = package(extra=[(bad, b"invalid")], public=updater.public_key)
    with pytest.raises(BaseUpdateError):
        asyncio.run(updater.stage_when_idle(Source(key, data), idle=True))


def test_archive_rejects_symlink_and_modified_extracted_file(context):
    key, updater = context
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr("ecommerce-worker.exe", b"x")
        archive.writestr("VERSION", "0.5.9")
        archive.writestr("_internal/capability-public-key.txt", base64.b64encode(updater.public_key))
        info = zipfile.ZipInfo("escape")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "../elsewhere")
    with pytest.raises(BaseUpdateError):
        asyncio.run(updater.stage_when_idle(Source(key, out.getvalue()), idle=True))
    release = asyncio.run(updater.stage_when_idle(Source(key, package(public=updater.public_key)), idle=True))
    release.executable.write_bytes(b"altered")
    with pytest.raises(BaseUpdateError):
        verify_release(release, updater.public_key)
