import asyncio
from types import SimpleNamespace

import pytest

from app.rpa_session_bridge import RpaBridgeError, _BridgeProcess


class FakeInput:
    def __init__(self, error=None):
        self.error = error
        self.writes = 0

    def write(self, value):
        self.writes += 1
        if self.error:
            raise self.error

    async def drain(self):
        pass


class FakeOutput:
    def __init__(self, result=None, delay=0):
        self.result = result
        self.delay = delay

    async def readline(self):
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.result


@pytest.mark.parametrize(("operation", "output", "returncode", "expected"), [
    ("init", b"", 1, "RPA_BRIDGE_INIT_EXITED"),
    ("read_session", b"", None, "RPA_BRIDGE_SESSION_EOF"),
    ("list_shops", b"{bad json with synthetic-secret\n", None, "RPA_BRIDGE_LIST_INVALID"),
    ("read_session", b'{"ok":true,"result":null}\n', None, "RPA_BRIDGE_SESSION_INVALID"),
])
def test_bridge_errors_are_safe_and_preserve_command_stage(operation, output, returncode, expected):
    process = SimpleNamespace(stdin=FakeInput(), stdout=FakeOutput(output), returncode=returncode)
    with pytest.raises(RpaBridgeError) as caught:
        asyncio.run(_BridgeProcess(process, timeout=.02).call({"type": operation}))
    assert caught.value.code == expected
    assert "synthetic-secret" not in str(caught.value)
    assert process.stdin.writes == 1


def test_bridge_timeout_and_io_are_distinct_without_retry():
    process = SimpleNamespace(stdin=FakeInput(), stdout=FakeOutput(b"", delay=.1), returncode=None)
    with pytest.raises(RpaBridgeError, match="RPA_BRIDGE_SESSION_TIMEOUT"):
        asyncio.run(_BridgeProcess(process, timeout=.01).call({"type": "read_session"}))
    assert process.stdin.writes == 1
    broken = SimpleNamespace(stdin=FakeInput(BrokenPipeError("synthetic-secret")),
                             stdout=FakeOutput(b""), returncode=1)
    with pytest.raises(RpaBridgeError) as caught:
        asyncio.run(_BridgeProcess(broken, timeout=.01).call({"type": "init"}))
    assert caught.value.code == "RPA_BRIDGE_INIT_IO"
    assert "synthetic-secret" not in str(caught.value)
    assert broken.stdin.writes == 1


def test_explicit_helper_error_is_preserved():
    process = SimpleNamespace(stdin=FakeInput(), stdout=FakeOutput(
        b'{"ok":false,"errorCode":"RPA_SHOP_IDENTITY_MISMATCH"}\n'), returncode=None)
    with pytest.raises(RpaBridgeError, match="RPA_SHOP_IDENTITY_MISMATCH"):
        asyncio.run(_BridgeProcess(process, timeout=.01).call({"type": "read_session"}))
