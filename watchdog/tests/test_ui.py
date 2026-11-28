"""Exercise configuration actions without displaying or controlling a desktop."""

from pathlib import Path

from siyu_guard import ui


class Value:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value


class Window:
    destroyed = False
    def destroy(self):
        self.destroyed = True


def editor(**values):
    result = object.__new__(ui.Editor)
    result.values = {key: Value(values.get(key, "")) for key in
                     ("name", "kind", "path", "data_root", "service", "url", "browser_id", "token")}
    result.restart = Value(True)
    result.window = Window()
    result.browser_options = {}
    result.service_options = {}
    result.saved = []
    result.callback = result.saved.append
    result.invalid = lambda: None
    return result


def test_selecting_worker_persists_its_explicit_local_data_directory(tmp_path):
    executable = tmp_path / "worker.exe"
    executable.write_bytes(b"fixture")
    chosen = editor(name="Worker", kind="Worker", path=str(executable), data_root=str(tmp_path / "data"))
    chosen.save()
    assert chosen.saved[0]["kind"] == "worker"
    assert chosen.saved[0]["path"] == str(executable.resolve())
    assert chosen.saved[0]["data_root"] == str((tmp_path / "data").resolve())
    assert chosen.window.destroyed


def test_selecting_1688_update_prefers_its_stable_bootstrap(tmp_path):
    bootstrap = tmp_path / "1688-Sourcing-Preview.exe"
    bootstrap.write_bytes(b"fixture")
    release = tmp_path / ".1688-updates" / "releases" / "v1"
    release.mkdir(parents=True)
    active = release / bootstrap.name
    active.write_bytes(b"fixture")
    chosen = editor(name="1688", kind="1688 采集", path=str(active))
    chosen.save()
    assert Path(chosen.saved[0]["path"]).resolve() == bootstrap.resolve()


def test_plugin_token_is_protected_and_window_name_maps_to_identity(monkeypatch):
    class Protector:
        def protect(self, value):
            assert value == "fixture-value"
            return "encrypted"
    monkeypatch.setattr(ui, "WindowsDpapiTokenProtector", Protector)
    chosen = editor(name="采集", kind="采集插件", url="https://ops.example.test",
                    browser_id="窗口 A", token="fixture-value")
    chosen.browser_options = {"窗口 A": "window-123"}
    chosen.save()
    assert chosen.saved[0]["protected_token"] == "encrypted"
    assert chosen.saved[0]["browser_id"] == "window-123"
    assert "fixture-value" not in str(chosen.saved)


def test_invalid_program_is_not_added(tmp_path):
    chosen = editor(name="程序", kind="普通程序", path=str(tmp_path / "missing.exe"))
    chosen.save()
    assert chosen.saved == []
    assert not chosen.window.destroyed
