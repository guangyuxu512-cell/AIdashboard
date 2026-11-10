import asyncio
import ast
import base64
import hashlib
import io
import json
import stat
import zipfile

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from app.capability_updates import CapabilityUpdateError, CapabilityUpdater


SKILL = "douyin.category_schema"


def archive(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        for name, value in files:
            zipped.writestr(name, value)
    return output.getvalue()


def package(data, *, skill=SKILL, version="1.0.0", entry="capability.py", host=1):
    return {"skill_id": skill, "version": version, "entrypoint": entry,
            "host_api_version": host, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


class Source:
    def __init__(self, key, sequence, packages, blobs):
        raw = json.dumps({"schema_version": 1, "sequence": sequence, "packages": packages},
                         separators=(",", ":")).encode()
        self.envelope = {"manifest": base64.b64encode(raw).decode(),
                         "signature": base64.b64encode(key.sign(raw)).decode()}
        self.blobs = blobs
        self.manifest_calls = 0
        self.downloads = []

    async def fetch_capability_manifest(self):
        self.manifest_calls += 1
        return self.envelope

    async def download_capability_package(self, digest, *, max_size):
        self.downloads.append(digest)
        assert len(self.blobs[digest]) <= max_size
        return self.blobs[digest]


@pytest.fixture
def context(tmp_path):
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    updater = CapabilityUpdater(tmp_path / "packages", public, 1)
    return key, updater


def run(coroutine):
    return asyncio.run(coroutine)


def test_signed_manifest_controls_trusted_rpa_helper_tree(context):
    key, updater = context
    data = archive([("capability.py", "VALUE = 1\n")])
    item = package(data)
    digest = "a" * 64
    raw = json.dumps({"schema_version": 1, "sequence": 1, "packages": [item],
                      "rpa_helper_sha256": [digest]}, separators=(",", ":")).encode()
    source = Source(key, 1, [item], {item["sha256"]: data})
    source.envelope = {"manifest": base64.b64encode(raw).decode(),
                       "signature": base64.b64encode(key.sign(raw)).decode()}
    run(updater.sync_when_idle(source, idle=True))
    assert updater.trusted_rpa_digests() == frozenset({digest})
    raw2 = raw.replace(digest.encode(), ("b" * 64).encode())
    source.envelope["manifest"] = base64.b64encode(raw2).decode()
    with pytest.raises(CapabilityUpdateError):
        run(updater.sync_when_idle(source, idle=True))
    assert updater.trusted_rpa_digests() == frozenset({digest})


def test_idle_update_restart_and_same_sequence(context):
    key, updater = context
    data = archive([("capability.py", "VALUE = 1\n"), ("data/config.json", "{}")])
    item = package(data)
    source = Source(key, 1, [item], {item["sha256"]: data})
    assert run(updater.sync_when_idle(source, idle=False)) is False
    assert source.manifest_calls == 0
    assert run(updater.sync_when_idle(source, idle=True)) is True
    (active,) = updater.active_packages()
    assert (active.skill_id, active.version, active.entrypoint.read_text()) == (SKILL, "1.0.0", "VALUE = 1\n")
    assert run(updater.sync_when_idle(source, idle=True)) is False
    assert len(source.downloads) == 1
    restored = CapabilityUpdater(updater.root,
        key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw),
        1)
    assert restored.active_packages() == updater.active_packages()
    newer = archive([("capability.py", "VALUE = 2\n")])
    newer_item = package(newer, version="2.0.0")
    newer_source = Source(key, 2, [newer_item], {newer_item["sha256"]: newer})
    assert run(updater.sync_when_idle(newer_source, idle=True)) is True
    assert updater.active_packages()[0].entrypoint.read_text() == "VALUE = 2\n"
    assert active.entrypoint.read_text() == "VALUE = 1\n"


def test_bad_signature_hash_sequence_or_download_preserves_current(context):
    key, updater = context
    first = archive([("capability.py", "v1")])
    item1 = package(first)
    run(updater.sync_when_idle(Source(key, 3, [item1], {item1["sha256"]: first}), idle=True))
    second = archive([("capability.py", "v2")])
    item2 = package(second, version="2")
    rollback = Source(key, 2, [item2], {item2["sha256"]: second})
    conflict = Source(key, 3, [item2], {item2["sha256"]: second})
    bad_signature = Source(Ed25519PrivateKey.generate(), 4, [item2], {item2["sha256"]: second})
    bad_hash = Source(key, 4, [item2], {item2["sha256"]: b"not-the-archive"})
    for source in (rollback, conflict, bad_signature, bad_hash):
        with pytest.raises(CapabilityUpdateError):
            run(updater.sync_when_idle(source, idle=True))
        assert updater.active_packages()[0].entrypoint.read_text() == "v1"


@pytest.mark.parametrize("bad_name", ["../escape.py", "/escape.py", "dir\\escape.py", "C:evil.py"])
def test_zip_paths_are_rejected(context, bad_name):
    key, updater = context
    if "\\" in bad_name:
        # zipfile normalizes native Windows separators when writing, so mutate
        # both filename records to represent an archive from an untrusted host.
        data = archive([("capability.py", "ok"), ("dir/escape.py", "bad")])
        data = data.replace(b"dir/escape.py", b"dir\\escape.py")
    else:
        data = archive([("capability.py", "ok"), (bad_name, "bad")])
    item = package(data)
    with pytest.raises(CapabilityUpdateError):
        run(updater.sync_when_idle(Source(key, 1, [item], {item["sha256"]: data}), idle=True))
    assert updater.active_packages() == ()


def test_symlink_and_unsigned_local_tampering_rejected(context):
    key, updater = context
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as zipped:
        zipped.writestr("capability.py", "ok")
        info = zipfile.ZipInfo("link")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zipped.writestr(info, "../elsewhere")
    data = output.getvalue()
    item = package(data)
    with pytest.raises(CapabilityUpdateError):
        run(updater.sync_when_idle(Source(key, 1, [item], {item["sha256"]: data}), idle=True))
    valid = archive([("capability.py", "v1")])
    item = package(valid)
    run(updater.sync_when_idle(Source(key, 1, [item], {item["sha256"]: valid}), idle=True))
    updater.active_packages()[0].entrypoint.write_text("changed")
    with pytest.raises(CapabilityUpdateError):
        updater.active_packages()


def test_fixed_entry_host_version_and_signed_new_skill(context):
    key, updater = context
    data = archive([("capability.py", "ok")])
    for item in (package(data, entry="other.py"), package(data, host=2), package(data, skill="bad-id")):
        with pytest.raises(CapabilityUpdateError):
            run(updater.sync_when_idle(Source(key, 1, [item], {item["sha256"]: data}), idle=True))
    unregistered = package(data, skill="other.example")
    source = Source(key, 1, [unregistered], {unregistered["sha256"]: data})
    assert run(updater.sync_when_idle(source, idle=True)) is True
    assert source.downloads == [unregistered["sha256"]]
    assert updater.active_packages()[0].skill_id == "other.example"


def test_invalid_entry_does_not_replace_existing_release(context):
    key, updater = context

    def validate(_skill, _version, content):
        tree = ast.parse(content)
        if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "execute"
                   for node in tree.body):
            raise ValueError("missing execute")

    good = archive([("capability.py", "async def execute(context, inputs):\n    return {}\n")])
    item = package(good)
    run(updater.sync_when_idle(Source(key, 1, [item], {item["sha256"]: good}),
                              idle=True, validate_entry=validate))
    for entry in ("def execute(:\n", "def other():\n    pass\n"):
        invalid = archive([("capability.py", entry)])
        new_item = package(invalid, version="2")
        with pytest.raises(CapabilityUpdateError, match="CAPABILITY_ENTRY_INVALID"):
            run(updater.sync_when_idle(Source(key, 2, [new_item], {new_item["sha256"]: invalid}),
                                      idle=True, validate_entry=validate))
        assert updater.active_packages()[0].version == "1.0.0"
