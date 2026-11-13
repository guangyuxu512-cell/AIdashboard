import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from app.rpa_session_bridge import (
    BridgeDiscovery, RpaAutoBridge, RpaBridgeError, RpaLocalBridge, TrustedRpaInstallation,
    _stored_session_revisions, discover_rpa, helper_tree_digest,
)


def fixture_installation(tmp_path: Path):
    root = tmp_path / "trusted-rpa"
    helper_dir = root / "resources" / "listing-worker"
    helper_dir.mkdir(parents=True)
    (helper_dir / "listing-worker.exe").write_bytes(b"synthetic exe")
    (root / "店群自动化软件.exe").write_bytes(b"synthetic RPA")
    (helper_dir / "_internal").mkdir()
    (helper_dir / "_internal" / "dependency.dll").write_bytes(b"synthetic dependency")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "shop-manager.db").write_bytes(b"synthetic database")
    installation_id = uuid4()
    discovery = BridgeDiscovery(contractVersion=1, installationId=installation_id,
        appVersion="test", helperPath=str(helper_dir / "listing-worker.exe"),
        databasePath=str(data_dir / "shop-manager.db"))
    (data_dir / "worker-session-bridge.json").write_text(
        discovery.model_dump_json(by_alias=True), encoding="utf-8")
    trust = TrustedRpaInstallation(root, helper_tree_digest(helper_dir))
    return root, data_dir, trust, discovery


def test_session_revision_changes_when_rpa_saves_a_new_snapshot(tmp_path):
    database = tmp_path / "shop-manager.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE worker_shop_sessions (local_shop_id TEXT, platform_shop_id TEXT, "
                           "captured_at TEXT, encrypted_payload TEXT)")
        connection.execute("INSERT INTO worker_shop_sessions VALUES (?, ?, ?, ?)",
                           ("local-1", "shop-1", "time-a", "synthetic-encrypted-a"))
    first = _stored_session_revisions(str(database))
    assert len(first[("local-1", "shop-1")]) == 64
    assert "synthetic-encrypted-a" not in repr(first)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE worker_shop_sessions SET encrypted_payload=?", ("synthetic-encrypted-b",))
    second = _stored_session_revisions(str(database))
    assert first[("local-1", "shop-1")] != second[("local-1", "shop-1")]
    assert _stored_session_revisions(str(tmp_path / "missing.db")) == {}


def test_discovery_rejects_tampered_helper_dependency(tmp_path):
    root, data_dir, trust, discovery = fixture_installation(tmp_path)
    assert discover_rpa(data_dir, trust) == discovery
    (root / "resources/listing-worker/_internal/dependency.dll").write_bytes(b"tampered")
    with pytest.raises(RpaBridgeError, match="RPA_HELPER_UNTRUSTED"):
        discover_rpa(data_dir, trust)


def test_marker_cannot_choose_another_executable(tmp_path):
    root, data_dir, trust, discovery = fixture_installation(tmp_path)
    other = tmp_path / "malicious/resources/listing-worker"
    other.mkdir(parents=True)
    (other / "listing-worker.exe").write_bytes(b"synthetic exe")
    tampered = discovery.model_copy(update={"helper_path": str(other / "listing-worker.exe")})
    (data_dir / "worker-session-bridge.json").write_text(tampered.model_dump_json(by_alias=True), encoding="utf-8")
    with pytest.raises(RpaBridgeError, match="RPA_HELPER_UNTRUSTED"):
        discover_rpa(data_dir, trust)


def test_automatic_discovery_requires_signed_release_digest(tmp_path):
    _, data_dir, trust, _ = fixture_installation(tmp_path)
    with pytest.raises(RpaBridgeError, match="RPA_HELPER_UNTRUSTED"):
        RpaAutoBridge(data_dir, lambda: frozenset())._bridge()
    bridge = RpaAutoBridge(data_dir, lambda: frozenset({trust.helper_tree_sha256}))._bridge()
    assert bridge.discovery.installation_id


def test_identity_checked_and_session_remains_in_memory(tmp_path, monkeypatch):
    _, data_dir, trust, info = fixture_installation(tmp_path)
    database = Path(info.database_path)
    database.unlink()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE worker_shop_sessions (local_shop_id TEXT, platform_shop_id TEXT, captured_at TEXT, encrypted_payload TEXT)")
        connection.execute("INSERT INTO worker_shop_sessions VALUES (?, ?, ?, ?)",
                           ("a", "1", "time-a", "synthetic-encrypted-a"))
    script = tmp_path / "fake_helper.py"
    script.write_text('''import json,sys\n'
'iid=sys.argv[1]\n'
'for line in sys.stdin:\n'
' d=json.loads(line)\n'
' if d["type"] == "init": r={"contractVersion":1,"installationId":iid}\n'
' elif d["type"] == "list_stored_shops": r={"installationId":iid,"shops":[{"localShopId":"a","platformShopId":"1","shopName":"demo","platform":"douyin","sessionStored":True}]}\n'
' elif d["type"] == "read_stored_session": r={"localShopId":"a","platformShopId":"1","platform":"douyin","userAgent":"test","cookies":[{"name":"example","value":"synthetic-secret","domain":".jinritemai.com","path":"/"}]}\n'
' else: raise ValueError("unexpected legacy browser command")\n'
' print(json.dumps({"ok":True,"result":r}),flush=True)\n'''.replace("'\n'", ""), encoding="utf-8")
    original = asyncio.create_subprocess_exec

    async def fake_spawn(*args, **kwargs):
        from app.shared.subprocesses import windows_no_window_creation_flags
        assert args[0].endswith("listing-worker.exe")
        assert args[1] == "--worker-session-stdio"
        assert kwargs.get("creationflags") == windows_no_window_creation_flags()
        return await original(sys.executable, str(script), str(info.installation_id), **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_spawn)
    bridge = RpaLocalBridge(info, data_dir, trust)
    inventory = asyncio.run(bridge.list_shops())
    assert inventory.shops[0].local_shop_id == "a"
    assert inventory.shops[0].session_stored is True
    assert len(inventory.shops[0].session_revision) == 64
    assert "synthetic-encrypted-a" not in inventory.model_dump_json()
    session = asyncio.run(bridge.read_session("a", "1"))
    assert session.cookies[0].value.get_secret_value() == "synthetic-secret"
    assert "synthetic-secret" not in repr(session)
    with pytest.raises(RpaBridgeError, match="RPA_SHOP_IDENTITY_MISMATCH"):
        asyncio.run(bridge.read_session("b", "1"))
